# Blindspot

**Blindspot is a stress-testing harness for AI scientific verifiers.**

Before trusting an AI reviewer’s PASS, test it against physics claims whose truth
is known independently. Blindspot changes a problem’s representation while
preserving the physical prediction, then measures missed errors, false alarms,
unavailable answers and cost.

The completed spectral-gap case study found **46.9% error detection and 18.4%
false alarms** for Spark-low in a general rational basis. Trusted checkpoints
raised detection to **1,680/1,680**, with **3/480 false alarms**. Wonder returned
**102 correct dense verdicts and six token-limit cutoffs**, then **108/108 correct
verdicts with checkpoints**. These findings concern the fixed testbed.

## Run the guided demo

Python 3.11 or newer is required. On a fresh Windows installation:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

On macOS/Linux, use `python3 -m venv .venv`, then `.venv/bin/python` for both
commands. With an existing configured environment, run `python run.py`.
Open **http://127.0.0.1:8000**. Stop with Ctrl+C; `--port 8001` chooses another port.

**No API key or model calls are needed.** The five-step viewer uses saved live
measurements. The included physics suites are implemented; a new scientific
domain requires code plus an independent correctness oracle.

## The three-minute path

1. **The claim.** The exact middle splitting is 1/104. The proposed 101/10400 is
   exactly 1% too large. Spark-low rejects it in the diagonal representation.
2. **Change basis.** Exact validation confirms unchanged levels, gap and false
   claim. In the general rational basis, Spark-low passes this claim eleven times
   in twenty attempts. Inspect the saved explanation.
3. **Density control.** A fully dense Hadamard representation remains easy.
4. **Trusted checkpoints.** Add only the exact lowest and highest levels; inspect
   the recovery and the optional algebra explaining the short exact route.
5. **Choose a verifier.** Compare wrong PASSes, rejected correct controls,
   unavailable verdicts and measured cost for the three tested configurations.

Spectrum 005 was selected after collection for illustration. Aggregate estimates
retain every frozen case. Full tables and exact evidence remain under Study
records. The current build is a research demonstrator and reusable evaluation
harness, with one completed physics case study.

## Why test the checker?

A developer planning to use an AI scientific reviewer needs evidence about the
reviewer’s approvals. Exact physics cases act as calibration weights: an
independent oracle already supplies their answers. For this 4×4 calculation,
exact linear algebra is the appropriate checker; its role is to test the AI.

Changing basis varies the work required of the reviewer while keeping the target
claim and truth fixed. Humans find some representations harder too. Difficulty
alone is not the contribution; a confident PASS on a known false exact claim is
the observable concern. Regression testing means rerunning such known cases when
the verifier configuration changes, before relying on it in a workflow.

## What the fixed experiments show

Twelve held-out spectra were tested through six exact representations and nine
claims, with twenty attempts per cell. Spark-low’s general-basis rates were
46.9% detection and 18.4% false alarms among usable verdicts. Fully dense Hadamard
matrices had 100% detection and 0% false alarms. Density alone is insufficient.

Trusted checkpoints are independently trusted intermediate facts. Here they are
the exact lowest and highest levels. The middle levels, Q, D and target splitting
are withheld from the verifier. Together with the already supplied traces, the
checkpoints create a short exact route and substantially simplify this benchmark.
They detected 1,680/1,680 wrong claims with 3/480 false alarms and no missing
verdicts. This is rescue by trusted structure, not a universal checkpoint method
or evidence of a unique internal mechanism. Obtaining trusted facts in practice
may itself cost work.

| Verifier | Dense: correct / wrong / unavailable | Checkpoints: correct / wrong / unavailable |
| --- | ---: | ---: |
| Spark 1.3 Contributor low, 20 attempts/cell | 1,165 / 965 / 30 | 2,157 / 3 / 0 |
| Spark 1.3 Standard high, 1 attempt/cell | 60 / 4 / 44 | 106 / 0 / 2 |
| Muse Wonder high, 1 attempt/cell | 102 / 0 / 6 | 108 / 0 / 0 |

All higher-model unavailable answers hit the 32,768-token limit; they are neither
correct rejections nor deliberate abstentions. One attempt per fixed cell is a
model-level panel, not a cell-level calibration study. Tier, reasoning and token
allowance change together. The family was discovered adaptively; these held-out
instances do not establish general scientific-review reliability.

Wonder main-call spend was $37.04 dense versus $5.35 with checkpoints on the same
108 claims. That includes cutoffs, excludes pilots and does not price checkpoint
acquisition. See [FINAL_FINDINGS.md](FINAL_FINDINGS.md) for the full distinctions.

<!-- FINAL_PANEL_STATUS_START -->
Final programme: 2,676 calls and $71.708640 of accounting including pilots.
The earlier representation/certificate study cost $11.910093 separately.
Collection is closed. [Measured costs](docs/public-cost-summary.md).
<!-- FINAL_PANEL_STATUS_END -->

## How to add another scientific stress test

1. **Choose a claim with an independent oracle.** Know whether it is correct
   without relying on the AI reviewer.
2. **Choose a truth-preserving transformation.** Change the representation while
   preserving the target physical fact.
3. **Create matched correct and incorrect claims.** Hold irrelevant details fixed
   wherever possible.
4. **Run the verifier across equivalent cases.** Measure wrong PASSes, false
   alarms, missing answers and cost.
5. **Choose the configuration.** Assess whether the cheap checker is adequate,
   benefits from trusted intermediate information or needs escalation.

**Implemented spectral test:** exact basis transformation → unchanged spectrum
and energy splitting → exact linear algebra as the oracle.

**Hypothetical relativity extension:** describe the same spacetime in different
coordinates, choose a coordinate-invariant quantity at corresponding physical
points, and use an independent symbolic or numerical relativity calculation as
the oracle. Metric components themselves need not stay the same. This is an
extension pattern, not an implemented or experimentally tested capability.
Automatic verifier routing also remains a future extension.

## Physics and provenance

A real symmetric 4×4 matrix can represent a four-level Hamiltonian. An orthogonal
basis change H = QDQᵀ preserves energies and their splittings. Recorded API
prompts used coupled modes; the Hamiltonian is a physical interpretation. We did
not test quantum hardware or an effect of quantum wording. See
[the physics explanation](docs/physics.md).

- [FINAL_FINDINGS.md](FINAL_FINDINGS.md): results and limits.
- [REPRODUCIBILITY.md](REPRODUCIBILITY.md): public data and private-ledger routes.
- [Measured costs](docs/public-cost-summary.md): public resource accounting.
- [Development and release](docs/development/PUBLISHING.md): tests and clean exports.

## Reviewing the displayed content

Click **Screen content ↓** to download the actual text, matrices, explanations
and numbers from all five steps and both comparison conditions. Optional proof
panels are included. This creates a local review file; no model call is made.
If Node is available, `node tools/export_screen_content.mjs` generates the same
local content from the source. Generated script-review material is excluded from
the public repository. Screenshots are useful when discussing visual layout.

## Build and scope

Will Yeadon is an assistant professor of physics. He designed the experiments,
requirements for exact ground truth and interpretation; coding agents generated
and iterated the implementation during the hackathon. The measured reviewers
were Meta models. No Muse Code usage or open-weight/local-model result is claimed.
The build runs the included suites and displays saved results. Arbitrary-paper
review and automatic routing are not implemented.
