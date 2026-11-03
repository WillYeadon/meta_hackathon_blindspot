"""Offline signal-detection analysis. No model calls and no explanation judging."""
import argparse
from collections import defaultdict
import csv
from fractions import Fraction
import json
import math
from pathlib import Path
import random
import re
import sqlite3
from statistics import NormalDist, mean
from .search import write_json


def discriminability(hits,n_errors,false_alarms,n_controls):
    if not n_errors or not n_controls:return None
    # Hautus/loglinear correction applied to EVERY rate, including non-extremes.
    return NormalDist().inv_cdf((hits+.5)/(n_errors+1))-NormalDist().inv_cdf((false_alarms+.5)/(n_controls+1))


def metrics(rows):
    usable=[r for r in rows if r['status']=='ok' and type(r.get('valid')) is bool]
    errors=[r for r in usable if not r['control']];controls=[r for r in usable if r['control']]
    hits=sum(not r['valid'] for r in errors);alarms=sum(not r['valid'] for r in controls)
    confidence=lambda values:mean(r['confidence'] for r in values) if values else None
    return dict(usable=len(usable),failed=len(rows)-len(usable),errors=len(errors),controls=len(controls),hits=hits,false_alarms=alarms,
        hit_rate=hits/len(errors) if errors else None,false_alarm_rate=alarms/len(controls) if controls else None,
        d_prime=discriminability(hits,len(errors),alarms,len(controls)),
        pass_likelihood_ratio=((1-(alarms+.5)/(len(controls)+1))/(1-(hits+.5)/(len(errors)+1))) if errors and controls else None,
        true_accept_confidence=confidence([r for r in controls if r['valid']]),
        false_accept_confidence=confidence([r for r in errors if r['valid']]))


def confidence_interval(rows,repetitions=600):
    """Resample whole underlying spectra, preserving paired cells/trials."""
    groups=defaultdict(list)
    for r in rows:groups[r['spectrum_id']].append(r)
    keys=sorted(groups)
    if len(keys)<2:return None
    rng=random.Random(81031);values=[]
    for _ in range(repetitions):
        sample=[r for _ in keys for r in groups[rng.choice(keys)]]
        v=metrics(sample)['d_prime']
        if v is not None:values.append(v)
    if not values:return None
    values.sort();return [values[int(.025*(len(values)-1))],values[int(.975*(len(values)-1))]]


def reason_flags(reason,certificate=False,reference=None):
    text=reason.lower()
    # Nonexclusive lexical flags, NOT validated semantic mechanism annotations.
    numerals=re.findall(r'\b(?:gap|splitting)\s*(?:=|is)\s*([-+]?\d+(?:/\d+)?)(?!\d|/\d|\.\d)',text)
    def differs(v):
        try:return Fraction(v)!=Fraction(reference)
        except (ValueError,ZeroDivisionError):return True
    mismatch=any(differs(v) for v in numerals) if reference is not None else False
    return dict(certificate_mentioned=certificate and bool(re.search(r'certificate|orthogon|q\^|q\s*d|q.t|similarity|diagonal (matrix|entries)|supplied.*\bd\b',text)),
        explicit_calculation_mentioned=bool(re.search(r'diagonali[sz]|eigenvalues? (are|=)|gap\s*=|characteristic polynomial|subtract|difference.*=',text)),
        plausibility_mentioned=bool(re.search(r'consistent|plausib|scale|denominator|factor|trace|no contradiction|invariant|non.?zero',text)),
        explicit_gap_numeral_mismatch=mismatch)


def load_rows(root,experiment=None):
    root=Path(root);bank=json.loads((root/'bank.json').read_text(encoding='utf-8'));problems={p['id']:p for p in bank['problems']}
    is_basis=bank.get('version','').startswith('basis-')
    database=root/experiment/'search.sqlite3' if experiment else root/'search.sqlite3'
    rows=[];forecasts={};ledger_totals={}
    with sqlite3.connect(f'file:{database.resolve()}?mode=ro',uri=True) as db:
        integrity=db.execute('PRAGMA quick_check').fetchone()[0]
        if integrity!='ok':raise ValueError('Use a complete SQLite backup or finished review.zip; integrity check failed.')
        count,cost=db.execute('SELECT COUNT(*),SUM(charged) FROM search_calls').fetchone();ledger_totals=dict(calls=count,accounted_usd=cost)
        for (raw,) in db.execute('SELECT record FROM search_calls'):
            r=json.loads(raw)
            if r['problem_id'] not in problems:raise ValueError('Ledger problem missing from bank.')
            p=problems[r['problem_id']]
            if r['stage'].endswith('forecast'):
                if r['status']=='ok':forecasts[r['cell_id']]=r['probability_percent']/100
                continue
            c=next(c for c in p['cells'] if c['id']==r['cell_id'])
            if is_basis:
                b=p['basis'];spectrum=b['spectrum_id'];condition=b['condition'];level=b['level'];label=b['label'];wording='gap_only'
            else:
                b=p['focus'];spectrum=b['base_id'];condition=b['matrix_form'];level=0 if condition=='diagonal' else 5;label=condition;wording=b['question_wording']
            rows.append(dict(problem_id=p['id'],cell_id=c['id'],spectrum_id=spectrum,level=level,label=label,condition=condition,wording=wording,
                mutation=c['type'],control=c['is_control'],status=r['status'],valid=r.get('valid'),confidence=r.get('confidence'),
                reason=r.get('reason',r.get('error','')),finish_reason=r.get('finish_reason'),ordinal=r['ordinal']))
    return bank,rows,forecasts,ledger_totals


def csv_rows(path,rows):
    if not rows:return
    with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def forecast_scores(rows,forecasts):
    """Leave-one-spectrum-out empirical baseline; held-out outcomes never train it."""
    cells=defaultdict(list)
    for r in rows:
        if r['status']=='ok':cells[r['cell_id']].append(r)
    scores=[]
    for cid,rs in cells.items():
        if cid not in forecasts:continue
        r=rs[0]
        train=[t for t in rows if t['status']=='ok' and t['spectrum_id']!=r['spectrum_id'] and
               (t['condition'],t['wording'],t['mutation'])==(r['condition'],r['wording'],r['mutation'])]
        if not train:continue
        baseline=(sum(not t['valid'] for t in train)+.5)/(len(train)+1)
        observed=mean(not t['valid'] for t in rs);forecast=forecasts[cid]
        scores.append(dict(cell_id=cid,spectrum_id=r['spectrum_id'],condition=r['condition'],mutation=r['mutation'],control=r['control'],
            forecast=forecast,observed=observed,history_baseline=baseline,usable=len(rs),
            forecast_brier=mean((forecast-(not t['valid']))**2 for t in rs),
            history_brier=mean((baseline-(not t['valid']))**2 for t in rs)))
    return scores


def plot_groups(groups,path,title,simulated=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    x=list(range(len(groups)));labels=[g['label'] for g in groups]
    fig,axes=plt.subplots(1,3,figsize=(12.5,3.9),layout='constrained')
    color='#355d48'
    for ax,key,ylabel in zip(axes,['d_prime','hit_rate','false_alarm_rate'],["Discriminability d′",'Hit rate on wrong claims','False-alarm rate on controls']):
        y=[g[key] for g in groups]
        ax.plot(x,y,'o-',color=color,lw=1.8)
        if key=='d_prime':
            for i,g in enumerate(groups):
                ci=g.get('d_prime_cluster_95')
                if ci and g[key] is not None:ax.vlines(i,*ci,color=color,lw=1.2)
            ax.axhline(0,color='#999',lw=.7,ls='--')
        else:ax.set_ylim(-.03,1.03)
        ax.set_xticks(x,labels,rotation=30,ha='right',fontsize=8);ax.set_ylabel(ylabel);ax.grid(axis='y',alpha=.18)
        ax.spines[['top','right']].set_visible(False)
    fig.suptitle(('SIMULATED SOFTWARE TEST\n' if simulated else '')+title,fontsize=11)
    fig.savefig(path,dpi=180,bbox_inches='tight');plt.close(fig)


def analyse(root,experiment=None,output=None,plots=True,bootstrap=600):
    root=Path(root);output=Path(output) if output else root/(experiment or 'analysis');output.mkdir(parents=True,exist_ok=True)
    bank,rows,forecasts,totals=load_rows(root,experiment);groups=defaultdict(list)
    for r in rows:groups[(r['level'],r['condition'],r['label'])].append(r)
    summaries=[]
    for (level,condition,label),rs in sorted(groups.items()):
        m=metrics(rs);m.update(level=level,condition=condition,label=label,spectra=len({r['spectrum_id'] for r in rs}),
            d_prime_cluster_95=confidence_interval(rs,bootstrap) if bootstrap else None);summaries.append(m)
    cell_groups=defaultdict(list)
    for r in rows:cell_groups[r['cell_id']].append(r)
    cell_results=[];explanations=[];references={c['id']:c['original']['expr'] for p in bank['problems'] for c in p['cells']}
    for cid,rs in cell_groups.items():
        r=rs[0];n=sum(t['status']=='ok' for t in rs);rej=sum(t['status']=='ok' and not t['valid'] for t in rs)
        cell_results.append(dict(cell_id=cid,problem_id=r['problem_id'],spectrum_id=r['spectrum_id'],level=r['level'],condition=r['condition'],mutation=r['mutation'],
            control=r['control'],usable=n,rejected=rej,failed=len(rs)-n,rejection_rate=rej/n if n else None,forecast=forecasts.get(cid)))
        for t in rs:
            if t['status']=='ok':explanations.append(dict(cell_id=cid,ordinal=t['ordinal'],valid=t['valid'],control=t['control'],confidence=t['confidence'],
                **reason_flags(t['reason'],t['condition']=='certificate',references[cid]),reference_gap=references[cid],
                numeric_calculation_review='Unreviewed: numeral mismatch may quote a rejected candidate; inspect context.',reason=t['reason']))
    comparison=forecast_scores(rows,forecasts) if forecasts else []
    forecast_summary=[]
    for condition in sorted({r['condition'] for r in comparison}):
        g=[r for r in comparison if r['condition']==condition]
        forecast_summary.append(dict(condition=condition,cells=len(g),forecast_brier=mean(r['forecast_brier'] for r in g),history_brier=mean(r['history_brier'] for r in g)))
    manifest_path=root/(experiment or '')/'manifest.json'
    mode=json.loads(manifest_path.read_text())['identity']['settings']['mode'] if manifest_path.exists() else 'unknown'
    result=dict(version='signal-analysis-1.0',source_version=bank.get('version'),mode=mode,
        **totals,verdicts=len(rows),usable_verdicts=sum(r['status']=='ok' for r in rows),groups=summaries,forecast_comparison=forecast_summary,
        d_prime_correction='Phi^-1((hits+0.5)/(n_errors+1)) - Phi^-1((false_alarms+0.5)/(n_controls+1))',
        caveats=['Intervals resample underlying spectra, retaining dependent trials and paired contexts.',
            'Discrete representation levels are named interventions, not a validated monotonic complexity scale.',
            'Equal-variance signal-detection d-prime is a descriptive summary; inspect hit and false-alarm rates.',
            'With zero observed errors, a near-degenerate bootstrap interval does not establish zero population error.',
            'Explanation flags are nonexclusive lexical cues, not validated mechanism labels or evidence about hidden reasoning.',
            'A valid certificate exposes answer-bearing structure. Rescue alone cannot establish independent verification of the certificate.'])
    result['caveats'].append('A posterior probability that a passed claim is correct also requires a prior error prevalence; a PASS has no universal confidence percentage.')
    write_json(output/'analysis.json',result);csv_rows(output/'conditions.csv',[{**g,'d_prime_cluster_95':json.dumps(g['d_prime_cluster_95'])} for g in summaries])
    csv_rows(output/'cells.csv',cell_results);csv_rows(output/'explanation-review.csv',explanations);csv_rows(output/'forecast-baseline.csv',comparison)
    lines=['# Blindspot evidence report','',f"Recorded requests: {totals['calls']}. Usable verdicts: {result['usable_verdicts']}/{len(rows)}.",'',
        '| Condition | Hits / errors | False alarms / controls | d′ | Confidence on false accepts |','| --- | ---: | ---: | ---: | ---: |']
    fmt=lambda v:f'{v:.3f}' if v is not None else 'unavailable'
    for g in summaries:lines.append(f"| {g['label']} | {g['hits']}/{g['errors']} | {g['false_alarms']}/{g['controls']} | {fmt(g['d_prime'])} | {fmt(g['false_accept_confidence'])} |")
    lines+=['','Higher hit rate and lower false-alarm rate indicate more useful checking. Rates condition on usable outputs.','',*['- '+s for s in result['caveats']]]
    if forecast_summary:
        lines+=['','History baseline uses only OTHER spectra with the same presentation, wording and candidate type. Lower Brier score is better.']
        for g in forecast_summary:lines.append(f"- {g['condition']}: self-forecast Brier {g['forecast_brier']:.4f}; leave-one-spectrum-out history {g['history_brier']:.4f}.")
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if plots and summaries:plot_groups(summaries,output/'discriminability.png','Verification over equivalent representations',result['mode']=='mock')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--experiment',choices=['sweep','certificate']);parser.add_argument('--output',type=Path);parser.add_argument('--no-plots',action='store_true')
    args=parser.parse_args();result=analyse(args.directory,args.experiment,args.output,not args.no_plots)
    print(json.dumps({k:result[k] for k in ['calls','accounted_usd','verdicts','usable_verdicts','groups','forecast_comparison']},indent=2))


if __name__=='__main__':main()
