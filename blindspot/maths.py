"""Only parse trusted, bundled expressions. No expression-evaluation API exists."""
import html
import sympy as sp


def namespace(problem):
    env = {name: sp.Symbol(name, **assumptions) for name, assumptions in problem["symbols"].items()}
    env.update({"I": sp.I, "pi": sp.pi, "oo": sp.oo})
    return env


def parse(expression, problem):
    return sp.sympify(expression, locals=namespace(problem))


def representation(expression):
    # Canonicalise only the machine expression. Unevaluated display trees retain
    # harmless rewrite spelling; sstr on such trees can omit needed parentheses.
    return {"expr": sp.sstr(sp.simplify(expression)), "display_ast": sp.srepr(expression), "latex": sp.latex(expression),
            "mathml": '<math xmlns="http://www.w3.org/1998/Math/MathML">' +
                      html.unescape(sp.printing.mathml(expression, printer="presentation")) + '</math>'}


def validate_pair(original, candidate, problem, control=False):
    """Accept identities, or exhibit an exact counterexample inside the stated domain.

    A counterexample proves non-identity, not inequality at every parameter value.
    Domain-preserving controls used here are arithmetic identities with constant,
    nonzero denominators. We never cancel a variable denominator to make a control.
    """
    if candidate.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
        return None
    difference = sp.simplify(original - candidate)
    if difference == 0:
        return {"kind": "symbolic_identity", "difference": "0"} if control else None
    if control:
        return None
    env = namespace(problem)
    for sample in problem["witnesses"]:
        substitutions = {env[key]: sp.sympify(value) for key, value in sample.items()}
        a, b = sp.simplify(original.subs(substitutions)), sp.simplify(candidate.subs(substitutions))
        delta = sp.simplify(a - b)
        if not delta.free_symbols and not delta.has(sp.nan, sp.zoo, sp.oo, -sp.oo) and delta.is_zero is False:
            return {"kind": "exact_counterexample", "substitutions": sample,
                    "reference_value": str(a), "candidate_value": str(b), "difference": str(delta)}
    return None
