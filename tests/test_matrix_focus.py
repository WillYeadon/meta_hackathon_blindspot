import argparse
import asyncio
import csv
import json
from zipfile import ZipFile
import pytest
import sympy as sp
from blindspot.config import Settings
from blindspot.matrix_focus import build_bank, execute
from blindspot.meta import MetaClient, ModelError
from blindspot.prompts import TRUTH_CRITERION
from blindspot.runner import Runner
from blindspot.search import write_json, import_results
from blindspot.semantic_bank import load_bank
from blindspot.storage import Store


def arguments(**changes):
    values=dict(seed=1234,spectra=1,trials=2,budget_usd=1,max_calls=1000,rpm=100,exclude_bank=[],build_only=False)
    return argparse.Namespace(**(values|changes))


def test_paired_spectra_exact_labels_wording_and_exclusions():
    bank=build_bank(2,1234)
    assert len(bank['problems'])==8
    by_base={}
    for p in bank['problems']:
        H=sp.sympify(p['question'].split('H=',1)[1].split(' describes four coupled modes.',1)[0],locals={'Matrix':sp.Matrix})
        poly=H.charpoly();roots=sp.polys.polytools.ground_roots(poly.as_expr(),poly.gen)
        spectrum=sorted(r for r,n in roots.items() for _ in range(n))
        gap=spectrum[2]-spectrum[1]
        by_base.setdefault(p['focus']['base_id'],set()).add(tuple(spectrum))
        assert H.trace()==sp.sympify(p['steps'][0]['expr'])
        assert (H*H).trace()==sp.sympify(p['steps'][1]['expr'])
        assert len(p['cells'])==9
        assert p['verifier_protocol']=='truth'
        for c in p['cells']:
            value=sp.sympify(c['candidate']['expr'])
            assert (value==gap)==c['is_control']
            assert c['candidate']['text']==c['original']['text']=='The exact middle spectral gap is as follows.'
            if c['type'] not in ['zero_gap','original_control','equivalent']:
                assert (value-gap)/gap==sp.sympify(c['relative_error'])
    assert all(len(spectra)==1 for spectra in by_base.values())
    p=bank['problems'][0]
    assert bank['problems'][1]['question'].startswith(p['question'])
    exclusion={tuple(p['oracle']['spectrum'])}
    fresh=build_bank(1,1234,exclusion)
    assert tuple(fresh['problems'][0]['oracle']['spectrum']) not in exclusion
    with pytest.raises(ValueError):build_bank(0)


class MatrixClient(MetaClient):
    def __init__(self,settings,log,fail_forecast=False):
        super().__init__(settings);self.log=log;self.fail_forecast=fail_forecast

    async def complete(self,request,**kwargs):
        cell=kwargs['cell'];forecast=request['response_format']['json_schema']['name']=='self_prediction'
        self.log.append((forecast,cell['id'],request))
        if forecast:
            if self.fail_forecast:
                self.fail_forecast=False;raise ModelError('Synthetic incomplete response')
            return dict(probability_percent=80,reason='Software test forecast')
        dense='-dense-' in cell['id']
        valid=cell['is_control'] or (dense and cell['type'].startswith(('lower_','higher_')))
        return dict(valid=valid,confidence=.9,reason='Software test verdict')


def test_fixed_run_forecast_barrier_resume_paired_rates_bundle_and_import(tmp_path):
    async def scenario():
        root=tmp_path/'focus';log=[];settings=Settings(concurrency=3,seed_demo=False,db_path=str(tmp_path/'app.sqlite3'))
        first=await execute(root,settings,arguments(max_calls=11),MatrixClient(settings,log))
        assert first['status']=='paused_at_limit' and first['calls']==11
        assert first['usable_verdicts']==0 and all(item[0] for item in log)
        result=await execute(root,settings,arguments(),MatrixClient(settings,log))
        assert result['status']=='finished' and result['planned_calls']==result['calls']==108
        assert result['usable_verdicts']==72 and result['underlying_spectra']==1
        assert all(item[0] for item in log[:36]) and not any(item[0] for item in log[36:])
        assert log[0][1]!=build_bank(1,1234)['problems'][0]['cells'][0]['id']
        calls=len(log)
        await execute(root,settings,arguments(),MatrixClient(settings,log))
        assert len(log)==calls
        rows=list(csv.DictReader((root/'paired.csv').open(encoding='utf-8-sig')))
        gap=[r for r in rows if r['contrast']=='representation' and r['mutation']=='lower_1']
        assert len(gap)==2 and all(float(r['right_minus_left_pp'])==-100 for r in gap)
        with ZipFile(root/'review.zip') as z:
            assert {'bank.json','plan.json','comparison.csv','cells.csv','paired.csv','search.sqlite3'}<=set(z.namelist())
            assert not any(name.startswith('exports/') for name in z.namelist())
        import_results(root,settings);import_results(root,settings)
        saved=Store(settings.db_path).all()
        assert len(saved)==4 and all(e['focus_study']=='matrix-focus-1.0' for e in saved)
        with pytest.raises(ValueError):await execute(root,settings,arguments(trials=3),MatrixClient(settings,log))
        assert len(log)==calls
    asyncio.run(scenario())


def test_failed_forecast_blocks_context_and_leaves_rates_missing(tmp_path):
    async def scenario():
        settings=Settings(concurrency=2,seed_demo=False);log=[]
        result=await execute(tmp_path,settings,arguments(),MatrixClient(settings,log,True))
        assert result['status']=='finished_with_unusable_slots'
        assert result['forecast_blocked_contexts']==1 and result['unattempted_verdicts']==18
        rows=list(csv.DictReader((tmp_path/'cells.csv').open(encoding='utf-8-sig')))
        missing=[r for r in rows if r['usable']=='0']
        assert len(missing)==9 and all(r['rejection_rate']=='' for r in missing)
    asyncio.run(scenario())


def test_app_live_cell_preserves_focused_criterion_and_forecast_settings(tmp_path):
    async def scenario():
        write_json(tmp_path/'bank.json',build_bank(1,1234));bank=load_bank(tmp_path/'bank.json')
        settings=Settings(seed_demo=False,max_completion_tokens=16384,db_path=str(tmp_path/'app.db'))
        log=[];client=MatrixClient(settings,log);runner=Runner(settings,bank,Store(settings.db_path),client)
        p=bank['problems'][0];e=runner.create(p['id'],[p['cells'][0]['id']],trials=1,temperature=.7)
        finished=await runner.run(e['id'],fast=True)
        assert finished['status']=='complete' and finished['verifier_protocol']=='truth'
        forecast=json.loads(log[0][2]['messages'][1]['content'])
        assert forecast['verification_criterion']==TRUTH_CRITERION
        assert forecast['sampling']['temperature']==.7 and forecast['sampling']['max_completion_tokens']==16384
        assert 'candidate_step' not in forecast
        assert log[1][2]['messages'][0]['content']==TRUTH_CRITERION
        await runner.shutdown()
    asyncio.run(scenario())
