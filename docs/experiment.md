# Interpreting a Blindspot run

Blindspot implements two experiments together: controlled local errors, and
prospective predictions by the same verifier about its ability to detect them.
The unit of analysis is a **fixed problem–step–mutation cell**. Repeated trials
resample that cell; they are not different mathematical mistakes.

## Protocol

1. Load an original synthetic problem and reference solution.
2. Deterministically edit one mathematical AST site in a suitable step.
3. Accept controls only if the difference simplifies to zero. Accept errors only
   if an exact counterexample establishes non-identity within the stated domain.
4. Ask the verifier for a percentage forecast, without revealing the edited
   expression. Forecast equivalent controls as rejection probabilities.
5. Save **all** forecasts before beginning any trial. The event log records this barrier.
6. Issue independent, stateless verification requests with only the original
   problem, correct earlier steps, and the candidate step.
7. Preserve each verdict, its brief explanation, confidence, raw response,
   timing and provider metadata. Aggregate usable classifications only.

This is prefix checking. It does not test a model's ability to recover from an
earlier mistake, reconcile inconsistent later working, or grade a whole solution.
The candidate is presented without its mutation type or correct reference RHS.

## Quantities

For a cell with N usable trials and R invalid verdicts:

- Observed rejection probability is R/N.
- On errors, this is detection probability. On controls, it is the false-positive rate.
- Calibration gap is forecast − R/N; absolute error is its absolute value.
- The UI displays probabilities as percentages and gaps as percentage points.
- Wilson intervals use N usable classifications. No interval is shown if N = 0.
- Verifier `confidence` is confidence in a particular verdict. It is never used
  as the earlier forecast or as a weight in the detection fraction.

An error cell with forecast 92% and one rejection in five trials has observed
detection 20%, gap +72 percentage points and absolute error 72 percentage points.
Its interval is wide; five observations are not precise evidence of the true rate.
The seeded version of this example is explicitly simulated.

## What is established by the mathematics

The checks establish scalar identity or non-identity for the displayed claims,
under the encoded assumptions. A counterexample proves that a claimed identity
is false; it does not prove that its two sides differ at every parameter value.
Some candidates coincide with the reference at isolated special points.

The checker does not infer full physical meaning from arbitrary prose. The
dataset is deliberately small and authored around explicit, fixed claims.
Generic “change a constant” errors are excluded when arbitrary constants can be
renamed without changing a solution family. The amplitude conventions in the
measurement problem are fixed by the specified Lüders projection and positive
normalisation multiplier. No arbitrary expression uploads are accepted.

These are deliberately limited deterministic edits. Some are easy to reject on
dimensional, sign or range grounds. Controls such as multiplication by 2/2 are
simple. The map should not be described as representative of naturally occurring
student errors or of a general physics benchmark.

## Limits on interpretation

- Eight problems and a few trials are a hackathon pilot, not a general reliability estimate.
- A forecast describes a mutation category, whereas the empirical cell contains
  one deterministic instance. This category-to-instance mismatch can create a gap.
- The task statement, wording, prompt, temperature and reasoning budget affect results.
- Separate HTTP requests and absent conversational history reduce dependence;
  provider-side independence and stable model weights are not guaranteed.
- Cells share problems and often mathematical structure. They are not independent
  problem samples; multiplying cells by trials does not increase the number of problems.
- The mean absolute gap gives each sampled error cell equal weight. With partial
  runs, different cells can have different denominators. Inspect failure counts.
- Discarding unusable responses can introduce selection bias. Exports preserve
  those failures so they can be reported or analysed under another policy.
- A prominent overconfident cell can be cherry-picked from many cells. Use new
  problem families and prespecified evaluation rules before making a general claim.
- Matching observed success rates could arise from general knowledge of task
  difficulty. This MVP does not establish privileged introspective information
  or self-awareness, nor compare self-prediction against a peer predictor.
- Live API validation still requires a user-supplied Meta key with model access.

## Provenance

The supplied workbook was inspected, including the eight requested archetypes.
The new questions change functions, differential equations, boundary conditions,
constitutive model, state coefficients or measurement system. The reference
solutions were derived afresh and independently verified. The source questions,
student data and historical GPT-4 responses are not distributed in this repository.

The implementation deliberately ends at controlled perturbation and prospective
self-prediction. A broader study would need additional original problems,
stronger controls and a prespecified statistical analysis.
