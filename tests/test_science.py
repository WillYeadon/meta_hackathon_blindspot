import copy
import json
import sympy as s
from blindspot.perturbations import catalog, generate, replace_at
from blindspot.maths import parse, namespace, validate_pair
from blindspot.prompts import verifier_messages, prediction_messages
from blindspot.metrics import aggregate


def test_reference_physics_independently():
    """Derive ground truth from definitions, rather than rechecking stored constants."""
    problems = {p["id"]: p for p in catalog()["problems"]}
    def rhs(pid, n):
        p = problems[pid]
        return parse(p["steps"][n-1]["expr"], p)
    def equal(a, b):
        assert s.simplify(a-b) == 0
    p = problems["gaussian"]; x, b = namespace(p)["x"], namespace(p)["beta"]
    integral = s.integrate(s.exp(-2*b*x*x), (x, -s.oo, s.oo))
    equal(rhs("gaussian", 1), integral)
    amplitude = rhs("gaussian", 2)
    equal(amplitude**2 * integral, 1)
    equal(rhs("gaussian", 3), s.integrate(x*amplitude**2*s.exp(-2*b*x*x), (x,-s.oo,s.oo)))
    moment = s.integrate(x*x*amplitude**2*s.exp(-2*b*x*x), (x,-s.oo,s.oo))
    equal(rhs("gaussian", 4), moment)
    equal(rhs("gaussian", 5), s.sqrt(moment))

    p = problems["nonlinear-ode"]; env=namespace(p); x,y,C=env["x"],env["y"],env["C"]
    equal(rhs(p["id"],1), 3*x*x+2*x)
    equal(s.diff(rhs(p["id"],2),y), y**-2)
    equal(s.diff(rhs(p["id"],3),x), 3*x*x+2*x)
    equal(rhs(p["id"],3).subs({x:0,C:rhs(p["id"],4)}), -1)
    sol=rhs(p["id"],5)
    equal(s.diff(sol,x), (3*x*x+2*x)*sol**2); equal(sol.subs(x,0),1)
    # The denominator stays positive throughout the specified interval.
    assert 1-s.Rational(1,16)-s.Rational(1,64)>0

    p=problems["euler-cauchy"]; e=namespace(p); x,r=e["x"],e["r"]
    operator=lambda f:x*x*s.diff(f,x,2)-2*x*s.diff(f,x)-4*f
    equal(rhs(p["id"],1), operator(x**r)/x**r)
    equal(rhs(p["id"],2), rhs(p["id"],1))
    equal(operator(rhs(p["id"],3)),0)
    solution=rhs(p["id"],5)
    equal(operator(solution),0); equal(solution.subs(x,1),3); equal(s.diff(solution,x).subs(x,1),2)
    constants=s.solve([e["C1"]+e["C2"]-3,4*e["C1"]-e["C2"]-2],[e["C1"],e["C2"]])
    equal(rhs(p["id"],4),constants[e["C1"]])

    p=problems["viscoelastic"]; e=namespace(p); t,w,G,eta=e["t"],e["omega"],e["G"],e["eta"]
    ansatz=e["A"]*s.cos(w*t)+e["B"]*s.sin(w*t)
    balance=s.expand(eta*s.diff(ansatz,t)+G*ansatz)
    equal(rhs(p["id"],1),balance.coeff(s.cos(w*t)))
    equal(rhs(p["id"],2),balance.coeff(s.sin(w*t)))
    solved=s.solve([rhs(p["id"],1)-e["sigma0"],rhs(p["id"],2)],[e["A"],e["B"]])
    equal(rhs(p["id"],3),solved[e["A"]]); equal(rhs(p["id"],4),solved[e["B"]])
    strain=rhs(p["id"],5)
    equal(eta*s.diff(strain,t)+G*strain,e["sigma0"]*s.cos(w*t))

    p=problems["radial-mode"]; e=namespace(p); r,a=e["r"],e["a"]
    radial=r*r*s.exp(-r/(3*a)); q=r*r*radial**2
    equal(rhs(p["id"],1),q)
    equal(rhs(p["id"],2),s.diff(q,r)/q)
    mode=rhs(p["id"],3)
    equal(s.diff(q,r).subs(r,mode),0)
    equal(rhs(p["id"],4),s.diff(s.log(q),r,2).subs(r,mode))
    assert rhs(p["id"],4).is_negative
    equal(s.limit(q,r,0),0); equal(s.limit(q,r,s.oo),0)

    p=problems["angular-momentum"]; e=namespace(p); x,y,h=e["x"],e["y"],e["hbar"]
    psi=(x-s.I*y)**3
    equal(rhs(p["id"],1),s.diff(psi,x)); equal(rhs(p["id"],2),s.diff(psi,y))
    orbital=x*s.diff(psi,y)-y*s.diff(psi,x)
    equal(rhs(p["id"],3),orbital); equal(rhs(p["id"],4),-s.I*h*orbital)
    equal(rhs(p["id"],5)*psi,-s.I*h*orbital)

    p=problems["well-energy"]; e=namespace(p); L,m,h=e["L"],e["m"],e["hbar"]; x=s.Symbol("x",real=True)
    integral=s.integrate(s.sin(s.pi*x/L)**6,(x,0,L))
    equal(rhs(p["id"],1),integral); equal(rhs(p["id"],2)**2*integral,1)
    psi=rhs(p["id"],2)*s.sin(s.pi*x/L)**3
    for n,step in [(1,3),(3,4)]:
        coefficient=s.integrate(s.sqrt(2/L)*s.sin(n*s.pi*x/L)*psi,(x,0,L))
        equal(rhs(p["id"],step),coefficient)
    energy=s.integrate(s.diff(psi,x)**2,(x,0,L))*h*h/(2*m)
    equal(rhs(p["id"],5),energy)

    p=problems["sequential"]
    psi=s.Matrix([s.sqrt(2),s.I*s.sqrt(3),s.sqrt(5)])/s.sqrt(10)
    projected=s.diag(1,1,0)*psi
    first=(projected.conjugate().T*projected)[0]
    equal(rhs(p["id"],1),first); equal(rhs(p["id"],2),1/s.sqrt(first))
    amplitude=(projected/s.sqrt(first))[1]
    equal(rhs(p["id"],3),amplitude)
    conditional=s.conjugate(amplitude)*amplitude
    equal(rhs(p["id"],4),conditional); equal(rhs(p["id"],5),first*conditional)


def test_every_perturbation_has_exact_evidence_and_changes_one_step():
    for p in catalog()["problems"]:
        original=copy.deepcopy(p)
        cells,_=generate(p)
        assert p==original
        assert 4<=len(p["steps"])<=6
        assert {c["step"] for c in cells if c["is_control"]}==set(range(1,len(p["steps"])+1))
        for c in cells:
            a=parse(c["original"]["expr"],p); b=parse(c["candidate"]["expr"],p)
            proof=validate_pair(a,b,p,c["is_control"])
            assert proof and proof["kind"]==c["validation"]["kind"]
            before=copy.deepcopy(p["steps"]); after=copy.deepcopy(before)
            after[c["step"]-1]=c["candidate"]
            assert all(before[i]==after[i] for i in range(len(before)) if i!=c["step"]-1)
            for key in ("text","lhs","label","operation","index"):
                assert c["candidate"][key]==c["original"][key]


def test_uncertain_and_equivalent_errors_are_rejected():
    p=catalog()["problems"][0]; x=namespace(p)["x"]
    assert validate_pair(x, x+0,p,False) is None
    assert validate_pair(x, x+1,p,True) is None
    assert validate_pair(x,s.zoo,p,False) is None


def test_no_false_error_labels_from_arbitrary_constant_reparameterisation():
    for p in catalog()["problems"]:
        if p["id"] in {"nonlinear-ode","euler-cauchy"}:
            assert p["steps"][2]["mutation_scope"]=="arbitrary_constant_family"
            assert all(c["is_control"] for c in p["cells"] if c["step"]==3)


def test_prefix_truncation_and_prediction_blinding():
    for p in catalog()["problems"]:
        for c in p["cells"]:
            v=json.loads(verifier_messages(p,c)[1]["content"])
            pred=json.loads(prediction_messages(p,c,5,1,"low")[1]["content"])
            assert len(v["previous_steps"])==c["step"]-1
            assert v["candidate_step"]["claim"].endswith(c["candidate"]["latex"])
            assert len(pred["correct_steps"])==c["step"]
            assert set(pred["planned_change"])=={"step","description"}
            assert not any(key in v for key in ("type","is_control","validation","mutation","prediction"))
            # Changing ONLY the candidate must not affect the prediction prompt at all.
            changed=copy.deepcopy(c); changed["candidate"]["latex"]="SECRET_MUTATION_TOKEN"
            assert prediction_messages(p,changed,5,1,"low")==prediction_messages(p,c,5,1,"low")
            # Future solution edits must have no effect on either prompt.
            changed_problem=copy.deepcopy(p)
            for future in changed_problem["steps"][c["step"]:]:
                future["latex"]="FUTURE_LEAK"
            assert verifier_messages(changed_problem,c)==verifier_messages(p,c)
            assert prediction_messages(changed_problem,c,5,1,"low")==prediction_messages(p,c,5,1,"low")


def test_calibration_and_failure_denominators():
    r={"prediction":{"status":"ok","probability_percent":92},
       "trials":[{"status":"ok","valid":False}]+[{"status":"ok","valid":True}]*4+[{"status":"error"}]}
    metrics=aggregate(r,False)
    assert metrics["observed"]==0.2
    assert abs(metrics["calibration_gap"]-0.72)<1e-12
    assert metrics["failed_trials"]==1 and metrics["valid_trials"]==5
    assert metrics["wilson_95"][0]<0.2<metrics["wilson_95"][1]
    assert aggregate(r,True)["metric"]=="false_positive_rate"
    assert aggregate({},False)["observed"] is None
