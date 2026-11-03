# Overnight follow-up

This run addresses two findings in the first live search. All 158 recorded
response failures reached the 4,096 completion-token cap (`finish_reason=length`),
usually before producing visible JSON. Three other slots had unknown interrupted
outcomes. The IVP false rejections overwhelmingly objected to missing displayed
proof, rather than demonstrating a false mathematical claim. The 26 IVP cases
with false rejections were independently rechecked by exact polynomial roots.

The first sweep therefore does not establish a robust missed-error blind spot,
and its apparent false-positive clusters need a clearer task definition.
The overnight recipe diagnoses those issues and then broadens the candidate
answers. It does not use the user's API credits until explicitly run locally.

## Run from Windows PowerShell

Stop the app/search, update the source files from the new archive, and preserve
your existing `.env`, virtual environment and `var/` folder. Use the same Python
environment that successfully ran the first sweep. No new dependencies are needed.

```powershell
$env:META_MODEL = "muse-spark-1.3-contributor"
$env:BLINDSPOT_MOCK = "false"
$env:META_TEMPERATURE = "1.0"
$env:META_REASONING_EFFORT = "low"
python -m blindspot.overnight --source var/search --directory var/overnight --budget-usd 10 --max-calls 10000
```

Keep your existing Windows `META_API_KEY`; there is no need to copy it into a file.
If your terminal's `python` is not the project environment, substitute
`.\.venv\Scripts\python.exe` for `python`.

The recipe sets eight concurrent requests, 100 request starts/minute maximum,
and a timeout of at least 360 seconds. It selects the token cap for each condition;
you do not need to change `META_MAX_COMPLETION_TOKENS`. Temperature and reasoning
effort stay fixed at the values above. All new banks are built and validated before
the first model call. Keep the computer awake and connected while it runs.

The original `var/search` is read only. All new data go in its separate sibling
`var/overnight`. Repeating the identical command resumes saved slots; it does
not spend another $10 automatically. Errors and ambiguous pending slots remain
in the record and are not silently resubmitted. The limits are cumulative for
the whole overnight directory, including every diagnostic condition and the
wider search. The dollar guard is local cost accounting, not a provider billing
cap. Prices are Contributor input $0.10, cached input $0.002 and output $0.20
per million tokens, checked on 30 October 2026.

## First, distinguish wording from token truncation

Choose eight fixed discovery examples from each of six families: IVP domains,
near degeneracy, radial moments, Robin boundaries, viscoelastic networks and
nonorthogonal metrics. Family selection was informed by the first sweep; this
is a targeted diagnostic, not a random sample of physics.

Test the same 48 cases under four conditions:

| Condition | Verifier criterion | Completion-token cap |
| --- | --- | ---: |
| legacy-4096 | Original instruction | 4,096 |
| truth-16384 | Explicit mathematical correctness | 16,384 |
| truth-4096 | Explicit mathematical correctness | 4,096 |
| legacy-16384 | Original instruction | 16,384 |

Each case retains its original error, correct target and equivalent rewrite.
Each cell receives one prospective forecast and two fresh verifier calls.
That is **1,728 diagnostic requests**. Forecasts explicitly include the actual
verifier instruction and token cap. Each condition saves all forecasts before
its empirical calls. No condition selects examples from another condition's
outcomes. The conditions run in the fixed order above, not concurrently; a
provider change during the run is a possible time confound.

The clarified instruction asks the verifier to calculate whether the claim is
true from all supplied information. Missing displayed algebra or proof alone
is not an error. It does not instruct the model to accept unsupported falsehoods
and never reveals the candidate label or hidden reference answer to the verifier.
Comparisons at a fixed cap isolate the instruction change; comparisons with a
fixed instruction examine the token-cap change. Raw failure counts accompany
every conditional-on-usable-verdict rate.

## Then search fresh examples and nearby wrong answers

Build 40 new parameter choices per family, excluding every question in the source
bank. Each now has four target variants: the semantic error, the original correct
target, an equivalent rewrite and a nearby exact numerical error. The nearby
error shifts the result approximately 1%, 2% or 5% towards zero, preserving its
dimensions and sign or complex phase. These are numerical perturbations, not
12 additional conceptual mechanisms. Exact nonidentity is validated. They
address an easy shortcut in some earlier examples: a zero spectral gap can be
rejected qualitatively without checking the actual small nonzero gap.

Of 480 fresh cases, 384 are used for discovery and 96 are reserved. The wider run
uses the clarified criterion, 16,384 tokens, and two screening verdicts per cell.
It freezes up to 16 selected cases, with at most four per family, based on any
observed misclassification with complete screening samples. This includes both
accepted wrong claims and rejected correct controls. Selection never uses the
forecast values. Every selected case receives 20 fresh verdicts per cell, and
two unused parameter choices per selected family are also tested. Screening,
confirmation and holdout outcomes remain separate.

The full default recipe plans **at most 9,632 requests**, with a 10,000-request
guard. Fewer are needed if few cases are shortlisted. The shared dollar guard
may stop it sooner. At the earlier observed latencies, an overnight run is
reasonable, but 16,384-token responses can take longer; no exact finish time is
promised. A higher cap allows more reasoning but does not force every request
to consume the full allowance. Known usage from truncated responses is now
accounted for directly; unknown outcomes retain their reservation.

## What to send back

When finished, or after stopping and allowing the process to exit, attach:

```text
var/overnight/review.zip
```

It contains `overview.json`, `comparison.csv`, condition summaries, the exact
banks and prompts/settings, and the shared `search.sqlite3` ledger. It omits the
redundant per-case exports, which remain in the stage directories. It includes
no API key or `.env`. The bundle is refreshed at condition boundaries and on
normal interruption/finalisation, not after every request.

This gives the next analysis the ground truth, reasons, truncation information
and matched comparisons in one attachment, reducing repeated setup and analysis.
Existing app exports and the original search remain usable. The legacy search
defaults retain their original cache identities. New search-only options are
`--verifier-protocol truth`, `--selection both` and `--show-budget` if you later
want to run a single condition manually.

The code has been tested with mocked responses. The higher-cap live behaviour
and the empirical difficulty of the new candidates are what this run will measure.

API references checked on 30 October 2026:
- https://dev.meta.ai/docs/api-reference/chat-completions/schemas
- https://dev.meta.ai/docs/pricing-rate-limits
