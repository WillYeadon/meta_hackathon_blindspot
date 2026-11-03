import argparse
import asyncio
import copy
import json
from pathlib import Path
import random
from zipfile import ZipFile
import pytest
import sympy as sp
from blindspot.config import Settings
from blindspot.maths import parse
from blindspot.meta import MetaClient
from blindspot.overnight import add_nearby_errors, diagnostic_bank, execute
from blindspot.prompts import search_messages
from blindspot.search import Search, write_json
from blindspot.semantic_bank import FAMILIES, make_case, load_bank


def test_truth_criterion_does_not_change_candidate_or_leak_reference():
    p=make_case('ivp_domain',0,random.Random(7));cell=p['cells'][0];settings=Settings(max_completion_tokens=16384)
    legacy=search_messages(p,cell,20,settings,False,'legacy');truth=search_messages(p,cell,20,settings,False,'truth')
    assert legacy[1]==truth[1]
    assert 'absence of displayed working alone' in truth[0]['content']
    payload=json.loads(truth[1]['content']);assert 'correct_steps' not in payload and 'validation' not in payload
    forecast=json.loads(search_messages(p,cell,20,settings,True,'truth',True)[1]['content'])
    assert forecast['sampling']['max_completion_tokens']==16384 and 'candidate_step' not in forecast


def test_nearby_candidates_are_distinct_for_all_families():
    problems=[make_case(f,i,random.Random(37+i)) for i,f in enumerate(FAMILIES)]
    bank=add_nearby_errors(dict(problems=[p for p in problems if p]))
    for p in bank['problems']:
        assert len(p['cells'])==4
        c=p['cells'][-1];assert c['type']=='nearby_value' and not c['is_control']
        assert sp.simplify(parse(c['original']['expr'],p)-parse(c['candidate']['expr'],p))!=0
        assert c['validation']['kind']=='exact_counterexample'


class VerdictClient(MetaClient):
    def __init__(self,settings,log):super().__init__(settings);self.log=log
    async def complete(self,request,**kwargs):
        cell=kwargs['cell'];prediction=request['response_format']['json_schema']['name']=='self_prediction'
        self.log.append((cell['id'],prediction,request['max_completion_tokens'],request['messages'][0]['content']))
        if prediction:return dict(probability_percent=80,reason='Test forecast')
        # No semantic error is missed. Correct original controls are rejected.
        return dict(valid=cell['type']=='equivalent',confidence=.9,reason='Test judgement')


def test_both_selection_follows_correct_control_rejections(tmp_path):
    async def scenario():
        p=make_case('ivp_domain',0,random.Random(4));p['split']='discovery'
        write_json(tmp_path/'bank.json',dict(problems=[p],seed=1));bank=load_bank(tmp_path/'bank.json');settings=Settings()
        opts=dict(budget_usd=1,max_calls=100,rpm=100,screen_trials=2,confirm_trials=2,top_k=1,max_per_family=1,holdout_per_family=1,input_price=.1,cached_price=.002,output_price=.2,selection='both',verifier_protocol='truth')
        search=Search(tmp_path,bank,settings,opts,VerdictClient(settings,[]))
        result=await search.run();assert result['selected_problems']==1
        assert search.record(p,'confirm')[p['cells'][1]['id']]['metrics']['observed']==1
    asyncio.run(scenario())


def test_overnight_shared_limit_resume_and_review_bundle(tmp_path):
    async def scenario():
        source=tmp_path/'old';source.mkdir();problems=[]
        for i,f in enumerate(['ivp_domain','near_degeneracy']):
            p=make_case(f,i,random.Random(23+i));p['split']='discovery';problems.append(p)
        write_json(source/'bank.json',dict(seed=1,problems=problems))
        root=tmp_path/'overnight';settings=Settings(concurrency=2,seed_demo=False)
        args=argparse.Namespace(seed=20261030,per_family=2,diagnostic_per_family=1,confirm_trials=2,top_k=2,budget_usd=1,max_calls=10,rpm=100)
        log=[];factory=lambda setting:VerdictClient(setting,log)
        first=await execute(source,root,settings,args,factory)
        assert first['calls']==10 and len(log)==10
        args.max_calls=1000
        again=await execute(source,root,settings,args,factory)
        assert again['calls']==len(log) and again['calls']>10
        assert len(again['phase_status'])==5
        assert {c[2] for c in log}=={4096,16384}
        calls=len(log);await execute(source,root,settings,args,factory);assert len(log)==calls
        with ZipFile(root/'review.zip') as z:
            assert 'search.sqlite3' in z.namelist() and 'comparison.csv' in z.namelist()
        old_questions={p['question'] for p in problems}
        fresh=json.loads((root/'wide/bank.json').read_text())
        assert not old_questions & {p['question'] for p in fresh['problems']}
    asyncio.run(scenario())
