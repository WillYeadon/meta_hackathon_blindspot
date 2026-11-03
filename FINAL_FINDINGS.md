# Final findings

New requests recorded: 2676; accounted cost $71.7086. Technical pilots are included in cost and excluded from science.

**Data collection is closed. No further model, reasoning-setting or task-family search is planned.**

## Established by held-out experiments

The completed 12-spectrum representation experiment found a nonmonotonic pattern: Hadamard remained easy despite being fully dense, while general rational matrices had 46.9% detection and 18.4% false alarms. Full Q,D certificates yielded 100% detection and 0.4% false alarms. These are fixed completed experiments, not a model-independent claim.

| Verifier | New repeats/cell | Dense usable | Dense d′ | Anchored usable | Anchored d′ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Spark 1.3 Contributor · low | 20 | 2130/2160 | 0.819 | 2160/2160 | 5.877 |
| Spark 1.3 Standard · high | 1 | 64/108 | 2.885 | 106/108 | 4.552 |
| Muse Wonder · high | 1 | 102/108 | 4.535 | 108/108 | 4.573 |

Detection, false alarms and d′ condition on usable verdicts. Unusable outputs are not correct rejections or deliberate abstentions. Sample-size corrections give perfect-score d′ different ceilings. In particular, perfect returned results at different counts do not establish a discrimination improvement.


| Verifier / condition | Detected / usable errors | False alarms / usable controls | Unusable | Correct PASS confidence mean / median | Incorrect PASS confidence mean / median |
| --- | ---: | ---: | ---: | ---: | ---: |
| Spark 1.3 Contributor · low / dense | 776/1653 (46.9%) | 88/477 (18.4%) | 30 | 0.941 / 0.950 | 0.858 / 0.880 |
| Spark 1.3 Contributor · low / outer_anchors | 1680/1680 (100.0%) | 3/480 (0.6%) | 0 | 0.991 / 1.000 | — / — |
| Spark 1.3 Contributor · low / full_certificate | 1680/1680 (100.0%) | 2/480 (0.4%) | 0 | 0.994 / 0.990 | — / — |
| Spark 1.3 Standard · high / dense | 41/44 (93.2%) | 1/20 (5.0%) | 44 | 0.990 / 0.990 | 0.920 / 0.900 |
| Spark 1.3 Standard · high / outer_anchors | 83/83 (100.0%) | 0/23 (0.0%) | 2 | 0.997 / 1.000 | — / — |
| Muse Wonder · high / dense | 79/79 (100.0%) | 0/23 (0.0%) | 6 | 0.961 / 0.960 | — / — |
| Muse Wonder · high / outer_anchors | 84/84 (100.0%) | 0/24 (0.0%) | 0 | 0.990 / 0.990 | — / — |

The fixed outer-anchor condition detected **1680/1680 incorrect claims** and falsely rejected **3/480 correct controls**. All 2,160 new main trials returned usable verdicts.
The observed anchor result meets the frozen >90% detection / <5% false-alarm prediction. This establishes a large rescue on these fixed instances. It does not uniquely establish an internal drifting-anchor mechanism.

Paired over 12 spectra:

| Quantity | Anchor minus baseline | 95% spectrum-bootstrap interval |
| --- | ---: | ---: |
| Detection | +53.1 pp | +50.4 pp to +55.9 pp |
| False alarms | -17.8 pp | -21.7 pp to -13.8 pp |
| d′ | +5.058 | +4.511 to +5.834 |

These intervals describe this twelve-spectrum resampling analysis, not a population prevalence estimate.

Technical continuation: original max settings failed the token-cap pilot; new **high** settings are separately frozen in panel-continuation.json. Max truncations are not correctness results. The original plan and all original spending remain intact.

A user-authorised token-budget extension authorises finishing these same high configurations with 32,768/65,536 ceilings. The separate token-budget-extension.json preserves the earlier stop and original plan. Both technical pilots precede joint cost-only repeat allocation. No new scientific task or model family was added.

### Fixed model panel

Spark 1.3 Standard · high / dense: **60/108 planned reviews produced a correct verdict**, 4 produced a wrong verdict, and 44 produced no usable verdict. Completion reasons: {"length": 44}.
Spark 1.3 Standard · high / outer_anchors: **106/108 planned reviews produced a correct verdict**, 0 produced a wrong verdict, and 2 produced no usable verdict. Completion reasons: {"length": 2}.
Muse Wonder · high / dense: **102/108 planned reviews produced a correct verdict**, 0 produced a wrong verdict, and 6 produced no usable verdict. Completion reasons: {"length": 6}.
Muse Wonder · high / outer_anchors: **108/108 planned reviews produced a correct verdict**, 0 produced a wrong verdict, and 0 produced no usable verdict. Completion reasons: {}.

Wonder main-call spend on the same planned cases was $37.0415 dense versus $5.3485 anchored, a descriptive 85.6% reduction. This excludes pilots and does not price the work of obtaining the anchors.

Production completion ceilings selected after the fixed pilots: Spark 1.3 Standard · high: 32768, Muse Wonder · high: 32768. No truncated main case was selectively retried.
The new configurations have one trial per fixed cell in this completed panel. This is a model-level transfer panel, not a cell-level calibration study.

Frozen Part-A prediction assessment: **met_on_usable_verdicts**. Prediction: If the main failure mechanism is that the verifier replaces exact checking with an approximate consistency argument in which the outer eigenvalues are allowed to drift, fixing the exact minimum and maximum eigenvalues should cause a large recovery in discriminability. We predict >90% detection of incorrect claims and <5% false rejection of correct controls.

Technical-only and skipped configurations supply no accuracy comparison. Individual missing verdicts remain visible in coverage counts and extreme-assignment bounds. Confidence distributions, per-spectrum/candidate effects and paired spectrum-bootstrap intervals are in dashboard.json and CSVs.

## Supported interpretation

Outer anchors and the supplied traces determine the gap. Rescue establishes the effect of adding those facts, not a unique internal mechanism.
The present product is a controlled test suite for developers and researchers evaluating an AI scientific reviewer. Basis changes vary the representation of a fixed spectral claim while exact ground truth remains known. They are experimental controls, not an extra step a physicist must perform to obtain an energy splitting.
Wonder-high supports practical escalation on this fixed dense testbed, with its no-verdict cases retained. Spark-high has substantial dense noncompletion, so its high conditional detection alone does not establish reliable end-to-end review. These observations concern the measured configurations, not all models.
Standard/high versus Contributor/low changes serving configuration, requested effort and token allowance. The comparison does not isolate inference compute as a single cause. Adding the tested anchors improves coverage and reduces Wonder token use, but obtaining those facts need not be free in a real workflow.

## Exploratory evidence

Earlier adaptive discovery and explanation-route patterns motivated this intervention. Frozen lexical flags are reused without tuning and do not establish hidden reasoning mechanisms. The prior self-forecasts recognised coarse task difficulty but did not establish privileged introspection.

## Not established

Generality to all models or scientific workflows, quantum-hardware performance, privileged introspection, independent certificate validation, and internal model mechanisms are not established. The original prompts describe coupled modes. Their Hamiltonian interpretation is explanatory context, not a claim that quantum wording caused the measured outcomes.
A spectral gap here is a difference of Hamiltonian energies (or a spectral quantity in a coupled-mode model). Unitary changes of representation preserve it. This is different from changing the physical observable measured on a fixed state.
Outer-anchor intervention and reused historical baseline run at different times. Rates condition on usable outputs, cells share spectra, and five or fewer repeats do not support cell-level calibration claims. The family was discovered adaptively; held-out spectra within it are not a representative sample of scientific review tasks.

## Cost and reproducibility

Low reference uses 20 repeats; new hosted configurations target 5 with prespecified cost-only fallback to 3 or 1. Fixed first-N sensitivity (N=the actual new repeat count, at most 5) is supplied; finite d-prime ceilings depend on counts.
Technical pilots do not enter these scientific estimates.
Immutable plan.json contains source hashes, exact hypothesis, candidate rules, pilot/budget policy and documentation sources. selected-protocol.json freezes each production configuration after its technical pilot. The shared SQLite ledger enforces both global and configuration guards, counting all pilot attempts and uncertain outcomes.
Historical completed representation/certificate accounting: $11.9101 for 15,120 requests; reused here without further API charges. New accounting includes full conservative reservations where returned usage is missing; it is not a reconciliation of the provider invoice.

| Configuration | New calls (pilot / main) | Accounted USD | State / reason |
| --- | ---: | ---: | --- |
| Spark 1.3 Contributor · low | 2164 (4 / 2160) | 1.1418 | finished:  |
| Spark 1.3 Standard · max | 16 (16 / 0) | 0.8437 | unusable_at_token_cap: More than 25% of the final-cap technical pilot truncated. No main run launched. |
| Muse Wonder · max | 16 (16 / 0) | 3.0753 | unusable_at_token_cap: More than 25% of the final-cap technical pilot truncated. No main run launched. |
| Muse Spark Open · xhigh | 0 (0 / 0) | 0.0000 | skipped: No preconfigured Fireworks key and explicit provider token prices. No GPU deployment or partner setup attempted. |
| Spark 1.3 Standard · high | 240 (24 / 216) | 20.4509 | finished_with_unusable_slots:  |
| Muse Wonder · high | 240 (24 / 216) | 46.1970 | finished_with_unusable_slots:  |
