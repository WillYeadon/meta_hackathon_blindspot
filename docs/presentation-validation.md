# Final release checks · 3 November 2026

Scientific collection is closed. The pass changed presentation and public-source
packaging only. Frozen data, manifests, raw measurements and FINAL_FINDINGS.md
remain byte-for-byte unchanged.

## Public-source tests and installation

The fresh public ZIP was extracted into a new directory. All **72 Python tests
passed from that copy**, with no private raw archives, operational summary,
creator script or local run directory. Offline UI checks also passed. The
existing upstream TestClient warning remains non-fatal.

The declared runtime requirements installed in a fresh isolated environment.
The extracted public application then launched using that environment with no
API key. Saved measurements and all five steps loaded successfully.

## Privacy and repository checks

The exporter now checks eligible filenames and file contents for credential
patterns, authorization values, private operational JSON fields, local absolute
paths, unnecessary email addresses, session/browser artefacts and unfinished
public documentation. It rejects candidate releases with findings and reports
only file and issue type. The final candidate had zero findings.

Account-specific numeric fixture inputs in the two public-export/extension test
modules were replaced with unrelated synthetic budgets. No actual secret values
are recorded here. Original scientific records were not changed.

All local Markdown links resolve inside the exported source. Creator-only
publication instructions and generated screen text are excluded from the root.
Public developer guidance is under docs/development/. There are no placeholder
repository URLs or badges. No licence was automatically selected; no LICENSE
file is present, and that remains a creator decision before publication.

## Recording-resolution review

Headless Chromium inspected the guided demo at **1920×1080**, device scale 1,
with normal browser zoom. In each of five steps, important results fit in frame;
matrices and the comparison table needed no horizontal scrolling. The false
PASS explanation uses a larger readable type size. All four top navigation
controls have consistent borders and corner treatment. No sticky element covers
the readouts. The UI was rendered and visually inspected.

The verifier selector, checkpoint condition, detailed study panels and four
public document routes passed. The screen-content download exactly matches the
source-generated local review text, including the current scope and explicitly
hypothetical relativity extension. A 390px mobile check also passed.

No JavaScript errors or external requests were observed. Application traffic was
GET only. No new Meta/model API call was made. Internal QA screenshots and browser
runtime files are not included in the public source.

## Script boundary

The creator-authored script attachment was unavailable to this pass. Its wording
and timing could not be checked. The existing local script is untouched, existing
scripts are preserved during offline report integration, and the working update
omits the script rather than overwriting the creator’s copy.
