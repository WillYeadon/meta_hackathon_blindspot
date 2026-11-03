# Fixed outer-anchor result

The run returned 2,160 usable main verdicts from Spark 1.3 Contributor at low
reasoning: twenty for each of the same twelve held-out matrices and nine claims.
All model-visible requests match the frozen bank. All responses identify the
intended Contributor model. No new spectra or outcome-selected examples were used.

| Information supplied | Wrong claims detected | Correct claims falsely rejected | d′ |
| --- | ---: | ---: | ---: |
| Dense matrix and original invariants | 776/1,653 (46.9%) | 88/477 (18.4%) | 0.819 |
| Same matrix/invariants + exact outer eigenvalues | 1,680/1,680 (100%) | 3/480 (0.625%) | 5.877 |
| Same matrix/invariants + full Q,D certificate | 1,680/1,680 (100%) | 2/480 (0.417%) | 5.996 |

The original dense baseline had thirty unusable trials, excluded from its rates.
New anchors and the prior certificate each had none. All twelve spectra improved
in detection and false alarms. The prespecified >90% detection and <5% false-alarm
prediction is met on the complete anchor data.

The paired pooled detection gain is **53.1 percentage points**, with a
12-spectrum bootstrap interval of **50.4 to 55.9 points**. False alarms decrease
by **17.8 points**, interval **13.8 to 21.7 points**. d′ increases by **5.058**,
interval **4.511 to 5.834**. These are resampling intervals for the fixed spectra,
not estimates of how common this failure is in physics or across models.

Correct PASS confidence rises from mean/median 0.941/0.950 in the dense baseline
to 0.991/1.000 with anchors. The baseline's 877 incorrect PASSes had mean/median
confidence 0.858/0.880. There were no incorrect PASSes in the anchor condition,
so confidence on that event is undefined, not zero.

## What this means

Two exact spectral facts recover very high discrimination on a fixed set of
otherwise troublesome representations. The observed recovery is close to the
full-certificate point estimates, while disclosing neither Q, D, the middle
eigenvalues nor the claimed gap directly.

This is consistent with the proposed approximate-consistency explanation, but
does not uniquely establish it. As frozen before collection, outer eigenvalues
plus Tr(H) and Tr(H²) determine the gap by short algebra. The intervention also
supplies an easier exact route. Baseline and anchor calls occurred at different
times; the design reuses the original matched baseline as specified.

For the product, this is evidence that verifier reliability can depend sharply
on how the same physical prediction is presented and what compact structural
facts accompany it. The question is when a PASS is trustworthy in a tested
regime, rather than whether a verifier can diagonalise every matrix unaided.

## Why the model comparison stopped

Spark max truncated 8/8 technical responses at 8,192 tokens and 8/8 at 16,384.
Wonder max truncated 5/8 at each ceiling. Those incomplete responses are excluded
from correctness analysis. No main max panel was launched. They establish a
technical mismatch between these settings and token ceilings, not bad verifier
accuracy or the effect of additional reasoning.

Accounting at the first uploaded final-programme snapshot was **$5.060780**: Spark-low anchors and their pilot $1.141837;
Spark-max pilots $0.843690; Wonder-max pilots $3.075254. Every request returned
usage, so there are no unknown-cost reservations in this archive.

The separately manifested **high-reasoning** continuation also stopped at its
technical gates: Spark truncated 5/8 and Wonder 3/8 at 16,384 tokens. It added
32 pilot requests costing $3.143224, for **2,228 cumulative requests and $8.204004**.
No additional main accuracy panel ran. There is no result establishing which
model is better or whether greater reasoning repairs the failure. Data collection
is closed; verifier selection remains a potential application of the instrument.
