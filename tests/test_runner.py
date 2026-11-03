import asyncio
import json
from pathlib import Path
from fastapi.testclient import TestClient
from blindspot.app import create_app
from blindspot.config import Settings
from blindspot.meta import MetaClient, ModelError
from blindspot.perturbations import catalog
from blindspot.runner import Runner, public_experiment
from blindspot.storage import Store


class CountingClient(MetaClient):
    def __init__(self, settings):
        super().__init__(settings)
        self.calls=[]
        self.fail_prediction=False
        self.fail_trial=None

    async def complete(self, request, **kwargs):
        prediction=request["response_format"]["json_schema"]["name"]=="self_prediction"
        self.calls.append(("prediction" if prediction else "trial",kwargs["cell"]["id"],kwargs["ordinal"]))
        if prediction and self.fail_prediction:
            raise ModelError("Deliberate forecast failure")
        if not prediction and kwargs["ordinal"]==self.fail_trial:
            raise ModelError("Deliberate parse failure")
        return await super().complete(request,**kwargs)


def test_phase_barrier_distinct_trials_and_reuse(tmp_path):
    async def scenario():
        settings=Settings(db_path=str(tmp_path/'test.db'),seed_demo=False)
        client=CountingClient(settings); store=Store(settings.db_path); runner=Runner(settings,catalog(),store,client)
        ids=['gaussian:4:sign','gaussian:4:equivalent']
        e=runner.create('gaussian',ids,trials=5)
        result=await runner.run(e['id'],fast=True)
        assert result['status']=='complete'
        assert [call[0] for call in client.calls[:2]]==['prediction','prediction']
        assert all(call[0]=='trial' for call in client.calls[2:])
        assert len(client.calls)==12
        assert {c[2] for c in client.calls if c[0]=='trial' and c[1]==ids[0]}==set(range(5))
        events=result['events']; barrier=next(x['sequence'] for x in events if x['kind']=='all_predictions_saved')
        assert all(x['sequence']>barrier for x in events if x['kind']=='trial_started')
        for record in result['results'].values():
            assert all(record['prediction']['completed_at']<=trial['started_at'] for trial in record['trials'])
        metrics=result['results'][ids[0]]['metrics']
        assert metrics['predicted']==.92 and metrics['observed']==.2
        # Repeated request uses the same experiment; refreshing never creates calls.
        assert runner.create('gaussian',ids,trials=5)['id']==e['id']
        await runner.run(e['id'],fast=True)
        assert len(client.calls)==12
        # A different scope still reuses matching cell/ordinal calls.
        single=runner.create('gaussian',[ids[0]],trials=5)
        again=await runner.run(single['id'],fast=True)
        assert again['cached_calls']==6 and len(client.calls)==12
        fresh=runner.create('gaussian',[ids[0]],trials=5,fresh=True)
        await runner.run(fresh['id'],fast=True)
        assert len(client.calls)==18
        assert 'cache_identity' not in public_experiment(result)
        await runner.shutdown()
    asyncio.run(scenario())


def test_prediction_failure_blocks_all_trials_and_resume_reuses_success(tmp_path):
    async def scenario():
        settings=Settings(db_path=str(tmp_path/'test.db'),seed_demo=False)
        client=CountingClient(settings); runner=Runner(settings,catalog(),Store(settings.db_path),client)
        client.fail_prediction=True
        e=runner.create('gaussian',['gaussian:4:sign'],trials=3)
        result=await runner.run(e['id'],fast=True)
        assert result['status']=='failed' and all(c[0]=='prediction' for c in client.calls)
        client.fail_prediction=False;client.fail_trial=1
        result=await runner.run(e['id'],fast=True)
        assert result['status']=='partial'
        assert result['results']['gaussian:4:sign']['metrics']['valid_trials']==2
        count=len(client.calls)
        client.fail_trial=None
        result=await runner.run(e['id'],fast=True)
        assert result['status']=='complete'
        assert len(client.calls)==count+1
        assert result['cached_calls']==3
        await runner.shutdown()
    asyncio.run(scenario())


def test_pause_waits_for_inflight_and_resumes(tmp_path):
    async def scenario():
        settings=Settings(db_path=str(tmp_path/'test.db'),seed_demo=False,concurrency=1)
        client=CountingClient(settings); store=Store(settings.db_path); runner=Runner(settings,catalog(),store,client)
        e=runner.create('gaussian',['gaussian:4:sign','gaussian:4:equivalent'],trials=5)
        runner.start(e['id'])
        await asyncio.sleep(.03)
        runner.cancelled.add(e['id'])
        await runner.tasks[e['id']]
        assert store.get(e['id'])['status']=='cancelled'
        count=len(client.calls)
        await asyncio.sleep(.1)
        assert len(client.calls)==count
        runner.cancelled.clear()
        result=await runner.run(e['id'],fast=True)
        assert result['status']=='complete' and result['cached_calls']>=1
        await runner.shutdown()
    asyncio.run(scenario())


def test_app_launch_catalog_history_and_export(tmp_path):
    settings=Settings(db_path=str(tmp_path/'app.db'),seed_demo=True)
    with TestClient(create_app(settings)) as client:
        assert client.get('/').status_code==200
        assert client.get('/static/app.js').status_code==200
        assert client.get('/api/health').json()['mode']=='mock'
        assert len(client.get('/api/catalog').json()['dataset']['problems'])==8
        history=client.get('/api/experiments').json(); assert len(history)==1
        e=client.get('/api/experiments/'+history[0]['id']).json()
        assert e['status']=='complete' and e['config']['mode']=='mock'
        exported=client.get('/api/experiments/'+e['id']+'/export').json()
        assert 'SIMULATED' in exported['warning']
        assert exported['experiment']['results']['gaussian:4:sign']['prediction']['request']['messages']
        assert client.post('/api/experiments',json={'problem_id':'unknown'}).status_code==400
        assert client.post('/api/experiments',json={'problem_id':'gaussian','trials':0}).status_code==422
        assert client.post('/api/experiments',headers={'Origin':'https://unrelated.example'},json={'problem_id':'gaussian'}).status_code==403
        assert client.post('/api/experiments',json={'problem_id':'gaussian','temperature':1.0,'trials':5}).json()['id']==e['id']
    # Restart preserves the demonstration without creating a second run.
    with TestClient(create_app(settings)) as client:
        assert len(client.get('/api/experiments').json())==1


def test_mock_and_live_cache_namespaces_are_separate(tmp_path):
    a=Settings(db_path=str(tmp_path/'test.db'))
    b=Settings(api_key='TEST_ONLY',db_path=a.db_path)
    assert a.mode=='mock' and b.mode=='live' and a.namespace!=b.namespace
    store=Store(a.db_path)
    async def scenario():
        r1=Runner(a,catalog(),store,MetaClient(a)); r2=Runner(b,catalog(),store,MetaClient(b))
        assert r1.create('gaussian',['gaussian:4:sign'])['id']!=r2.create('gaussian',['gaussian:4:sign'])['id']
        await r1.shutdown();await r2.shutdown()
    asyncio.run(scenario())
