# Development and release

The app is a research demonstrator and evaluation harness. Scientific collection
is closed for this case study. UI checks and source packaging make no model calls.

## Local checks

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

If Node is available, run `node tools/check_demo.mjs` to exercise the renderers.
The public app itself needs Python 3.11 or newer and `requirements.txt`; no Node
installation or frontend build is required.

## Clean source export

```powershell
python tools/prepare_public.py --output ../blindspot-public.zip
```

Git must be installed for this packaging command. It applies the project’s
`.gitignore` in a fresh temporary Git context, rather than relying on an existing
index. The exporter audits eligible filenames, JSON fields and text patterns
before writing the ZIP. Findings identify file and issue type, without printing
possible secret values. A candidate with audit findings is rejected.

The exported source excludes environment files, private ledgers, uploaded review
archives, local operational records, browser/session state, recordings and
creator-only scripts or publication drafts. The included public summary preserves
the final scientific metrics and measured costs. Private archives stay on disk.

Extract the new ZIP into an empty folder and test it as a fresh checkout. Ignore
rules do not remove files already committed to an existing repository. No GitHub
repository or external publication is created by the export command.

## Screen text

The toolbar can download the actual five-step demo content for review. To produce
a local copy without a browser, run `node tools/export_screen_content.mjs`.
Generated screen text is ignored by Git and is not a public-source dependency.

## Metadata and licence

Suggested repository description: Stress-testing AI scientific verifiers with
exact physics invariances and controlled ground truth.

Relevant topics: `ai-safety`, `ai-for-science`, `physics`, `llm-evaluation`,
`llm-as-a-judge`, `scientific-ai`, `meta-ai`.

No LICENSE has been selected in this release. The creator must choose and add
one before treating the source as a licensed open-source release. This guide
neither chooses a licence nor adds placeholder repository URLs or badges.

The completed release validation is recorded in [Final release checks](../presentation-validation.md).
