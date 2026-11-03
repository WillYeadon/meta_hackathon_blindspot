import asyncio
import copy
from dataclasses import replace
from io import BytesIO
import json
import random
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import pytest
import sympy as s
from fastapi.testclient import TestClient
from blindspot.app import create_app
from blindspot.config import Settings
from blindspot.excel_export import workbook_spec, xlsx_bytes
from blindspot.maths import parse
from blindspot.meta import MetaClient, ModelError
from blindspot.search import Search, Ledger, LimitReached, measured_cost, write_json, import_results
from blindspot.semantic_bank import FAMILIES, make_case, load_bank


@pytest.mark.parametrize('family',FAMILIES)
def test_exact_physical_oracles(family):
    rng=random.Random(1995)
    for number in range(3):
        p=make_case(family,number,rng)
        if p is None:continue
        o=p['oracle'];value=parse(p['steps'][-1]['expr'],p)
        q=lambda key:s.sympify(o[key])
        if family=='postselection':
            v=s.Matrix(o['v']);u=s.Matrix(o['u']);P=s.diag(1,1,0);u3=s.Matrix([u[0],u[1],0])
            expected=(u3.T*P*v)[0]**2/(v.T*v)[0]
        elif family=='gram_metric':
            v=s.Matrix(o['physical_vector']);E=s.diag(*map(s.sympify,o['physical_energies']))
            expected=(v.T*E*v)[0]/(v.T*v)[0]
        elif family=='near_degeneracy':
            H=s.Matrix(o['H']);U=s.Matrix(o['U']);D=s.diag(*map(s.sympify,o['spectrum']))
            assert U.T*U==s.eye(4) and H*U==U*D
            expected=D[2,2]-D[1,1]
        elif family=='radial_measure':
            r=s.Symbol('r',positive=True);f=r**q('ell')*(1-q('q')*r)**q('degree')*s.exp(-q('beta')*r)
            expected=s.integrate(f*f*r**(q('moment')+2),(r,0,s.oo))/s.integrate(f*f*r*r,(r,0,s.oo))
        elif family=='quench':
            A,B=s.symbols('A B');solution=s.solve([A+B-q('q'),-s.I*q('w2')*(A-B)-q('qdot')],[A,B])
            expected=solution[A]
        elif family=='degenerate_perturbation':
            u=s.Matrix(o['u']);G=s.Matrix.hstack(*[s.Matrix(v) for v in o['couplings']]);den=s.diag(*[1/s.sympify(e) for e in o['energies']])
            expected=-(u.T*G*den*G.T*u)[0]
        elif family=='noncommuting':expected=-q('b')**2*(q('a')**2+q('b')**2)/3
        elif family=='robin_boundary':
            x=s.Symbol('x',real=True);f=s.sympify(o['f'],locals={'x':x})
            assert s.diff(f,x).subs(x,0)==q('a')*f.subs(x,0)
            assert s.diff(f,x).subs(x,1)==-q('a')*f.subs(x,1)
            expected=(q('bulk')+q('boundary'))/q('norm')
        elif family=='ivp_domain':
            x=s.Symbol('x',real=True);D=s.sympify(o['D'],locals={'x':x});roots=s.polys.polytools.ground_roots(D,x)
            expected=min(r for r in roots if r>0)
            assert D.subs(x,0)==1 and s.simplify(s.diff(1/D,x)+s.diff(D,x)/D**2)==0
        elif family=='euler_resonance':
            x=s.Symbol('x',real=True);residual=value
            for _ in range(int(q('m'))):residual=s.simplify(x*s.diff(residual,x)-q('r')*residual)
            assert s.simplify(residual-x**q('r')*s.log(x)**q('q'))==0
            expected=value
        elif family=='viscoelastic':
            E=list(map(s.sympify,o['springs']));eta=list(map(s.sympify,o['viscosities']));w=q('omega')
            # Independent compliance construction for each subnetwork.
            compliance1=1/E[0]+1/(s.I*w*eta[0]);compliance2=1/E[1]+1/(s.I*w*eta[1])
            assembly_compliance=1/(1/compliance1+1/compliance2)+1/(E[2]+s.I*w*eta[2])
            expected=E[3]+1/assembly_compliance
        else:
            overlap=s.exp(-q('d')**2);a,b=q('a'),q('b')
            expected=((a*a+b*b)*(q('d')**2+s.Rational(1,2))+a*b*overlap)/(a*a+b*b+2*a*b*overlap)
        assert s.simplify(value-expected)==0
        assert all((s.simplify(parse(c['candidate']['expr'],p)-value)==0)==c['is_control'] for c in p['cells'])


def bank_fixture(tmp_path):
    problems=[]
    for family in ['postselection','noncommuting']:
        for i in range(3):
            p=make_case(family,i,random.Random(100+i));p['split']='holdout' if i==2 else 'discovery';problems.append(p)
    write_json(tmp_path/'bank.json',dict(seed=1,version='test',problems=problems))
    return load_bank(tmp_path/'bank.json')


class ScriptedClient(MetaClient):
    def __init__(self,settings):super().__init__(settings);self.calls=[]
    async def complete(self,request,**kwargs):
        prediction=request['response_format']['json_schema']['name']=='self_prediction';c=kwargs['cell'];ordinal=kwargs['ordinal']
        self.calls.append((prediction,c['id'],ordinal))
        # Every discovery error is missed, all controls accepted; independent
        # confirmation discovers perfect detection instead. Selection must not
        # accidentally reuse discovery outcomes to manufacture persistence.
        return dict(probability_percent=90,reason='test forecast') if prediction else dict(valid=c['is_control'] or ordinal<10000,confidence=.9,reason='test verdict')


def test_search_fresh_confirmation_resume_and_import(tmp_path):
    async def scenario():
        bank=bank_fixture(tmp_path);settings=Settings(db_path=str(tmp_path/'app.db'),seed_demo=False)
        options=dict(budget_usd=10,max_calls=1000,rpm=100,screen_trials=2,confirm_trials=4,top_k=2,max_per_family=1,holdout_per_family=1,input_price=.1,cached_price=.002,output_price=.2)
        client=ScriptedClient(settings);search=Search(tmp_path,bank,settings,options,client)
        summary=await search.run()
        assert summary['selected_problems']==2 and summary['holdout_problems']==2
        assert all(x[0] for x in client.calls[:12])
        assert any(x[2]>=10000 for x in client.calls if not x[0])
        files=list((tmp_path/'exports').glob('confirm-*.json'));assert len(files)==2
        for path in files:
            e=json.loads(path.read_text())['experiment'];r=next(r for k,r in e['results'].items() if not k.endswith(('equivalent','original_control')))
            assert r['metrics']['observed']==1 and r['metrics']['valid_trials']==4
        calls=len(client.calls)
        await Search(tmp_path,bank,settings,options,client).run();assert len(client.calls)==calls
        import_results(tmp_path,settings);import_results(tmp_path,settings)
        with TestClient(create_app(replace(settings,bank_path=str(tmp_path/'shortlist-bank.json')))) as http:
            history=http.get('/api/experiments').json();assert len(history)==4
            response=http.get('/api/experiments/'+history[0]['id']+'/export.xlsx');assert response.status_code==200
            with ZipFile(BytesIO(response.content)) as archive:assert 'xl/workbook.xml' in archive.namelist()
    asyncio.run(scenario())


def test_ledger_reservation_and_unknown_outcome(tmp_path):
    ledger=Ledger(tmp_path/'calls.db',.02,2)
    ledger.reserve('a',.015,dict(status='pending'))
    with pytest.raises(LimitReached):ledger.reserve('b',.015,{})
    ledger.finish('a',.001,dict(status='ok'))
    ledger.reserve('b',.015,dict(status='pending'))
    with pytest.raises(LimitReached):ledger.reserve('c',0,{})
    assert Ledger(tmp_path/'calls.db',.02,2).get('b')['status']=='pending'
    assert measured_cost({'prompt_tokens':1000,'completion_tokens':2000,'prompt_tokens_details':{'cached_tokens':500},'completion_tokens_details':{'reasoning_tokens':1500}},.1,.002,.2)==pytest.approx(.000451)


def test_search_limit_resume_and_authentication_stop(tmp_path):
    async def scenario():
        bank=bank_fixture(tmp_path);settings=Settings(concurrency=1,seed_demo=False)
        options=dict(budget_usd=10,max_calls=1,rpm=100,screen_trials=1,confirm_trials=2,top_k=1,max_per_family=1,holdout_per_family=1,input_price=.1,cached_price=.002,output_price=.2)
        client=ScriptedClient(settings)
        result=await Search(tmp_path,bank,settings,options,client).run()
        assert result['status']=='paused_at_limit' and result['calls']==1
        options['max_calls']=1000
        result=await Search(tmp_path,bank,settings,options,client).run()
        assert result['status']=='finished' and result['calls']==len(client.calls)
        other=tmp_path/'auth';other.mkdir();bank2=bank_fixture(other)
        class Rejected(ScriptedClient):
            async def complete(self,request,**kwargs):
                self.calls.append(request)
                raise ModelError('Meta HTTP 401. Check META_API_KEY and access to the configured model.')
        rejected=Rejected(settings)
        result=await Search(other,bank2,settings,options,rejected).run()
        assert result['status']=='stopped_on_error' and len(rejected.calls)==1
        assert result['forecast_blocked_problems']==4 and result['screen_usable_trials']==0
    asyncio.run(scenario())


def test_export_cached_formulas_controls_and_literal_model_text(tmp_path):
    p=make_case('postselection',0,random.Random(3));e=dict(id='example',created_at='2026-10-29',config=dict(model='test',mode='mock',trials=2),results={})
    for c in p['cells']:
        e['results'][c['id']]=dict(prediction=dict(status='ok',probability_percent=80,reason='test'),trials=[dict(status='ok',valid=c['is_control'],reason='=HYPERLINK("bad")',ordinal=0)])
    payload=dict(experiment=e,problem=p);spec=workbook_spec(payload)
    assert spec[1]['cells']['I7']['value']==1
    assert spec[1]['cells']['J7']['value']==pytest.approx(-20)
    with ZipFile(BytesIO(xlsx_bytes(payload))) as archive:
        for name in archive.namelist():ET.fromstring(archive.read(name))
        trials=archive.read('xl/worksheets/sheet3.xml').decode()
        assert '=HYPERLINK' in trials and '<f>' not in trials
        detail=ET.fromstring(archive.read('xl/worksheets/sheet2.xml'));ns={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        assert detail.find('.//x:c[@r="I7"]/x:f',ns).text=='IF(G7=0,"",F7/G7)'
    # Missing outcomes remain blank; no artificial zero detection.
    e['results']={};assert workbook_spec(payload)[1]['cells']['I7']['value'] is None
