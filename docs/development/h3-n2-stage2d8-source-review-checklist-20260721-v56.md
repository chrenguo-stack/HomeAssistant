# H3/N2 Stage 2D-8 Source Review Checklist V56

This checklist is review-only. It grants no live action.

- [x] Branch starts from accepted Stage 2D-7 head.
- [x] Stage 2D-6, Stage 2D-7, production `f1_0_rc2.yml`, and product packages are protected.
- [x] ESPHome component remains compile-only and constructs no object.
- [x] Wi-Fi remains disabled at boot in the dedicated target.
- [x] No repository-default Broker, credential, test key, NVS partition, namespace, board, or serial path exists.
- [x] Physical persistence writes require a mirrored one-shot generation-bound grant.
- [x] Stage 2D-7 package and Stage 2D-8 driver grants are armed together by one binder.
- [x] Validation uses only runtime-injected `gh-test/` topics.
- [x] Candidate record is committed before the active marker.
- [x] Missing marker-last evidence closes to reboot-required.
- [x] Marker or promotion ambiguity quiesces all sessions.
- [x] Cleanup is a separately authorized namespace-only operation.
- [x] eFuse access, partition erase, production services, and automatic startup execution are absent.
- [x] Execution manifest defaults to `LOCKED`; live-capable gates require an explicit command-line override and later approval record.
- [ ] Host fault matrix passes in CI.
- [ ] Dedicated ESP32-C6 compile target passes in CI.
- [ ] Full RC2 product-board compatibility overlay passes in CI.
- [ ] All repository safety workflows pass.
- [ ] Exact board, serial path, partition table, rollback artifact, and evidence directory are available for the later G1/G2 decision gate.
