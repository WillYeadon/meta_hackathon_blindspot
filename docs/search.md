# Searching for failures worth studying

The original attached run (Euler–Cauchy, fbde7626) rejected 80/80 erroneous
steps and accepted 25/25 equivalent controls. That is a ceiling result on that
run, not evidence that every possible perturbation is easy. Repeating those
same examples more often mainly estimates an already high detection rate.

The useful search target is a **plausible local inference whose validity depends
on the physical setup**, while retaining a trustworthy reference answer. The
model that writes a test does not have to be unable to solve it. Exact generation
and repeated empirical evaluation are separate tasks.

## New constructed mechanisms

These names describe how the generator creates an error. They are not a claim
that humans can reliably assign a universal taxonomy to unconstrained traces.
The prior paper's Section 3.5 and Appendix J motivate this direction, especially
unsupported degeneracy, use of an inappropriate physical invariant and reasoning
errors whose effects on a later answer are masked. No HLE question, trace,
annotation or reference-answer intervention is reused here.

| Mechanism | Incorrect inference | Independent reference |
| --- | --- | --- |
| Degenerate postselection | Dephase a Lüders projection and lose interference | Exact matrix projection and squared amplitude |
| Nonorthogonal basis | Use coefficient length instead of the Gram norm | Rayleigh quotient in orthonormal coordinates |
| Near-degenerate modes | Conclude exact degeneracy without a protecting symmetry | Rational orthogonal similarity with a known split spectrum |
| Radial moments | Use dr instead of r²dr and renormalise consistently | Monomial integrals against an exponential |
| Temporal quenches | Apply the wrong frequency factor at an interface | Continuity of displacement and velocity |
| Degenerate perturbation theory | Add incoherent component intensities for virtual transitions | Rotated-state matrix elements and energy denominators |
| Noncommuting evolution | Replace exp(A+B) by exp(A)exp(B) | Matrix series and an independent Pauli-matrix solution |
| Robin boundary conditions | Drop the surface contribution to an expectation | Direct integration of the differential operator |
| IVP domains | Continue through the first pole to a later branch | Exact roots of the reciprocal solution |
| Coherent Gaussians | Normalise a mixture instead of a superposition | Analytic overlap and cross-moment integrals |
| Euler resonance | Lose an order of a repeated characteristic root | Repeated application of the Euler differential operator |
| Viscoelastic topology | Apply a series rule at one parallel internal node | Independent stiffness/compliance composition |

Each case has two correct prefix steps and one target. The error replaces only
the target expression; its neutral prose is the same for errors and controls.
Both an unchanged correct step and an equivalent rewrite are tested. Exact
nonidentity is checked before the candidate is admitted. Physical derivations
are implemented as construction oracles and independently checked in tests;
symbolic nonidentity alone would not establish physical correctness.

More parameters broaden the search within these mechanisms. They do not create
hundreds of independent conceptual mechanisms. Long rational matrices can also
produce arithmetic difficulty rather than an interesting conceptual failure.
Review successful examples manually before drawing a scientific conclusion.

## Frozen stages

1. Build a reproducible bank. Reserve the last 20% of each deterministic family
   for unseen parameter testing. No outcomes enter generation or the split.
2. Record all discovery forecasts before any screening verdicts. Forecasts use
   the correct reference and a mechanism description, without the actual wrong
   expression. They predict rejection over the planned confirmation trial count.
3. Screen with two independent requests per cell. Every verifier sees only the
   problem, assumptions, correct prefix and candidate. No label, reference target,
   forecast, earlier verdict or future working is passed to it.
4. Freeze up to 20 cases that exhibit a miss, have complete screening samples,
   and have zero observed control rejections. Rank by observed miss rate, then
   stable ID; cap selections per family. Forecasts never determine selection.
5. Obtain 20 **new** verdicts for each selected error and each matched control.
   The forecast remains the one recorded before discovery. Report these results
   separately from the screening outcomes used to select the cases.
6. Test two previously unused parameter choices per selected family, including
   their correct controls, whether or not those holdouts show a miss. Their own
   forecasts are saved before their verification outcomes.

An empty shortlist is a valid outcome. Do not lower acceptance criteria after
seeing results and then describe that as the original protocol. To modify the
generator or settings, use another directory and record it as a new search.

Confirmation estimates performance on the selected instances. Parameter holdouts
test transfer within selected mechanisms. Neither estimates the prevalence of
blind spots across physics. Wilson intervals describe finite-trial uncertainty
for a cell, not uncertainty across the entire task distribution or correction
for searching many hypotheses. Repeated model requests are stateless samples,
not different models or different physics problems. Increase confirmation trials
in a new run if precise item-level estimates are needed.

The CSVs report usable and failed trials. Invalid JSON, refusals, truncation,
HTTP errors and unknown interrupted outcomes never count as an accepted error.
They are excluded from rates and retained for inspection. This missingness can
be systematic, so low usable counts or frequent truncation deserve investigation.
The local self-prediction experiment remains distinct from the earlier HLE
full-trace/answer-anchoring study; this is a design distinction, not a literature
search establishing priority or a guarantee of publishable novelty.

## Cost, rate limits and interruptions

Defaults use Contributor pricing checked on 29 October 2026:
input $0.10, cached input $0.002, output $0.20 per million tokens.
The documented Contributor request limit is 150 per minute per team; the runner
uses at most 100 starts per minute and the configured concurrency (default 3).
Other applications on the same team share the allowance. No tools/web search
are enabled in these requests. Contributor content may be used by Meta for
training; this bank consists of new synthetic examples.

Source: https://dev.meta.ai/docs/pricing-rate-limits

`--budget-usd 10` is a conservative **local guard**, not a provider-enforced
billing cap. Before sending, the ledger reserves an input allowance based on
UTF-8 size plus protocol overhead and the maximum completion budget. After a
usable response, it substitutes the cost calculated from reported usage.
Completion usage already includes reasoning tokens, which are not counted twice.
Unknown-cost failures retain the full reservation. Prices are configurable with
`--input-price`, `--cached-price` and `--output-price` (all per million tokens).
For other model IDs, supply all three prices explicitly.

The search disables automatic HTTP retries to keep call and budget accounting
transparent. Every reserved request counts towards `--max-calls`. On restart,
saved successes, errors and ambiguous pending requests are reused as records;
ambiguous requests are **not** sent again. Ctrl+C can leave such a pending slot.
The same command continues unsent slots. Increasing only the dollar/call/RPM
limits is permitted. A new independent search is needed to replace failed or
ambiguous slots or to change model/token/protocol settings.

The default 480-problem search plans 3,456 discovery requests, up to 1,200
confirmation requests, and up to 1,512 holdout requests: **6,168 maximum**.
At 1,000 uncached input plus 1,000 output tokens per request that would be about
$1.85; this is an illustration, not a quote. Harder reasoning and truncation can
change usage considerably. Measure the first run before spending the rest of a
$150 allowance. Completion and budget records are in `progress.json`,
`summary.json` and `search.sqlite3`.

## Study and display outputs

`screen.csv` is discovery. `confirm.csv` is fresh measurement of selected
instances. `holdout.csv` is unused-parameter measurement. Do not pool them.
Each row includes the stage, mechanism, control flag, forecast, rejection rate,
gap in percentage points, usable/failed counts and a 95% Wilson interval.
The exports directory contains complete JSON records compatible with the app's
Excel converter. The shortlist bank can be loaded through `BLINDSPOT_BANK`,
and `import-results` adds saved confirmation/holdout maps without API calls.
The `search_stage` and bank `split` fields preserve provenance.

Generated JSON banks are trusted local code-adjacent inputs: expression parsing
uses SymPy. Do not load an unreviewed bank supplied by an untrusted party.

## If the ceiling persists

Do not automatically spend the remaining balance on more copies of the same
mechanisms. Inspect the screening refusals and model reasons first. Then expand
the **construction mechanisms**, derivation dependencies or contextual burden.
It is reasonable next to adapt research-level material from TheoPhysEval with
proper attribution and independently checked solutions. It is a solver benchmark,
so difficulty there does not itself establish verifier difficulty here. Its
reported best agent result is 98% on 50 problems in a tool-enabled setting,
which also differs from this stateless no-tool verification protocol.

Source: https://arxiv.org/abs/2610.16733
