"""Deterministic, single-site mathematical edits; no model-generated errors."""
import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path
import sympy as sp
from .maths import parse, representation, validate_pair

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "problems.json"
TYPES = [
    ("sign", "Sign flip"), ("coefficient", "Coefficient"), ("dropped_term", "Dropped term"),
    ("exponent", "Exponent"), ("operator", "Operator swap"), ("denominator", "Denominator"),
    ("calculus", "Calculus result"), ("equivalent", "Equivalent control")]
LABELS = dict(TYPES)
PLAN_DESCRIPTIONS = {
    "sign": "Reverse the sign of one term or coefficient in the result.",
    "coefficient": "Change one multiplicative numerical factor in the result.",
    "dropped_term": "Omit one additive term from the result.",
    "exponent": "Change one exponent in the result.",
    "operator": "Replace one addition operation in the result with multiplication.",
    "denominator": "Change one numerical factor in a denominator of the result.",
    "calculus": "Introduce a factor-of-two error in the result of an integration or differentiation.",
    "equivalent": "Rewrite the result using a domain-preserving arithmetic identity, without changing its value."
}


def walk(expr, path=()):
    yield path, expr
    for i, child in enumerate(expr.args):
        yield from walk(child, path + (i,))


def replace_at(expr, path, replacement):
    """Change exactly one AST site; duplicate subexpressions elsewhere are untouched."""
    if not path:
        return replacement
    args = list(expr.args)
    args[path[0]] = replace_at(args[path[0]], path[1:], replacement)
    return expr.func(*args, evaluate=False)


def proposals(expr, operation):
    # Edit the first additive term if there is one; otherwise flip the result.
    sign_path = (0,) if expr.is_Add else ()
    old = expr.args[0] if expr.is_Add else expr
    yield "sign", sign_path, old, -old, "Reverse the sign of this term."
    coefficient = next(((p, n) for p, n in walk(expr) if n.is_Rational and n not in (0, 1, -1)
                        and (not p or not _node(expr, p[:-1]).is_Pow)), None)
    if coefficient:
        p, n = coefficient
        yield "coefficient", p, n, 2*n, "Double one numerical coefficient."
    else:
        yield "coefficient", (), expr, 2*expr, "Change the implicit overall factor from 1 to 2."
    additive = next(((p, n) for p, n in walk(expr) if n.is_Add and len(n.args) >= 2), None)
    if additive:
        p, n = additive
        yield "dropped_term", p + (0,), n.args[0], sp.Integer(0), "Replace one additive term by zero."
        yield "operator", p, n, sp.Mul(*n.args, evaluate=False), "Replace this addition node with multiplication."
    power = next(((p, n) for p, n in walk(expr) if n.is_Pow and n.exp.is_Rational and n.exp != -1), None)
    if power:
        p, n = power
        yield "exponent", p + (1,), n.exp, n.exp+1, "Increase one exponent by one."
    denominator = next(((p, n) for p, n in walk(expr) if n.is_Rational and n.q > 1
                        and (not p or not _node(expr, p[:-1]).is_Pow)), None)
    if denominator:
        p, n = denominator
        yield "denominator", p, n, sp.Rational(n.p, n.q+1), "Increase this numerical denominator by one."
    if operation in {"integration", "differentiation"}:
        yield "calculus", (), expr, expr/2, "Omit a factor of two from the calculus result."
    # Unevaluated form retains a visibly different spelling, including for zero.
    if expr == 0:
        control = sp.Add(sp.Integer(1), sp.Integer(-1), evaluate=False)
    else:
        control = sp.Mul(sp.Integer(2), expr, sp.Pow(sp.Integer(2), -1, evaluate=False), evaluate=False)
    yield "equivalent", (), expr, control, "Multiply the expression by 2/2 (or write zero as 1−1)."


def _node(expr, path):
    for part in path:
        expr = expr.args[part]
    return expr


def generate(problem):
    cells, rejected = [], []
    for step in problem["steps"]:
        original = parse(step["expr"], problem)
        seen = []
        for kind, path, before, after, note in proposals(original, step["operation"]):
            if step.get("mutation_scope") == "arbitrary_constant_family" and kind != "equivalent":
                rejected.append({"step": step["index"], "type": kind, "reason": "A non-identical expression may encode the same family after renaming an arbitrary constant."})
                continue
            candidate = replace_at(original, path, after)
            control = kind == "equivalent"
            proof = validate_pair(original, candidate, problem, control)
            if not proof or (not control and any(sp.simplify(candidate - previous) == 0 for previous in seen)):
                rejected.append({"step": step["index"], "type": kind, "reason": "Not provably different, or duplicates another accepted mutation."})
                continue
            if not control:
                seen.append(candidate)
            rendered = representation(candidate)
            cells.append(dict(id=f'{problem["id"]}:{step["index"]}:{kind}', problem_id=problem["id"],
                              step=step["index"], type=kind, type_label=LABELS[kind], is_control=control,
                              original=copy.deepcopy(step), candidate={**copy.deepcopy(step), **rendered},
                              mutation=dict(ast_path=list(path), before=str(before), after=str(after),
                                            before_latex=sp.latex(before), after_latex=sp.latex(after),
                                            description=note, rule=kind),
                              plan_description=PLAN_DESCRIPTIONS[kind], validation=proof))
    return cells, rejected


@lru_cache(maxsize=1)
def catalog(bank_path=None):
    if bank_path:
        from .semantic_bank import load_bank
        return load_bank(bank_path)
    raw = DATA_PATH.read_bytes()
    data = json.loads(raw)
    data["source_hash"] = hashlib.sha256(raw).hexdigest()
    data["mutation_types"] = [{"id": key, "label": label} for key, label in TYPES]
    for p in data["problems"]:
        p["cells"], p["rejected"] = generate(p)
        p["cell_count"] = len(p["cells"])
    # The identity covers generated candidates too, so an engine edit cannot
    # attach old results to a new mutation merely because its cell ID is stable.
    data["hash"] = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return data
