"""One bounded overnight run: protocol diagnosis followed by a broader search.

Example: python -m blindspot.overnight --source var/search --directory var/overnight
No API key is written to the output. Existing source data are read, never edited.
"""
import argparse
import asyncio
import copy
import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import sqlite3
from zipfile import ZipFile, ZIP_DEFLATED
import sympy as sp
from .config import load_settings
from .maths import parse, representation, validate_pair
from .search import Ledger, Search, write_json
from .semantic_bank import build_bank, load_bank

VERSION='overnight-1.0'
DIAGNOSTIC_FAMILIES=['ivp_domain','near_degeneracy','radial_measure','robin_boundary','viscoelastic','gram_metric']


def diagnostic_bank(source,per_family=8):
    chosen=[];rng=random.Random('paired-diagnostic-20261030')
    for family in DIAGNOSTIC_FAMILIES:
        candidates=[p for p in source['problems'] if p['family']==family and p['split']=='discovery']
        rng.shuffle(candidates)
        for original in candidates[:per_family]:
            p=copy.deepcopy(original);p['split']='discovery';chosen.append(p)
    if not chosen:raise ValueError('No matching diagnostic families in the source bank.')
    return dict(version=VERSION,seed=20261030,problems=chosen,description='Same fixed cases in four prompt/token-cap conditions. Families were chosen after the first sweep; do not treat them as a random physics sample.')


def add_nearby_errors(bank):
    """Add one exact but nearby wrong value to each original problem.

    The original false claim can be easy to dismiss qualitatively (e.g. a zero
    gap when no symmetry was established). A nearby nonzero wrong gap asks a
    different question: can the verifier actually check the value? This is a
    numerical perturbation, not a claim about a new physical error mechanism.
    """
    for p in bank['problems']:
        original=p['steps'][-1];reference=parse(original['expr'],p)
        h=int(hashlib.sha256(p['id'].encode()).hexdigest()[:8],16)
        denominator=[19,49,99][h%3]
        candidate=reference*(1-sp.Rational(1,denominator))
        proof=validate_pair(reference,candidate,p)
        if not proof:raise ValueError(f'Cannot validate nearby candidate for {p["id"]}')
        if any(sp.simplify(parse(c['candidate']['expr'],p)-candidate)==0 for c in p['cells']):
            candidate=reference*(1-sp.Rational(1,denominator+2));proof=validate_pair(reference,candidate,p)
        if not proof:raise ValueError('Nearby error is not provably distinct.')
        note='Move the scalar result slightly towards zero while keeping the same dimensions and sign or complex phase. All claimed quantities are exact, so this is not a rounding tolerance.'
        p['cells'].append(dict(id=f'{p["id"]}:{original["index"]}:nearby_value',problem_id=p['id'],step=original['index'],type='nearby_value',type_label='Nearby wrong value',is_control=False,
                              original=copy.deepcopy(original),candidate={**copy.deepcopy(original),**representation(candidate)},
                              mutation=dict(ast_path=[],before=str(reference),after=str(candidate),before_latex=sp.latex(reference),after_latex=sp.latex(candidate),description=note,rule='nearby_value'),
                              plan_description=note,validation=proof))
        p['cell_count']=len(p['cells'])
    bank['description']='Fresh parameter choices with semantic errors, nearby numerical errors and two correct controls. Excludes every question in the source bank.'
    return bank


def ensure_bank(path,data):
    if path.exists():
        existing=json.loads(path.read_text(encoding='utf-8'))
        if existing!=data:raise ValueError(f'Bank changed at {path}; use a new overnight directory.')
    else:write_json(path,data)


def make_review(root):
    """Compact comparison plus raw provenance in one attachment for review."""
    groups={};phase_status=[]
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        if (directory/'summary.json').exists():
            summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
            phase_status.append(dict(condition=directory.name,status=summary['status'],reason=summary.get('reason'),selected=summary['selected_problems']))
        for path in directory.glob('*.csv'):
            with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            for r in rows:
                key=(directory.name,r['stage'],r['family'],r['control'])
                g=groups.setdefault(key,dict(condition=key[0],stage=key[1],family=key[2],control=key[3],cells=0,usable=0,rejected=0,failed=0,forecast_sum=0,forecast_count=0))
                g['cells']+=1
                for k in ['usable','rejected','failed']:g[k]+=int(r[k])
                if r['forecast']!='':g['forecast_sum']+=float(r['forecast']);g['forecast_count']+=1
    rows=[]
    for g in groups.values():
        n=g.pop('forecast_count');total=g.pop('forecast_sum');g['mean_forecast']=total/n if n else None
        g['rejection_rate']=g['rejected']/g['usable'] if g['usable'] else None;rows.append(g)
    if rows:
        with (root/'comparison.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    db=sqlite3.connect(root/'search.sqlite3')
    statuses={};failures={};call_count,cost=db.execute('SELECT COUNT(*),COALESCE(SUM(charged),0) FROM search_calls').fetchone()
    for (raw,) in db.execute('SELECT record FROM search_calls'):
        r=json.loads(raw);statuses[r['status']]=statuses.get(r['status'],0)+1
        if r['status']!='ok':
            label=r.get('finish_reason') or r.get('error') or 'pending / unknown outcome';failures[label]=failures.get(label,0)+1
    db.close()
    overview=dict(version=VERSION,phase_status=phase_status,calls=call_count,accounted_usd=cost,status_counts=statuses,unusable_reasons=failures,
                  interpretation='Compare diagnostic conditions only on their matched cases. Report discovery, selected-instance confirmation and unused-parameter holdout separately. Rejection is detection for errors and a false positive for controls. Rows exclude unusable verdicts from rates.')
    write_json(root/'overview.json',overview)
    with ZipFile(root/'review.zip','w',ZIP_DEFLATED) as z:
        allowed={'plan.json','search.sqlite3','overview.json','comparison.csv','bank.json','manifest.json','summary.json','progress.json','shortlist.json','shortlist-bank.json','screen.csv','confirm.csv','holdout.csv'}
        for path in sorted(root.rglob('*')):
            if not path.is_file() or path.name not in allowed:continue
            # Full ledger plus bank/manifest/CSV summaries suffice; per-case JSON
            # exports duplicate all requests and are already available locally.
            if 'exports' in path.relative_to(root).parts:continue
            z.write(path,path.relative_to(root).as_posix())
    return overview


async def execute(source,root,settings,args,client_factory=None):
    root.mkdir(parents=True,exist_ok=True)
    source_bank=load_bank(source/'bank.json')
    plan=dict(version=VERSION,source_hash=source_bank['hash'],seed=args.seed,per_family=args.per_family,
              diagnostic_per_family=args.diagnostic_per_family,model=settings.model,temperature=settings.temperature,reasoning_effort=settings.reasoning_effort,
              conditions=[['legacy',4096],['truth',16384],['truth',4096],['legacy',16384]],screen_trials=2,confirm_trials=args.confirm_trials,top_k=args.top_k)
    ensure_bank(root/'plan.json',plan)
    ledger=Ledger(root/'search.sqlite3',args.budget_usd,args.max_calls)
    diagnostic=diagnostic_bank(source_bank,args.diagnostic_per_family)
    wide_directory=root/'wide';wide_directory.mkdir(exist_ok=True);wide_path=wide_directory/'bank.json'
    if not wide_path.exists():
        print('Preparing fresh parameter cases and exact nearby-value errors before any API calls.',flush=True)
        fresh=build_bank(args.per_family,args.seed,{p['question'] for p in source_bank['problems']})
        write_json(wide_path,add_nearby_errors(fresh))
    wide_bank=load_bank(wide_path)
    options=dict(budget_usd=args.budget_usd,max_calls=args.max_calls,rpm=args.rpm,screen_trials=2,confirm_trials=args.confirm_trials,top_k=args.top_k,max_per_family=4,holdout_per_family=2,
                 input_price=.10,cached_price=.002,output_price=.20,selection='none',show_budget=True)
    stopped=False
    try:
        for protocol,cap in plan['conditions']:
            directory=root/f'diagnostic-{protocol}-{cap}';directory.mkdir(exist_ok=True)
            ensure_bank(directory/'bank.json',diagnostic)
            condition=replace(settings,max_completion_tokens=cap)
            search=Search(directory,load_bank(directory/'bank.json'),condition,{**options,'verifier_protocol':protocol},
                          client=client_factory(condition) if client_factory else None,ledger=ledger)
            print(f'\nStarting {directory.name}; shared limits ${args.budget_usd} / {args.max_calls} requests.',flush=True)
            result=await search.run();make_review(root)
            if result['status'] in {'paused_at_limit','stopped_on_error'}:stopped=True;break
        if not stopped:
            condition=replace(settings,max_completion_tokens=16384)
            search=Search(wide_directory,wide_bank,condition,{**options,'verifier_protocol':'truth','selection':'both'},
                          client=client_factory(condition) if client_factory else None,ledger=ledger)
            print('\nStarting wide search, including follow-up of false positives.',flush=True)
            await search.run()
    finally:
        overview=make_review(root)
        print(json.dumps(overview,indent=2),flush=True)
        print(f'Review attachment: {root / "review.zip"}',flush=True)
    return overview


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('var/search'));parser.add_argument('--directory',type=Path,default=Path('var/overnight'))
    parser.add_argument('--budget-usd',type=float,default=10);parser.add_argument('--max-calls',type=int,default=10000)
    parser.add_argument('--rpm',type=int,default=100);parser.add_argument('--concurrency',type=int,default=8)
    parser.add_argument('--per-family',type=int,default=40);parser.add_argument('--seed',type=int,default=20261030)
    parser.add_argument('--diagnostic-per-family',type=int,default=8);parser.add_argument('--confirm-trials',type=int,default=20);parser.add_argument('--top-k',type=int,default=16)
    parser.add_argument('--mock',action='store_true')
    args=parser.parse_args();source=args.source.resolve();root=args.directory.resolve()
    if source==root or source in root.parents or root in source.parents:raise SystemExit('Use a separate sibling output directory, not the original search directory or its parent.')
    if not 1<=args.concurrency<=8 or not 1<=args.rpm<=150 or args.budget_usd<=0 or args.max_calls<1 or not 1<=args.diagnostic_per_family<=32 or not 2<=args.per_family<=50 or not 1<=args.confirm_trials<=100 or not 1<=args.top_k<=100:raise SystemExit('Invalid overnight settings. Use --help; per-family supports 2–50 fresh cases.')
    settings=load_settings()
    if args.mock:settings=replace(settings,force_mock=True)
    elif settings.mode!='live':raise SystemExit('Set META_API_KEY and BLINDSPOT_MOCK=false, or use --mock in a separate directory.')
    if not args.mock and settings.model!='muse-spark-1.3-contributor':raise SystemExit('This budgeted recipe uses Contributor pricing. Set META_MODEL=muse-spark-1.3-contributor.')
    settings=replace(settings,concurrency=args.concurrency,timeout=max(360,settings.timeout),retries=0)
    asyncio.run(execute(source,root,settings,args))


if __name__=='__main__':main()
