# Reproducibility and research provenance

Data collection is closed. Opening the study viewer and following the guided
demonstration makes no model calls. The new visual style changes presentation,
not the experiment or any saved verdict.

## Public source and scientific data

The public repository contains the code, exact representation bank and plans,
completed representation/certificate verdicts, and `data/final-panel-public.json`.
That public summary preserves final counts, metrics, verdict examples and measured
costs. Personal remaining-credit estimates and the spending-authorisation record
are omitted. The archival condition key `outer_anchors` means Trusted Checkpoints.

| Record | Location |
| --- | --- |
| Exact held-out cases | `data/basis-study-bank.json` |
| Frozen representation plan | `data/basis-study-plan.json` |
| Completed representation/certificate verdicts | `data/basis-study-results.json` |
| Final derived public summary | `data/final-panel-public.json` |
| Original and high-effort panel plans | `data/final-panel-plan.json`, `data/final-panel-continuation.json` |
| Measured API accounting | `docs/public-cost-summary.md` |

The app prefers a local `var/final-study/dashboard.json` when present, otherwise
its working/private summary if available, then the public summary. Public-source
launches need neither the private files nor an API key.

## Local raw archives

The creator's working copy retains `data/final-study-review.zip`,
`data/final-anchor-review.zip`, the full private summary and original token-budget
extension. They preserve the uploaded SQLite ledgers, exact requests, responses,
usage and operational metadata. They are ignored by Git and excluded from the
public export. Publishing the source does not claim those full ledgers are bundled.

If you have the private final archive, reproduce its analysis without API calls:

```powershell
python -m pip install -r requirements-analysis.txt
python -m zipfile -e data/final-study-review.zip var/final-panel-reproduction
python -m blindspot.final_report --directory var/final-panel-reproduction
```

To update local derived summaries from your completed working directory:

```powershell
python -m blindspot.final_report --directory var/final-study --integrate
```

This also writes a derived public summary, without changing the raw ledger.
Any existing local submission script is retained, including scripts without a generated-file marker. The public clone supports
case validation, inspection, code review and tests; full final-ledger reanalysis
requires the raw archive. No new model collection is needed for the submission.

## Checks

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Exact SymPy checks cover orthogonality, similarity, characteristic polynomial,
ordered spectrum and gap. Tests also cover budgets, caching, truncation, ledger
integrity, public-summary preservation and export exclusions. Test fixtures are
rebuilt from public cases/plans, so private review ZIPs are not required.

If Node is available, `node tools/check_demo.mjs` checks the UI renderers offline;
`node tools/export_screen_content.mjs` generates a local content-review file, which is ignored by Git.
Neither needs a browser, network access or a model key. The app itself does not
require Node or a frontend build.

## Interpretation

Detection and false-alarm rates condition on usable verdicts; the main decision
table retains missing answers separately. Mean cost per attempt includes every
main attempt and excludes pilots. Historical dense per-call costs are unavailable.
Spark-low has twenty attempts per cell; the higher-model panel has one. There are
twelve underlying spectra. Perfect d′ ceilings depend on sample size. Explanation
inspection is exploratory. The recorded prompts say coupled modes; the Hamiltonian
is a physical interpretation. No HLE material or quantum-hardware result is used.

Earlier discovery code and research findings remain in the source and `docs/`.
The old editable maps are removed from the app. Archived UI snapshots and personal
video/submission documents are preserved only in the creator's working release.

For public packaging and repository metadata, see [Development and release](docs/development/PUBLISHING.md).
