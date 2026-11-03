# Truth-preserving representation experiments

Blindspot now asks how much verifier reliability changes while the mathematical
truth is fixed. Both the earlier pilot and the completed basis/certificate results are preserved.
The study below has finished; see `basis-study-results.md` for the findings.
Collection commands are retained for reproduction and need not be run to view
the cached live results.

## What is established so far

The final matrix-focus ledger passes SQLite integrity checking and contains all
9,072 recorded requests: 432 forecasts and 8,640 verdict attempts. There are
8,572 usable verdicts, 64 length-limited responses and four HTTP 503 responses.
Accounted cost was $7.932903086. This is the earlier pilot, not the new basis run.

| Presentation | Hits on wrong claims | False alarms on correct claims | Corrected d′ |
| --- | ---: | ---: | ---: |
| Diagonal | 3,359/3,359 | 0/960 | 6.897 |
| Dense, same spectra | 1,562/3,296 | 180/957 | 0.818 |

False accepts in dense cases carried mean reported confidence 86.9%. A
leave-one-spectrum-out history baseline scores Brier 0.208 on dense cells,
compared with 0.330 for advance self-forecasts. The baseline uses only other
spectra with matching presentation, wording and candidate type. This offline
comparison is exploratory, not a preregistered privileged-information test.

Exact diagonal success is an observed ceiling. Its finite corrected d′ does
not establish that the true error rate is zero. See `matrix-focus-results.md`
and the completed-pilot panel in the app for the prior results.

## Frozen new design

`data/basis-study-bank.json` contains **12 new underlying spectra**, excluding
all 92 spectra in the previous search banks and matrix-focus run. It stores
every transformation, candidate, exact validation and the excluded spectra.
It was constructed without inspecting outcomes from these new cases.

The following six bases preserve each ordered spectrum:

| Level | Transformation |
| --- | --- |
| 0 | Identity: canonical diagonal |
| 1 | Fixed permutation: unsorted diagonal |
| 2 | One embedded rational 3/5, 4/5 rotation |
| 3 | Three simple rational rotations on different coordinate pairs |
| 4 | Fixed normalized Hadamard basis with entries ±1/2 |
| 5 | General composition of rational rotations, as in the earlier dense construction |

These are named interventions, not an established monotonic scalar complexity
measure. The Hadamard case may be easier than some earlier levels; that would
be a legitimate result. Fresh spectra with an accidental zero entry in either
intended fully dense matrix are excluded deterministically before model calls.

For every representation the tool checks exactly that QᵀQ=I, H=QDQᵀ,
characteristic polynomial coefficients and ordered roots agree, and the target
gap is unchanged. The same question wording, prefix invariants and candidate
prose are used; only the presented matrix changes. No degeneracy-wording factor
is added to this experiment.

Each context retains the previous nine candidates: zero, signed 1%, 5% and 20%
errors, unchanged correct value and an equivalent control. Twenty stateless
verdicts per cell give **12,960 planned sweep calls**.

The certificate experiment covers **all** new level-5 cases, predetermined
before outcomes. It adds the exact Q,D and stated identities as a candidate
structural certificate in a separate prompt field. The dense matrix, question,
prefix, candidate and sampling parameters otherwise match the sweep. The
baseline is reused from level 5; **2,160 additional calls** test the certificate.

The verifier is asked to check whether the supplied structure certifies the
claim. No numerical gap is stated in the certificate prose. D nevertheless
exposes answer-bearing structure, intentionally making the gap easier to
obtain. Rescue would demonstrate benefit from a correct witness; it would not
prove that the model independently verified QᵀQ or the full matrix product.
There is no false-certificate condition in this fixed design.

No new advance forecasts are collected. Earlier forecasts remain available in
the app and reports. No peer, new task family or optional higher-effort run has
been added. The optional effort comparison remains deferred while these two
live experiments are pending.

## Run on Windows

Copy updated source files over your installation. Preserve `.env`, `.venv`
and all `var/` data. Install the analysis dependency for plots:

```powershell
python -m pip install -r requirements-analysis.txt
$env:META_MODEL = "muse-spark-1.3-contributor"
$env:BLINDSPOT_MOCK = "false"
$env:META_TEMPERATURE = "1.0"
$env:META_REASONING_EFFORT = "low"
python -m blindspot.basis --directory var/basis-study --budget-usd 15 --certificate-budget-usd 5
```

Use `.\.venv\Scripts\python.exe` instead of `python` if needed. The runner fixes
16,384 completion tokens, no automatic HTTP retries, at least 360-second
timeouts, eight concurrent calls and at most 100 starts/minute. The two local
cost guards are separate and cumulative: $15 for the sweep, $5 for the
certificate. They are accounting ceilings, not expected costs or provider caps.
The default request ceiling is 15,000 **per experiment**; planned combined calls
are 15,120. Prices use the same verified Contributor constants as earlier runs.

To inspect the frozen plan without sending requests, first add `--build-only`
to the same command; remove that flag to collect. This writes and validates the
entire bank and `plan.json` before any API calls. The bundled bank is reused
for the default seed and size. An explicit custom seed or `--regenerate`
constructs a new bank, excluding the earlier banks found under `var/`.

All sweep levels are mixed in a fixed shuffled request order. The certificate
experiment follows the sweep, with its own shuffled order. A provider change
between those phases is therefore a possible time confound. Paired comparisons
match spectra and candidate types, not individual random trial ordinals.

Keep the computer awake. Repeating the same command reuses recorded slots;
only the financial guards, request ceiling and RPM may change in the same
directory. Failed and unknown pending outcomes are retained, not silently
retried. If a guard stops collection, increase it explicitly and resume. A
changed design, sampling setting or model requires a new directory.

A small dry run, clearly labelled simulated, is available:

```powershell
python -m blindspot.basis --directory var/basis-smoke --spectra 1 --trials 2 --mock
```

Do not use that directory for live data. The app and plot titles distinguish
simulated runs from the completed live pilot.

## Analysis and outputs

Attach **`var/basis-study/review.zip`** after collection. It contains the full
frozen design, both ledgers, exact prompts, errors and usage, summary tables,
plots and paired certificate comparison. No key or `.env` is included.

The primary analysis reports hits on incorrect claims and false alarms on
correct controls alongside

`d′ = Φ⁻¹((hits+0.5)/(n_errors+1)) − Φ⁻¹((false_alarms+0.5)/(n_controls+1))`.

The same loglinear correction applies to every rate. d′ is a descriptive
equal-variance signal-detection summary of this fixed candidate mixture, not a
general model capability score. Tables include failed outputs and confidence
on true and false accepts. Rates condition on usable responses.

The code also reports a corrected likelihood ratio for PASS. A posterior
probability that a passed claim is correct additionally requires an assumed
prior error prevalence; the constructed error/control mixture supplies no
universal confidence percentage.

Confidence intervals resample whole spectra, preserving dependent cells and
repetitions. There are 12 problem units, not hundreds of independent problems.
At a ceiling with no observed errors, cluster-bootstrap intervals cannot
capture unseen population errors. Inspect the raw rates and denominators.

The paired certificate report computes changes in hit rate, false-alarm rate
and d′, with a whole-spectrum bootstrap. Its baseline reuses existing level-5
calls. A nonmonotonic ladder, changing false alarms or failure to recover under
a certificate are possible outcomes; no additional search is launched.

Per experiment:

- `analysis.json`, `conditions.csv` and `cells.csv` contain numerical results.
- `discriminability.png` shows d′, hit rate and false-alarm rate together.
- `report.md` states counts and interpretation limits.
- `explanation-review.csv` provides nonexclusive lexical flags for calculation,
  certificate and plausibility mentions, plus explicit numeric-gap mismatch
  flags and a manual review field. A mismatch can quote a rejected candidate;
  these flags are exploratory review aids, not verified mechanism labels.
- `exports/*.json` retains per-context maps and every verdict.

At the study root, `comparison.json`, `comparison.md` and
`certificate-comparison.png` compare the same dense cases with and without
the certificate. The core result never depends on explanation categorization.

Rerun analysis offline without any model calls:

```powershell
python -m blindspot.signal_analysis --directory var/basis-study --experiment sweep
python -m blindspot.signal_analysis --directory var/basis-study --experiment certificate
```

## Open the new study in the app

After collection, use the same model/mode environment as above:

```powershell
python -m blindspot.basis --directory var/basis-study --import-results
$env:BLINDSPOT_BANK = "var/basis-study/bank.json"
$env:META_MAX_COMPLETION_TOKENS = "16384"
$env:META_TIMEOUT_SECONDS = "360"
python run.py
```

Restart a running server before changing the bank. The primary panel shows the
representation curve and per-level table. Choose a spectrum, retain the same
candidate and switch basis. Exact D,Q,H and preservation checks remain visible.
The certificate button uses the matched fixed intervention. Open the full
verdict map for every trial, JSON and Excel exports. Opening saved data makes
no model calls. New live app runs on this bank also omit forecasts.

The secondary self-forecast panel preserves the completed pilot and its
history-baseline comparison. The old maps remain available by selecting the
earlier bank. Before importing new data, the app explicitly shows the completed
two-presentation pilot, not invented six-level or certificate results.

## Completion status

Both experiments have completed with 15,120 recorded requests and 14,791 usable
verdicts. The accounted cost was $11.91. The completed results open immediately
in the app, without an API key or result import. Every structured trial and
explanation is included in the compact demo cache. Raw prompts, usage and
responses remain in the original review archive.

The ladder is nonmonotonic: the simple fully dense Hadamard condition succeeds,
whereas the general rational basis performs poorly. The exact certificate
substantially restores performance. See `basis-study-results.md` for counts,
missing-response sensitivity and interpretation limits. No additional model
calls were made while checking and packaging the completed results.
