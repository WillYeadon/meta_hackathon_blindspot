import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
from zipfile import ZipFile
import pytest
import sympy as sp
from blindspot.config import Settings,ROOT,load_settings
from blindspot.final_study import prepare_bank,ProgrammeLedger,execute,PREDICTION,estimate
from blindspot.final_report import analyse_final,integrate_final
from blindspot.meta import MetaClient,ModelError
from blindspot.prompts import search_messages
from blindspot.search import LimitReached


def arguments(**overrides):
    return argparse.Namespace(**(dict(total_budget=75.,anchor_budget=4.,spark_budget=20.,wonder_budget=45.,open_budget=6.,
        open_input_price=None,open_cached_price=None,open_output_price=None,max_calls=1000,rpm=100,concurrency=4,
        repeat_policy='budget-fit',only='all',mock=True,mock_trials=1,build_only=False,no_plots=True)|overrides))


def test_anchors_are_only_new_payload_field_and_determine_gap_exactly():
    source=json.loads((ROOT/'data/basis-study-bank.json').read_text());bank=prepare_bank(source)
    assert len(bank['problems'])==24
    for p in bank['problems']:
        if p['basis']['condition']!='outer_anchors':continue
        original=next(a for a in bank['problems'] if a['basis']['spectrum_id']==p['basis']['spectrum_id'] and a['basis']['condition']=='dense')
        assert p['question']==original['question'] and p['steps']==original['steps']
        a,z=map(sp.sympify,[p['outer_eigenvalue_anchors']['smallest_eigenvalue'],p['outer_eigenvalue_anchors']['largest_eigenvalue']])
        H=sp.Matrix(p['basis']['H']);gap=sp.sqrt(2*(sp.trace(H*H)-a*a-z*z)-(sp.trace(H)-a-z)**2)
        assert gap==sp.sympify(p['steps'][-1]['expr'])
        for x,y in zip(original['cells'],p['cells']):
            assert x['candidate']==y['candidate']
            payload_a=json.loads(search_messages(original,x,20,Settings(),False,'truth')[1]['content'])
            payload_b=json.loads(search_messages(p,y,20,Settings(),False,'truth')[1]['content'])
            anchors=payload_b.pop('outer_eigenvalue_anchors')
            assert payload_a==payload_b and set(anchors)=={'smallest_eigenvalue','largest_eigenvalue','statement'}
            assert 'structural_certificate' not in payload_b


def test_programme_and_profile_guards_share_atomic_accounting(tmp_path):
    a=ProgrammeLedger(tmp_path/'calls.db',1.,10,'a',.5,'main')
    a.reserve('a1',.3,{})
    with pytest.raises(LimitReached):a.reserve('a2',.3,{})
    a.finish('a1',.1,dict(status='ok'));a.reserve('a2',.3,{})
    b=ProgrammeLedger(tmp_path/'calls.db',1.,10,'b',.8,'technical_pilot')
    with pytest.raises(LimitReached):b.reserve('b1',.7,{})
    b.reserve('b1',.5,{})
    assert a.profile_spent()==pytest.approx(.4) and a.totals()['charged_usd']==pytest.approx(.9)


class FinalClient(MetaClient):
    def __init__(self,settings,log):super().__init__(settings);self.log=log
    async def complete(self,request,**kwargs):
        payload=json.loads(request['messages'][1]['content']);cell=kwargs['cell']
        self.log.append((self.settings.model,self.settings.reasoning_effort,cell['id']))
        if self.settings.model.endswith('-contributor'):assert self.settings.reasoning_effort=='low'
        if self.settings.model in ['muse-spark-1.3','muse-wonder-1.0']:assert self.settings.reasoning_effort in ['max','high']
        assert request['response_format']['json_schema']['name']=='step_verdict'
        good='outer_eigenvalue_anchors' in payload
        return dict(valid=cell['is_control'] or not good,confidence=.9,reason='SIMULATED software test verdict')


def test_programme_pilots_reuse_cost_resume_and_pending_report(tmp_path):
    async def scenario():
        log=[];settings=Settings(seed_demo=False,force_mock=True)
        factory=lambda cfg:FinalClient(cfg,log)
        first=await execute(tmp_path,settings,arguments(max_calls=11),factory)
        assert first['spark_low']['status']=='paused_at_guard' and len(log)==11
        assert json.loads((tmp_path/'plan.json').read_text())['anchor_prediction']==PREDICTION
        complete=await execute(tmp_path,settings,arguments(),factory)
        assert all(p['status']=='finished' for p in complete.values())
        assert len(log)==784  # 756 main calls plus 28 predetermined technical calls.
        calls=len(log);await execute(tmp_path,settings,arguments(),factory);assert len(log)==calls
        result=analyse_final(tmp_path,plots=False)
        assert result['mode']=='mock' and result['new_calls']==784
        assert result['collection_closed'] and result['accuracy_panel_available']
        assert result['models'][0]['dense']['errors']==1653  # Reused source; never rerun.
        assert result['models'][1]['outer_anchors']['hit_rate']==1
        assert 'SIMULATED SOFTWARE TEST' in (tmp_path/'FINAL_FINDINGS.md').read_text()
        assert (tmp_path/'candidate-effects.csv').exists() and (tmp_path/'review.zip').exists()
        with ZipFile(tmp_path/'review.zip') as z,tempfile.TemporaryDirectory() as scratch:
            snapshot=Path(scratch)/'ledger.sqlite3';snapshot.write_bytes(z.read('search.sqlite3'))
            with sqlite3.connect(snapshot) as db:
                assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
                assert db.execute('SELECT COUNT(*) FROM search_calls').fetchone()[0]==784
        with pytest.raises(ValueError):await execute(tmp_path,settings,arguments(repeat_policy='fixed-five'),factory)
    asyncio.run(scenario())


def test_max_effort_requires_supported_standard_model(monkeypatch):
    monkeypatch.setenv('META_REASONING_EFFORT','max');monkeypatch.setenv('META_MODEL','muse-spark-1.3-contributor')
    with pytest.raises(ValueError):load_settings()
    monkeypatch.setenv('META_MODEL','muse-spark-1.3');assert load_settings().reasoning_effort=='max'


def test_truncated_technical_pilot_escalates_cap_then_stops_without_scientific_run(tmp_path):
    caps=[]
    class TruncatingClient(MetaClient):
        async def complete(self,request,**kwargs):
            caps.append(request['max_completion_tokens'])
            raise ModelError('Unusable model response: incomplete',raw=json.dumps(dict(choices=[dict(finish_reason='length')],
                usage=dict(prompt_tokens=200,completion_tokens=request['max_completion_tokens']))))
    result=asyncio.run(execute(tmp_path,Settings(force_mock=True),arguments(only='spark_max'),TruncatingClient))
    assert caps.count(8192)==8 and caps.count(16384)==8
    assert result['spark_max']['status']=='unusable_at_token_cap'
    assert not (tmp_path/'spark_max/main').exists()
    report=analyse_final(tmp_path,plots=False)
    assert report['models'][1]['dense'] is None and report['accounting']['spark_max']['pilot_calls']==16
    original_plan=(tmp_path/'plan.json').read_bytes()
    log=[];settings=Settings(force_mock=True);args=arguments(continue_panel='high',only='spark_high')
    continued=asyncio.run(execute(tmp_path,settings,args,lambda cfg:FinalClient(cfg,log)))
    assert continued['spark_max']['status']=='unusable_at_token_cap' and continued['spark_high']['status']=='finished'
    assert len(log)==224 and all(effort=='high' for _,effort,_ in log)
    assert (tmp_path/'plan.json').read_bytes()==original_plan
    assert json.loads((tmp_path/'panel-continuation.json').read_text())['profiles'][0]['id']=='spark_high'
    new_report=analyse_final(tmp_path,plots=False)
    assert new_report['new_calls']==240 and new_report['accounting']['spark_max']['pilot_calls']==16
    assert next(m for m in new_report['models'] if m['id']=='spark_high')['reasoning_effort']=='high'
    asyncio.run(execute(tmp_path,settings,args,lambda cfg:FinalClient(cfg,log)))
    assert len(log)==224  # Neither max attempts nor completed high trials are repurchased.


def test_cost_projection_includes_reasoning_once_and_cached_prompt_tokens():
    record=dict(usage=dict(prompt_tokens=1000,completion_tokens=4000,prompt_tokens_details=dict(cached_tokens=500),
        completion_tokens_details=dict(reasoning_tokens=3800)))
    ledger=SimpleNamespace(get=lambda key:record)
    pilot=SimpleNamespace(bank=dict(problems=[dict(cells=[dict(id='a')])]),ledger=ledger,key=lambda *args:'a',
        settings=Settings(api_key='unit-test'))
    projection=estimate(pilot,dict(input_price=4.,cached_price=.2,output_price=20.),1080)
    assert projection['expected_usd']==pytest.approx(.0821*1080)
    assert projection['conservative_usd']==pytest.approx(.0821*1080*1.5)


def test_simulated_or_pending_reports_cannot_replace_real_app_findings(tmp_path):
    for mode in ['mock','pending']:
        with pytest.raises(ValueError,match='LIVE'):
            integrate_final(tmp_path,dict(mode=mode))


def test_damaged_existing_ledger_stops_before_any_model_calls(tmp_path):
    (tmp_path/'search.sqlite3').write_bytes(b'not a SQLite ledger')
    calls=[]
    with pytest.raises(ValueError,match='No calls launched'):
        asyncio.run(execute(tmp_path,Settings(force_mock=True),arguments(),lambda cfg:FinalClient(cfg,calls)))
    assert calls==[]
