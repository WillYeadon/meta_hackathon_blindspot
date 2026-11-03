"""Complete the EXISTING high-reasoning panel with 32k/64k token ceilings.

No new spectra, claims, models, effort settings or forecasts. Existing calls
and manifests are preserved. Both pilots precede joint cost-only planning.
"""
import argparse
import asyncio
import copy
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from contextlib import closing
from .config import ROOT,load_settings
from .final_study import prepare_bank,create_search,selected_pilot,estimate,review_bundle,ProgrammeLedger
from .overnight import ensure_bank
from .search import write_json,SearchStopped,LimitReached
from .meta import utcnow


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def snapshot(root):
    with closing(sqlite3.connect(root/'search.sqlite3')) as db:
        if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Existing ledger is damaged; no calls launched.')
        n,cost=db.execute('SELECT COUNT(*),COALESCE(SUM(charged),0) FROM search_calls').fetchone()
        spent={p:c for p,c in db.execute('SELECT p.profile,SUM(c.charged) FROM search_calls c JOIN final_profiles p ON c.key=p.key GROUP BY p.profile')}
    return dict(calls=n,charged_usd=cost,profiles=spent)


def freeze_extension(root,args):
    root=Path(root)
    for name in ['plan.json','panel-continuation.json','bank.json','reference.json','search.sqlite3','execution-context.json']:
        if not (root/name).exists():raise ValueError('Use the existing var/final-study directory containing the completed anchor study and high pilots.')
    path=root/'token-budget-extension.json';old=read(path) if path.exists() else None
    if not all(math.isfinite(v) and v>0 for v in [args.additional_budget,args.credit_remaining]):raise ValueError('Use finite positive dollar limits.')
    if args.additional_budget>args.credit_remaining:raise ValueError('Additional budget exceeds the reported remaining credit.')
    status=read(root/'progress.json')
    bank=read(root/'bank.json')
    if bank!=prepare_bank(read(ROOT/'data/basis-study-bank.json')):raise ValueError('Frozen case bank changed.')
    initial=old['initial_accounting'] if old else snapshot(root)
    profiles=copy.deepcopy(read(root/'panel-continuation.json')['profiles'])
    if old:profiles=old['profiles']
    else:
        profiles=[p for p in profiles if status.get(p['id'],{}).get('status')=='unusable_at_token_cap']
        if not profiles:raise ValueError('No high configuration stopped at its old token ceiling.')
        for p in profiles:
            if (root/p['id']/'selected-protocol.json').exists():raise ValueError('A main protocol already exists; preserve it rather than replacing its token ceiling.')
            p['caps']=[32768,65536]
            p['pilot_additional_guard']=6. if p['id']=='spark_high' else 18.
    proposal=dict(version='token-budget-extension-1.0',created_at=old['created_at'] if old else utcnow(),
        parents={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['plan.json','panel-continuation.json','bank.json']},
        initial_accounting=initial,reported_remaining_credit=args.credit_remaining,initial_additional_budget=args.additional_budget,
        profiles=profiles,previous_status=old['previous_status'] if old else {p['id']:status[p['id']] for p in profiles},
        scope='Finish the current high-reasoning comparison: same twelve spectra, nine claims and two conditions. No low rerun, no max rerun, no new families or forecasts.',
        technical_rule='Same eight predetermined pilot cases. Try 32768, then 65536 only on truncation; stop if more than 25% truncate at 65536 or non-length errors occur.',
        planning_rule='Pilot BOTH configurations before main collection. Choose the largest common repeat count from 5,3,1 fitting combined expected main cost plus one worst-case concurrent reservation window. Accuracy never selects cases or repeats.',
        budget_rule='Expected pilot-usage costs plus explicit reservation headroom, without the former 1.5x per-model projection multiplier. All actual/unknown costs still obey atomic global and per-profile guards. Unused allocations can fund remaining preplanned slots; repeats never increase on resume.',
        software_test_repeat_override=args.mock_trials if args.mock else None)
    if old:
        proposal['initial_additional_budget']=old['initial_additional_budget']
    ensure_bank(path,proposal)
    # Administrative pending states preserve the prior terminal states above.
    for p in profiles:
        if status.get(p['id'],{}).get('status')=='unusable_at_token_cap' and 'token_extension' not in status.get(p['id'],{}):
            status[p['id']]=dict(status='awaiting_extended_pilot',token_extension=True,reason='Authorised 32768/65536 ceiling extension; original 16384 result remains archived.')
    write_json(root/'progress.json',status)
    return proposal,bank


def runner_args(args,plan):
    return argparse.Namespace(total_budget=plan['initial_accounting']['charged_usd']+args.additional_budget,max_calls=args.max_calls,
        rpm=args.rpm,concurrency=args.concurrency,repeat_policy='budget-fit')


def records(search,trials):
    return [search.ledger.get(search.key(c,'confirm',i)) for p in search.bank['problems'] for c in p['cells'] for i in range(trials)]


def choose_joint(estimates,remaining,headroom,choices=(5,3,1)):
    projections=[]
    for n in choices:
        costs={pid:e['expected_usd']*n for pid,e in estimates.items()}
        total=sum(costs.values());projections.append(dict(repeats=n,expected_main_usd=costs,total_expected_usd=total,headroom_usd=headroom,available_usd=remaining))
        if total+headroom<=remaining:return n,projections
    return None,projections


def refresh(root,args):
    from .final_report import analyse_final
    analyse_final(root,plots=not args.no_plots,integrate=not args.mock);review_bundle(root)


async def collect_main(root,bank,settings,args,run,profile,selected,guard,client_factory):
    profile=copy.deepcopy(profile);profile['budget']=guard
    main=create_search(root,bank,settings,run,profile,selected['max_completion_tokens'],selected['trials'],'main',client_factory)
    state='finished';reason=None
    try:
        while True:
            before=main.ledger.totals()
            try:
                await main.phase(main.bank['problems'],'confirm',selected['trials']);break
            except LimitReached as exc:
                after=main.ledger.totals()
                # A settled in-flight reservation can release room. Revisit only
                # the same frozen slots; saved errors/pending calls are never resent.
                if after['calls']>before['calls'] and after['calls']<run.max_calls:continue
                state='paused_at_guard';reason=str(exc);break
            except SearchStopped as exc:state='stopped_on_error';reason=str(exc);break
    finally:await main.client.close()
    rs=records(main,selected['trials']);count=sum(r is not None for r in rs);usable=sum(r is not None and r['status']=='ok' for r in rs)
    if state=='finished' and usable<len(rs):state='finished_with_unusable_slots'
    status=read(root/'progress.json');status[profile['id']]=dict(status=state,reason=reason,recorded=count,usable=usable,planned=len(rs),token_extension=True,**selected)
    write_json(root/'progress.json',status)
    return state


async def execute_extension(root,settings,args,client_factory=None):
    root=Path(root);plan,bank=freeze_extension(root,args);run=runner_args(args,plan)
    if args.build_only:
        print(json.dumps(dict(plan=plan,cumulative_guard_usd=run.total_budget),indent=2));return
    cfg=replace(settings,force_mock=True) if args.mock else settings
    ensure_bank(root/'execution-context.json',dict(mode=cfg.mode,account_namespace=cfg.namespace))
    history=read(root/'guard-history.json') if (root/'guard-history.json').exists() else []
    history.append(dict(started_at=utcnow(),global_budget_usd=run.total_budget,additional_guard_usd=args.additional_budget,
        original_accounting_usd=plan['initial_accounting']['charged_usd'],profile_budgets_usd={},max_calls=run.max_calls,only='token_extension'))
    write_json(root/'guard-history.json',history)
    print(f'Same fixed high-reasoning panel; 32768 then 65536 tokens. Additional guard ${args.additional_budget:.2f}; cumulative ledger guard ${run.total_budget:.6f}.',flush=True)
    ready={};joint_path=root/'token-extension-allocation.json';blocked=False
    try:
        if joint_path.exists():allocation=read(joint_path)
        else:
            for profile in plan['profiles']:
                pid=profile['id'];initial=plan['initial_accounting']['profiles'].get(pid,0)
                profile=copy.deepcopy(profile);profile['budget']=initial+profile['pilot_additional_guard']
                for cap in profile['caps']:
                    pilot=create_search(root,selected_pilot(bank),cfg,run,profile,cap,1,f'pilot-{cap}',client_factory)
                    print(f'Technical pilot: {profile["label"]}, {cap} total completion tokens; same eight cases; cumulative profile pilot guard ${profile["budget"]:.4f}.',flush=True)
                    stopped=None
                    try:await pilot.phase(pilot.bank['problems'],'confirm',1)
                    except SearchStopped as exc:stopped=str(exc)
                    finally:await pilot.client.close()
                    rs=records(pilot,1);lengths=sum(r is not None and r.get('finish_reason')=='length' for r in rs)
                    bad=[r for r in rs if r is not None and r['status']!='ok' and r.get('finish_reason')!='length']
                    status=read(root/'progress.json')
                    if stopped or any(r is None for r in rs):
                        blocked=True
                        status[pid]=dict(status='technical_pilot_stopped',reason=stopped or 'Pilot incomplete.',token_extension=True);write_json(root/'progress.json',status);break
                    if bad:
                        status[pid]=dict(status='technical_pilot_failed',reason=bad[0].get('error','Unusable or uncertain pilot slot.'),token_extension=True);write_json(root/'progress.json',status);break
                    if lengths and cap!=profile['caps'][-1]:continue
                    if lengths>len(rs)/4:
                        status[pid]=dict(status='unusable_at_token_cap',reason='More than 25% truncated at 65536; no further ceiling search.',token_extension=True);write_json(root/'progress.json',status);break
                    projection=estimate(pilot,profile,216)
                    if projection['expected_usd'] is None or (cfg.mode=='live' and projection['known_usage_calls']!=len(rs)):
                        status[pid]=dict(status='technical_pilot_failed',reason='Complete pilot usage is required before projecting costs.',token_extension=True);write_json(root/'progress.json',status);break
                    ready[pid]=dict(profile=profile,cap=cap,truncations=lengths,projection=projection,
                        max_reservation=max(r.get('reserved_usd',0) for r in rs))
                    print(json.dumps(dict(profile=pid,token_cap=cap,one_repeat_projection=projection),indent=2),flush=True)
                    status[pid]=dict(status='extended_pilot_ready',token_extension=True,max_completion_tokens=cap)
                    write_json(root/'progress.json',status);break
            if blocked or not ready:return
            spent=snapshot(root);remaining=run.total_budget-spent['charged_usd']
            headroom=args.concurrency*max(r['max_reservation'] for r in ready.values())
            choices=[args.mock_trials] if args.mock and args.mock_trials else [5,3,1]
            n,projections=choose_joint({k:r['projection'] for k,r in ready.items()},remaining,headroom,choices)
            print(json.dumps(dict(joint_cost_projections=projections,selected_common_repeats=n,additional_cap=args.additional_budget),indent=2),flush=True)
            write_json(root/'token-extension-cost-estimate.json',dict(projections=projections,selected_repeats=n,pilots=ready,
                warning='Small-pilot projection plus concurrent reservation headroom, not a guaranteed bill. Actual shared guards remain enforced.'))
            if n is None:
                status=read(root/'progress.json')
                for pid in ready:status[pid]=dict(status='cost_projection_exceeds_guard',reason='Even one repeat of every fixed claim exceeds the joint available guard.',token_extension=True)
                write_json(root/'progress.json',status);return
            total_expected=sum(r['projection']['expected_usd']*n for r in ready.values())
            production=[]
            for pid,r in ready.items():
                expected=r['projection']['expected_usd']*n
                weight=expected/total_expected if total_expected else 1/len(ready)
                guard=spent['profiles'].get(pid,0)+expected+max(0,remaining-total_expected)*weight
                p=copy.deepcopy(r['profile']);p['budget']=guard
                selected=dict(model=p['model'],reasoning_effort=p['effort'],max_completion_tokens=r['cap'],trials=n,
                    pilot_calls=8,pilot_truncations=r['truncations'],selection_basis='Fixed joint cost-only choice after both available pilots; no accuracy selection.',frozen_at=utcnow())
                production.append(dict(profile=p,selected=selected,initial_guard_usd=guard))
            allocation=dict(version=plan['version'],created_at=utcnow(),production=production,common_repeats=n,initial_cumulative_guard=run.total_budget)
            ensure_bank(joint_path,allocation)
        for item in allocation['production']:
            ensure_bank(root/item['profile']['id']/'selected-protocol.json',item['selected'])
        for i,item in enumerate(allocation['production']):
            profile=item['profile'];pid=profile['id']
            now=snapshot(root)
            guard=item['initial_guard_usd'] if i<len(allocation['production'])-1 else now['profiles'].get(pid,0)+max(0,run.total_budget-now['charged_usd'])
            history[-1]['profile_budgets_usd'][pid]=guard;write_json(root/'guard-history.json',history)
            print(f'Main: {profile["label"]}, {item["selected"]["trials"]} repeats across all 216 fixed cells; cap {item["selected"]["max_completion_tokens"]}; profile guard ${guard:.4f}.',flush=True)
            await collect_main(root,bank,cfg,args,run,profile,item['selected'],guard,client_factory);refresh(root,args)
        # Return unspent allocations to remaining preplanned slots, without new
        # repeats or resending any previously recorded attempt.
        for item in allocation['production']:
            pid=item['profile']['id'];status=read(root/'progress.json').get(pid,{})
            if status.get('status')!='paused_at_guard':continue
            now=snapshot(root);guard=now['profiles'].get(pid,0)+max(0,run.total_budget-now['charged_usd'])
            history[-1]['profile_budgets_usd'][pid]=guard;write_json(root/'guard-history.json',history)
            await collect_main(root,bank,cfg,args,run,item['profile'],item['selected'],guard,client_factory)
    finally:
        refresh(root,args)
        print(f'Review archive: {root/"review.zip"}')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,default=Path('var/final-study'))
    p.add_argument('--credit-remaining',dest='credit_remaining',type=float,required=True)
    p.add_argument('--additional-budget',type=float,default=110.)
    p.add_argument('--max-calls',type=int,default=6000);p.add_argument('--rpm',type=int,default=100);p.add_argument('--concurrency',type=int,default=8)
    p.add_argument('--build-only',action='store_true');p.add_argument('--no-plots',action='store_true');p.add_argument('--mock',action='store_true')
    p.add_argument('--mock-trials',type=int,choices=[1,2])
    args=p.parse_args()
    if args.mock_trials and not args.mock:p.error('--mock-trials requires --mock.')
    if not 1<=args.concurrency<=8 or not 1<=args.rpm<=150 or args.max_calls<1:p.error('Use 1–8 concurrent calls, 1–150 RPM and a positive call guard.')
    settings=load_settings()
    if not args.build_only and not args.mock and settings.mode!='live':p.error('Use your existing Windows META_API_KEY with BLINDSPOT_MOCK=false.')
    if not args.no_plots:
        try:import matplotlib
        except ImportError:p.error('Install requirements-analysis.txt or use --no-plots.')
    asyncio.run(execute_extension(args.directory.resolve(),settings,args))


if __name__=='__main__':main()
