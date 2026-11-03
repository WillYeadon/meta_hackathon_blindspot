"""Final fixed anchor intervention and cost-bounded Meta transfer panel.

python -m blindspot.final_study --directory var/final-study
No new spectra, candidate tuning, forecasts or adaptive scientific selection.
"""
import argparse
import asyncio
import copy
from contextlib import closing
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import random
import sqlite3
from statistics import mean
import tempfile
from zipfile import ZipFile,ZIP_DEFLATED
import sympy as sp
from .basis import validate_basis
from .config import ROOT,load_settings
from .meta import utcnow
from .overnight import ensure_bank
from .search import Search,Ledger,LimitReached,SearchStopped,write_json,measured_cost
from .semantic_bank import load_bank

VERSION='final-study-1.0'
PREDICTION=('If the main failure mechanism is that the verifier replaces exact checking with an approximate consistency argument in which the outer eigenvalues are allowed to drift, fixing the exact minimum and maximum eigenvalues should cause a large recovery in discriminability. We predict >90% detection of incorrect claims and <5% false rejection of correct controls.')
DOCS={'checked':'2026-11-01','reasoning':'https://dev.meta.ai/docs/reasoning',
      'models':'https://dev.meta.ai/docs/models','pricing':'https://dev.meta.ai/docs/pricing-rate-limits',
      'schema':'https://dev.meta.ai/docs/api-reference/chat-completions/schemas',
      'open':'https://dev.meta.ai/docs/muse-spark-open/deploy'}


def prepare_bank(source):
    source=copy.deepcopy(source);problems=[]
    for p in source['problems']:
        if p['basis']['level']!=5 or p['basis']['condition']!='sweep':continue
        b=p['basis'];D,Q,H=map(sp.Matrix,[b['D'],b['Q'],b['H']]);proof=validate_basis(D,Q,H)
        if proof!=b['validation']:raise ValueError('Source invariance check changed.')
        a,z=D[0,0],D[3,3];T=sp.trace(H);S=sp.trace(H*H)
        gap=sp.sqrt(2*(S-a*a-z*z)-(T-a-z)**2)
        if gap!=sp.sympify(p['steps'][-1]['expr']):raise ValueError('Outer anchors do not determine the saved gap.')
        for anchored in [False,True]:
            c=copy.deepcopy(p);old=c['id'];pid=old+'-outer-anchors' if anchored else old
            c.update(id=pid,title=c['title']+(' · outer anchors' if anchored else ' · dense baseline'))
            c.pop('structural_certificate',None)
            c['basis'].update(condition='outer_anchors' if anchored else 'dense',label='Outer spectral anchors' if anchored else 'Dense baseline')
            if anchored:c['outer_eigenvalue_anchors']=dict(smallest_eigenvalue=str(a),largest_eigenvalue=str(z),
                statement='These are the exact smallest and largest eigenvalues of the supplied H.')
            for cell in c['cells']:
                cell['problem_id']=pid;cell['id']=pid+cell['id'][len(old):]
            problems.append(c)
    if len(problems)!=24 or len({p['basis']['spectrum_id'] for p in problems})!=12:raise ValueError('Expected the SAME 12 held-out general-rational spectra.')
    return dict(version=VERSION,seed=source['seed'],problems=problems,
        description='Fixed final panel: existing twelve spectra, original nine claims, dense and exact outer-anchor conditions; no forecasts.')


def profiles(args):
    return [dict(id='spark_low',label='Spark 1.3 Contributor · low',model='muse-spark-1.3-contributor',effort='low',trials=20,
                 caps=[16384],budget=args.anchor_budget,input_price=.10,cached_price=.002,output_price=.20,provider='meta'),
            dict(id='spark_max',label='Spark 1.3 Standard · max',model='muse-spark-1.3',effort='max',trials=5,
                 caps=[8192,16384],budget=args.spark_budget,input_price=1.25,cached_price=.15,output_price=4.25,provider='meta'),
            dict(id='wonder_max',label='Muse Wonder · max',model='muse-wonder-1.0',effort='max',trials=5,
                 caps=[8192,16384],budget=args.wonder_budget,input_price=4.,cached_price=.20,output_price=20.,provider='meta'),
            dict(id='spark_open',label='Muse Spark Open · xhigh',model='accounts/fireworks/models/muse-spark-open',effort='xhigh',trials=5,
                 caps=[8192,16384],budget=args.open_budget,input_price=args.open_input_price,cached_price=args.open_cached_price,
                 output_price=args.open_output_price,provider='fireworks',base_url='https://api.fireworks.ai/inference/v1')]


class ProgrammeLedger(Ledger):
    """One global reservation guard plus separate profile guards, atomically."""
    def __init__(self,path,budget,max_calls,profile,profile_budget,phase):
        super().__init__(path,budget,max_calls);self.profile=profile;self.profile_budget=profile_budget;self.phase=phase
        with self.db() as db:db.execute('CREATE TABLE IF NOT EXISTS final_profiles (key TEXT PRIMARY KEY, profile TEXT NOT NULL)')

    def reserve(self,key,cost,record):
        record.update(budget_profile=self.profile,phase_kind=self.phase,global_guard_usd=self.budget,profile_guard_usd=self.profile_budget,max_calls_guard=self.max_calls)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            n,total=db.execute('SELECT COUNT(*),COALESCE(SUM(charged),0) FROM search_calls').fetchone()
            spent=db.execute('SELECT COALESCE(SUM(c.charged),0) FROM search_calls c JOIN final_profiles p ON c.key=p.key WHERE p.profile=?',(self.profile,)).fetchone()[0]
            if n>=self.max_calls or total+cost>self.budget:raise LimitReached('Global final-programme guard reached; saved work retained.')
            if spent+cost>self.profile_budget:raise LimitReached(f'{self.profile} spending guard reached; saved work retained.')
            db.execute('INSERT INTO search_calls VALUES (?,?,?)',(key,cost,json.dumps(record)))
            db.execute('INSERT INTO final_profiles VALUES (?,?)',(key,self.profile))

    def finish(self,key,cost,record):
        record.update(budget_profile=self.profile,phase_kind=self.phase);super().finish(key,cost,record)

    def profile_spent(self):
        with self.db() as db:return db.execute('SELECT COALESCE(SUM(c.charged),0) FROM search_calls c JOIN final_profiles p ON c.key=p.key WHERE p.profile=?',(self.profile,)).fetchone()[0]


class FinalSearch(Search):
    def manifest_warning(self):
        return 'MOCK: simulated outcomes' if self.settings.mode=='mock' else 'Fixed held-out final panel; every frozen cell is retained. Technical pilots are excluded from scientific estimates.'

    def jobs(self,problems,stage,count):
        jobs=super().jobs(problems,stage,count);random.Random('final-fixed-1101').shuffle(jobs);return jobs

    def prepare_request(self,request):
        if self.options.get('provider')=='fireworks':
            request=copy.deepcopy(request);request['max_tokens']=request.pop('max_completion_tokens')
            for m in request['messages']:
                if m['role']=='developer':m['role']='system'
        return request


def selected_pilot(bank,anchor_only=False):
    ids=sorted({p['basis']['spectrum_id'] for p in bank['problems']});chosen={ids[0],ids[6]}
    ps=[]
    for p in bank['problems']:
        if p['basis']['spectrum_id'] not in chosen or (anchor_only and p['basis']['condition']!='outer_anchors'):continue
        c=copy.deepcopy(p);c['cells']=[c for c in c['cells'] if c['type'] in ['lower_1','original_control']];c['cell_count']=2;ps.append(c)
    return dict(version=VERSION,seed=bank['seed'],problems=ps,description='Predetermined technical pilot; excluded from scientific estimates.')


def options(args,profile,trials,purpose):
    return dict(budget_usd=args.total_budget,max_calls=args.max_calls,rpm=args.rpm,screen_trials=trials,confirm_trials=trials,
        top_k=1,max_per_family=1,holdout_per_family=1,selection='none',verifier_protocol='truth',show_budget=False,
        input_price=profile['input_price'],cached_price=profile['cached_price'],output_price=profile['output_price'],
        provider=profile['provider'],purpose=purpose)


def create_search(root,bank,setting,args,profile,cap,trials,purpose,client_factory):
    directory=root/profile['id']/purpose;directory.mkdir(parents=True,exist_ok=True)
    ensure_bank(directory/'bank.json',bank)
    cfg=replace(setting,model=profile['model'],reasoning_effort=profile['effort'],max_completion_tokens=cap,
        timeout=max(1200,setting.timeout),retries=0,concurrency=args.concurrency,temperature=1.,base_url=profile.get('base_url',setting.base_url))
    ledger=ProgrammeLedger(root/'search.sqlite3',args.total_budget,args.max_calls,profile['id'],profile['budget'],'main' if purpose=='main' else 'technical_pilot')
    search=FinalSearch(directory,load_bank(directory/'bank.json'),cfg,options(args,profile,trials,purpose),
        client_factory(cfg) if client_factory else None,ledger)
    return search


def estimate(pilot,profile,planned_calls):
    records=[r for p in pilot.bank['problems'] for c in p['cells'] if (r:=pilot.ledger.get(pilot.key(c,'confirm',0)))]
    costs=[measured_cost(r.get('usage'),profile['input_price'],profile['cached_price'],profile['output_price']) for r in records]
    known=[c for c in costs if c is not None]
    if pilot.settings.mode=='mock':average=0.
    elif known:average=mean(known)
    else:return dict(expected_usd=None,conservative_usd=None,known_usage_calls=0)
    return dict(expected_usd=average*planned_calls,conservative_usd=average*planned_calls*1.5,known_usage_calls=len(known),
        mean_prompt_tokens=mean(r.get('usage',{}).get('prompt_tokens',0) for r in records if r.get('usage')) if known else 0,
        mean_completion_tokens=mean(r.get('usage',{}).get('completion_tokens',0) for r in records if r.get('usage')) if known else 0)


def review_bundle(root):
    temporary=root/'review.zip.tmp'
    with tempfile.TemporaryDirectory(prefix='blindspot-review-') as snapshots, ZipFile(temporary,'w',ZIP_DEFLATED) as z:
        for path in sorted(root.rglob('*')):
            if not path.is_file() or path.name=='review.zip' or path.suffix not in {'.json','.sqlite3','.csv','.md','.png'}:continue
            name=path.relative_to(root).as_posix();source=path
            if path.suffix=='.sqlite3':
                source=Path(snapshots)/(hashlib.sha256(name.encode()).hexdigest()+'.sqlite3')
                with closing(sqlite3.connect(path)) as src, closing(sqlite3.connect(source)) as dst:
                    src.backup(dst)
                    if dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Review database snapshot failed integrity check.')
            z.write(source,name)
    temporary.replace(root/'review.zip')


def freeze(root,args):
    root.mkdir(parents=True,exist_ok=True)
    source=json.loads((ROOT/'data/basis-study-bank.json').read_text(encoding='utf-8'));bank=prepare_bank(source)
    ensure_bank(root/'bank.json',bank)
    raw_reference=(ROOT/'data/basis-study-results.json').read_bytes();reference=json.loads(raw_reference)
    ensure_bank(root/'reference.json',reference)
    plan=dict(version=VERSION,source_bank_sha256=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest(),
        reference_sha256=hashlib.sha256(raw_reference).hexdigest(),spectra=12,candidates=9,anchor_prediction=PREDICTION,
        alternative_interpretation='Outer anchors plus the supplied Tr(H),Tr(H^2) determine the gap algebraically. Rescue does not uniquely establish an internal drifting-anchor strategy.',
        hidden_analysis_identity='gap^2=2*(Tr(H^2)-lambda_min^2-lambda_max^2)-(Tr(H)-lambda_min-lambda_max)^2; NEVER sent to verifier.',
        profiles=profiles(args),repeat_policy=args.repeat_policy,
        software_test_repeat_override=args.mock_trials if args.mock else None,
        pilot_policy='Fixed spectra 001 and 007, lower-1% and unchanged correct claims, both conditions; pilots excluded from science. Escalate token cap on length failures only.',
        budget_policy='Pilot usage projected to all fixed cells with 1.5x margin. Target five repeats; budget-fit may choose three or one, using cost only. Part A remains twenty.',
        reference_policy='Reuse all saved twenty-repeat low baseline/certificate verdicts; additionally report fixed ordinals 0-4 for equal-repeat sensitivity.',
        explanation_policy='Reuse frozen lexical rules unchanged; exploratory only.',docs=DOCS,
        profiles_execution='Anchor low, Standard Spark max, Wonder max, optional configured Fireworks Spark Open xhigh; no additional experiments.',
        primary='Hit rate, false alarms, corrected d-prime and confidence distributions; effects paired by spectrum and candidate; no five-trial calibration claims.',
        initial_total_budget=args.total_budget,created_at=utcnow())
    if (root/'plan.json').exists():
        old=json.loads((root/'plan.json').read_text(encoding='utf-8'));plan['created_at']=old['created_at'];plan['initial_total_budget']=old['initial_total_budget']
        # Spending limits may increase explicitly on resume; design stays immutable.
        for new,prior in zip(plan['profiles'],old['profiles']):new['budget']=prior['budget']
    ensure_bank(root/'plan.json',plan)
    return bank


def freeze_panel_continuation(root,args):
    """Explicit technical amendment; never overwrite the original fixed plan."""
    path=root/'panel-continuation.json'
    statuses=json.loads((root/'progress.json').read_text(encoding='utf-8')) if (root/'progress.json').exists() else {}
    if not (root/'plan.json').exists():raise ValueError('Continue in the existing final-study directory, not a fresh directory.')
    old=json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    prior=[p for p in profiles(args) if p['id'] in ['spark_max','wonder_max'] and statuses.get(p['id'],{}).get('status')=='unusable_at_token_cap']
    if not prior:raise ValueError('High continuation requires a max configuration stopped by its technical token-cap pilot.')
    amended=[]
    for p in prior:
        p=copy.deepcopy(p);p['replaces_technical_profile']=p['id'];p['id']=p['id'].replace('_max','_high')
        p['label']=p['label'].replace(' · max',' · high');p['effort']='high';amended.append(p)
    amendment=dict(version='panel-continuation-1.0',created_at=utcnow(),
        original_plan_sha256=hashlib.sha256((root/'plan.json').read_bytes()).hexdigest(),
        bank_sha256=hashlib.sha256((root/'bank.json').read_bytes()).hexdigest(),
        reason='Original max pilots exceeded the frozen token-cap usability threshold. Use explicitly named high configurations to obtain the planned model-level comparison within the deadline/budget. No model accuracy selected the amendment.',
        profiles=amended,scope='Same twelve spectra, nine candidates, two conditions. No Spark-low rerun, no new families, no forecasts.',
        analysis='Max attempts remain technical-only, not correctness evidence. High is a distinct setting; do not describe it as max.',
        pilot_policy='Same predetermined eight technical cases per configuration; 8192 then 16384 only for truncation. Stop if final cap remains unusable; no automatic further effort changes.',
        budget_policy='Retain the original shared ledger, total-dollar/call guards, profile guards and five/three/one cost-only repeat rule. All previous spending still counts.')
    if old:
        amendment['created_at']=old['created_at']
        for p,prior in zip(amendment['profiles'],old['profiles']):p['budget']=prior['budget']
    ensure_bank(path,amendment)
    return amended


async def execute(root,settings,args,client_factory=None):
    root=Path(root)
    if (root/'search.sqlite3').exists():
        try:
            with closing(sqlite3.connect(root/'search.sqlite3')) as db:
                if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise sqlite3.DatabaseError('Invalid existing ledger.')
        except sqlite3.DatabaseError as exc:
            raise ValueError('Existing final ledger failed integrity check. No calls launched. Preserve it and restore a verified review.zip database before resuming; do not silently repurchase the experiment.') from exc
    bank=freeze(root,args)
    active_profiles=freeze_panel_continuation(root,args) if getattr(args,'continue_panel',None) else profiles(args)
    if args.build_only:
        print(json.dumps(json.loads((root/('panel-continuation.json' if getattr(args,'continue_panel',None) else 'plan.json')).read_text(encoding='utf-8')),indent=2));return
    ensure_bank(root/'execution-context.json',dict(mode='mock' if args.mock else 'live',account_namespace=settings.namespace))
    history_path=root/'guard-history.json'
    history=json.loads(history_path.read_text(encoding='utf-8')) if history_path.exists() else []
    history.append(dict(started_at=utcnow(),global_budget_usd=args.total_budget,max_calls=args.max_calls,
        profile_budgets_usd={p['id']:p['budget'] for p in active_profiles},rpm=args.rpm,concurrency=args.concurrency,only=args.only))
    write_json(history_path,history)
    status_path=root/'progress.json';statuses=json.loads(status_path.read_text(encoding='utf-8')) if status_path.exists() else {}
    print(f'Frozen final programme. Global local-accounting guard ${args.total_budget:.2f}; mode {"MOCK" if args.mock else "LIVE"}.',flush=True)
    if getattr(args,'continue_panel',None):print('Explicit technical amendment: HIGH reasoning, same fixed cases and shared ledger. Original max pilots remain technical-only; Spark-low anchors are not rerun.',flush=True)
    try:
        for profile in active_profiles:
            pid=profile['id']
            if args.only not in ['all',pid]:continue
            condition=replace(settings,force_mock=True) if args.mock else settings
            if profile['provider']=='fireworks':
                key=os.getenv('FIREWORKS_API_KEY','')
                if not args.mock and (not key or any(profile[k] is None for k in ['input_price','cached_price','output_price'])):
                    statuses[pid]=dict(status='skipped',reason='No preconfigured Fireworks key and explicit provider token prices. No GPU deployment or partner setup attempted.');write_json(status_path,statuses);continue
                if args.mock:profile.update(input_price=.1,cached_price=.002,output_price=.2)
                condition=replace(condition,api_key=key or condition.api_key)
            selected_path=root/pid/'selected-protocol.json'
            if selected_path.exists():selected=json.loads(selected_path.read_text(encoding='utf-8'))
            else:
                selected=None
                for cap in profile['caps']:
                    pilot_bank=selected_pilot(bank,pid=='spark_low')
                    pilot=create_search(root,pilot_bank,condition,args,profile,cap,1,f'pilot-{cap}',client_factory)
                    print(f'Technical pilot: {profile["label"]}, cap {cap}, {sum(len(p["cells"]) for p in pilot_bank["problems"])} fixed requests; profile guard ${profile["budget"]:.2f}.',flush=True)
                    stopped=None
                    try:await pilot.phase(pilot.bank['problems'],'confirm',1)
                    except SearchStopped as exc:stopped=str(exc)
                    finally:await pilot.client.close()
                    records=[pilot.ledger.get(pilot.key(c,'confirm',0)) for p in pilot.bank['problems'] for c in p['cells']]
                    if stopped or any(r is None for r in records):
                        statuses[pid]=dict(status='technical_pilot_stopped',reason=stopped or 'Pilot incomplete.');break
                    lengths=sum(r.get('finish_reason')=='length' for r in records)
                    bad=[r for r in records if r['status']!='ok' and r.get('finish_reason')!='length']
                    if bad:
                        statuses[pid]=dict(status='technical_pilot_failed',reason=bad[0].get('error','Unusable pilot response.'));break
                    if lengths and cap!=profile['caps'][-1]:continue
                    if lengths>len(records)/4:
                        statuses[pid]=dict(status='unusable_at_token_cap',reason='More than 25% of the final-cap technical pilot truncated. No main run launched.');break
                    choices=[args.mock_trials] if args.mock and args.mock_trials is not None else ([20] if pid=='spark_low' else ([5] if args.repeat_policy=='fixed-five' else [5,3,1]))
                    chosen=None;projections=[]
                    for trials in choices:
                        calls=12*9*(1 if pid=='spark_low' else 2)*trials
                        projection=estimate(pilot,profile,calls);projection.update(trials=trials,planned_calls=calls);projections.append(projection)
                        print(json.dumps(dict(profile=pid,token_cap=cap,projection=projection,already_accounted_usd=pilot.ledger.profile_spent(),profile_guard_usd=profile['budget']),indent=2),flush=True)
                        # Keep room for concurrent reservations, which use worst-case tokens.
                        reserve_margin=0 if args.mock else args.concurrency*(cap*profile['output_price']/1e6+.02)
                        if projection['conservative_usd'] is not None and pilot.ledger.profile_spent()+projection['conservative_usd']+reserve_margin<=profile['budget']:
                            chosen=trials;break
                    write_json(root/pid/'cost-estimate.json',dict(projections=projections,selected_repeats=chosen,token_cap=cap,pilot_truncations=lengths,
                        warning='Small-pilot cost projection, not a guaranteed bill. Both global and profile reservations remain enforced.'))
                    if chosen is None:
                        statuses[pid]=dict(status='cost_projection_exceeds_guard',reason='Even the prespecified smallest repeat count exceeds the profile guard. No main run launched.');break
                    selected=dict(model=profile['model'],reasoning_effort=profile['effort'],max_completion_tokens=cap,trials=chosen,
                        pilot_calls=len(records),pilot_truncations=lengths,selection_basis='Technical usability and cost only; verifier accuracy not used.',frozen_at=utcnow())
                    ensure_bank(selected_path,selected);break
                if selected is None:
                    write_json(status_path,statuses);continue
            subset=[p for p in bank['problems'] if pid!='spark_low' or p['basis']['condition']=='outer_anchors']
            main_bank=dict(version=VERSION,seed=bank['seed'],problems=subset,description=bank['description'])
            main=create_search(root,main_bank,condition,args,profile,selected['max_completion_tokens'],selected['trials'],'main',client_factory)
            print(f'Main fixed run: {profile["label"]}; {selected["trials"]} repeats, {len(subset)*9*selected["trials"]} planned verdicts, token cap {selected["max_completion_tokens"]}.',flush=True)
            state='finished';reason=None
            try:await main.phase(main.bank['problems'],'confirm',selected['trials'])
            except SearchStopped as exc:state='paused_at_guard' if isinstance(exc,LimitReached) else 'stopped_on_error';reason=str(exc)
            finally:await main.client.close()
            records=[main.ledger.get(main.key(c,'confirm',i)) for p in main.bank['problems'] for c in p['cells'] for i in range(selected['trials'])]
            recorded=sum(r is not None for r in records);usable=sum(r is not None and r['status']=='ok' for r in records)
            if state=='finished' and usable<len(records):state='finished_with_unusable_slots'
            statuses[pid]=dict(status=state,reason=reason,recorded=recorded,usable=usable,planned=len(records),**selected)
            write_json(status_path,statuses)
            from .final_report import analyse_final
            analyse_final(root,plots=not args.no_plots,integrate=not args.mock)
            review_bundle(root)
    finally:
        write_json(status_path,statuses)
        from .final_report import analyse_final
        analyse_final(root,plots=not args.no_plots,integrate=not args.mock);review_bundle(root)
    print(f'Final review archive: {root / "review.zip"}')
    return statuses


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=Path('var/final-study'))
    p.add_argument('--total-budget',type=float,default=75);p.add_argument('--anchor-budget',type=float,default=4)
    p.add_argument('--spark-budget',type=float,default=20);p.add_argument('--wonder-budget',type=float,default=45);p.add_argument('--open-budget',type=float,default=6)
    p.add_argument('--repeat-policy',choices=['budget-fit','fixed-five'],default='budget-fit')
    p.add_argument('--only',choices=['all','spark_low','spark_max','wonder_max','spark_open','spark_high','wonder_high'],default='all')
    p.add_argument('--continue-panel',choices=['high'],help='Explicit high-reasoning continuation after max technical truncation; same directory/ledger/cases')
    p.add_argument('--open-input-price',type=float);p.add_argument('--open-cached-price',type=float);p.add_argument('--open-output-price',type=float)
    p.add_argument('--max-calls',type=int,default=6000);p.add_argument('--rpm',type=int,default=100);p.add_argument('--concurrency',type=int,default=8)
    p.add_argument('--mock',action='store_true');p.add_argument('--build-only',action='store_true');p.add_argument('--no-plots',action='store_true')
    p.add_argument('--mock-trials',type=int,choices=[1,2],help='Small software check only; requires --mock and never changes a live design')
    args=p.parse_args()
    if min(args.total_budget,args.anchor_budget,args.spark_budget,args.wonder_budget,args.open_budget)<=0 or args.total_budget>80 or args.max_calls<1 or not 1<=args.rpm<=150 or not 1<=args.concurrency<=8:p.error('Use positive guards, at most $80 total, 1–150 RPM and 1–8 concurrent requests.')
    if any(v is not None and v<0 for v in [args.open_input_price,args.open_cached_price,args.open_output_price]):p.error('Token prices must be nonnegative.')
    if args.mock_trials is not None and not args.mock:p.error('--mock-trials requires --mock.')
    if args.continue_panel and args.only not in ['all','spark_high','wonder_high']:p.error('--continue-panel high selects spark_high/wonder_high; use --only all or one of those IDs.')
    if not args.continue_panel and args.only in ['spark_high','wonder_high']:p.error('Use --continue-panel high for the explicit amended configurations.')
    settings=load_settings()
    if not args.mock and not args.build_only and settings.mode!='live':p.error('Use the existing Windows META_API_KEY with BLINDSPOT_MOCK=false, or explicitly use --mock in another directory.')
    if not args.no_plots:
        try:import matplotlib
        except ImportError:p.error('Install requirements-analysis.txt or pass --no-plots.')
    asyncio.run(execute(args.directory.resolve(),settings,args))


if __name__=='__main__':main()
