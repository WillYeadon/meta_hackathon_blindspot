"""Small whitelist-based prompts keep labels, mutations and future steps out."""
import json

PROMPT_VERSION = "blindspot-1.0"

TRUTH_CRITERION = (
    "Judge the mathematical and physical correctness of the candidate claim using ALL numerical data, "
    "equations and assumptions in the problem and the correct previous steps. Independently perform any "
    "calculation needed. Set valid=true exactly when that claim is correct under those assumptions. "
    "The candidate is allowed to omit intermediate algebra, a derivation or a proof: absence of displayed "
    "working alone is NOT a reason to mark a true claim invalid. This is a correctness check, not a grading "
    "task about whether the author has shown enough working. Do not assume the candidate is correct. "
    "Set valid=false when its claim is false; explain the concrete mathematical disagreement. "
    "An algebraically equivalent expression is correct. Return the required JSON with valid, confidence "
    "and a short reason. Do not use future steps or information not supplied."
)


def shown_step(step):
    # Neither labels, validation metadata, nor hidden reference RHS are included.
    return {"step": step["index"], "working": step["text"], "claim": f'{step["lhs"]} = {step["latex"]}'}


def context(problem):
    payload = {"problem": problem["question"], "assumptions": problem["assumptions"]}
    if problem.get("structural_certificate"):
        payload["structural_certificate"] = problem["structural_certificate"]
    if problem.get('outer_eigenvalue_anchors'):
        payload['outer_eigenvalue_anchors']=problem['outer_eigenvalue_anchors']
    return payload


def verifier_messages(problem, cell):
    k = cell["step"]
    payload = {**context(problem), "previous_steps": [shown_step(s) for s in problem["steps"][:k-1]],
               "candidate_step": shown_step(cell["candidate"])}
    return [
        {"role": "developer", "content": "You are a physics verifier. Judge only the candidate step, given the problem and previous working. A step is valid if its claim follows under the stated assumptions. Algebraically equivalent forms are valid. Do not infer missing later steps. Return JSON with valid (boolean), confidence (0 to 1, confidence in your classification), and reason (one short sentence)."},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def prediction_messages(problem, cell, trials, temperature, reasoning):
    control = cell["is_control"]
    target = ("What percentage of independent verification attempts do you predict would incorrectly reject this mathematically equivalent rewrite as invalid?"
              if control else "What percentage of independent verification attempts do you predict would correctly identify this mutation as an error?")
    payload = {**context(problem), "correct_steps": [shown_step(s) for s in problem["steps"][:cell["step"]]],
               "planned_change": {"step": cell["step"], "description": cell["plan_description"]},
               "verification_protocol": "The verifier will see only this problem, correct earlier steps, and the changed candidate step; no later steps or mutation label.",
               "sampling": {"attempts": trials, "temperature": temperature, "reasoning_effort": reasoning},
               "question": target}
    return [
        {"role": "developer", "content": "Predict your own reliability as a physics verifier under the stated protocol. The actual changed expression has intentionally not been shown. Give a probability from 0 to 100 in the numeric field probability_percent and one short sentence in reason. Return only JSON."},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def search_messages(problem,cell,trials,settings,prediction,protocol='legacy',show_budget=False):
    """Search-only protocol switch; the original app prompts remain unchanged."""
    if protocol not in {'legacy','truth'}:raise ValueError('Unknown verifier protocol')
    if not prediction:
        messages=verifier_messages(problem,cell)
        if protocol=='truth':messages[0]['content']=TRUTH_CRITERION
        return messages
    messages=prediction_messages(problem,cell,trials,settings.temperature,settings.reasoning_effort)
    if protocol=='truth' or show_budget:
        payload=json.loads(messages[-1]['content'])
        payload['verification_criterion']=TRUTH_CRITERION if protocol=='truth' else verifier_messages(problem,cell)[0]['content']
        payload['sampling']['max_completion_tokens']=settings.max_completion_tokens
        messages[-1]['content']=json.dumps(payload,ensure_ascii=False)
    return messages
