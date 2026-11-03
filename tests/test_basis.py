import argparse
import asyncio
import copy
from dataclasses import replace
import json
from pathlib import Path
from zipfile import ZipFile
import pytest
import sympy as sp
from fastapi.testclient import TestClient
from blindspot.app import create_app
from blindspot.basis import build_bank,validate_basis,execute,prepare
from blindspot.config import Settings,load_settings,ROOT
from blindspot.meta import MetaClient
from blindspot.prompts import search_messages
from blindspot.search import write_json,import_results
from blindspot.semantic_bank import load_bank
from blindspot.signal_analysis import metrics,discriminability,reason_flags,analyse
from blindspot.runner import Runner
from blindspot.storage import Store
from blindspot.study_dashboard import study_data,cache_completed_study


def arguments(**changes):
    return argparse.Namespace(**(dict(spectra=1,seed=88,trials=2,exclude_bank=[],regenerate=True,build_only=False,
        budget_usd=1,certificate_budget_usd=1,max_calls=1000,rpm=100,experiment='all',no_plots=True,bootstrap=0)|changes))


def test_exact_ladder_and_paired_certificate_contents():
    bank=build_bank(2,88)
    assert len(bank['problems'])==14
    for p in bank['problems']:
        b=p['basis'];D,Q,H=map(sp.Matrix,[b['D'],b['Q'],b['H']])
        assert validate_basis(D,Q,H)==b['validation']
        presented=sp.sympify(p['question'].split('H=',1)[1].split(' describes four coupled modes.',1)[0],locals={'Matrix':sp.Matrix})
        assert presented==H
        assert all((sp.sympify(c['candidate']['expr'])==D[2,2]-D[1,1])==c['is_control'] for c in p['cells'])
        if b['condition']=='certificate':
            a=next(a for a in bank['problems'] if a['basis']['spectrum_id']==b['spectrum_id'] and a['basis']['level']==5 and a['basis']['condition']=='sweep')
            assert p['question']==a['question'] and p['steps']==a['steps']
            for x,y in zip(a['cells'],p['cells']):
                assert x['candidate']==y['candidate']
                payload_a=json.loads(search_messages(a,x,20,Settings(),False,'truth')[1]['content'])
                payload_b=json.loads(search_messages(p,y,20,Settings(),False,'truth')[1]['content'])
                cert=payload_b.pop('structural_certificate')
                assert payload_a==payload_b and cert['Q']==b['Q'] and cert['D']==b['D']
                assert 'gap' not in cert
    first=bank['problems'][0]
    excluded={tuple(first['oracle']['spectrum'])}
    assert tuple(build_bank(1,88,excluded)['problems'][0]['oracle']['spectrum']) not in excluded
    broken=sp.eye(4);broken[0,0]=2
    with pytest.raises(ValueError):validate_basis(sp.diag(0,1,2,3),broken,sp.diag(0,1,2,3))


def test_d_prime_correction_and_unusable_outputs():
    assert discriminability(5,10,5,10)==pytest.approx(0)
    assert discriminability(10,10,0,10)>3
    assert discriminability(0,10,10,10)<-3
    assert discriminability(0,0,0,10) is None
    rs=[dict(status='ok',valid=False,control=False,confidence=.8),dict(status='ok',valid=True,control=True,confidence=.9),dict(status='error',control=False)]
    m=metrics(rs);assert m['hit_rate']==1 and m['false_alarm_rate']==0 and m['failed']==1
    assert m['false_accept_confidence'] is None and m['true_accept_confidence']==.9
    f=reason_flags('By orthogonal similarity the supplied certificate gives gap = 2/5.',True,'1/5')
    assert f['certificate_mentioned'] and f['explicit_gap_numeral_mismatch']


class BasisClient(MetaClient):
    def __init__(self,settings,log):super().__init__(settings);self.log=log
    async def complete(self,request,**kwargs):
        assert request['response_format']['json_schema']['name']=='step_verdict'
        cell=kwargs['cell'];self.log.append(cell['id'])
        certified='structural_certificate' in json.loads(request['messages'][1]['content'])
        dense='-level-5' in cell['id']
        return dict(valid=cell['is_control'] or (dense and not certified),confidence=.9,reason='SIMULATED test: certificate used' if certified else 'SIMULATED test verdict')


def test_fixed_collection_caps_resume_rescue_and_app_import(tmp_path):
    async def scenario():
        settings=Settings(concurrency=3,seed_demo=False,db_path=str(tmp_path/'app.sqlite3'));log=[]
        root=tmp_path/'study';factory=lambda s:BasisClient(s,log)
        first=await execute(root,settings,arguments(max_calls=11),factory)
        assert first[0]['status']=='paused_at_limit' and len(log)==11
        assert not (root/'certificate/search.sqlite3').exists()
        result=await execute(root,settings,arguments(),factory)
        assert len(log)==126 and sum(g['calls'] for g in result)==126
        assert [g['planned_calls'] for g in result]==[108,18]
        calls=len(log);await execute(root,settings,arguments(),factory);assert len(log)==calls
        d=study_data(root);assert d['certificate_effect']['certificate_minus_baseline']['hit_rate']==1
        with pytest.raises(ValueError):cache_completed_study(root)
        with ZipFile(root/'review.zip') as z:
            assert {'bank.json','plan.json','sweep/search.sqlite3','certificate/search.sqlite3','comparison.json'}<=set(z.namelist())
        combined=load_bank(root/'bank.json')
        for condition in ['sweep','certificate']:import_results(root/condition,settings,combined)
        with TestClient(create_app(replace(settings,bank_path=str(root/'bank.json')))) as http:
            history=http.get('/api/experiments').json();assert len(history)==7
            dashboard=http.get('/api/representation').json();assert len(dashboard['current']['cases'])==7
            assert dashboard['current']['certificate_effect']['certificate_minus_baseline']['hit_rate']==1
            e=http.get('/api/experiments/'+history[0]['id']).json()
            assert e['total_calls']==18 and e['forecasts_expected'] is False
            assert all(r['prediction'] is None for r in e['results'].values())
            assert http.get('/api/experiments/'+history[0]['id']+'/export.xlsx').status_code==200
        with pytest.raises(ValueError):await execute(root,settings,arguments(trials=3),factory)
    asyncio.run(scenario())


def test_basis_live_cell_does_not_collect_forecast(tmp_path):
    async def scenario():
        write_json(tmp_path/'bank.json',build_bank(1,88));bank=load_bank(tmp_path/'bank.json')
        settings=Settings(seed_demo=False,db_path=str(tmp_path/'app.db'));log=[]
        runner=Runner(settings,bank,Store(settings.db_path),BasisClient(settings,log));p=bank['problems'][0]
        e=runner.create(p['id'],[p['cells'][0]['id']],trials=2);done=await runner.run(e['id'],fast=True)
        assert done['status']=='complete' and done['total_calls']==2 and len(log)==2
        assert done['results'][p['cells'][0]['id']]['prediction'] is None
        await runner.shutdown()
    asyncio.run(scenario())


def test_saved_matrix_tampering_is_rejected(tmp_path):
    write_json(tmp_path/'bank.json',build_bank(1,88))
    raw=json.loads((tmp_path/'bank.json').read_text());raw['problems'][0]['basis']['Q'][0][0]='2';write_json(tmp_path/'bank.json',raw)
    with pytest.raises(ValueError):prepare(tmp_path,1,88,[],True)


def test_environment_can_select_a_frozen_custom_bank(monkeypatch):
    monkeypatch.setenv('BLINDSPOT_BANK','var/basis-study/bank.json')
    assert load_settings().bank_path==str(ROOT/'var/basis-study/bank.json')


def test_completed_live_cache_retains_all_outcomes_and_matches_aggregates():
    cached=json.loads((ROOT/'data/basis-study-results.json').read_text())
    assert cached['mode']=='live' and len(cached['cases'])==84
    assert cached['planned_verdicts']==cached['recorded_verdicts']==15120
    groups={}
    for case in cached['cases']:
        key=(case['level'],case['condition']);groups.setdefault(key,[])
        for c in case['cells']:
            assert len(c['examples'])==20
            assert len({t['ordinal'] for t in c['examples']})==20
            ok=[t for t in c['examples'] if t['status']=='ok']
            assert c['usable']==len(ok) and c['failed']==20-len(ok)
            for t in c['examples']:groups[key].append({**t,'control':c['control']})
    assert sum(t['status']=='ok' for rs in groups.values() for t in rs)==14791
    for g in cached['groups']:
        actual=metrics(groups[(g['level'],g['condition'])])
        for key in ['hits','false_alarms','errors','controls','failed','d_prime']:assert actual[key]==pytest.approx(g[key])
