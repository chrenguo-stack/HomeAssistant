# N3-W P4 T1 — R4 A1 repaired-source independent closure and prelive decision (2026-10-09)

## 1. Authorization and exact source

User explicitly authorized `N3W_P4_T1_R4_A1_REPAIR_EXACT_SOURCE_INDEPENDENT_CLOSURE_AND_PRELIVE_DECISION` for **independent source-only review**. This does **not** authorize R4 T1 live cutover, source mutation in this review, Broker/TLS/network changes, board boot, Setup Secret import or PR merge.

```text
TASK=N3W_P4_T1_R4_A1_REPAIR_EXACT_SOURCE_INDEPENDENT_CLOSURE_AND_PRELIVE_DECISION
REVIEW_MAINLINE=N3W_P4_T1_FIRST_PAIR_CLEAN_PRODUCT
PR=540_OPEN_DRAFT
FRESH_REVIEW_PR_HEAD=129219e20d8aa1ca8e8d9d979e4376a4dc0fe11a
REPAIRED_11_SCRIPT_EXACT_REF=938ff0686a02e3633f96d6e421789ecdd4cabefd
A1_CODE_FIX_COMMIT=cf878f7f5228756f8b9ff822eeeb262486d63ae9
REPAIRED_R4_FINGERPRINT_BLOB=8e4a6f5505c01b655ce991a46947485c791b0598
EXACT_LAUNCHER_SOURCE_COMMIT=8f7c5fdc5a7a3b91b4bc546ff6b3b1fa22d49033
EXACT_LAUNCHER_BLOB=bde632153e9f0223bf5675a1f6889505f18b215d
EXACT_LAUNCHER_11_BLOBS_MATCH=true
A1_TEST_COMMIT=938ff0686a02e3633f96d6e421789ecdd4cabefd
FINAL_PROJECT_STATE_HEAD_BEFORE_REVIEW=129219e20d8aa1ca8e8d9d979e4376a4dc0fe11a
SYNTHETIC_TEST_RUN=37949509680
SYNTHETIC_TESTS=134_PASS
MANAGER_CI_RUN=37949509800
MANAGER_CI=PASS
PUBLIC_SAFETY_CI_RUN=37949509718
PUBLIC_SAFETY_CI=PASS
SOURCE_OR_T1_MUTATION_IN_THIS_REVIEW=false
```

## 2. Independent closure: A1 CLOSED_PASS

Read actual immutable source `r4_shadow_stable_fingerprint.py`, caller `fresh_manager_operator`, deployment preflight, source-binding launcher and tests.

- `verify_legacy_r3_seal_readonly` continues to perform unchanged `r3.verify_r2` full R2 live safety/rollback/shadow and Manager/Broker validation, compares legacy R3 saved-vs-live field set, forbids all differences except `r2_shadow_inspect_sha256`, requires both digests be lowercase 64-hex.
- It still calculates the **transient** `legacy_full_inspect_digest_mismatch` as an explanatory result; there is no different caller putting that value into the R4 sealed document.
- `r4_authority_document` now **omits** `r3_legacy_digest_mismatch_classified`, and its durable protected fields are the raw saved-R3-seal bytes SHA, R2 journal SHA, stable R2 stopped-shadow protected config fingerprint, old Manager/Broker/R2 shadow IDs and fixed full-revalidation indicators. It cannot fail solely because a repeat Docker whole-inspect SHA happened to become equal or unequal.
- The R3 legacy seal itself stays unchanged, 0600, immutable as historical evidence. The R4 protected seal still uses exclusive create and 0600 state with replay prevention.
- The regression test `test_legacy_full_inspect_flip_both_directions_keeps_r4_seal_valid` actually calls seal and recheck with real stable shadow fixture and simulated **True→False** and **False→True** legacy SHA equality transitions, and verifies the R4 saved bytes remain identical. A separate test combines a mismatch-flag flip with original Manager identity change and requires `R4_SEAL_PROTECTED_STATE_DRIFT`. Existing tests reject unrelated history, journal, security, mount, network, log and privilege drift.
- All 11 file blob hashes in source-pinned Mac launcher at immutable launcher commit match the intended 11 source blobs at exact repaired-source commit; stage and R4 authorization ID unchanged.
- Latest PR-head 134 synthetic tests, Manager CI and Public safety CI all SUCCESS.

```text
A1=INDEPENDENT_CLOSED_PASS
A2_R4_DISTINCT_STATE_STAGE_CONTAINER_NAMES=CLOSED_SOURCE
A3_SYSTEMD_EXECSTOPPOST_IDENTITY_BOUND_RECOVERY=CLOSED_SOURCE
A4_SIX_BIND_MOUNTS_LOGGING_AND_SECURITY_PARITY=CLOSED_SOURCE
A5_REPAIRED_11_SCRIPT_EXACT_BINDING=CLOSED_PASS
```

These are **source reviews**, not claims of a current live T1 Manager replacement, a real successful rollback injection or first board boot.

## 3. A6 escalated to OPEN_PRELIVE_OPERATIONAL_BLOCKER

The repaired R4 exact source retains three independent timing budgets:

```text
SYSTEMD_ONESHOT_TIMEOUT_START_SECONDS=300
OPERATOR_WAIT_LIMIT_SECONDS=430
REMOTE_OPERATOR_EXECUTE_TIMEOUT_SECONDS=530
MAC_SSH_MAX_REMOTE_SECONDS=600
```

Concrete source paths:
- `fresh_manager_systemd_unit.render_unit`: `TimeoutStartSec=300`, `TimeoutStopSec=120`, `Restart=no`, `ExecStopPost` recovery.
- `fresh_manager_operator.WAIT_LIMIT_SECONDS=430`, with `wait_for_unit` checking loaded/inactive/failed and `ExecMainStartTimestampMonotonic`.
- `fresh_manager_mac_launcher.REMOTE_CODE`: the post-preflight remote operator execution is bounded to 530 s; launcher SSH is bounded to 600 s.
- `fresh_manager_deploy.LiveOps.preflight` validates the R4 seal (which revalidates R5 archive and R2 evidence) and again validates R5 backup; candidate UID/GID preflights use bounded Docker calls. `execute_transaction` performs shadow create/compare, stop old, park old, create/start candidate, repeat postflight, restart policy and commit. These are sequential, and their individually allowed waits collectively can exceed systemd's 300-second kill deadline on a slow host.

A timeout-triggered kill is **designed to fail closed** and invoke `ExecStopPost` rollback. However, if it occurs after the original Manager has been stopped or parked, it causes avoidable downtime and exercises critical rollback under load. A successful rollback under arbitrary host/Docker failures is not guaranteed. The existing synthetic tests do not establish a coherent total deadline or prove systemd interruption/rollback across each cutover phase.

The previously recorded A6 note is therefore elevated from nonblocking code-review note to **prelive operational reliability blocker** (not a newly observed T1 runtime failure). R4 can pass A1/A2–A5 source review while still being NOT READY for a fourth production replacement.

Required narrow repair design:
1. Establish one hierarchy of enforced timeouts with the systemd actual kill deadline safely **beyond** the operator's bounded transaction expectation, while keeping the outer remote/SSH deadlines able to return the supervised STOP and rollback result; explicitly account for preflight, candidate/old Manager cutover, `ExecStopPost` recovery, systemd cleanup and safe margin.
2. Avoid simply removing all deadlines or raising one timer in isolation. Keep `Restart=no`, nonreplayable R4 transaction/forensic seal, source manifest, six-mount contract and identity-bound rollback unchanged.
3. Add deterministic synthetic tests for slow source validation, slow candidate startup/postflight, systemd deadline expiring with no transaction, after old Manager stop/park, and after commit; verify FAIL_CLOSED and original Manager/Broker/rollback evidence as appropriate without claiming power-loss guarantees.
4. Rebind any changed protected script blobs and launcher source SHA; run exact-source CI and a fresh reviewer closure before requesting any **separate explicit** R4 live authorization.
5. No T1 cleanup/retry, no R2/R3 evidence deletion, and no Broker or board mutations.

## 4. Final prelive decision and STOP

```text
A1_FINAL=INDEPENDENT_CLOSED_PASS
A2_A5_FINAL=CLOSED_SOURCE
A6_FINAL=OPEN_PRELIVE_OPERATIONAL_BLOCKER
R4_PRELIVE_DECISION=NO_GO
R4_LIVE_PRODUCTION_AUTHORIZATION=false
R4_LIVE_ATTEMPT=false
R4_PRODUCTION_ACCEPTANCE=false
NEXT_ONE_GATE=N3W_P4_T1_R4_TIMEOUT_BUDGET_HIERARCHY_SOURCE_REPAIR_AND_SUPERVISED_ROLLBACK_REGRESSION
R2_R3_PRIVATE_JOURNALS_SHADOWS_SEALS=KEEP
R5_PRIVATE_BACKUP_AND_OLD_MANAGER_RW=KEEP
OLD_MANAGER_AND_BROKER=LAST_USER_READONLY_OBSERVED_RUNNING_ORIGINAL
CURRENT_T1_RUNTIME_REFRESH_THIS_GATE=false
BOARD_FIRST_NORMAL_BOOT=false
SETUP_SECRET_IMPORT=false
MERGE=false
AUTO_RETRY=false
```

Do not publish a fourth production Mac launcher command or infer live readiness from CI success alone. This gate is concluded **NO GO** pending A6 bounded timing/rollback source work, its CI and independent review.
