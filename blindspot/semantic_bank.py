"""Original, parameterised physics examples with exact construction oracles.

These are hypotheses about verifier difficulty, not established blind spots.
No HLE/TheoPhysEval questions, answers, or model traces are used.
"""
import copy
import hashlib
import json
import random
import sympy as s
from .maths import representation, validate_pair, parse

VERSION = 'semantic-1.0'


def show(x):
    return s.sstr(x)


def rotation(rng):
    a, b = rng.choice([(3,4),(5,12),(8,15),(7,24)])
    h = s.sqrt(a*a+b*b)
    return s.Matrix([[a/h,-b/h],[b/h,a/h]])


def make_case(family, number, rng):
    """Return question, assumptions, two valid prefix steps, and one target."""
    if family == 'postselection':
        v=s.Matrix([rng.randint(1,9),rng.randint(1,9),rng.randint(1,9)])
        u=rotation(rng)[:,0]; n=(v.T*v)[0]; post=v[:2,0]
        correct=s.cancel((u.T*post)[0]**2/n)
        wrong=s.cancel(sum(u[i]**2*v[i]**2 for i in range(2))/n)
        question=f'A three-state system starts in psi=v/sqrt(v^T v), v={show(v.T)}. First measure the projector P=diag(1,1,0) using the Lüders instrument, then the rank-one projector onto u=({u[0]}, {u[1]}, 0)^T. Find the joint probability of yes then yes.'
        assumptions='Real amplitudes; ideal projective measurements; no environmental dephasing between measurements.'
        prefix=[('Initial norm','The initial state is normalised using the squared norm of v.','v^T v',n),('First outcome','The probability of the first yes outcome is the population in the projected subspace.','p_1',sum(x*x for x in post)/n)]
        target=('Joint probability','Applying the specified measurement instrument and then the second projector gives the joint probability.','p_{12}',correct)
        label='Lost postselection coherence'; mechanism='Replace a degenerate Lüders projection by an incoherent mixture of its basis states.'
        oracle={'method':'squared coherent amplitude versus sum of squared amplitudes','v':list(v),'u':list(u),'norm':n}
    elif family == 'gram_metric':
        n=rng.choice([3,4,5]); T=s.eye(n)
        for i in range(n):
            for j in range(i+1,n): T[i,j]=s.Rational(rng.randint(-3,3),rng.randint(2,5))
        T[0,0]=2; E=s.diag(*[rng.randint(1,12) for _ in range(n)])
        G=T.T*T; H=T.T*E*T; c=s.Matrix([rng.randint(1,5) for _ in range(n)])
        numerator=(c.T*H*c)[0]; denominator=(c.T*G*c)[0]
        correct=numerator/denominator; wrong=numerator/(c.T*c)[0]
        question=f'In a linearly independent nonorthogonal basis, the overlap matrix is G={show(G)}, Hamiltonian matrix elements H_ij=<b_i|H|b_j> form H={show(H)}, and the unnormalised coefficient vector is c={show(c.T)}. Compute the energy expectation of the normalised state.'
        assumptions='All entries are exact; the overlap matrix is positive definite. H denotes matrix elements, not the coefficient-space action G^(-1)H.'
        prefix=[('Covariant matrix','The Hamiltonian numerator follows by the coefficient contraction.','c^T H c',numerator),('Coefficient length','The ordinary coefficient-space Euclidean norm is as follows.','c^T c',(c.T*c)[0])]
        target=('Energy expectation','Normalising the state and evaluating its energy gives this value.','E',correct)
        label='Wrong inner-product metric'; mechanism='Normalise nonorthogonal-basis coefficients with the Euclidean metric instead of their Gram matrix.'
        oracle={'method':'Rayleigh quotient in physical orthonormal coordinates','physical_vector':list(T*c),'physical_energies':list(E.diagonal()),'numerator':numerator,'norm':denominator}
    elif family == 'near_degeneracy':
        n=4; U=s.eye(n)
        for i,j in [(0,1),(1,2),(2,3),(0,3),(0,2)]:
            R=s.eye(n); r=rotation(rng)
            for a,ia in enumerate([i,j]):
                for b,ib in enumerate([i,j]): R[ia,ib]=r[a,b]
            U=U*R
        a=s.Integer(rng.randint(3,9)); eps=s.Rational(1,rng.randint(20,250)); b=a+rng.randint(3,8)
        D=s.diag(0,a-eps,a+eps,b); H=U*D*U.T
        correct=2*eps; wrong=s.Integer(0)
        question=f'The exact real symmetric matrix H={show(H)} describes four coupled modes. In ascending order its eigenvalues are lambda_0 through lambda_3. Compute lambda_2-lambda_1, and in particular determine whether these two middle modes are exactly degenerate.'
        assumptions='Use the exact rational entries; near equality is not exact degeneracy. No additional symmetry is assumed.'
        prefix=[('Trace invariant','The trace fixes the sum of the four eigenvalues.','Tr(H)',s.trace(H)),('Quadratic invariant','The squared trace invariant is computed directly from the matrix.','Tr(H^2)',s.trace(H*H))]
        target=('Middle spectral gap','Diagonalisation of the exact matrix gives the middle spectral gap.','lambda_2-lambda_1',correct)
        label='Unsupported exact degeneracy'; mechanism='Infer exact degeneracy of two nearby modes without establishing a symmetry that enforces it.'
        oracle={'method':'exact orthogonal similarity H=U D U^T','U':U.tolist(),'spectrum':list(D.diagonal()),'H':H.tolist()}
    elif family == 'radial_measure':
        r=s.Symbol('r',positive=True); ell=rng.randint(1,5); degree=rng.randint(1,3); q=s.Rational(rng.randint(1,5),rng.randint(2,7)); beta=s.Rational(rng.randint(2,6),rng.randint(1,3)); moment=rng.choice([1,2])
        poly=s.Poly(s.expand(r**(2*ell)*(1-q*r)**(2*degree)),r)
        def integral(k):return s.factor(sum(coef*s.factorial(power[0]+k)/(2*beta)**(power[0]+k+1) for power,coef in poly.terms()))
        correct=integral(moment+2)/integral(2); wrong=integral(moment)/integral(0)
        question=f'A three-dimensional central-potential wavefunction has radial amplitude R(r)=N*r^{ell}*(1-({q})*r)^{degree}*exp(-({beta})*r), with angular factor Y normalised to integral |Y|^2 dOmega=1. Calculate <r^{moment}>. R is the radial amplitude, not the reduced function rR.'
        assumptions='r >= 0; dimensionless atomic units; N is fixed by the full three-dimensional norm.'
        prefix=[('Angular norm','The normalised angular factor separates from the radial integration.','integral |Y|^2 dOmega',s.Integer(1)),('Radial polynomial','Before the exponential and N squared are included, the squared radial factor expands to this polynomial.','|R/N|^2 exp(2 beta r)',poly.as_expr())]
        target=('Radial moment','Normalising the wavefunction and forming the requested radial moment gives this result.','<r^'+str(moment)+'>',correct)
        label='Wrong physical measure'; mechanism='Use the measure dr for a three-dimensional radial amplitude, renormalising consistently with that wrong measure.'
        oracle={'method':'integrate each monomial against exp(-2 beta r)','ell':ell,'degree':degree,'q':q,'beta':beta,'moment':moment,'physical_norm_integral':integral(2)}
    elif family == 'quench':
        w0,w1,w2=map(s.Integer,rng.sample(range(1,10),3)); R=rotation(rng); c,t=R[0,0],R[1,0]
        # q(0)=1, qdot(0)=-i*w0; intermediate phase has cos=c, sin=t.
        q=c-s.I*w0/w1*t; qdot=-w1*t-s.I*w0*c
        correct=s.simplify((q+s.I*qdot/w2)/2); wrong=s.simplify((q+s.I*qdot*w2/w1**2)/2)
        question=f'A unit-mass oscillator has q(0)=1 and qdot(0)=-i*{w0}. At t=0 its frequency changes instantaneously from {w0} to {w1}. At t=T it changes from {w1} to {w2}, with cos({w1}T)={c} and sin({w1}T)={t}. Write q(t)=A exp(-i*{w2}*(t-T))+B exp(i*{w2}*(t-T)) for t>T and compute A.'
        assumptions='Complex solutions encode two real solutions. Frequency changes add no impulsive force: q and qdot are continuous at each temporal interface.'
        prefix=[('Intermediate propagation','The displacement just before the second frequency change is obtained from the first oscillator propagator.','q(T^-)',q),('Velocity propagation','The corresponding velocity is obtained by differentiating the propagated displacement.','qdot(T^-)',qdot)]
        target=('Outgoing amplitude','Matching displacement and velocity at the second temporal interface gives this positive-frequency amplitude.','A',correct)
        label='Wrong interface matching'; mechanism='Use a reciprocal frequency factor in temporal matching, as if the conserved quantity came from a spatial interface.'
        oracle={'method':'solve A+B=q and -i*w2*(A-B)=qdot','w0':w0,'w1':w1,'w2':w2,'cos':c,'sin':t,'q':q,'qdot':qdot}
    elif family == 'degenerate_perturbation':
        U=rotation(rng); u=U[:,0]; low=s.Integer(rng.randint(1,4)); high=low+rng.randint(1,5); W=U*s.diag(low,high)*U.T
        energies=[s.Integer(rng.randint(5,15)) for _ in range(rng.randint(2,5))]
        couplings=[s.Matrix([rng.randint(1,5),rng.randint(1,5)]) for _ in energies]
        correct=-sum((u.T*v)[0]**2/e for v,e in zip(couplings,energies))
        wrong=-sum(sum(u[j]**2*v[j]**2 for j in range(2))/e for v,e in zip(couplings,energies))
        question=f'Consider H(g)=H0+gV. H0 has an exactly degenerate zero-energy pair |1>,|2>, and additional orthonormal states with energies {show(energies)}. In the zero-energy subspace PVP={show(W)}. Couplings (<1|V|j>,<2|V|j>) to the additional states are respectively {show([list(v) for v in couplings])}. Find the coefficient of g^2 in the eigenvalue branch with the lower first-order shift.'
        assumptions='All matrices are real symmetric; g is perturbatively small. V has no other entries. The requested coefficient is the Taylor-series coefficient, not the second derivative.'
        prefix=[('First-order splitting','Diagonalising PVP fixes the lower first-order energy coefficient.','E^(1)',low),('Chosen state','A normalised zeroth-order eigenvector in the degenerate subspace is as follows.','u',u)]
        target=('Second-order shift','Summing the virtual transitions to states outside the degenerate subspace gives the second-order coefficient.','E^(2)',correct)
        label='Incoherent virtual transitions'; mechanism='Sum squared basis-component couplings instead of squaring each coherent matrix element from the correctly rotated degenerate state.'
        oracle={'method':'degenerate perturbation theory after diagonalising PVP','u':list(u),'energies':energies,'couplings':[list(v) for v in couplings]}
    elif family == 'noncommuting':
        a,b=map(s.Integer,rng.sample(range(1,80),2)); A=s.Matrix([[a,0],[0,-a]]); B=s.Matrix([[0,b],[b,0]]); t=s.Symbol('t',real=True)
        def exp4(M):return sum(((-s.I*M*t)**k/s.factorial(k) for k in range(5)),s.zeros(2))
        exact=s.expand(exp4(A+B)[1,0]); split=s.expand((exp4(A)*exp4(B))[1,0])
        correct=s.expand(exact*s.conjugate(exact)).coeff(t,4); wrong=s.expand(split*s.conjugate(split)).coeff(t,4)
        question=f'A two-level system evolves with the time-independent Hamiltonian H=A+B, where A={show(A)} and B={show(B)}. It starts in |0>=(1,0)^T. Find the coefficient of t^4 in the small-t expansion of |<1|exp(-iHt)|0>|^2.'
        assumptions='hbar=1; simultaneous evolution under A+B throughout the interval; |1>=(0,1)^T. The coefficient is not divided by 4!.'
        prefix=[('Initial transition','The transition probability at t=0 vanishes.','P(0)',s.Integer(0)),('Leading transition','The coefficient of t squared follows from the off-diagonal Hamiltonian matrix element.','[t^2]P',b*b)]
        target=('Quartic transition','Expanding the time-evolution operator to the required order gives the quartic coefficient.','[t^4]P',correct)
        label='Noncommuting composition'; mechanism='Replace simultaneous evolution exp(-i(A+B)t) by the ordered product exp(-iAt)exp(-iBt), which agrees at leading order but not at the requested order.'
        oracle={'method':'Pauli-matrix solution b^2/(a^2+b^2)*sin(sqrt(a^2+b^2)*t)^2','a':a,'b':b}
    elif family == 'robin_boundary':
        x=s.Symbol('x',real=True); a=s.Integer(rng.randint(1,7)); b=s.Integer(rng.randint(1,12)); degree=rng.randint(2,4)
        f=1+a*x*(1-x)+b*x**degree*(1-x)**degree; norm=s.integrate(f*f,(x,0,1)); kinetic=s.integrate(s.diff(f,x)**2,(x,0,1))
        correct=s.cancel(-s.integrate(f*s.diff(f,x,2),(x,0,1))/norm); wrong=kinetic/norm
        question=f'On 0<=x<=1 consider L=-d^2/dx^2 with outward Robin boundary condition partial_n psi + {a} psi=0 at both endpoints. The real trial function is f(x)={show(s.expand(f))}. Compute <f,Lf>/<f,f>.'
        assumptions='Standard L2 inner product on [0,1]; f is in the stated operator domain; all coefficients and endpoints are exact.'
        prefix=[('Boundary values','Evaluation at the two endpoints gives equal boundary amplitudes.','f(0)=f(1)',s.Integer(1)),('State norm','The squared L2 norm is obtained by polynomial integration.','<f,f>',norm)]
        target=('Operator expectation','Evaluating the expectation of the specified operator on its stated domain gives this value.','<L>',correct)
        label='Discarded boundary contribution'; mechanism='Use only the bulk gradient-squared term after integration by parts, discarding the nonzero Robin boundary contribution.'
        oracle={'method':'direct polynomial integration of -f*f second derivative','f':f,'a':a,'norm':norm,'bulk':kinetic,'boundary':2*a}
    elif family == 'ivp_domain':
        x=s.Symbol('x',real=True); poles=sorted(rng.sample(range(2,30),3)); negatives=[-rng.randint(2,12),-rng.randint(13,30)]
        D=s.prod(1-x/s.Integer(r) for r in poles+negatives); D=s.expand(D)
        correct=s.Integer(poles[0]); wrong=s.Integer(poles[1])
        question=f'For the real IVP yprime(x)=-Dprime(x)*y(x)^2, y(0)=1, with D(x)={show(D)}, find the right endpoint of the maximal connected interval containing 0 on which the solution is finite.'
        assumptions='A classical real solution must be finite and differentiable throughout its interval. Continuation to a disconnected branch is not an extension through a pole.'
        prefix=[('Separation','Where the solution is finite and nonzero, its reciprocal has derivative Dprime.','d(1/y)/dx',s.diff(D,x)),('Integration constant','The initial condition fixes the reciprocal solution.','1/y',D)]
        target=('Maximal branch','The right endpoint of the branch connected to the initial condition is this value.','x_right',correct)
        label='Continuation across a pole'; mechanism='Choose a later positive pole after implicitly continuing across the first singularity of the IVP branch.'
        oracle={'method':'constructed simple roots of the reciprocal solution','positive_roots':poles,'negative_roots':negatives,'D':D}
    elif family == 'gaussian_coherence':
        q=s.Integer(rng.randint(2,15)); a=s.Integer(rng.randint(1,6)); b=s.Integer(rng.randint(1,6)); d=s.sqrt(s.log(q)); overlap=1/q
        # phi_(+/-d)=(pi)^(-1/4)*exp(-(x-/+d)^2/2); overlap=e^-d^2.
        norm=a*a+b*b+2*a*b*overlap
        second=(a*a+b*b)*(d*d+s.Rational(1,2))+a*b*overlap
        correct=s.simplify(second/norm); wrong=d*d+s.Rational(1,2)
        question=f'Let phi_c(x)=pi^(-1/4)*exp(-(x-c)^2/2) on the real line and psi=N*({a}*phi_d+{b}*phi_(-d)), where d=sqrt(log({q})). Find <x^2> in the normalised coherent pure state psi.'
        assumptions='Real positive amplitudes; log is the natural logarithm; use the standard dx inner product. The state is a coherent superposition.'
        prefix=[('Component norms','Each shifted Gaussian has unit norm.','<phi_d|phi_d>',s.Integer(1)),('Component moments','Each separate component has this second moment about the origin.','<x^2>_component',d*d+s.Rational(1,2))]
        target=('Superposition moment','Normalising the superposed wavefunction and integrating its density gives the second moment.','<x^2>',correct)
        label='Coherent state treated as mixture'; mechanism='Discard overlap terms in both the normalisation and the moment, producing a consistently normalised but incoherent mixture.'
        oracle={'method':'analytic Gaussian overlap and mixed second moment','a':a,'b':b,'d':d,'overlap':overlap,'norm':norm,'moment_numerator':second}
    elif family == 'euler_resonance':
        r=s.Integer(rng.randint(1,5));m=rng.randint(2,5);q=rng.randint(1,5);x=s.Symbol('x',real=True)
        correct=x**r*s.factorial(q)/s.factorial(q+m)*s.log(x)**(q+m)
        wrong=x**r*s.factorial(q)/s.factorial(q+m-1)*s.log(x)**(q+m-1)
        question=f'Let D=x*d/dx. For x>0 solve (D-{r})^{m} y=x^{r}*(log(x))^{q} by finding the particular solution with no terms x^{r}*(log(x))^j for 0<=j<{m}.'
        assumptions='log is the natural logarithm; the power on D-r means repeated operator composition. The excluded terms fix the homogeneous freedom.'
        prefix=[('Logarithmic coordinate','With t=log(x), the Euler operator becomes a derivative in t.','D t',s.Integer(1)),('Repeated root','The homogeneous characteristic root r has the stated algebraic multiplicity.','multiplicity',s.Integer(m))]
        target=('Resonant particular solution','Accounting for the forcing and the repeated root gives the following particular solution.','y_p(x)',correct)
        label='Resonance multiplicity lost';mechanism='Integrate one time too few after the logarithmic-coordinate change, losing one order of resonance while keeping a plausible power-log form.'
        oracle={'method':'apply the Euler operator repeatedly to the proposed function','r':r,'m':m,'q':q}
    elif family == 'viscoelastic':
        w=s.Integer(rng.randint(1,8));springs=list(map(s.Integer,rng.sample(range(2,25),4)));etas=list(map(s.Integer,rng.sample(range(2,25),3)))
        series=lambda a,b:s.cancel(a*b/(a+b))
        M1=series(springs[0],s.I*w*etas[0]);M2=series(springs[1],s.I*w*etas[1]);KV=springs[2]+s.I*w*etas[2]
        # Two Maxwell branches parallel, that subnetwork in series with KV;
        # finally an elastic spring in parallel with the resulting network.
        correct=s.cancel(springs[3]+series(M1+M2,KV))
        wrong=s.cancel(springs[3]+series(series(M1,M2),KV))
        question=f'A linear viscoelastic network has Maxwell branches M1=(spring {springs[0]} in series with dashpot {etas[0]}) and M2=(spring {springs[1]} in series with dashpot {etas[1]}). M1 and M2 are in parallel. This parallel subnetwork is in series with a Kelvin-Voigt branch (spring {springs[2]} in parallel with dashpot {etas[2]}). A final spring {springs[3]} is in parallel with the entire preceding assembly. Find its complex modulus at angular frequency {w}.'
        assumptions='Use exp(i omega t) convention, positive spring moduli and viscosities, equal reference cross-sections and lengths, small strain. All numerical parameters use one consistent unit system.'
        prefix=[('First Maxwell branch','The first isolated Maxwell branch has this complex modulus.','M_1',M1),('Second Maxwell branch','The second isolated Maxwell branch has this complex modulus.','M_2',M2)]
        target=('Network modulus','Combining the branches according to the stated connectivity gives the total complex modulus.','G^*(omega)',correct)
        label='Local network rule misapplied';mechanism='Treat the two parallel Maxwell branches as series elements at one internal node, then combine the remaining network correctly.'
        oracle={'method':'add stiffnesses in parallel and compliances in series','springs':springs,'viscosities':etas,'omega':w}
    else:
        raise ValueError(f'Unknown family: {family}')
    correct,wrong=s.simplify(correct),s.simplify(wrong)
    if s.simplify(correct-wrong)==0: return None
    pid=f'{family}-{number:04d}'
    p=dict(id=pid,title=f'{label} · {number+1}',topic=label,question=question,assumptions=assumptions,
           symbols={'r':{'positive':True},'x':{'real':True},'t':{'real':True}},witnesses=[{'x':'E'},{'x':'exp(2)'}] if family=='euler_resonance' else [{}],steps=[],family=family,
           provenance='Original synthetic construction; mechanism inspired by reasoning-error analysis, not a reused benchmark question.',
           oracle=json.loads(json.dumps(oracle,default=str)))
    for index,(name,text,lhs,expr) in enumerate(prefix+[target],1):
        p['steps'].append(dict(index=index,label=name,text=text,lhs=lhs,operation='semantic',**representation(expr)))
    original=p['steps'][-1]; p['cells']=[]
    equivalent=s.Add(correct/3,2*correct/3,evaluate=False) if correct!=0 else s.Add(1,-1,evaluate=False)
    for kind,title,value,control,note in [
        (family,label,wrong,False,mechanism),
        ('original_control','Original correct step',correct,True,'Keep the original correct step unchanged.'),
        ('equivalent','Equivalent rewrite',equivalent,True,'Rewrite the scalar as the sum of one third and two thirds of itself; preserve its value.')]:
        proof=validate_pair(correct,value,p,control)
        if not proof:raise ValueError(f'Failed exact validation: {pid} {kind}')
        p['cells'].append(dict(id=f'{pid}:3:{kind}',problem_id=pid,step=3,type=kind,type_label=title,is_control=control,
            original=copy.deepcopy(original),candidate={**copy.deepcopy(original),**representation(value)},
            mutation=dict(ast_path=[],before=show(correct),after=show(value),before_latex=s.latex(correct),after_latex=s.latex(value),description=note,rule=kind),
            plan_description=note,validation=proof))
    p['cell_count']=3;p['rejected']=[]
    return p


FAMILIES=['postselection','gram_metric','near_degeneracy','radial_measure','quench','degenerate_perturbation','noncommuting','robin_boundary','ivp_domain','gaussian_coherence','euler_resonance','viscoelastic']


def build_bank(per_family=40,seed=20261029,exclude_questions=None):
    if not 2 <= per_family <= 1000:raise ValueError('per-family must be 2–1000 (includes reserved parameter holdouts).')
    problems=[]
    for family in FAMILIES:
        rng=random.Random(f'{VERSION}:{seed}:{family}');seen=set(exclude_questions or []);accepted=[];attempts=0
        while len(accepted)<per_family:
            attempts+=1
            if attempts>per_family*100:raise ValueError(f'Insufficient unique cases for {family}; reduce per-family.')
            p=make_case(family,len(accepted),rng)
            if p is None or p['question'] in seen:continue
            seen.add(p['question']);accepted.append(p)
        holdout=max(1,per_family//5)
        for i,p in enumerate(accepted):p['split']='holdout' if i>=per_family-holdout else 'discovery'
        problems.extend(accepted)
    return dict(version=VERSION,seed=seed,problems=problems,description='Original semantic-error search bank; reserved parameters are never used for discovery.')


def load_bank(path):
    """Local trusted files only: SymPy parsing is not a sandbox."""
    from pathlib import Path
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if not data.get('problems'):raise ValueError('Bank has no problems.')
    types={};ids=set()
    for p in data['problems']:
        if p['id'] in ids:raise ValueError('Duplicate problem ID')
        ids.add(p['id'])
        for c in p['cells']:
            if c['original']!=p['steps'][c['step']-1]:raise ValueError('Candidate reference mismatch')
            proof=validate_pair(parse(c['original']['expr'],p),parse(c['candidate']['expr'],p),p,c['is_control'])
            if not proof:raise ValueError('Invalid candidate in trusted bank')
            types[c['type']]=c['type_label']
    data['mutation_types']=[dict(id=k,label=v) for k,v in types.items()]
    data['hash']=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return data
