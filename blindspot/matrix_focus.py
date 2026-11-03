"""Fixed, paired follow-up of exact spectral-gap verification.

python -m blindspot.matrix_focus --directory var/matrix-focus --budget-usd 10
Builds and validates the complete design before sending any model requests.
"""
import argparse
import asyncio
import copy
import csv
from dataclasses import replace
import json
from pathlib import Path
import random
from zipfile import ZipFile, ZIP_DEFLATED
import sympy as sp
from .config import load_settings
from .maths import representation, validate_pair
from .overnight import ensure_bank
from .search import Search, SearchStopped, LimitReached, write_json, import_results
from .semantic_bank import make_case, load_bank

VERSION='matrix-focus-1.0'
FORMS=['diagonal','dense']
WORDINGS=['gap_only','gap_and_degeneracy']


def excluded_spectra(paths):
    """Exclude spectra, not merely matrix strings, from earlier supplied banks."""
    excluded=set();sources=[]
    for path in paths:
        path=Path(path)
        if not path.exists():continue
        data=json.loads(path.read_text(encoding='utf-8'))
        count=0
        for p in data['problems']:
            if p.get('family')!='near_degeneracy':continue
            spectrum=tuple(map(str,map(sp.sympify,p['oracle']['spectrum'])))
            excluded.add(spectrum);count+=1
        sources.append(dict(path=str(path),matrix_cases=count))
    return excluded,sources


def variants(gap):
    yield 'zero_gap','Zero gap',sp.Integer(0),False,'Replace the exact positive middle gap by zero (claim exact degeneracy).',None
    for percent in [1,5,20]:
        for sign,name in [(-1,'lower'),(1,'higher')]:
            shift=sp.Rational(sign*percent,100)
            yield f'{name}_{percent}',f'{percent}% {name}',gap*(1+shift),False,f'Replace the exact middle gap by a value exactly {percent}% {name}. This is an exact claim, not rounding.',str(shift)
    yield 'original_control','Correct value',gap,True,'Keep the exact correct middle gap unchanged.','0'
    equivalent=sp.Add(gap/3,2*gap/3,evaluate=False)
    yield 'equivalent','Equivalent rewrite',equivalent,True,'Write the exact correct gap as one third plus two thirds of itself; preserve its exact value.','0'


def build_bank(spectra=12,seed=20261031,excluded=None):
    if not 1<=spectra<=100:raise ValueError('Use 1–100 underlying spectra.')
    rng=random.Random(f'{VERSION}:{seed}');seen=set(excluded or []);problems=[];accepted=0;attempts=0
    while accepted<spectra:
        attempts+=1
        if attempts>100*spectra:raise ValueError('Could not construct enough new spectra.')
        base=make_case('near_degeneracy',accepted,rng)
        values=tuple(map(str,map(sp.sympify,base['oracle']['spectrum'])))
        if values in seen:continue
        seen.add(values)
        H=sp.Matrix(base['oracle']['H']);D=sp.diag(*map(sp.sympify,values))
        polynomial=H.charpoly();roots=sp.polys.polytools.ground_roots(polynomial.as_expr(),polynomial.gen)
        exact=sorted([r for r,n in roots.items() for _ in range(n)])
        if len(exact)!=4 or tuple(map(str,exact))!=values:raise ValueError('Independent characteristic-polynomial verification failed.')
        gap=exact[2]-exact[1]
        if gap!=sp.sympify(base['steps'][-1]['expr']):raise ValueError('Incorrect spectral-gap reference.')
        base_id=f'spectrum-{accepted+1:03d}'
        for form in FORMS:
            matrix=D if form=='diagonal' else H
            for wording in WORDINGS:
                p=copy.deepcopy(base);pid=f'{base_id}-{form}-{wording}'
                question=f'The exact real symmetric matrix H={sp.sstr(matrix)} describes four coupled modes. In ascending order its eigenvalues are lambda_0 through lambda_3. Compute the exact value of lambda_2-lambda_1.'
                if wording=='gap_and_degeneracy':question+=' In particular, determine whether these two middle modes are exactly degenerate.'
                p.update(id=pid,title=f'Matrix {accepted+1:02d} · {form} · '+('gap only' if wording=='gap_only' else 'gap + degeneracy'),
                         topic='Exact middle spectral gap',question=question,split='discovery',verifier_protocol='truth',
                         assumptions='Use the exact rational entries. The candidate asserts an exact equality; agreement within a numerical tolerance is insufficient. No additional symmetry is assumed.',
                         focus=dict(base_id=base_id,matrix_form=form,question_wording=wording),cells=[])
                p['oracle']['H']=[[str(v) for v in row] for row in matrix.tolist()]
                p['oracle']['method']='Exact roots of the characteristic polynomial; paired isospectral presentations'
                p['steps'][-1]['text']='The exact middle spectral gap is as follows.'
                target=p['steps'][-1]
                for kind,label,value,control,note,relative in variants(gap):
                    proof=validate_pair(gap,value,p,control)
                    if not proof:raise ValueError('Invalid exact matrix candidate.')
                    p['cells'].append(dict(id=f'{pid}:3:{kind}',problem_id=pid,step=3,type=kind,type_label=label,is_control=control,
                        original=copy.deepcopy(target),candidate={**copy.deepcopy(target),**representation(value)},
                        relative_error=relative,plan_description=note,validation=proof,
                        mutation=dict(ast_path=[],before=str(gap),after=str(sp.simplify(value)),before_latex=sp.latex(gap),after_latex=sp.latex(value),description=note,rule=kind)))
                p['cell_count']=len(p['cells']);problems.append(p)
        accepted+=1
    return dict(version=VERSION,seed=seed,problems=problems,
                description='Fixed paired matrix evaluation. All cases are evaluated; no outcome-based selection. Four contexts per underlying spectrum, nine candidates per context.')


class Focus(Search):
    def jobs(self,problems,stage,count):
        jobs=super().jobs(problems,stage,count)
        random.Random(f'{VERSION}:{self.bank["seed"]}:{stage}').shuffle(jobs)
        return jobs

    def report(self,problems,stage):
        rows=super().report(problems,stage)
        for p in problems:
            path=self.root/'exports'/f'{stage}-{p["id"]}.json'
            payload=json.loads(path.read_text(encoding='utf-8'))
            payload['experiment'].update(focus_study=VERSION,focus_context=p['focus'])
            payload['warning']='SIMULATED DATA' if self.settings.mode=='mock' else 'Fixed matrix evaluation; all prespecified cases are included. Repeats and paired presentations are not independent problems.'
            write_json(path,payload)
        return rows


def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def analyse(search,status,reason=None):
    """Export all outcomes and paired differences without selecting winners."""
    root=search.root;rows=[];groups={};paired={}
    for p in search.bank['problems']:
        records=search.record(p,'confirm')
        for c in p['cells']:
            record=records[c['id']];m=record['metrics'];forecast=m['predicted'];observed=m['observed'];n=m['valid_trials']
            expected=search.options['confirm_trials'];missing=expected-n-m['failed_trials']
            row=dict(problem_id=p['id'],**p['focus'],cell_id=c['id'],mutation=c['type'],control=c['is_control'],relative_error=c['relative_error'],
                     forecast=forecast,rejected=m['rejected_trials'],usable=n,failed=m['failed_trials'],unattempted=missing,
                     rejection_rate=observed,gap_pp=None if m['calibration_gap'] is None else 100*m['calibration_gap'],
                     wilson_lower=(m['wilson_95'] or [None,None])[0],wilson_upper=(m['wilson_95'] or [None,None])[1])
            rows.append(row);paired[(p['focus']['base_id'],p['focus']['matrix_form'],p['focus']['question_wording'],c['type'])]=row
            key=(p['focus']['matrix_form'],p['focus']['question_wording'],c['type'])
            groups.setdefault(key,[]).append(row)
    write_csv(root/'cells.csv',rows)
    summary_rows=[]
    for (form,wording,mutation),g in groups.items():
        usable=sum(r['usable'] for r in g);rejected=sum(r['rejected'] for r in g)
        forecasts=[r['forecast'] for r in g if r['forecast'] is not None]
        measured=[r for r in g if r['usable']]
        # Matched rate/forecast averages give each underlying spectrum one vote.
        matched=[r for r in measured if r['forecast'] is not None]
        fmean=sum(r['forecast'] for r in matched)/len(matched) if matched else None
        rmean=sum(r['rejection_rate'] for r in matched)/len(matched) if matched else None
        summary_rows.append(dict(matrix_form=form,question_wording=wording,mutation=mutation,control=g[0]['control'],
            spectra=len(g),spectra_with_verdicts=len(measured),fully_sampled_spectra=sum(r['usable']==search.options['confirm_trials'] for r in g),
            rejected=rejected,usable=usable,failed=sum(r['failed'] for r in g),unattempted=sum(r['unattempted'] for r in g),
            pooled_rejection_rate=rejected/usable if usable else None,
            mean_forecast=sum(forecasts)/len(forecasts) if forecasts else None,
            matched_spectra=len(matched),matched_mean_forecast=fmean,matched_mean_rejection_rate=rmean,
            matched_gap_pp=100*(fmean-rmean) if matched else None))
    write_csv(root/'comparison.csv',summary_rows)
    paired_rows=[]
    bases=sorted({p['focus']['base_id'] for p in search.bank['problems']})
    mutations=[c['type'] for c in search.bank['problems'][0]['cells']]
    for base in bases:
        for mutation in mutations:
            for contrast in ['representation','wording']:
                for fixed in WORDINGS if contrast=='representation' else FORMS:
                    left=(base,'diagonal',fixed,mutation) if contrast=='representation' else (base,fixed,'gap_only',mutation)
                    right=(base,'dense',fixed,mutation) if contrast=='representation' else (base,fixed,'gap_and_degeneracy',mutation)
                    a,b=paired[left],paired[right]
                    delta=100*(b['rejection_rate']-a['rejection_rate']) if a['usable'] and b['usable'] else None
                    paired_rows.append(dict(base_id=base,mutation=mutation,contrast=contrast,fixed_condition=fixed,
                        left=('diagonal' if contrast=='representation' else 'gap_only'),right=('dense' if contrast=='representation' else 'gap_and_degeneracy'),
                        left_rejection_rate=a['rejection_rate'],right_rejection_rate=b['rejection_rate'],right_minus_left_pp=delta,
                        left_usable=a['usable'],right_usable=b['usable']))
    write_csv(root/'paired.csv',paired_rows)
    statuses={};failures={}
    with search.ledger.db() as db:
        for (raw,) in db.execute('SELECT record FROM search_calls'):
            r=json.loads(raw);statuses[r['status']]=statuses.get(r['status'],0)+1
            if r['status']!='ok':
                label=r.get('finish_reason') or r.get('error') or 'pending / unknown';failures[label]=failures.get(label,0)+1
    blocked=sum(not search.forecast_ready(p) for p in search.bank['problems'])
    if status=='finished' and (blocked or any(r['failed'] or r['unattempted'] for r in rows)):status='finished_with_unusable_slots'
    overview=dict(version=VERSION,mode=search.settings.mode,status=status,reason=reason,
        underlying_spectra=len(bases),contexts=len(search.bank['problems']),cells=len(rows),trials_per_cell=search.options['confirm_trials'],
        planned_calls=len(rows)*(search.options['confirm_trials']+1),forecast_blocked_contexts=blocked,
        usable_verdicts=sum(r['usable'] for r in rows),failed_verdicts=sum(r['failed'] for r in rows),unattempted_verdicts=sum(r['unattempted'] for r in rows),
        status_counts=statuses,unusable_reasons=failures,**search.ledger.totals(),
        interpretation='Fixed evaluation of new spectra after adaptive family discovery. Compare paired contexts within each spectrum; repeats are not independent problems. Rate denominators exclude unusable outputs. No privileged self-knowledge claim follows.')
    write_json(root/'summary.json',overview)
    with ZipFile(root/'review.zip','w',ZIP_DEFLATED) as z:
        for name in ['plan.json','bank.json','manifest.json','summary.json','comparison.csv','cells.csv','paired.csv','confirm.csv','search.sqlite3']:
            path=root/name
            if path.exists():z.write(path,name)
    return overview


async def execute(root,settings,args,client=None):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    bank_path=root/'bank.json';plan_path=root/'plan.json'
    if bank_path.exists():
        bank=load_bank(bank_path)
        if bank.get('version')!=VERSION or bank['seed']!=args.seed or len(bank['problems'])!=4*args.spectra:
            raise ValueError('Existing bank differs from this fixed design. Use a new directory.')
        exclusions=[]
    else:
        excluded,exclusions=excluded_spectra(args.exclude_bank)
        write_json(bank_path,build_bank(args.spectra,args.seed,excluded));bank=load_bank(bank_path)
    plan=dict(version=VERSION,seed=args.seed,underlying_spectra=args.spectra,matrix_forms=FORMS,question_wordings=WORDINGS,
        mutations=[c['type'] for c in bank['problems'][0]['cells']],trials_per_cell=args.trials,model=settings.model,
        temperature=settings.temperature,reasoning_effort=settings.reasoning_effort,max_completion_tokens=settings.max_completion_tokens,
        verifier_protocol='truth',forecasts='All saved before any verdict; direction and percentage specified, candidate expression not displayed.',
        order='Deterministically shuffled requests within forecast and verdict phases.',selection='None: evaluate every prespecified context and cell.',
        planned_calls=len(bank['problems'])*9*(args.trials+1),excluded_sources=exclusions)
    if plan_path.exists():plan['excluded_sources']=json.loads(plan_path.read_text(encoding='utf-8'))['excluded_sources']
    ensure_bank(plan_path,plan)
    # Alias used only by the existing offline importer: this includes ALL cases.
    ensure_bank(root/'shortlist-bank.json',json.loads(bank_path.read_text(encoding='utf-8')))
    if args.build_only:
        print(json.dumps(plan,indent=2));print('Built and validated. No API calls.');return plan
    options=dict(budget_usd=args.budget_usd,max_calls=args.max_calls,rpm=args.rpm,screen_trials=args.trials,confirm_trials=args.trials,
        top_k=1,max_per_family=1,holdout_per_family=1,input_price=.10,cached_price=.002,output_price=.20,
        selection='none',show_budget=True,verifier_protocol='truth')
    search=Focus(root,bank,settings,options,client)
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    manifest.update(warning='MOCK: simulated outcomes' if settings.mode=='mock' else 'Fixed paired matrix evaluation. No outcome-based selection.',study=VERSION)
    write_json(root/'manifest.json',manifest)
    status='finished';reason=None
    try:
        await search.phase(bank['problems'],'forecast')
        ready=[p for p in bank['problems'] if search.forecast_ready(p)]
        await search.phase(ready,'confirm',args.trials)
    except SearchStopped as exc:
        status='paused_at_limit' if isinstance(exc,LimitReached) else 'stopped_on_error';reason=str(exc)
    except (KeyboardInterrupt,asyncio.CancelledError):
        status='interrupted';reason='Interrupted; pending calls may have unknown outcomes.';raise
    except Exception as exc:
        status='stopped_on_error';reason=f'{type(exc).__name__}: {exc}';raise
    finally:
        search.report(bank['problems'],'confirm')
        overview=analyse(search,status,reason)
        await search.client.close()
        print(json.dumps(overview,indent=2));print(f'Review attachment: {root / "review.zip"}')
    return overview


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path('var/matrix-focus'))
    parser.add_argument('--spectra',type=int,default=12);parser.add_argument('--seed',type=int,default=20261031)
    parser.add_argument('--trials',type=int,default=20);parser.add_argument('--budget-usd',type=float,default=10)
    parser.add_argument('--max-calls',type=int,default=10000);parser.add_argument('--rpm',type=int,default=100)
    parser.add_argument('--concurrency',type=int,default=8);parser.add_argument('--mock',action='store_true')
    parser.add_argument('--build-only',action='store_true',help='Freeze and validate the design without model calls')
    parser.add_argument('--import-results',action='store_true',help='Import the fixed saved maps into the app without model calls')
    parser.add_argument('--exclude-bank',type=Path,action='append',help='Exclude spectra from a previous bank; repeatable. Defaults to the two previous search banks when present.')
    args=parser.parse_args()
    if not 1<=args.spectra<=100 or not 1<=args.trials<=100 or args.budget_usd<=0 or args.max_calls<1 or not 1<=args.rpm<=150 or not 1<=args.concurrency<=8:
        parser.error('Invalid experiment size, trials, concurrency or limits.')
    if args.build_only and args.import_results:parser.error('Choose build-only or import-results.')
    args.exclude_bank=args.exclude_bank if args.exclude_bank is not None else [Path('var/search/bank.json'),Path('var/overnight/wide/bank.json')]
    settings=load_settings()
    if args.mock:settings=replace(settings,force_mock=True)
    if args.import_results:return import_results(args.directory.resolve(),settings)
    if not args.mock and not args.build_only:
        if settings.mode!='live':parser.error('Set META_API_KEY and BLINDSPOT_MOCK=false, or use --mock in another directory.')
        if settings.model!='muse-spark-1.3-contributor':parser.error('This budget recipe uses Contributor pricing. Set META_MODEL=muse-spark-1.3-contributor.')
    settings=replace(settings,max_completion_tokens=16384,timeout=max(360,settings.timeout),retries=0,concurrency=args.concurrency)
    asyncio.run(execute(args.directory.resolve(),settings,args))


if __name__=='__main__':main()
