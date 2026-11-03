"""Small read-only summaries for the representation dashboard."""
from collections import defaultdict
import json
from pathlib import Path
import random
import hashlib
from .signal_analysis import metrics,load_rows,confidence_interval


def paired_effect(rows,repetitions=600):
    groups=defaultdict(lambda:defaultdict(list))
    for r in rows:
        if r['level']==5:groups[r['spectrum_id']][r['condition']].append(r)
    complete={k:v for k,v in groups.items() if 'sweep' in v and 'certificate' in v}
    if not complete:return None
    def difference(ids):
        a=metrics([r for i in ids for r in complete[i]['sweep']]);b=metrics([r for i in ids for r in complete[i]['certificate']])
        return {key:None if a[key] is None or b[key] is None else b[key]-a[key] for key in ['hit_rate','false_alarm_rate','d_prime']}
    keys=sorted(complete);result=dict(spectra=len(keys),certificate_minus_baseline=difference(keys))
    if repetitions and len(keys)>1:
        rng=random.Random(1101);values=[difference([rng.choice(keys) for _ in keys]) for _ in range(repetitions)]
        result['cluster_95']={}
        for key in ['hit_rate','false_alarm_rate','d_prime']:
            a=sorted(v[key] for v in values if v[key] is not None)
            result['cluster_95'][key]=[a[int(.025*(len(a)-1))],a[int(.975*(len(a)-1))]] if a else None
    return result


def summarise(rows,bootstrap=0):
    groups=defaultdict(list)
    for r in rows:groups[(r['level'],r['condition'],r['label'])].append(r)
    return [dict(level=k[0],condition=k[1],label=k[2],**metrics(rs),
        d_prime_cluster_95=confidence_interval(rs,bootstrap) if bootstrap else None)
        for k,rs in sorted(groups.items(),key=lambda item:(item[0][0],item[0][1]=='certificate',item[0][1]))]


def study_data(root):
    root=Path(root);rows=[]
    for experiment in ['sweep','certificate']:
        if (root/experiment/'search.sqlite3').exists():rows+=load_rows(root,experiment)[1]
    return dict(groups=summarise(rows,600),certificate_effect=paired_effect(rows),
        interpretation='Paired by spectrum. A correct certificate supplies answer-bearing structure; a rescue does not prove the model independently checked every matrix identity.')


def from_experiments(experiments):
    rows=[];cases=[]
    for e in experiments:
        if not e.get('basis_study'):continue
        p=e['problem_snapshot'];b=p['basis'];cell_rows=[]
        for c in p['cells']:
            r=e['results'].get(c['id'],{});m=r.get('metrics',{})
            cell_rows.append(dict(id=c['id'],type=c['type'],label=c['type_label'],control=c['is_control'],
                candidate=c['candidate']['expr'],reference=c['original']['expr'],rejection_rate=m.get('observed'),
                usable=m.get('valid_trials',0),failed=m.get('failed_trials',0)))
            for t in r.get('trials',[]):rows.append(dict(spectrum_id=b['spectrum_id'],level=b['level'],condition=b['condition'],label=b['label'],
                control=c['is_control'],status=t['status'],valid=t.get('valid'),confidence=t.get('confidence')))
        cases.append(dict(id=p['id'],title=p['title'],experiment_id=e['id'],**b,cells=cell_rows))
    cases.sort(key=lambda c:(c['spectrum_id'],c['level'],c['condition']=='certificate'))
    return dict(source='Fixed basis study',groups=summarise(rows),cases=cases,certificate_effect=paired_effect(rows,0),
        planned_verdicts=sum(len(e['cell_ids'])*e['config']['trials'] for e in experiments if e.get('basis_study')),
        usable_verdicts=sum(r['status']=='ok' for r in rows),recorded_verdicts=len(rows))


def cache_completed_study(root):
    """Compact public demo record; retain every verdict, not repeated requests."""
    root=Path(root);bank=json.loads((root/'bank.json').read_text());rows=[];totals=[];hashes={}
    for experiment in ['sweep','certificate']:
        manifest=json.loads((root/experiment/'manifest.json').read_text())
        summary=json.loads((root/experiment/'summary.json').read_text())
        if manifest['identity']['settings']['mode']!='live' or summary['status'] not in ['finished','finished_with_unusable_slots'] or summary.get('unattempted_verdicts',0):
            raise ValueError('Only completed live studies can become the saved live demo.')
        _,part,_,cost=load_rows(root,experiment);rows+=part;totals.append(cost)
        hashes[experiment]=hashlib.sha256((root/experiment/'search.sqlite3').read_bytes()).hexdigest()
    by_cell=defaultdict(list)
    for r in rows:by_cell[r['cell_id']].append(r)
    cases=[]
    for p in bank['problems']:
        cells=[]
        for c in p['cells']:
            rs=sorted(by_cell[c['id']],key=lambda r:r['ordinal']);usable=[r for r in rs if r['status']=='ok']
            cells.append(dict(id=c['id'],type=c['type'],label=c['type_label'],control=c['is_control'],
                candidate=c['candidate']['expr'],reference=c['original']['expr'],
                rejection_rate=sum(not r['valid'] for r in usable)/len(usable) if usable else None,
                usable=len(usable),failed=len(rs)-len(usable),
                examples=[{k:r.get(k) for k in ['ordinal','status','valid','confidence','reason']} for r in rs]))
        cases.append(dict(id=p['id'],title=p['title'],experiment_id=None,**p['basis'],cells=cells))
    cases.sort(key=lambda c:(c['spectrum_id'],c['level'],c['condition']=='certificate'))
    combined=study_data(root)
    return dict(source='Completed live basis and certificate study',mode='live',cases=cases,**combined,
        planned_verdicts=sum(json.loads((root/e/'summary.json').read_text())['planned_calls'] for e in ['sweep','certificate']),
        recorded_verdicts=len(rows),usable_verdicts=sum(r['status']=='ok' for r in rows),
        accounted_usd=sum(t['accounted_usd'] for t in totals),source_ledger_sha256=hashes,
        settings={k:v for k,v in json.loads((root/'plan.json').read_text()).items() if k in ['model','temperature','reasoning_effort','max_completion_tokens']})
