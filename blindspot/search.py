"""Budgeted discovery, fresh confirmation and reserved-parameter validation.

Run `python -m blindspot.search --help`. Building a bank makes no model calls.
Live runs are explicit; failures are retained, never counted as missed errors.
"""
import argparse
import asyncio
import csv
from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import time
import uuid
from .config import load_settings
from .meta import MetaClient, ModelError, build_request, utcnow
from .metrics import aggregate
from .prompts import search_messages, PROMPT_VERSION
from .runner import digest, Runner, public_experiment
from .semantic_bank import build_bank, load_bank, VERSION
from .storage import Store

SEARCH_VERSION='search-1.0'


def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    temporary.replace(path)


class SearchStopped(Exception):
    pass


class LimitReached(SearchStopped):
    pass


class Ledger:
    """Reserve before sending; interrupted/ambiguous calls remain charged.

    A pending request is never silently sent again on resume. Its outcome may
    be unknown, so its full reservation remains in the local budget ledger.
    """
    def __init__(self,path,budget,max_calls):
        self.path=path;self.budget=budget;self.max_calls=max_calls
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS search_calls (key TEXT PRIMARY KEY, charged REAL NOT NULL, record TEXT NOT NULL)')

    @contextmanager
    def db(self):
        connection=sqlite3.connect(self.path,timeout=30)
        try:
            with connection:yield connection
        finally:connection.close()

    def get(self,key):
        with self.db() as db:row=db.execute('SELECT record FROM search_calls WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None

    def totals(self):
        with self.db() as db:count,cost=db.execute('SELECT COUNT(*),COALESCE(SUM(charged),0) FROM search_calls').fetchone()
        return dict(calls=count,charged_usd=cost,budget_usd=self.budget,max_calls=self.max_calls)

    def reserve(self,key,cost,record):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            count,spent=db.execute('SELECT COUNT(*),COALESCE(SUM(charged),0) FROM search_calls').fetchone()
            if count>=self.max_calls:raise LimitReached('Maximum call count reached.')
            if spent+cost>self.budget:raise LimitReached('Local budget guard reached; completed work is saved.')
            db.execute('INSERT INTO search_calls VALUES (?,?,?)',(key,cost,json.dumps(record)))

    def finish(self,key,cost,record):
        with self.db() as db:db.execute('UPDATE search_calls SET charged=?,record=? WHERE key=?',(cost,json.dumps(record),key))


def measured_cost(usage,input_price,cached_price,output_price):
    if not usage or 'prompt_tokens' not in usage or 'completion_tokens' not in usage:return None
    prompt=usage['prompt_tokens'];completion=usage['completion_tokens']
    cached=(usage.get('prompt_tokens_details') or {}).get('cached_tokens',0)
    # Completion tokens already include reasoning tokens; do not add them again.
    return (max(0,prompt-cached)*input_price+cached*cached_price+completion*output_price)/1_000_000


class Search:
    def __init__(self,root,bank,settings,options,client=None,ledger=None):
        self.root=Path(root);self.bank=bank;self.settings=replace(settings,retries=0)
        self.options=options;self.client=client or MetaClient(self.settings)
        self.ledger=ledger or Ledger(self.root/'search.sqlite3',options['budget_usd'],options['max_calls'])
        self.limit=asyncio.Semaphore(settings.concurrency);self.rate_lock=asyncio.Lock();self.next_start=0
        protocol={k:v for k,v in options.items() if k not in {'budget_usd','max_calls','rpm'}}
        # Preserve identities for already-run searches with the original defaults.
        for key,default in [('verifier_protocol','legacy'),('selection','misses'),('show_budget',False)]:
            if protocol.get(key)==default:protocol.pop(key)
        self.identity=dict(version=SEARCH_VERSION,bank=bank['hash'],prompt=PROMPT_VERSION,settings=settings.public(),account=settings.namespace,protocol=protocol)
        self.signature=digest(self.identity)
        manifest_path=self.root/'manifest.json'
        if manifest_path.exists():
            old=json.loads(manifest_path.read_text(encoding='utf-8'))
            if old['signature']!=self.signature:raise ValueError('Run settings or bank changed. Use a new output directory; do not mix experiments.')
            self.created=old['created_at']
        else:
            self.created=utcnow()
            write_json(manifest_path,dict(signature=self.signature,created_at=self.created,identity=self.identity,initial_limits={k:options[k] for k in ['budget_usd','max_calls','rpm']},warning=self.manifest_warning()))

    def manifest_warning(self):
        return 'MOCK: simulated outcomes' if self.settings.mode=='mock' else 'Live search; discovery-selected items are not an unbiased benchmark.'

    def key(self,cell,stage,ordinal):return digest(dict(run=self.signature,cell=cell['id'],stage=stage,ordinal=ordinal))

    def prepare_request(self,request):return request

    def record(self,p,stage):
        records={}
        count=self.options['screen_trials'] if stage=='screen' else self.options['confirm_trials']
        forecast_stage='holdout_forecast' if stage=='holdout' else 'forecast'
        for c in p['cells']:
            prediction=self.ledger.get(self.key(c,forecast_stage,0))
            trials=[r for i in range(count) if (r:=self.ledger.get(self.key(c,stage,i))) is not None]
            records[c['id']]={'prediction':prediction,'trials':trials,'metrics':aggregate({'prediction':prediction,'trials':trials},c['is_control'])}
        return records

    async def obtain(self,p,c,stage,ordinal=0):
        key=self.key(c,stage,ordinal)
        fatal_prefixes=('Meta HTTP 400.','Meta HTTP 401.','Meta HTTP 403.','Meta HTTP 404.')
        if saved:=self.ledger.get(key):
            if saved.get('error','').startswith(fatal_prefixes):raise SearchStopped(saved['error'])
            return saved
        prediction=stage.endswith('forecast')
        messages=search_messages(p,c,self.options['confirm_trials'],self.settings,prediction,self.options.get('verifier_protocol','legacy'),self.options.get('show_budget',False))
        request=self.prepare_request(build_request(self.settings,messages,prediction,self.settings.temperature))
        prices=self.options
        # UTF-8 bytes plus a generous protocol allowance bound estimated input
        # tokens conservatively for these text prompts; not a provider billing cap.
        reserved=(len(json.dumps(request,ensure_ascii=False).encode('utf-8'))+4096)*prices['input_price']/1e6+self.settings.max_completion_tokens*prices['output_price']/1e6
        if self.settings.mode=='mock':reserved=0
        async with self.limit:
            if self.settings.mode!='mock':
                async with self.rate_lock:
                    await asyncio.sleep(max(0,self.next_start-time.monotonic()))
                    self.next_start=time.monotonic()+60/self.options['rpm']
            base=dict(status='pending',stage=stage,ordinal=ordinal,request=request,mode=self.settings.mode,started_at=utcnow(),reserved_usd=reserved,cost_known=False,
                      run_signature=self.signature,problem_id=p['id'],cell_id=c['id'],family=p.get('family'),is_control=c['is_control'],verifier_protocol=self.options.get('verifier_protocol','legacy'))
            self.ledger.reserve(key,reserved,base)
            try:
                offset={'forecast':0,'holdout_forecast':0,'screen':0,'confirm':10000,'holdout':20000}[stage]
                answer=await self.client.complete(request,cell=c,ordinal=offset+ordinal,fast=True)
                cost=0 if self.settings.mode=='mock' else measured_cost(answer.get('usage'),prices['input_price'],prices['cached_price'],prices['output_price'])
                result={**base,**answer,'status':'ok','ordinal':ordinal,'cost_known':cost is not None,'estimated_cost_usd':cost}
                self.ledger.finish(key,reserved if cost is None else cost,result)
            except ModelError as exc:
                result={**base,'status':'error','error':str(exc),'raw_response':exc.raw,'completed_at':utcnow()}
                # Truncations still report billable usage. Retain the failure,
                # but account for known cost instead of the reservation ceiling.
                cost=None
                if exc.raw:
                    try:
                        body=json.loads(exc.raw);result['usage']=body.get('usage')
                        result['finish_reason']=body.get('choices',[{}])[0].get('finish_reason')
                        cost=measured_cost(result['usage'],prices['input_price'],prices['cached_price'],prices['output_price'])
                    except (ValueError,KeyError,IndexError,TypeError):pass
                result.update(cost_known=cost is not None,estimated_cost_usd=cost)
                self.ledger.finish(key,reserved if cost is None else cost,result)
                if str(exc).startswith(fatal_prefixes):raise SearchStopped(str(exc)) from exc
            return result

    def jobs(self,problems,stage,count):
        return [(p,c,i) for p in problems for c in p['cells'] for i in range(count)]

    async def phase(self,problems,stage,count=1):
        # All tasks settle before any next phase. A small queue bounds memory.
        jobs=self.jobs(problems,stage,count)
        queue=asyncio.Queue()
        for job in jobs:queue.put_nowait(job)
        stopped=[];completed=0
        async def worker():
            nonlocal completed
            while not queue.empty() and not stopped:
                try:job=queue.get_nowait()
                except asyncio.QueueEmpty:return
                try:await self.obtain(*job[:2],stage,job[2])
                except SearchStopped as exc:stopped.append(exc)
                completed+=1
                if completed%100==0:print(f'{stage}: {completed}/{len(jobs)} slots; {self.ledger.totals()}',flush=True)
        await asyncio.gather(*(worker() for _ in range(self.settings.concurrency)))
        if stopped:raise stopped[0]
        print(f'{stage}: completed {len(jobs)} slots (cached slots included)',flush=True)

    def forecast_ready(self,p,stage='forecast'):
        return all((self.ledger.get(self.key(c,stage,0)) or {}).get('status')=='ok' for c in p['cells'])

    def select(self,discovery):
        mode=self.options.get('selection','misses')
        if mode=='none':return []
        ranked=[]
        for p in discovery:
            records=self.record(p,'screen')
            errors=[records[c['id']]['metrics'] for c in p['cells'] if not c['is_control']]
            controls=[records[c['id']]['metrics'] for c in p['cells'] if c['is_control']]
            complete=all(m['valid_trials']==self.options['screen_trials'] for m in errors+controls)
            if not complete:continue
            missed=max(1-m['observed'] for m in errors);false_positive=max((m['observed'] for m in controls),default=0)
            score=max(missed,false_positive) if mode=='both' else missed if false_positive==0 else 0
            if score>0:ranked.append((-score,p['id'],p))
        chosen=[];counts={}
        for _,_,p in sorted(ranked,key=lambda x:x[:2]):
            if counts.get(p['family'],0)>=self.options['max_per_family']:continue
            chosen.append(p);counts[p['family']]=counts.get(p['family'],0)+1
            if len(chosen)>=self.options['top_k']:break
        return chosen

    def report(self,problems,stage):
        rows=[];output=self.root/'exports';output.mkdir(exist_ok=True)
        for p in problems:
            records=self.record(p,stage)
            for c in p['cells']:
                m=records[c['id']]['metrics'];interval=m['wilson_95'] or [None,None]
                rows.append(dict(problem_id=p['id'],family=p['family'],stage=stage,cell_id=c['id'],control=c['is_control'],forecast=m['predicted'],detection_or_false_positive_rate=m['observed'],gap_pp=None if m['calibration_gap'] is None else 100*m['calibration_gap'],rejected=m['rejected_trials'],usable=m['valid_trials'],failed=m['failed_trials'],wilson_lower=interval[0],wilson_upper=interval[1],verifier_protocol=self.options.get('verifier_protocol','legacy'),max_completion_tokens=self.settings.max_completion_tokens))
            expected=self.options['screen_trials'] if stage=='screen' else self.options['confirm_trials']
            complete=all(r['prediction'] and r['prediction']['status']=='ok' and r['metrics']['valid_trials']==expected for r in records.values())
            eid=str(uuid.UUID(digest([self.signature,p['id'],stage])[:32]))
            e=dict(id=eid,problem_id=p['id'],status='complete' if complete else 'partial',phase=stage,config={**self.settings.public(),'trials':expected},created_at=self.created,updated_at=utcnow(),results=records,cell_ids=[c['id'] for c in p['cells']],search_stage=stage,search_signature=self.signature,verifier_protocol=self.options.get('verifier_protocol','legacy'))
            write_json(output/f'{stage}-{p["id"]}.json',dict(experiment=e,problem=p,warning='SIMULATED DATA' if self.settings.mode=='mock' else 'Selected discovery sample; use fresh confirmation and reserved parameters separately.'))
        path=self.root/f'{stage}.csv'
        if rows:
            with path.open('w',newline='',encoding='utf-8-sig') as f:
                writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
        write_json(self.root/'progress.json',dict(at=utcnow(),mode=self.settings.mode,**self.ledger.totals()))
        return rows

    async def run(self):
        discovery=[p for p in self.bank['problems'] if p['split']=='discovery']
        selected=[];holdout=[];stopped=None;status='finished'
        try:
            # A real global forecast barrier: no discovery outcomes exist yet.
            await self.phase(discovery,'forecast')
            ready=[p for p in discovery if self.forecast_ready(p)]
            await self.phase(ready,'screen',self.options['screen_trials'])
            self.report(discovery,'screen')
            shortlist=self.root/'shortlist.json'
            if shortlist.exists():
                frozen=json.loads(shortlist.read_text(encoding='utf-8'));selected=[p for p in discovery if p['id'] in frozen['problem_ids']]
            else:
                selected=self.select(ready)
                criteria={'misses':'Observed screening misses, complete samples, zero screening control rejections.', 'both':'Any observed misclassification, including incorrect rejection of a correct control; complete screening samples.', 'none':'Diagnostic only: no adaptive selection.'}
                write_json(shortlist,dict(frozen_at=utcnow(),criterion=criteria[self.options.get('selection','misses')]+' Forecasts are not used for ranking.',problem_ids=[p['id'] for p in selected]))
            families={p['family'] for p in selected}
            for family in sorted(families):holdout.extend([p for p in self.bank['problems'] if p['family']==family and p['split']=='holdout'][:self.options['holdout_per_family']])
            write_json(self.root/'shortlist-bank.json',dict(version=VERSION,seed=self.bank['seed'],problems=selected+holdout,description='Frozen selected instances and unused parameter holdouts. Selection is not evidence of population prevalence.'))
            if selected:
                await self.phase(holdout,'holdout_forecast')
                # Fresh namespaces; discovery verdicts never enter these counts.
                await self.phase(selected,'confirm',self.options['confirm_trials'])
                await self.phase([p for p in holdout if self.forecast_ready(p,'holdout_forecast')],'holdout',self.options['confirm_trials'])
        except SearchStopped as exc:
            stopped=str(exc);status='paused_at_limit' if isinstance(exc,LimitReached) else 'stopped_on_error'
        finally:
            screen=self.report(discovery,'screen');confirmed=self.report(selected,'confirm');held=self.report(holdout,'holdout')
            blocked=sum(not self.forecast_ready(p) for p in discovery)
            failed=sum(r['failed'] for r in screen+confirmed+held)
            if status=='finished' and (blocked or failed):status='finished_with_unusable_slots'
            summary=dict(mode=self.settings.mode,status=status,reason=stopped,discovery_problems=len(discovery),forecast_blocked_problems=blocked,selected_problems=len(selected),holdout_problems=len(holdout),screen_rows=len(screen),screen_usable_trials=sum(r['usable'] for r in screen),screen_failed_trials=sum(r['failed'] for r in screen),confirmation_rows=len(confirmed),holdout_rows=len(held),**self.ledger.totals(),interpretation='No automatic finding of a blind spot. Review exact claims, failure rates and fresh confirmation; report holdout results separately. MOCK values are only a software test.' if self.settings.mode=='mock' else 'Discovery is adaptive. Confirmation estimates only the frozen selected instances. Holdouts test new parameters within selected families. No population prevalence claim follows.')
            write_json(self.root/'summary.json',summary)
            await self.client.close()
        print(json.dumps(summary,indent=2),flush=True)
        return summary


def import_results(root,settings,catalog_bank=None):
    bank=catalog_bank or load_bank(root/'shortlist-bank.json');store=Store(settings.db_path)
    # Creating saved experiments uses no client/network requests.
    runner=Runner(settings,bank,store,None);count=0
    for path in sorted((root/'exports').glob('*.json')):
        payload=json.loads(path.read_text(encoding='utf-8'));source=payload['experiment']
        if source.get('search_stage') not in {'confirm','holdout'}:continue
        if source['config']['mode']!=settings.mode or source['config']['model']!=settings.model:raise ValueError('Import mode/model must match the active configuration.')
        e=runner.create(source['problem_id'],trials=source['config']['trials'],fresh=True)
        # Stable identity allows repeat import without creating duplicate history.
        temporary_id=e['id'];e.update(source);e['problem_snapshot']=payload['problem'];e['signature']=digest(['search-import',source['id'],bank['hash'],settings.namespace])
        e['cache_identity']['config']=source['config']
        e.update(batch='search-'+source['search_stage'],completed_calls=sum(len(r['trials'])+bool(r['prediction']) for r in source['results'].values()),total_calls=len(e['cell_ids'])*(e['config']['trials']+int(source.get('forecasts_expected',True))),cached_calls=0,error=None)
        with store.connection() as db:db.execute('DELETE FROM experiments WHERE id=?',(temporary_id,))
        store.save(e);count+=1
    if catalog_bank is not None:print(f'Imported {count} fixed maps into the combined study catalogue.')
    else:print(f'Imported {count} confirmation/holdout maps. Set BLINDSPOT_BANK={root / "shortlist-bank.json"} and restart the app.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    build=commands.add_parser('build',help='Construct exact-labelled examples locally; no API calls')
    build.add_argument('--directory',type=Path,default=Path('var/search'));build.add_argument('--per-family',type=int,default=40);build.add_argument('--seed',type=int,default=20261029)
    run=commands.add_parser('run',help='Run/resume discovery then confirmation with explicit limits')
    run.add_argument('--directory',type=Path,default=Path('var/search'));run.add_argument('--mock',action='store_true')
    run.add_argument('--budget-usd',type=float,default=10);run.add_argument('--max-calls',type=int,default=6500);run.add_argument('--rpm',type=int,default=100)
    run.add_argument('--screen-trials',type=int,default=2);run.add_argument('--confirm-trials',type=int,default=20);run.add_argument('--top-k',type=int,default=20);run.add_argument('--max-per-family',type=int,default=4);run.add_argument('--holdout-per-family',type=int,default=2)
    run.add_argument('--input-price',type=float);run.add_argument('--cached-price',type=float);run.add_argument('--output-price',type=float)
    run.add_argument('--verifier-protocol',choices=['legacy','truth'],default='legacy')
    run.add_argument('--selection',choices=['misses','both','none'],default='misses')
    run.add_argument('--show-budget',action='store_true',help='Include the exact verifier instruction and token cap in the prospective forecast')
    imp=commands.add_parser('import-results',help='Import saved confirmation maps into the local app; no API calls');imp.add_argument('--directory',type=Path,default=Path('var/search'))
    args=parser.parse_args();root=args.directory.resolve();root.mkdir(parents=True,exist_ok=True)
    if args.command=='build':
        if (root/'bank.json').exists():raise SystemExit('bank.json already exists. Use a new directory to build another bank.')
        print('Constructing exact examples; this can take a few minutes.',flush=True)
        bank=build_bank(args.per_family,args.seed);write_json(root/'bank.json',bank)
        print(f'Built {len(bank["problems"])} problems / {3*len(bank["problems"])} cells, including reserved holdouts. No API calls.')
        return
    settings=load_settings()
    if args.command=='import-results':return import_results(root,settings)
    if not args.mock and settings.mode!='live':raise SystemExit('No live API configuration. Set META_API_KEY and BLINDSPOT_MOCK=false, or explicitly pass --mock in a separate directory.')
    if args.mock:settings=replace(settings,force_mock=True)
    if any(x is None for x in [args.input_price,args.cached_price,args.output_price]):
        if settings.model!='muse-spark-1.3-contributor' and not args.mock:raise SystemExit('Default pricing is only for muse-spark-1.3-contributor. Set that model or supply all three per-million-token prices.')
        args.input_price=.10 if args.input_price is None else args.input_price;args.cached_price=.002 if args.cached_price is None else args.cached_price;args.output_price=.20 if args.output_price is None else args.output_price
    options={k:v for k,v in vars(args).items() if k not in {'command','directory','mock'}}
    if args.budget_usd<=0 or args.max_calls<1 or not 1<=args.rpm<=150 or any(options[k]<1 for k in ['screen_trials','confirm_trials','top_k','max_per_family','holdout_per_family']) or any(options[k]<0 for k in ['input_price','cached_price','output_price']):raise SystemExit('Invalid limits, prices or trial counts.')
    asyncio.run(Search(root,load_bank(root/'bank.json'),settings,options).run())


if __name__=='__main__':main()
