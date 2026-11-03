# Same truth, different verification reliability

Both fixed experiments completed on 1 November 2026. All 15,120 planned
requests are recorded. The ledgers pass SQLite integrity checking, contain
14,791 usable verdicts and account for **$11.910092512**. No new forecasts were
collected. This report describes the completed run, not the software dry run.

## The principal result

Verification reliability changes substantially across exactly isospectral
representations. The pattern is **not monotonic across the named basis ladder**.
In particular, the fully dense Hadamard condition returns to perfect observed
classification, whereas the general rational condition performs poorly.

| Representation | Hits / wrong claims | Hit rate | False alarms / controls | False-alarm rate | Corrected d′ | Unusable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Canonical diagonal | 1679/1679 | 100.0% | 0/480 | 0.0% | 6.51 | 1 |
| Permuted diagonal | 1680/1680 | 100.0% | 0/480 | 0.0% | 6.51 | 0 |
| One rational rotation | 1678/1678 | 100.0% | 2/480 | 0.4% | 6.00 | 2 |
| Three rational rotations | 1190/1402 | 84.9% | 26/462 | 5.6% | 2.61 | 296 |
| Simple Hadamard, fully dense | 1680/1680 | 100.0% | 0/480 | 0.0% | 6.51 | 0 |
| General rational basis | 776/1653 | 46.9% | 88/477 | 18.4% | 0.82 | 30 |
| Same general matrices + certificate | 1680/1680 | 100.0% | 2/480 | 0.4% | 6.00 | 0 |

All rates condition on usable responses. The loglinear correction makes d′
finite at observed ceilings; perfect sampled outcomes do not establish a zero
population error rate. There are 12 underlying spectra, not 15,120 independent
mathematical examples.

Density alone is therefore insufficient to explain this result. The evidence
supports dependence on the particular presentation and availability of usable
structure. It does not isolate one internal cause or establish a universal
scalar measure of representation complexity. In inspected Hadamard examples,
returned explanations explicitly used simple ±1 eigenvectors. These
explanations are evidence about the reported justification, not hidden reasoning.

## Certificate intervention

On the same level-5 matrices and candidate claims, adding the correct Q,D
certificate raises detection by **53.1 percentage points** and lowers false
alarms by **18.0 points**. The corrected d′ increase is **5.18**.

Whole-spectrum bootstrap 95% intervals for the paired changes are:

- Detection: +50.4 to +55.7 percentage points.
- False alarms: −22.2 to −15.1 points.
- Corrected d′: +4.77 to +5.83.

Detection improves on every one of the 12 spectra. Both residual false alarms
concern correct claims for spectrum 006; the returned explanations incorrectly
claim that the supplied Q is not orthogonal. Exact matrix arithmetic confirms
that it is orthogonal.

This establishes recovery when correct answer-bearing structure is supplied.
It does not establish that the model independently checked the certificate:
the diagonal D makes the gap easy to obtain. Certificate requests followed the
sweep in time, so a provider change between phases is a possible confound.

## Incomplete responses and sensitivity

The 329 unusable outputs comprise 324 token-limit failures, four HTTP 503s and
one timeout. Level 3 accounts for 296 failures, or 13.7% of its 2,160 attempts.
They are retained and excluded from classification denominators.

Even assigning every unavailable level-3 response in the most favourable or
unfavourable way gives detection bounds of 70.8–87.4%, false-alarm bounds of
5.4–9.2%, and corrected d′ bounds of 1.87–2.74. The corresponding level-5 d′
bounds are 0.78–0.85. Thus the major pattern survives extreme assignments of
missing verdicts. These are sensitivity bounds, not confidence intervals.

On erroneous level-5 claims that passed, mean reported confidence was **85.8%**.
This is verdict confidence, not an advance forecast or a calibrated posterior.
The prior prevalence of errors would also be needed to interpret a PASS as a
probability that the claim is correct.

## Verification and provenance

The saved bank exactly matches the design frozen before collection. All 84
contexts and 756 candidates were rechecked for exact orthogonality, similarity,
characteristic polynomial, ordered spectrum and target gap. The actual paired
API payloads differ only by the structural-certificate field. Every request
uses muse-spark-1.3-contributor, temperature 1.0, low reasoning and a 16,384-token
completion cap. Successful provider response IDs are distinct.

The app's completed-study cache retains all structured verdicts and reasons,
their trial ordinals and source-ledger SHA-256 hashes. Full requests, raw
responses, usage and error provenance remain in the original review archive.

## Demonstration and stopping point

The central demonstration can hold one wrong claim fixed, switch through exact
basis transformations, show the perfect dense Hadamard control and the weak
general-rational case, then add the certificate and show recovery. Use the
aggregate table to keep individual demonstrations in context.

The defensible claim is: **on this model, task family and inference setting,
verification reliability changes under exact truth-preserving representations,
and supplying a correct structural certificate substantially restores it.**

The monotonic-ladder hypothesis is not supported. No further search or
higher-effort experiment is needed for this hackathon pilot. The remaining
work is demonstration and submission preparation, rather than more data mining.
