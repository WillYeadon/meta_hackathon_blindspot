"""Fixed basis ladder and paired certificate intervention, with no new forecasts."""
import argparse
import asyncio
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
from zipfile import ZipFile, ZIP_DEFLATED
import sympy as sp
from .config import load_settings, ROOT
from .maths import representation, validate_pair
from .matrix_focus import excluded_spectra, variants
from .meta import utcnow
from .overnight import ensure_bank
from .search import Search, SearchStopped, LimitReached, write_json, import_results
from .semantic_bank import make_case, load_bank
from .signal_analysis import analyse

VERSION='basis-1.0'
LEVELS=['Canonical diagonal','Permuted diagonal','One rational rotation','Three rational rotations','Simple Hadamard basis','General rational basis']


def givens(i,j,c=sp.Rational(3,5),s=sp.Rational(4,5)):
    Q=sp.eye(4);Q[i,i]=Q[j,j]=c;Q[i,j]=-s;Q[j,i]=s;return Q


def transformations(general):
    permutation=sp.zeros(4)
    for i,j in enumerate([2,0,3,1]):permutation[i,j]=1
    hadamard=sp.Matrix([[1,1,1,1],[1,-1,1,-1],[1,1,-1,-1],[1,-1,-1,1]])/2
    return [sp.eye(4),permutation,givens(0,1),
        givens(0,1)*givens(1,2,sp.Rational(5,13),sp.Rational(12,13))*givens(2,3),hadamard,general]


def serial(matrix):return [[str(x) for x in row] for row in matrix.tolist()]


def validate_basis(D,Q,H):
    if Q.T*Q!=sp.eye(4) or H!=Q*D*Q.T:raise ValueError('Invalid orthogonal similarity.')
    a,b=D.charpoly(),H.charpoly()
    if a.all_coeffs()!=b.all_coeffs():raise ValueError('Characteristic polynomial changed.')
    roots=sp.polys.polytools.ground_roots(b.as_expr(),b.gen)
    spectrum=sorted(r for r,n in roots.items() for _ in range(n))
    if spectrum!=list(D.diagonal()):raise ValueError('Ordered spectrum changed.')
    return dict(orthogonal=True,similarity=True,characteristic_polynomial_preserved=True,
        spectrum=list(map(str,spectrum)),gap=str(spectrum[2]-spectrum[1]),
        characteristic_coefficients=list(map(str,b.all_coeffs())),method='Exact rational matrix products and characteristic polynomial roots')


def build_bank(spectra=12,seed=20261101,excluded=None):
    if not 1<=spectra<=100:raise ValueError('Use 1–100 spectra.')
    seen=set(excluded or []);rng=random.Random(f'{VERSION}:{seed}');problems=[];number=0;attempts=0
    while number<spectra:
        attempts+=1
        if attempts>100*spectra:raise ValueError('Insufficient new validated spectra.')
        base=make_case('near_degeneracy',number,rng);values=tuple(map(str,base['oracle']['spectrum']))
        D=sp.diag(*map(sp.sympify,values));general=sp.Matrix(base['oracle']['U'])
        if values in seen or D[3,3]==2*(D[1,1]+D[2,2])/2:continue
        ladder=transformations(general)
        matrices=[Q*D*Q.T for Q in ladder]
        if any(v==0 for H in [matrices[4],matrices[5]] for v in H):continue
        seen.add(values);spectrum_id=f'basis-spectrum-{number+1:03d}'
        for level,(Q,H) in enumerate(zip(ladder,matrices)):
            validation=validate_basis(D,Q,H);gap=sp.sympify(validation['gap'])
            for certified in ([False,True] if level==5 else [False]):
                condition='certificate' if certified else 'sweep';pid=f'{spectrum_id}-level-{level}'+('-certificate' if certified else '')
                p=copy.deepcopy(base)
                p.update(id=pid,title=f'Spectrum {number+1:02d} · L{level} · '+('certificate' if certified else LEVELS[level]),
                    topic='Truth-preserving basis transformation',split='discovery',verifier_protocol='truth',collect_forecasts=False,cells=[],
                    question=f'The exact real symmetric matrix H={sp.sstr(H)} describes four coupled modes. In ascending order its eigenvalues are lambda_0 through lambda_3. Compute the exact value of lambda_2-lambda_1.',
                    assumptions='Use the exact rational entries. The candidate asserts an exact equality; agreement within a numerical tolerance is insufficient. No additional symmetry is assumed.',
                    basis=dict(spectrum_id=spectrum_id,level=level,label=('Exact certificate' if certified else LEVELS[level]),condition=condition,
                        D=serial(D),Q=serial(Q),H=serial(H),validation=validation))
                p['oracle'].update(H=serial(H),U=serial(Q));p['steps'][-1]['text']='The exact middle spectral gap is as follows.'
                if certified:p['structural_certificate']=dict(Q=serial(Q),D=serial(D),identities=['H = Q D Q^T','Q^T Q = I'],
                    instruction='Q and D are supplied as a candidate structural certificate. Determine whether they certify the spectrum of H and whether the candidate spectral-gap claim follows. The certificate does not itself assert a numerical gap.')
                target=p['steps'][-1]
                for kind,label,value,control,note,relative in variants(gap):
                    proof=validate_pair(gap,value,p,control)
                    if not proof:raise ValueError('Invalid candidate label.')
                    p['cells'].append(dict(id=f'{pid}:3:{kind}',problem_id=pid,step=3,type=kind,type_label=label,is_control=control,
                        original=copy.deepcopy(target),candidate={**copy.deepcopy(target),**representation(value)},relative_error=relative,
                        validation=proof,plan_description=note,mutation=dict(ast_path=[],before=str(gap),after=str(sp.simplify(value)),
                            before_latex=sp.latex(gap),after_latex=sp.latex(value),description=note,rule=kind)))
                p['cell_count']=9;problems.append(p)
        number+=1
    return dict(version=VERSION,seed=seed,problems=problems,levels=LEVELS,
        excluded_spectra=[list(v) for v in sorted(excluded or [])],
        description='Fixed held-out isospectral basis ladder plus valid-certificate intervention on every level-5 case. No new forecasts; no adaptive selection.')


class BasisSearch(Search):
    def jobs(self,problems,stage,count):
        jobs=super().jobs(problems,stage,count);random.Random(f'{VERSION}:{self.bank["seed"]}:{self.options["experiment"]}').shuffle(jobs);return jobs

    def report(self,problems,stage):
        rows=super().report(problems,stage)
        for p in problems:
            path=self.root/'exports'/f'{stage}-{p["id"]}.json';payload=json.loads(path.read_text(encoding='utf-8'));e=payload['experiment']
            e.update(basis_study=VERSION,basis_context=p['basis'],forecasts_expected=False,
                status='complete' if all(r['metrics']['valid_trials']==self.options['confirm_trials'] for r in e['results'].values()) else 'partial')
            payload['warning']='SIMULATED SOFTWARE TEST' if self.settings.mode=='mock' else 'Fixed representation intervention. Paired descriptions share the same underlying spectrum.'
            write_json(path,payload)
        return rows


def prepare(root,spectra=12,seed=20261101,exclude_paths=None,regenerate=False):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);path=root/'bank.json'
    if path.exists():
        bank=load_bank(path)
        if bank['version']!=VERSION or bank['seed']!=seed or len(bank['problems'])!=7*spectra:raise ValueError('Frozen design differs; use a new directory.')
    else:
        excluded,sources=excluded_spectra(exclude_paths or [])
        bundled=ROOT/'data'/'basis-study-bank.json'
        if not regenerate and spectra==12 and seed==20261101 and bundled.exists():
            raw=json.loads(bundled.read_text(encoding='utf-8'))
            if any(tuple(p['oracle']['spectrum']) in excluded for p in raw['problems']):raise ValueError('Bundled spectra overlap your prior data; build with a new seed.')
        else:raw=build_bank(spectra,seed,excluded)
        write_json(path,raw);bank=load_bank(path)
    # Validate every saved transformation again, including resumed/trusted banks.
    for p in bank['problems']:
        b=p['basis'];proof=validate_basis(sp.Matrix(b['D']),sp.Matrix(b['Q']),sp.Matrix(b['H']))
        if proof!=b['validation'] or proof['gap']!=p['steps'][-1]['expr']:raise ValueError('Saved validation or gap changed.')
    return bank


def bundle(root):
    root=Path(root)
    with ZipFile(root/'review.zip','w',ZIP_DEFLATED) as z:
        for p in sorted(root.rglob('*')):
            if not p.is_file() or p.name=='review.zip' or 'exports' in p.relative_to(root).parts:continue
            if p.suffix in {'.json','.csv','.sqlite3','.md','.png'}:z.write(p,p.relative_to(root).as_posix())


async def execute(root,settings,args,client_factory=None):
    root=Path(root);bank=prepare(root,args.spectra,args.seed,args.exclude_bank,args.regenerate)
    plan=dict(version=VERSION,seed=args.seed,bank_hash=bank['hash'],spectra=args.spectra,levels=LEVELS,trials_per_cell=args.trials,
        model=settings.model,temperature=settings.temperature,reasoning_effort=settings.reasoning_effort,max_completion_tokens=settings.max_completion_tokens,
        verifier_protocol='truth',forecasts=False,certificate_rule='Every level-5 spectrum; same H, claim, and sampling. Only certificate content differs.',
        planned_sweep_calls=args.spectra*6*9*args.trials,planned_certificate_calls=args.spectra*9*args.trials,
        primary='Hit rate, false-alarm rate and loglinear-corrected d-prime by named level; 95% intervals resample whole spectra.',
        paired='Certificate minus level-5 baseline; pair by spectrum and mutation, not by trial ordinal.',
        explanation_analysis='Exploratory lexical flags plus an explicit numerical-calculation review column; not used for primary results.',
        ordering='Deterministically shuffled within each experiment; sweep precedes certificate, so timing is a possible confound.',
        limits=dict(sweep_usd=args.budget_usd,certificate_usd=args.certificate_budget_usd,max_calls_each=args.max_calls))
    # Allow increases to financial limits on resume, while retaining initial plan.
    if (root/'plan.json').exists():plan['limits']=json.loads((root/'plan.json').read_text())['limits']
    ensure_bank(root/'plan.json',plan)
    if args.build_only:print(json.dumps(plan,indent=2));print('All data and invariance checks frozen before model calls.');return plan
    results=[]
    for experiment,cap in [('sweep',args.budget_usd),('certificate',args.certificate_budget_usd)]:
        if args.experiment not in ['all',experiment]:continue
        directory=root/experiment;directory.mkdir(exist_ok=True)
        problems=[p for p in bank['problems'] if p['basis']['condition']==experiment]
        raw=dict(version=VERSION,seed=bank['seed'],problems=problems,levels=LEVELS,description=bank['description'])
        ensure_bank(directory/'bank.json',raw);ensure_bank(directory/'shortlist-bank.json',raw)
        local=load_bank(directory/'bank.json')
        options=dict(budget_usd=cap,max_calls=args.max_calls,rpm=args.rpm,screen_trials=args.trials,confirm_trials=args.trials,
            top_k=1,max_per_family=1,holdout_per_family=1,input_price=.10,cached_price=.002,output_price=.20,
            selection='none',verifier_protocol='truth',show_budget=False,experiment=experiment)
        search=BasisSearch(directory,local,settings,options,client_factory(settings) if client_factory else None)
        manifest=json.loads((directory/'manifest.json').read_text());manifest.update(study=VERSION,warning='SIMULATED SOFTWARE TEST' if settings.mode=='mock' else 'Fixed representation experiment, no forecasts and no adaptive selection.')
        write_json(directory/'manifest.json',manifest)
        status='finished';reason=None
        try:
            await search.phase(problems,'confirm',args.trials)
        except SearchStopped as exc:status='paused_at_limit' if isinstance(exc,LimitReached) else 'stopped_on_error';reason=str(exc)
        except (KeyboardInterrupt,asyncio.CancelledError):status='interrupted';reason='Interrupted; pending outcomes may be unknown.';raise
        except Exception as exc:status='stopped_on_error';reason=f'{type(exc).__name__}: {exc}';raise
        finally:
            rows=search.report(problems,'confirm')
            summary=dict(version=VERSION,mode=settings.mode,experiment=experiment,status=status,reason=reason,planned_calls=len(problems)*9*args.trials,
                usable_verdicts=sum(r['usable'] for r in rows),failed_verdicts=sum(r['failed'] for r in rows),**search.ledger.totals())
            summary['unattempted_verdicts']=summary['planned_calls']-summary['usable_verdicts']-summary['failed_verdicts']
            if status=='finished' and summary['failed_verdicts']:summary['status']='finished_with_unusable_slots'
            write_json(directory/'summary.json',summary)
            await search.client.close();results.append(summary)
            analyse(root,experiment,plots=not args.no_plots,bootstrap=args.bootstrap)
            bundle(root)
            print(json.dumps(summary,indent=2))
        if status not in ['finished']:break
    if (root/'sweep/search.sqlite3').exists() and (root/'certificate/search.sqlite3').exists():
        from .study_dashboard import study_data
        combined=study_data(root);write_json(root/'comparison.json',combined)
        if not args.no_plots:
            from .signal_analysis import plot_groups
            plot_groups([g for g in combined['groups'] if g['level']==5],root/'certificate-comparison.png',
                'Certificate intervention on the same dense cases',settings.mode=='mock')
        (root/'comparison.md').write_text('# Paired certificate comparison\n\n'+
            json.dumps(combined['certificate_effect'],indent=2)+'\n\n'+combined['interpretation']+'\n',encoding='utf-8')
        bundle(root)
    print(f'Review attachment: {root / "review.zip"}');return results


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=Path('var/basis-study'))
    p.add_argument('--spectra',type=int,default=12);p.add_argument('--seed',type=int,default=20261101);p.add_argument('--trials',type=int,default=20)
    p.add_argument('--budget-usd',type=float,default=15);p.add_argument('--certificate-budget-usd',type=float,default=5)
    p.add_argument('--max-calls',type=int,default=15000);p.add_argument('--rpm',type=int,default=100);p.add_argument('--concurrency',type=int,default=8)
    p.add_argument('--experiment',choices=['all','sweep','certificate'],default='all');p.add_argument('--build-only',action='store_true')
    p.add_argument('--mock',action='store_true');p.add_argument('--regenerate',action='store_true');p.add_argument('--no-plots',action='store_true')
    p.add_argument('--bootstrap',type=int,default=600);p.add_argument('--import-results',action='store_true');p.add_argument('--exclude-bank',type=Path,action='append')
    args=p.parse_args()
    if not 1<=args.spectra<=100 or not 1<=args.trials<=30 or min(args.budget_usd,args.certificate_budget_usd)<=0 or args.max_calls<1 or not 1<=args.rpm<=150 or not 1<=args.concurrency<=8 or args.bootstrap<0:p.error('Invalid size, limits or bootstrap count.')
    args.exclude_bank=args.exclude_bank or [Path('var/search/bank.json'),Path('var/overnight/wide/bank.json'),Path('var/matrix-focus/bank.json')]
    settings=load_settings()
    if args.mock:settings=replace(settings,force_mock=True)
    if args.import_results:
        for experiment in ['sweep','certificate']:
            directory=args.directory/experiment
            if (directory/'shortlist-bank.json').exists():import_results(directory,settings,load_bank(args.directory/'bank.json'))
        print(f'Set BLINDSPOT_BANK={args.directory / "bank.json"}; run python run.py.');return
    if not args.mock and not args.build_only:
        if settings.mode!='live' or settings.model!='muse-spark-1.3-contributor':p.error('Set META_API_KEY, META_MODEL=muse-spark-1.3-contributor and BLINDSPOT_MOCK=false, or use --mock.')
    if not args.no_plots and not args.build_only:
        try:import matplotlib
        except ImportError:p.error('Install requirements-analysis.txt before starting, or pass --no-plots.')
    settings=replace(settings,max_completion_tokens=16384,retries=0,timeout=max(360,settings.timeout),concurrency=args.concurrency)
    asyncio.run(execute(args.directory.resolve(),settings,args))


if __name__=='__main__':main()
