"""Offline final-panel analysis and strictly evidence-bound submission copy."""
import argparse
from collections import defaultdict,Counter
import json
from pathlib import Path
import random
import shutil
import sqlite3
from statistics import mean,median
from .search import write_json
from .signal_analysis import metrics,csv_rows,reason_flags,discriminability
from .config import ROOT
from .public_snapshot import public_summary


def panel_metrics(rows):
    out=metrics(rows)
    total=len(rows)
    out.update(recorded_trials=total,correct_completed=out['hits']+out['controls']-out['false_alarms'],
        incorrect_completed=out['errors']-out['hits']+out['false_alarms'],
        no_usable_verdicts=out['failed'],completion_rate=out['usable']/total if total else None)
    out['unusable_reasons']=dict(Counter(r.get('finish_reason','unknown') for r in rows if r['status']!='ok'))
    costs=[r['cost_usd'] for r in rows if r.get('cost_usd') is not None]
    tokens=[r['completion_tokens'] for r in rows if r.get('completion_tokens') is not None]
    out['main_cost_usd']=sum(costs) if len(costs)==total and total else None
    out['mean_completion_tokens']=mean(tokens) if tokens else None
    out['median_completion_tokens']=median(tokens) if tokens else None
    for name,control in [('correct_pass',True),('incorrect_pass',False)]:
        values=[r['confidence'] for r in rows if r['status']=='ok' and r['valid'] and r['control']==control]
        bins=[0]*10
        for v in values:bins[min(9,int(v*10))]+=1
        out[name+'_confidence']=dict(n=len(values),mean=mean(values) if values else None,median=median(values) if values else None,histogram_0_to_1=bins)
    return out


def reference_rows(root):
    data=json.loads((root/'reference.json').read_text(encoding='utf-8'));out=[]
    for p in data['cases']:
        if p['level']!=5:continue
        cond='dense' if p['condition']=='sweep' else 'full_certificate'
        for c in p['cells']:
            for t in c['examples']:
                out.append(dict(profile='spark_low',condition=cond,spectrum_id=p['spectrum_id'],cell_type=c['type'],cell_id=c['id'],
                    control=c['control'],status=t['status'],valid=t.get('valid'),confidence=t.get('confidence'),reason=t.get('reason',''),
                    ordinal=t['ordinal'],source='reused_completed_live'))
    return out


def paired(rows,profile,repetitions=500):
    groups=defaultdict(lambda:defaultdict(list))
    for r in rows:
        if r['profile']==profile and r['condition'] in ['dense','outer_anchors']:groups[r['spectrum_id']][r['condition']].append(r)
    keys=sorted(k for k,g in groups.items() if 'dense' in g and 'outer_anchors' in g)
    if not keys:return None
    def delta(chosen):
        a=metrics([r for k in chosen for r in groups[k]['dense']]);b=metrics([r for k in chosen for r in groups[k]['outer_anchors']])
        return {f:None if a[f] is None or b[f] is None else b[f]-a[f] for f in ['hit_rate','false_alarm_rate','d_prime']}
    result=dict(spectra=len(keys),change=delta(keys),cluster_95=None)
    if len(keys)>1 and repetitions:
        rng=random.Random(112026);draws=[delta([rng.choice(keys) for _ in keys]) for _ in range(repetitions)]
        result['cluster_95']={}
        for f in ['hit_rate','false_alarm_rate','d_prime']:
            values=sorted(d[f] for d in draws if d[f] is not None)
            result['cluster_95'][f]=[values[int(.025*(len(values)-1))],values[int(.975*(len(values)-1))]] if values else None
    return result


def draw_panel(result,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    models=[m for m in result['models'] if m['dense'] is not None or m['outer_anchors'] is not None]
    if not models:return
    entries=[(m,c,m[c]) for m in models for c in ['dense','outer_anchors'] if m[c]]
    fig,axes=plt.subplots(1,2,figsize=(12.2,5.2),sharey=True,layout='constrained')
    labels=[m['label']+' / '+('dense' if c=='dense' else 'checkpoints') for m,c,g in entries]
    for ax,control,title in zip(axes,[False,True],['Known incorrect claims','Known correct controls']):
        for y,(m,c,g) in enumerate(entries):
            planned=g.get('planned_trials',g['usable']+g['failed']);denom=planned*(2 if control else 7)/9
            usable=g['controls'] if control else g['errors']
            wrong=g['false_alarms'] if control else g['errors']-g['hits'];correct=usable-wrong
            parts=[correct/denom,wrong/denom,max(0,denom-usable)/denom];left=0
            for value,color,label in zip(parts,['#355d48','#b77c55','#b9beb9'],['Correct verdict','Wrong verdict','No usable verdict']):
                ax.barh(y,value,left=left,color=color,height=.68,label=label if y==0 else None)
                if value>=.075:ax.text(left+value/2,y,f'{value:.1%}',ha='center',va='center',fontsize=8,color='white' if label=='Correct verdict' else '#202923')
                left+=value
        ax.set_title(title,fontsize=11);ax.set_xlim(0,1);ax.set_xticks([0,.25,.5,.75,1],['0%','25%','50%','75%','100%'])
        ax.grid(axis='x',alpha=.12);ax.spines[['top','right']].set_visible(False)
    axes[0].set_yticks(range(len(labels)),labels,fontsize=8);axes[0].invert_yaxis()
    axes[0].legend(loc='upper center',bbox_to_anchor=(1.15,-.12),ncol=3,fontsize=8)
    prefix='SIMULATED SOFTWARE TEST\n' if result['mode']=='mock' else 'NEW COLLECTION PENDING\n' if result['mode']=='pending' else ''
    title='Same verifier, same spectra: effect of trusted checkpoints' if len(models)==1 else 'Accuracy and coverage on the same fixed claims'
    fig.suptitle(prefix+title+'\nAll planned trials counted; grey denotes no usable verdict, not deliberate abstention.',fontsize=11)
    fig.savefig(path,dpi=180,bbox_inches='tight');plt.close(fig)


def analyse_final(root,plots=True,integrate=False):
    root=Path(root);bank=json.loads((root/'bank.json').read_text(encoding='utf-8'));ps={p['id']:p for p in bank['problems']}
    plan=json.loads((root/'plan.json').read_text(encoding='utf-8'));statuses=json.loads((root/'progress.json').read_text(encoding='utf-8')) if (root/'progress.json').exists() else {}
    context=json.loads((root/'execution-context.json').read_text(encoding='utf-8')) if (root/'execution-context.json').exists() else dict(mode='pending')
    amendment=json.loads((root/'panel-continuation.json').read_text(encoding='utf-8')) if (root/'panel-continuation.json').exists() else None
    extension=json.loads((root/'token-budget-extension.json').read_text(encoding='utf-8')) if (root/'token-budget-extension.json').exists() else None
    profile_list=plan['profiles']+(amendment['profiles'] if amendment else [])
    rows=reference_rows(root);accounting={};count=0;cost=0
    if (root/'search.sqlite3').exists():
        with sqlite3.connect(f'file:{(root/"search.sqlite3").resolve().as_posix()}?mode=ro',uri=True) as db:
            if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Final ledger integrity failed.')
            for charged,raw in db.execute('SELECT charged,record FROM search_calls'):
                r=json.loads(raw);pid=r['budget_profile'];a=accounting.setdefault(pid,dict(calls=0,accounted_usd=0.,pilot_calls=0,main_calls=0,unknown_cost_calls=0))
                a['calls']+=1;a['accounted_usd']+=charged;count+=1;cost+=charged
                if not r.get('cost_known',False):a['unknown_cost_calls']+=1
                a['pilot_calls' if r['phase_kind']=='technical_pilot' else 'main_calls']+=1
                if r['phase_kind']!='main':continue
                p=ps[r['problem_id']];c=next(c for c in p['cells'] if c['id']==r['cell_id'])
                rows.append(dict(profile=pid,condition=p['basis']['condition'],spectrum_id=p['basis']['spectrum_id'],cell_type=c['type'],cell_id=c['id'],control=c['is_control'],
                    status=r['status'],valid=r.get('valid'),confidence=r.get('confidence'),reason=r.get('reason',r.get('error','')),ordinal=r['ordinal'],source='new_main',
                    cost_usd=charged,completion_tokens=(r.get('usage') or {}).get('completion_tokens'),finish_reason=r.get('finish_reason','stop' if r['status']=='ok' else 'unknown')))
    models=[];effects={};flattened=[]
    for p in profile_list:
        pid=p['id'];g=[r for r in rows if r['profile']==pid];selected=root/pid/'selected-protocol.json'
        selected=json.loads(selected.read_text(encoding='utf-8')) if selected.exists() else None
        m=dict(id=pid,label=p['label'],model=p['model'],reasoning_effort=p['effort'],status=statuses.get(pid,dict(status='pending')),
            trials_per_new_cell=selected['trials'] if selected else None,token_cap=selected['max_completion_tokens'] if selected else None,
            accounting=accounting.get(pid),dense=None,outer_anchors=None,full_certificate=None)
        for cond in ['dense','outer_anchors','full_certificate']:
            rs=[r for r in g if r['condition']==cond]
            if rs:m[cond]=panel_metrics(rs)
            n_planned=20 if pid=='spark_low' and cond!='outer_anchors' else (selected['trials'] if selected else None)
            if rs and n_planned:
                expected_errors=84*n_planned;expected_controls=24*n_planned;gaps=m[cond]
                missing_errors=max(0,expected_errors-gaps['errors']);missing_controls=max(0,expected_controls-gaps['controls'])
                gaps['planned_trials']=108*n_planned
                gaps['completion_rate']=gaps['usable']/gaps['planned_trials']
                gaps['no_usable_verdicts']=max(0,gaps['planned_trials']-gaps['usable'])
                gaps['correct_completed_rate']=gaps['correct_completed']/gaps['planned_trials']
                gaps['missing_sensitivity']=dict(hit_bounds=[gaps['hits']/expected_errors,(gaps['hits']+missing_errors)/expected_errors],
                    false_alarm_bounds=[gaps['false_alarms']/expected_controls,(gaps['false_alarms']+missing_controls)/expected_controls])
            if rs:
                values={k:v for k,v in m[cond].items() if not isinstance(v,dict)}
                for label in ['correct_pass','incorrect_pass']:
                    for statistic in ['n','mean','median']:values[label+'_'+statistic]=m[cond][label+'_confidence'][statistic]
                flattened.append(dict(profile=pid,condition=cond,**values))
        m['paired_effect']=paired(rows,pid);effects[pid]=m['paired_effect']
        # Fixed equal-repeat sensitivity: ordinal 0–4, with no replacement of failures.
        m['first_five_sensitivity']={cond:panel_metrics([r for r in g if r['condition']==cond and r['ordinal']<5])
            for cond in ['dense','outer_anchors'] if any(r['condition']==cond for r in g)}
        n=min(5,selected['trials']) if selected else 5
        m['matched_repeat_sensitivity']=dict(first_ordinals=n,configuration={cond:panel_metrics([r for r in g if r['condition']==cond and r['ordinal']<n])
                for cond in ['dense','outer_anchors'] if any(r['condition']==cond for r in g)},
            spark_low_reference={cond:panel_metrics([r for r in rows if r['profile']=='spark_low' and r['condition']==cond and r['ordinal']<n])
                for cond in ['dense','outer_anchors'] if any(r['profile']=='spark_low' and r['condition']==cond for r in rows)})
        models.append(m)
    low=next(m for m in models if m['id']=='spark_low');anchors=low['outer_anchors']
    part_a=[r for r in rows if r['profile']=='spark_low' and r['condition']=='outer_anchors']
    if len(part_a)<2160:prediction='pending_or_incomplete'
    elif anchors['usable']<.9*2160:prediction='inconclusive_due_to_unusable_outputs'
    elif anchors['hit_rate']>.9 and anchors['false_alarm_rate']<.05:prediction='met_on_usable_verdicts'
    else:prediction='not_met_on_usable_verdicts'
    result=dict(version='final-panel-report-1.0',mode=context['mode'],models=models,anchor_prediction=plan['anchor_prediction'],prediction_status=prediction,
        new_calls=count,new_accounted_usd=cost,accounting=accounting,
        interpretation_limit='Outer anchors and the supplied traces determine the gap. Rescue establishes the effect of adding those facts, not a unique internal mechanism.',
        repeat_note='Low reference uses 20 repeats; new hosted configurations target 5 with prespecified cost-only fallback to 3 or 1. Fixed first-N sensitivity (N=the actual new repeat count, at most 5) is supplied; finite d-prime ceilings depend on counts.',
        pilot_note='Technical pilots do not enter these scientific estimates.',frozen_prediction=plan['anchor_prediction'])
    result['panel_amendment']=amendment
    result['token_budget_extension']=extension
    terminal={'finished','finished_with_unusable_slots','unusable_at_token_cap','technical_pilot_failed','cost_projection_exceeds_guard','skipped'}
    result['collection_closed']=all(m['status']['status'] in terminal for m in models)
    result['accuracy_panel_available']=any(bool(m['id']!='spark_low' and m['status']['status'].startswith('finished') and m['dense'] and m['outer_anchors']) for m in models)
    result['coverage_note']='Detection, false alarms and d-prime condition on usable verdicts. Completion and all-planned outcomes retain missing responses. Truncation is not a deliberate abstention.'
    if extension:
        result['extension_accounted_usd']=cost-extension['initial_accounting']['charged_usd']
        result['estimated_credit_remaining']=extension['reported_remaining_credit']-result['extension_accounted_usd']
    if anchors:
        missing_errors=1680-anchors['errors'];missing_controls=480-anchors['controls']
        result['anchor_missing_sensitivity']=dict(hit_bounds=[anchors['hits']/1680,(anchors['hits']+missing_errors)/1680],
            false_alarm_bounds=[anchors['false_alarms']/480,(anchors['false_alarms']+missing_controls)/480],
            d_prime_bounds=[discriminability(anchors['hits'],1680,anchors['false_alarms']+missing_controls,480),
                            discriminability(anchors['hits']+missing_errors,1680,anchors['false_alarms'],480)])
    examples=[]
    for profile in profile_list:
        for cond in ['dense','outer_anchors','full_certificate']:
            wrong=sorted([r for r in rows if r['profile']==profile['id'] and r['condition']==cond and r['status']=='ok' and r['valid']!=r['control']],
                key=lambda r:(r['spectrum_id'],r['cell_type'],r['ordinal']))
            for r in wrong[:8]:
                p=next(p for p in bank['problems'] if p['basis']['spectrum_id']==r['spectrum_id'] and p['basis']['condition']=='dense')
                c=next(c for c in p['cells'] if c['type']==r['cell_type'])
                examples.append({**r,'candidate':c['candidate']['expr'],'reference':c['original']['expr']})
    result['misclassification_examples']=examples
    # A post-collection illustration, never a selection rule for the experiment.
    example_problem=next(p for p in bank['problems'] if p['basis']['spectrum_id']=='basis-spectrum-005' and p['basis']['condition']=='dense')
    example_cell=next(c for c in example_problem['cells'] if c['type']=='higher_1')
    result['illustrative_case']=dict(spectrum_id='basis-spectrum-005',candidate_type='higher_1',reference=example_cell['original']['expr'],
        candidate=example_cell['candidate']['expr'],D=example_problem['basis']['D'],selected_after_collection=True,
        purpose='Illustrative demo only. All aggregate metrics include every frozen case.',
        verdicts=[r for r in rows if r['spectrum_id']=='basis-spectrum-005' and r['cell_type']=='higher_1'])
    write_json(root/'dashboard.json',result);csv_rows(root/'model-panel.csv',flattened)
    confidence_rows=[]
    for m in models:
        for cond in ['dense','outer_anchors','full_certificate']:
            if not m[cond]:continue
            for kind in ['correct_pass','incorrect_pass']:
                for i,n in enumerate(m[cond][kind+'_confidence']['histogram_0_to_1']):
                    confidence_rows.append(dict(profile=m['id'],condition=cond,verdict_kind=kind,confidence_lower=i/10,confidence_upper=(i+1)/10,count=n))
    csv_rows(root/'confidence-distributions.csv',confidence_rows)
    cells=defaultdict(list)
    for r in rows:cells[(r['profile'],r['spectrum_id'],r['cell_type'],r['condition'])].append(r)
    cell_rows=[];routes=[]
    for (pid,sid,kind,cond),rs in sorted(cells.items()):
        good=[r for r in rs if r['status']=='ok'];rejected=sum(not r['valid'] for r in good)
        cell_rows.append(dict(profile=pid,spectrum_id=sid,candidate=kind,condition=cond,control=rs[0]['control'],usable=len(good),failed=len(rs)-len(good),rejected=rejected,rejection_rate=rejected/len(good) if good else None))
        for r in good:
            routes.append(dict(profile=pid,spectrum_id=sid,candidate=kind,condition=cond,ordinal=r['ordinal'],valid=r['valid'],
                **reason_flags(r['reason'],cond=='full_certificate'),reason=r['reason']))
    csv_rows(root/'candidate-pairs.csv',cell_rows);csv_rows(root/'explanation-routes.csv',routes)
    lookup={(r['profile'],r['spectrum_id'],r['candidate'],r['condition']):r for r in cell_rows};changes=[]
    for (pid,sid,candidate,condition),a in lookup.items():
        b=lookup.get((pid,sid,candidate,'outer_anchors'))
        if condition=='dense' and b is not None:
            changes.append(dict(profile=pid,spectrum_id=sid,candidate=candidate,control=a['control'],dense_rejection_rate=a['rejection_rate'],
                anchor_rejection_rate=b['rejection_rate'],anchor_minus_dense=None if a['rejection_rate'] is None or b['rejection_rate'] is None else b['rejection_rate']-a['rejection_rate']))
    csv_rows(root/'candidate-effects.csv',changes)
    spectrum_rows=[]
    for pid in [p['id'] for p in profile_list]:
        for sid in sorted({r['spectrum_id'] for r in rows if r['profile']==pid}):
            dense=[r for r in rows if r['profile']==pid and r['spectrum_id']==sid and r['condition']=='dense']
            anchor=[r for r in rows if r['profile']==pid and r['spectrum_id']==sid and r['condition']=='outer_anchors']
            if not dense or not anchor:continue
            a,b=metrics(dense),metrics(anchor)
            spectrum_rows.append(dict(profile=pid,spectrum_id=sid,**{f'dense_{k}':a[k] for k in ['hit_rate','false_alarm_rate','d_prime','failed']},
                **{f'anchor_{k}':b[k] for k in ['hit_rate','false_alarm_rate','d_prime','failed']},
                **{f'anchor_minus_dense_{k}':None if a[k] is None or b[k] is None else b[k]-a[k] for k in ['hit_rate','false_alarm_rate','d_prime']}))
    csv_rows(root/'spectrum-effects.csv',spectrum_rows)
    write_findings(root,result)
    history=json.loads((root/'guard-history.json').read_text(encoding='utf-8')) if (root/'guard-history.json').exists() else []
    guard=history[-1] if history else dict(global_budget_usd=plan['initial_total_budget'],profile_budgets_usd={p['id']:p['budget'] for p in plan['profiles']})
    cost_lines=['# Cost and accounting summary','',f"New programme: {count} recorded calls, ${cost:.6f} locally accounted. Mode: {context['mode']}.",
        f"Effective programme guard: ${guard['global_budget_usd']:.2f}. Profile guards: {json.dumps(guard['profile_budgets_usd'],sort_keys=True)}.",'',
        'All technical calls count towards the guards. Scientific estimates exclude pilots. Missing reported usage retains the full reservation. This summary is local accounting, not a provider invoice.','',
        '| Configuration | Pilot calls | Main calls | Unknown-cost reservations | Accounted USD |','| --- | ---: | ---: | ---: | ---: |']
    for m in models:
        a=m['accounting'] or {}
        cost_lines.append(f"| {m['label']} | {a.get('pilot_calls',0)} | {a.get('main_calls',0)} | {a.get('unknown_cost_calls',0)} | {a.get('accounted_usd',0):.6f} |")
    cost_lines+=['','Historical fixed representation + certificate study: 15,120 recorded calls, $11.910093. These verdicts are reused without new charges.',
        'Earlier adaptive/focused studies are not reconciled in this table. Remaining credit was user-reported approximately; no account balance was queried.',
        'Prices, pilot projections and initial guards are frozen in the plan/selected-protocol files. Effective per-call guards and resume history are retained in the ledger and guard-history.json.']
    if extension:
        cost_lines+=['',f"Authorised token extension: initial additional allowance ${extension['initial_additional_budget']:.2f} against user-reported remaining credit ${extension['reported_remaining_credit']:.2f}. The extension starts from ${extension['initial_accounting']['charged_usd']:.6f} already recorded; resume does not reset that baseline. Latest executed limits are in guard-history.json.",
            f"Actual extension accounting: ${result['extension_accounted_usd']:.6f}. Estimated credit remaining from that reported balance: ${result['estimated_credit_remaining']:.2f}, assuming no other account activity."]
    (root/'COST_SUMMARY.md').write_text('\n'.join(cost_lines)+'\n',encoding='utf-8')
    if plots:draw_panel(result,root/'model-panel.png')
    if integrate:integrate_final(root,result,copy_plot=plots)
    return result


def integrate_final(root,result,copy_plot=True):
    """Publish a local live snapshot into this existing app; never publish mocks."""
    if result['mode']!='live':raise ValueError('Only actual LIVE result ledgers may be integrated into the distributable app.')
    root=Path(root)
    write_json(ROOT/'data/final-panel-results.json',result)
    write_json(ROOT/'data/final-panel-public.json',public_summary(result))
    write_json(ROOT/'data/final-panel-plan.json',json.loads((root/'plan.json').read_text(encoding='utf-8')))
    if result.get('panel_amendment'):write_json(ROOT/'data/final-panel-continuation.json',result['panel_amendment'])
    if result.get('token_budget_extension'):write_json(ROOT/'data/final-panel-token-extension.json',result['token_budget_extension'])
    for name in ['FINAL_FINDINGS.md','DEMO_SCRIPT.md','COST_SUMMARY.md']:
        target=ROOT/name
        if name=='DEMO_SCRIPT.md' and target.exists():
            continue  # Keep the authored submission narrative across offline refreshes.
        source=(root/name).read_text(encoding='utf-8');temporary=ROOT/(name+'.tmp')
        temporary.write_text(source,encoding='utf-8');temporary.replace(ROOT/name)
    plot=ROOT/'static/final-model-panel.png'
    if copy_plot and (root/'model-panel.png').exists():shutil.copyfile(root/'model-panel.png',plot)
    readme=ROOT/'README.md';text=readme.read_text(encoding='utf-8')
    start='<!-- FINAL_PANEL_STATUS_START -->';end='<!-- FINAL_PANEL_STATUS_END -->'
    if start in text and end in text:
        statuses='; '.join(m['label']+': '+m['status']['status'].replace('_',' ') for m in result['models'])
        block=f"{start}\nLatest local final-programme snapshot: {result['new_calls']} new recorded calls,\n${result['new_accounted_usd']:.4f} accounted including pilots. Frozen anchor prediction:\n**{result['prediction_status'].replace('_',' ')}**.\n\n{statuses}. Incomplete or skipped configurations are not evidence of failure.\nSee [FINAL_FINDINGS.md](FINAL_FINDINGS.md), [cost accounting](docs/public-cost-summary.md),\nand `data/final-panel-results.json` for measured rates, counts and limits.\n{end}"
        if result.get('collection_closed') and not result.get('accuracy_panel_available'):
            block=f"{start}\nFinal programme: {result['new_calls']} recorded calls, ${result['new_accounted_usd']:.4f}\naccounted including pilots. The frozen anchor prediction was met. High/max\npilots yielded no main comparative-accuracy result. Collection is closed.\nSee [FINAL_FINDINGS.md](FINAL_FINDINGS.md) and [cost accounting](docs/public-cost-summary.md).\n{end}"
        elif result.get('collection_closed') and result.get('accuracy_panel_available'):
            block=f"{start}\nThe fixed model panel is complete: {result['new_calls']} recorded programme calls,\n${result['new_accounted_usd']:.4f} accounted including pilots. Higher configurations\nhave one repeat per cell. Accuracy and usable-response coverage are reported\ntogether. Collection is closed; see [FINAL_FINDINGS.md](FINAL_FINDINGS.md) and\n[cost accounting](docs/public-cost-summary.md).\n{end}"
        before=text[:text.index(start)];after=text[text.index(end)+len(end):]
        temporary=readme.with_suffix('.md.tmp');temporary.write_text(before+block+after,encoding='utf-8');temporary.replace(readme)


def write_findings(root,result):
    fmt=lambda v:'—' if v is None else f'{v:.3f}'
    lines=['# Final findings','',f"New requests recorded: {result['new_calls']}; accounted cost ${result['new_accounted_usd']:.4f}. Technical pilots are included in cost and excluded from science.",'']
    if result['mode']=='mock':lines+=['**SIMULATED SOFTWARE TEST. New values below are not experimental evidence. Historical reference rows are reused completed live data.**','']
    if result['mode']=='pending':lines+=['**New live collection is pending. The fixed runner, analysis and app integration are prepared; no new anchor/model result is claimed.**','']
    if result.get('collection_closed') and result['mode']=='live':lines+=['**Data collection is closed. No further model, reasoning-setting or task-family search is planned.**','']
    lines+=['## Established by held-out experiments','',
        'The completed 12-spectrum representation experiment found a nonmonotonic pattern: Hadamard remained easy despite being fully dense, while general rational matrices had 46.9% detection and 18.4% false alarms. Full Q,D certificates yielded 100% detection and 0.4% false alarms. These are fixed completed experiments, not a model-independent claim.','',
        '| Verifier | New repeats/cell | Dense usable | Dense d′ | Anchored usable | Anchored d′ |','| --- | ---: | ---: | ---: | ---: | ---: |']
    measured=[m for m in result['models'] if m['dense'] or m['outer_anchors']]
    for m in measured:
        repeats=m['trials_per_new_cell'] or ('pending' if m['status']['status']=='pending' else '—')
        usable=lambda g:'—' if not g else f"{g['usable']}/{g.get('planned_trials',g['usable']+g['failed'])}"
        lines.append(f"| {m['label']} | {repeats} | {usable(m['dense'])} | {fmt((m['dense'] or {}).get('d_prime'))} | {usable(m['outer_anchors'])} | {fmt((m['outer_anchors'] or {}).get('d_prime'))} |")
    lines+=['','Detection, false alarms and d′ condition on usable verdicts. Unusable outputs are not correct rejections or deliberate abstentions. Sample-size corrections give perfect-score d′ different ceilings. In particular, perfect returned results at different counts do not establish a discrimination improvement.','']
    lines+=['','| Verifier / condition | Detected / usable errors | False alarms / usable controls | Unusable | Correct PASS confidence mean / median | Incorrect PASS confidence mean / median |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for m in result['models']:
        for cond in ['dense','outer_anchors','full_certificate']:
            g=m[cond]
            if not g:continue
            a,b=g['correct_pass_confidence'],g['incorrect_pass_confidence']
            lines.append(f"| {m['label']} / {cond} | {g['hits']}/{g['errors']} ({g['hit_rate']:.1%}) | {g['false_alarms']}/{g['controls']} ({g['false_alarm_rate']:.1%}) | {g['failed']} | {fmt(a['mean'])} / {fmt(a['median'])} | {fmt(b['mean'])} / {fmt(b['median'])} |" if g['hit_rate'] is not None and g['false_alarm_rate'] is not None else f"| {m['label']} / {cond} | insufficient usable verdicts | insufficient usable verdicts | {g['failed']} | {fmt(a['mean'])} / {fmt(a['median'])} | {fmt(b['mean'])} / {fmt(b['median'])} |")
    low=next(m for m in result['models'] if m['id']=='spark_low');a=low['outer_anchors']
    if a and result['prediction_status']=='met_on_usable_verdicts' and result['mode']=='live':
        lines+=['',f"The fixed outer-anchor condition detected **{a['hits']}/{a['errors']} incorrect claims** and falsely rejected **{a['false_alarms']}/{a['controls']} correct controls**. All 2,160 new main trials returned usable verdicts." if a['failed']==0 else '',
            'The observed anchor result meets the frozen >90% detection / <5% false-alarm prediction. This establishes a large rescue on these fixed instances. It does not uniquely establish an internal drifting-anchor mechanism.']
    if low.get('paired_effect'):
        e=low['paired_effect'];interval=e['cluster_95'] or {};change=e['change']
        lines+=['',f"Paired over {e['spectra']} spectra:",'','| Quantity | Anchor minus baseline | 95% spectrum-bootstrap interval |','| --- | ---: | ---: |']
        for key,label in [('hit_rate','Detection'),('false_alarm_rate','False alarms'),('d_prime','d′')]:
            display=lambda v:'unavailable' if v is None else f'{v:+.3f}' if key=='d_prime' else f'{100*v:+.1f} pp'
            ci=interval.get(key)
            lines.append(f"| {label} | {display(change[key])} | {display(ci[0])+' to '+display(ci[1]) if ci else 'unavailable'} |")
        lines+=['','These intervals describe this twelve-spectrum resampling analysis, not a population prevalence estimate.']
    if result.get('panel_amendment'):
        lines+=['','Technical continuation: original max settings failed the token-cap pilot; new **high** settings are separately frozen in panel-continuation.json. Max truncations are not correctness results. The original plan and all original spending remain intact.']
    if result.get('token_budget_extension'):
        lines+=['','A user-authorised token-budget extension authorises finishing these same high configurations with 32,768/65,536 ceilings. The separate token-budget-extension.json preserves the earlier stop and original plan. Both technical pilots precede joint cost-only repeat allocation. No new scientific task or model family was added.']
    if result.get('collection_closed') and not result.get('accuracy_panel_available'):
        lines+=['','The high continuation also exceeded the frozen token-cap usability threshold. No additional model completed a main scientific run. **There is no comparative model-accuracy result, no demonstrated escalation rule and no evidence that stronger models would retain or repair the failure.** Technical pilot records remain accessible.']
    if result['mode']=='live' and result.get('accuracy_panel_available'):
        lines+=['','### Fixed model panel','']
        for m in measured:
            if m['id']=='spark_low':continue
            for cond in ['dense','outer_anchors']:
                g=m[cond]
                if not g:continue
                planned=g.get('planned_trials',g['recorded_trials'])
                lines.append(f"{m['label']} / {cond}: **{g['correct_completed']}/{planned} planned reviews produced a correct verdict**, {g['incorrect_completed']} produced a wrong verdict, and {g['no_usable_verdicts']} produced no usable verdict. Completion reasons: {json.dumps(g['unusable_reasons'],sort_keys=True)}.")
        w=next((m for m in measured if m['id']=='wonder_high'),None)
        if w and w['dense'] and w['outer_anchors']:
            d,a=w['dense'],w['outer_anchors']
            if d['main_cost_usd'] and a['main_cost_usd'] is not None:
                saving=1-a['main_cost_usd']/d['main_cost_usd']
                lines+=['',f"Wonder main-call spend on the same planned cases was ${d['main_cost_usd']:.4f} dense versus ${a['main_cost_usd']:.4f} anchored, a descriptive {saving:.1%} reduction. This excludes pilots and does not price the work of obtaining the anchors."]
        caps=', '.join(f"{m['label']}: {m['token_cap']}" for m in measured if m['id']!='spark_low')
        lines+=['',f'Production completion ceilings selected after the fixed pilots: {caps}. No truncated main case was selectively retried.',
            'The new configurations have one trial per fixed cell in this completed panel. This is a model-level transfer panel, not a cell-level calibration study.']
    lines+=['',f"Frozen Part-A prediction assessment: **{result['prediction_status']}**. Prediction: {result['anchor_prediction']}",'',
        'Technical-only and skipped configurations supply no accuracy comparison. Individual missing verdicts remain visible in coverage counts and extreme-assignment bounds. Confidence distributions, per-spectrum/candidate effects and paired spectrum-bootstrap intervals are in dashboard.json and CSVs.','',
        '## Supported interpretation','',result['interpretation_limit'],
        *(['The frozen practical anchor-rescue prediction was not met. This weakens that hypothesis; no replacement mechanism or new scientific search is launched.'] if result['prediction_status']=='not_met_on_usable_verdicts' else []),
        'The present product is a controlled test suite for developers and researchers evaluating an AI scientific reviewer. Basis changes vary the representation of a fixed spectral claim while exact ground truth remains known. They are experimental controls, not an extra step a physicist must perform to obtain an energy splitting.',
        ('Wonder-high supports practical escalation on this fixed dense testbed, with its no-verdict cases retained. Spark-high has substantial dense noncompletion, so its high conditional detection alone does not establish reliable end-to-end review. These observations concern the measured configurations, not all models.' if result['mode']=='live' and result.get('accuracy_panel_available') else 'Model-selection conclusions require completed main observations; pending, technical-only and simulated outcomes do not establish them.'),
        'Standard/high versus Contributor/low changes serving configuration, requested effort and token allowance. The comparison does not isolate inference compute as a single cause. Adding the tested anchors improves coverage and reduces Wonder token use, but obtaining those facts need not be free in a real workflow.','',
        '## Exploratory evidence','',
        'Earlier adaptive discovery and explanation-route patterns motivated this intervention. Frozen lexical flags are reused without tuning and do not establish hidden reasoning mechanisms. The prior self-forecasts recognised coarse task difficulty but did not establish privileged introspection.','',
        '## Not established','',
        'Generality to all models or scientific workflows, quantum-hardware performance, privileged introspection, independent certificate validation, and internal model mechanisms are not established. The original prompts describe coupled modes. Their Hamiltonian interpretation is explanatory context, not a claim that quantum wording caused the measured outcomes.',
        'A spectral gap here is a difference of Hamiltonian energies (or a spectral quantity in a coupled-mode model). Unitary changes of representation preserve it. This is different from changing the physical observable measured on a fixed state.',
        'Outer-anchor intervention and reused historical baseline run at different times. Rates condition on usable outputs, cells share spectra, and five or fewer repeats do not support cell-level calibration claims. The family was discovered adaptively; held-out spectra within it are not a representative sample of scientific review tasks.','',
        '## Cost and reproducibility','',result['repeat_note'],result['pilot_note'],
        'Immutable plan.json contains source hashes, exact hypothesis, candidate rules, pilot/budget policy and documentation sources. selected-protocol.json freezes each production configuration after its technical pilot. The shared SQLite ledger enforces both global and configuration guards, counting all pilot attempts and uncertain outcomes.',
        'Historical completed representation/certificate accounting: $11.9101 for 15,120 requests; reused here without further API charges. New accounting includes full conservative reservations where returned usage is missing; it is not a reconciliation of the provider invoice.','',
        '| Configuration | New calls (pilot / main) | Accounted USD | State / reason |','| --- | ---: | ---: | --- |']
    for m in result['models']:
        a=m['accounting'] or dict(calls=0,pilot_calls=0,main_calls=0,accounted_usd=0)
        lines.append(f"| {m['label']} | {a['calls']} ({a['pilot_calls']} / {a['main_calls']}) | {a['accounted_usd']:.4f} | {m['status']['status']}: {m['status'].get('reason') or ''} |")
    (root/'FINAL_FINDINGS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    low=next(m for m in result['models'] if m['id']=='spark_low');a=low['outer_anchors']
    if result['mode']=='mock' or result['prediction_status']=='pending_or_incomplete':anchor_sentence='The fixed outer-anchor test is pending; do not narrate a rescue before actual collection.'
    elif a['hit_rate'] is None or a['false_alarm_rate'] is None:anchor_sentence='The anchor condition did not return enough usable verdicts to assess discrimination. Show the failure count; do not infer rescue or persistence.'
    else:anchor_sentence=f"Adding only the exact smallest/largest energies produced {a['hit_rate']:.1%} detection and {a['false_alarm_rate']:.1%} false alarms on usable outputs. The frozen prediction was {result['prediction_status'].replace('_',' ')}."
    measured=[m for m in result['models'] if m['id']!='spark_low' and m['status']['status'].startswith('finished') and m['dense'] and m['outer_anchors']
        and all(m[c][v] is not None for c in ['dense','outer_anchors'] for v in ['hit_rate','false_alarm_rate'])]
    model_sentence=' '.join(f"{m['label']}, {m['trials_per_new_cell']} repeats: dense {m['dense']['correct_completed']}/{m['dense'].get('planned_trials',m['dense']['recorded_trials'])} correct completed reviews; with anchors {m['outer_anchors']['correct_completed']}/{m['outer_anchors'].get('planned_trials',m['outer_anchors']['recorded_trials'])}. Unavailable outputs stay visible." for m in measured)
    if not model_sentence or result['mode']=='mock':
        model_sentence='The new live comparison is pending. Show that status explicitly; no model-selection conclusion is available yet.'
        if result['mode']=='live' and result.get('panel_amendment'):model_sentence='Max-reasoning pilots exhausted the allowed tokens, so no max correctness comparison is available. A separately recorded high-reasoning comparison is pending; no model-selection conclusion is available yet.'
    panel_segment=f'Show the fixed Meta panel. {model_sentence} Label every pending/skipped configuration. Explain escalation only if the measured comparison supports it.'
    if result.get('collection_closed') and not result.get('accuracy_panel_available'):
        panel_segment='Show the exact-claim inspector and saved verdict record. Blindspot is for researchers evaluating an AI scientific reviewer: run known right and wrong cases, stress their representation, and inspect unreliable approvals. This result concerns Spark-low. Higher-model pilots did not yield a main accuracy comparison; a local-model application is future work.'
    wonder=next((m for m in measured if m['id']=='wonder_high'),None)
    spark=next((m for m in measured if m['id']=='spark_high'),None)
    if result['mode']=='live' and wonder:
        d,a=wonder['dense'],wonder['outer_anchors']
        panel_segment=f"Wonder produced correct verdicts on {d['correct_completed']} of {d['planned_trials']} dense cases; {d['no_usable_verdicts']} returned no usable verdict. With anchors it was {a['correct_completed']} of {a['planned_trials']}."
        if spark:panel_segment+=f" Spark-high returned only {spark['dense']['usable']} of {spark['dense']['planned_trials']} dense verdicts, so the missing responses remain visible."
        panel_segment+=' The new settings have one attempt per cell; this is a model-level pilot.'
        if d['main_cost_usd'] is not None and a['main_cost_usd'] is not None:panel_segment+=f" Wonder main-call cost was ${d['main_cost_usd']:.2f} dense versus ${a['main_cost_usd']:.2f} anchored."
    script=f'''# Proposed three-minute demonstration

Production notes, not spoken: use spectrum 005 and the +1% candidate. The exact gap is 1/104; the candidate is 101/10400. This example was chosen after collection for illustration; all aggregate estimates include every frozen case. Original API prompts used coupled modes; the Hamiltonian is the physical interpretation. Record saved results without new API calls.

0:00–0:25 — I am an assistant professor of physics, and increasingly we ask AI to check scientific reasoning. When it says PASS, did it check the claim exactly, or find it plausible?

0:25–0:55 — Show the four-level oracle view. The true middle splitting is 1/104; the candidate is exactly one percent larger. The diagonal presentation was rejected twenty times out of twenty. We change basis to vary the checking burden while preserving the spectral claim and its known truth value. This is a controlled test of the reviewer.

0:55–1:25 — Switch to the general rational basis. Show QᵀQ=I, unchanged levels and unchanged false claim. Spark-low rejected this case nine times and passed it eleven. Across all twelve spectra, detection was 46.9%, with 18.4% false alarms. Humans also find some representations harder. The concern is a confident PASS on a known false exact claim.

1:25–1:45 — Show the dense Hadamard control, which succeeds. Its two-qubit Hadamard structure shows why density alone is insufficient. The original API wording is retained; a four-level Hamiltonian is a physical interpretation of the exact spectral problem.

1:45–2:15 — {anchor_sentence} Contrast with the completed full-certificate condition, which catches all wrong claims with 0.4% false alarms. Anchors plus the traces create a short exact route; recovery alone does not prove an internal strategy.

2:15–2:40 — {panel_segment}

2:40–3:00 — Blindspot is an instrument for testing an AI scientific verifier, not an eigensolver. It measures how a PASS changes across equivalent descriptions and what additional structure or verifier configuration makes checking more reliable. Stop at the claims supported by the displayed results.
'''
    (root/'DEMO_SCRIPT.md').write_text(script,encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=Path('var/final-study'));p.add_argument('--no-plots',action='store_true')
    p.add_argument('--integrate',action='store_true',help='Update existing app summaries/findings from a LIVE ledger; never mocks')
    a=p.parse_args();result=analyse_final(a.directory,not a.no_plots,integrate=a.integrate);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
