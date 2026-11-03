# Focused matrix experiment

The hackathon target remains the original two features: controlled error
stress-testing and prospective self-prediction, displayed in the app. This
follow-up supplies a fixed, informative dataset for those features.

The overnight data found frequent acceptance of slightly wrong middle
eigenvalue gaps. Confirmation accepted 58/79 wrong nearby values on four
selected cases; reserved parameters accepted 19/38 on two cases. Exact
characteristic polynomials confirmed the references. The model also forecast
low detection for this family. These results motivate this experiment; they
do not establish privileged self-knowledge or population prevalence.

## Fixed design

Generate **12 new underlying spectra**, excluding spectra in the previous
`var/search/bank.json` and `var/overnight/wide/bank.json` when those files exist.
Exclusion compares exact eigenvalue lists, so rotating an old matrix does not
make it a new spectrum. Every generated case is used, regardless of its outcome.

For each spectrum, cross these two factors:

| Factor | First version | Second version |
| --- | --- | --- |
| Matrix presentation | Diagonal, making the gap easy to calculate | Dense rational orthogonal similarity, with exactly the same spectrum |
| Question wording | Ask for the exact middle gap | Ask for the exact middle gap and additionally emphasise exact degeneracy |

This produces **48 problem contexts**, with nine candidates each:

- False zero gap.
- Exactly 1%, 5% and 20% below the correct gap.
- Exactly 1%, 5% and 20% above the correct gap.
- Unchanged correct value.
- A mathematically equivalent rewrite of the correct value.

All claims explicitly assert exact equality; rounding does not make an error
acceptable. Candidate prose is neutral and identical across variants. It no
longer asserts that an exact diagonalisation has already been carried out.
Both wording conditions share these changes, so comparisons with the earlier
overnight prompts involve more than one change. The paired comparisons within
this experiment isolate presentation and the added degeneracy sentence.

The diagonal matrix is an intentionally easy control for verifying the same
spectrum. A presentation effect would be consistent with a calculation burden;
it would not by itself identify an internal reasoning mechanism.

## Collection and forecasts

- The reference spectrum is independently checked by exact characteristic
  polynomial roots before any model call. All candidate labels are validated.
- One forecast per cell specifies the exact mutation direction and size.
  The changed candidate expression is not displayed, although the stated
  transformation and reference value make it inferable. This narrows the
  category-to-instance mismatch of the earlier forecasts.
- **All 432 forecasts are saved before any empirical verdict starts.**
- Each cell then receives 20 independent, stateless verifier requests, using
  the explicit mathematical-correctness instruction. Earlier correct steps
  are included; the target reference, mutation label, forecasts, other verdicts
  and future steps are withheld.
- Request order is deterministically shuffled within each phase, mixing all
  conditions rather than running each condition in a separate time block.
- All cases are retained. There is no screening, adaptive shortlist or
  additional outcome-selected confirmation within this fixed follow-up.

Defaults are Contributor, the current environment's temperature/reasoning,
16,384 completion tokens, eight concurrent requests, 100 starts/minute,
at least 360 seconds per request and no automatic HTTP retries.

There are **9,072 planned requests**: 432 forecasts and 8,640 verdicts.
A $10 local accounting guard and 10,000-request ceiling cover the whole run.
These are ceilings, not expected charges or provider billing caps. The pricing
constants are Contributor $0.10 input, $0.002 cached input and $0.20 output per
million tokens, checked against https://dev.meta.ai/docs/pricing-rate-limits
on 30 October 2026. The previous run's approximately seven-hour duration is
useful context, not a promised duration for this one.

## Run on Windows

Update the source files from the new archive, preserving your `.env`, virtual
environment and `var/` directory. No new dependencies are needed. Keep your
existing Windows `META_API_KEY`.

```powershell
$env:META_MODEL = "muse-spark-1.3-contributor"
$env:BLINDSPOT_MOCK = "false"
$env:META_TEMPERATURE = "1.0"
$env:META_REASONING_EFFORT = "low"
python -m blindspot.matrix_focus --directory var/matrix-focus --budget-usd 10 --max-calls 10000
```

The runner sets its completion-token cap itself. Keep the computer awake. Use
`.\.venv\Scripts\python.exe` instead of `python` if that is how you run the app.

To build and inspect the design without model calls, add `--build-only` to
the same command. Remove that flag to run the frozen design. To exclude other
previous banks, use repeated `--exclude-bank PATH` arguments; supplying any
explicit exclusions replaces the default exclusion list.

Repeating the identical run command resumes saved slots. Only the budget,
call ceiling and RPM limit may change in the same directory. Unknown pending
outcomes and failed responses are retained and not silently retried. A failed
forecast blocks that problem context; its unattempted verdicts remain explicit.
Use only one process per output directory.

After completion, attach **`var/matrix-focus/review.zip`**. It includes the exact
bank, frozen plan, raw SQLite requests and responses, per-cell results,
condition comparisons and paired differences. It contains no API key.

For a short, keyless software test use a separate directory:

```powershell
python -m blindspot.matrix_focus --directory var/matrix-focus-mock --spectra 1 --trials 2 --mock
```

Mock results are simulated software checks and carry no scientific meaning.

## Inspect the maps in the app

The output also contains `exports/*.json` for all 48 fixed contexts. Import
them offline after the run:

```powershell
python -m blindspot.matrix_focus --directory var/matrix-focus --import-results
$env:BLINDSPOT_BANK = "var/matrix-focus/bank.json"
$env:META_MAX_COMPLETION_TOKENS = "16384"
$env:META_TIMEOUT_SECONDS = "360"
python run.py
```

Stop a running app before restarting. Saved maps open instantly and can be
exported with the existing Excel and JSON buttons. Imported fixed runs are
frozen; they are labelled **FIXED MATRIX TEST**. The `shortlist-bank.json` file
is only a compatibility alias for the importer and contains **all** fixed
contexts, without outcome-based selection.

Fresh app runs on this focused bank use the same mathematical-correctness
criterion. The footer and Excel export identify the criterion and token cap.
A live single-cell demonstration is an additional experiment; it does not
replace the fixed run's measurements. A UI live run is not governed by the
CLI's $10 guard.

## Read the result

`cells.csv` reports forecasts, actual rejection fractions, usable/failed/
unattempted counts and per-cell Wilson intervals. Rejection is successful
detection for errors and a false positive for controls.

`comparison.csv` groups by presentation, wording and exact mutation. It shows
pooled counts, denominators and equal-spectrum matched forecast/observed
averages. `paired.csv` compares the same underlying spectrum across the two
presentations or the two wordings. A negative representation difference means
less rejection with the dense matrix. For error cells this means worse detection;
for correct controls it means fewer false positives.

The prespecified reading order is:

1. Check unavailable outputs and false-positive rates on the correct controls.
2. Compare small wrong values with zero and 20% errors, in each direction.
3. Compare dense versus diagonal presentations within the same spectrum.
4. Compare the two wordings within the same spectrum and presentation.
5. Compare the prospective forecasts with observed rates for those same cells.

There are **12 underlying problem units**, not 48 independent problems or
8,640 independent mathematical examples. Repeated trials estimate cell
reliability; a study-level uncertainty calculation should resample whole
spectra and preserve their paired conditions. The CSV cell intervals describe
repeated-trial uncertainty only. All reported rates exclude unusable outputs,
so failure counts and incomplete coverage must accompany the comparisons.

The family was chosen after a broad search. This is a fixed follow-up in that
family, not an unbiased physics benchmark. Accurate self-forecasts could still
come from ordinary knowledge of task difficulty. The MVP has no peer-predictor
baseline and cannot establish privileged introspective information.

## Hackathon scope

The deliverable remains a polished app with real cached measurements, exact
controls, a live single-cell option, and prospective/observed comparisons. A
useful demo can show reliable detection of obvious mistakes, poor detection of
nearby mistakes, how that changes with presentation, and whether the forecasts
track the change. It does not require a selected 92%-predicted/20%-observed
example. If forecasts acknowledge the weakness, that is a substantive measured
result to display rather than a reason to keep searching for a preferred story.
