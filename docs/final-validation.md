# Final software validation — 1 November 2026

The complete suite passed: **65 tests**, Python 3.12.14. It covers exact
oracles, prompt blinding, global/profile spending guards, truncation handling,
cache reuse, SQLite integrity, offline reporting and the application. An upstream
TestClient deprecation warning does not affect results.

The final-programme checks cover:

- All twelve fixed general-rational matrices: exact orthogonality, similarity,
  characteristic polynomial, ordered spectrum and middle gap.
- Identical scientific payloads and candidates after removing the sole added
  outer-anchor field. No Q, D, middle eigenvalue or derivation is added.
- The exact gap identity implied by outer anchors and existing traces.
- Atomic guards and actual usage, with cached and reasoning tokens counted once.
- Fixed pilots, cap escalation, explicit cost-only repeat allocation, and resume
  without repurchasing recorded attempts. Pilots are excluded from science.
- Consistent database snapshots and refusal to collect from a damaged ledger.
- Refusal to integrate simulated or pending ledgers into live result summaries.
- Separate reporting of correct verdicts, wrong verdicts and unavailable verdicts.

Earlier simulated software checks exercised all adapters, cache/resume paths and
both extension caps. Those generated mock results are excluded from the research
snapshot. The extension test constructs its historical stop state explicitly;
it does not depend on the latest live snapshot still being unfinished.

The final upload adds 448 calls without changing any of the prior 2,228 records
or original manifests. All 432 new main message arrays match the frozen bank,
requested high effort and 32,768-token ceiling. All 52 unusable main responses
have finish_reason=length. Usable returned model identifiers match the requested
Spark and Wonder models. No main case was selectively retried.

Read-only app checks inspect the physics header, 84 basis/certificate contexts,
776/1653 historical dense hits, 1,680/1,680 anchor hits with three false alarms,
and higher-model coverage. JavaScript syntax is checked separately.
No live Meta or partner key is present here; no additional paid call is made by
these checks. Reproduce with `python -m pytest -q` and the offline commands in
`docs/final-study.md`.

The completed-panel API smoke and JavaScript rendering checks passed. The
all-planned-outcomes plot was rendered and visually inspected. Browser binaries
were unavailable here, so a full browser layout review remains in the recording
checklist. No browser screenshot or simulated result is shipped as evidence.
