import argparse
import asyncio
import json
from pathlib import Path
from zipfile import ZipFile
import pytest
from blindspot.config import ROOT,Settings
from blindspot.final_study import ProgrammeLedger,prepare_bank
from blindspot.panel_extension import execute_extension,freeze_extension,choose_joint,snapshot
from blindspot.meta import MetaClient,ModelError


def arguments(**changes):
    return argparse.Namespace(**(dict(additional_budget=110.,credit_remaining=150.0,max_calls=1000,rpm=100,concurrency=4,
        mock=True,mock_trials=1,no_plots=True,build_only=False)|changes))


def fixture_root(root):
    source=json.loads((ROOT/'data/basis-study-bank.json').read_text())
    fixtures={'bank.json':prepare_bank(source),
              'reference.json':json.loads((ROOT/'data/basis-study-results.json').read_text()),
              'plan.json':json.loads((ROOT/'data/final-panel-plan.json').read_text()),
              'panel-continuation.json':json.loads((ROOT/'data/final-panel-continuation.json').read_text()),
              'progress.json':{profile:dict(status='unusable_at_token_cap') for profile in ['spark_high','wonder_high']}}
    for name,value in fixtures.items():(root/name).write_text(json.dumps(value),encoding='utf-8')
    cfg=Settings(force_mock=True,seed_demo=False)
    (root/'execution-context.json').write_text(json.dumps(dict(mode='mock',account_namespace=cfg.namespace)),encoding='utf-8')
    ledger=ProgrammeLedger(root/'search.sqlite3',10.,1000,'spark_high',10.,'technical_pilot')
    ledger.reserve('historical-16k',0,dict(status='error',finish_reason='length',request=dict(max_completion_tokens=16384)))
    return cfg


def test_joint_budget_keeps_both_models_and_uses_only_cost():
    n,projections=choose_joint({'spark':dict(expected_usd=2.16),'wonder':dict(expected_usd=25.92)},100.,5.)
    assert n==3 and projections[0]['total_expected_usd']==pytest.approx(140.4)
    assert choose_joint({'wonder':dict(expected_usd=101)},100,1)[0] is None


def test_extended_pilots_resume_and_keep_original_design_and_calls(tmp_path):
    cfg=fixture_root(tmp_path);original={n:(tmp_path/n).read_bytes() for n in ['plan.json','panel-continuation.json','bank.json']}
    log=[]
    class Client(MetaClient):
        async def complete(self,request,**kwargs):
            assert self.settings.reasoning_effort=='high' and self.settings.model in ['muse-spark-1.3','muse-wonder-1.0']
            cap=request['max_completion_tokens'];assert cap in [32768,65536]
            log.append((self.settings.model,cap,kwargs['cell']['id']))
            if cap==32768 and self.settings.model=='muse-spark-1.3':
                raise ModelError('SIMULATED truncation',raw=json.dumps(dict(choices=[dict(finish_reason='length')],usage=dict(prompt_tokens=600,completion_tokens=32768))))
            return dict(valid=kwargs['cell']['is_control'],confidence=.9,reason='SIMULATED software check',usage=dict(prompt_tokens=600,completion_tokens=2000))
    async def scenario():
        await execute_extension(tmp_path,cfg,arguments(max_calls=12),Client)
        assert snapshot(tmp_path)['calls']==12 and not (tmp_path/'token-extension-allocation.json').exists()
        await execute_extension(tmp_path,cfg,arguments(),Client)
        assert len(log)==456 and snapshot(tmp_path)['calls']==457
        assert sum(model=='muse-spark-1.3' and cap==32768 for model,cap,_ in log)==8
        count=len(log);await execute_extension(tmp_path,cfg,arguments(),Client);assert len(log)==count
        for name,raw in original.items():assert (tmp_path/name).read_bytes()==raw
        allocation=json.loads((tmp_path/'token-extension-allocation.json').read_text())
        assert allocation['common_repeats']==1
        report=json.loads((tmp_path/'dashboard.json').read_text())
        assert report['mode']=='mock' and report['accuracy_panel_available']
        assert report['token_budget_extension']['reported_remaining_credit']==150.0
        assert json.loads((tmp_path/'spark_high/selected-protocol.json').read_text())['max_completion_tokens']==65536
    asyncio.run(scenario())


def test_credit_limit_rejects_excess_and_budget_does_not_reset(tmp_path):
    fixture_root(tmp_path)
    with pytest.raises(ValueError,match='remaining credit'):freeze_extension(tmp_path,arguments(additional_budget=151.))
    with pytest.raises(ValueError,match='finite'):freeze_extension(tmp_path,arguments(additional_budget=float('nan')))
    p,_=freeze_extension(tmp_path,arguments())
    ledger=ProgrammeLedger(tmp_path/'search.sqlite3',110,1000,'spark_high',110,'technical_pilot')
    ledger.reserve('later-cost',3,dict(status='pending'))
    resumed,_=freeze_extension(tmp_path,arguments())
    assert resumed['initial_accounting']==p['initial_accounting'] and resumed['initial_accounting']['charged_usd']==0
