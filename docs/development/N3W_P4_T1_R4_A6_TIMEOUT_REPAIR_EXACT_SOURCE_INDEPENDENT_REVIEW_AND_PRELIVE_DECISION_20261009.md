# N3-W P4 T1 — R4 A6 independent timeout / supervised recovery review (2026-10-09)

## Authority and source identity

User explicitly approved `N3W_P4_T1_R4_A6_TIMEOUT_REPAIR_EXACT_SOURCE_INDEPENDENT_REVIEW_AND_PRELIVE_DECISION`. The scope is **independent exact-source and prelive review**; not production execution, source repair within this review, T1 SSH access, any Manager/Broker/board/Setup Secret mutation, or PR merge.

```text
TASK=N3W_P4_T1_R4_A6_TIMEOUT_REPAIR_EXACT_SOURCE_INDEPENDENT_REVIEW_AND_PRELIVE_DECISION
PR=540_OPEN_DRAFT
PR_HEAD_AT_FRESH_REVIEW=39d47157cb7c2a9b9b541196b9950cf19c5e345e
FROZEN_PROTECTED_11_SCRIPT_SOURCE_REF=1528ae970974fd711f8a8a6441c29817a118d825
EXACT_LAUNCHER_COMMIT=c5d8b0137a509d1b4a80bd03208d1232b01ae84b
EXACT_LAUNCHER_GIT_BLOB=d66b7735e80550e2f6df6281978330edd3566d78
LAUNCHER_SOURCE_MANIFEST_11_FILES=ALL_EXACT_MATCH
A1_R4_LEGACY_SHA_VOLATILITY=CLOSED_SOURCE
REVIEW_CODE_MUTATION=false
T1_ACCESS=false
```

The independent review read `fresh_manager_deploy.py`, `fresh_manager_systemd_unit.py`, `fresh_manager_operator.py`, `fresh_manager_recovery.py`, `controlled_window.py`, `fresh_manager_mac_launcher.py`, targeted timeout and rollback tests, and immutable GitHub source blobs. `fresh_manager_mac_launcher.py` at its bound exact commit includes R4-only stage/authorization and the revised outer timeout. All eleven SHA1 Git blobs match the protected source commit.

## Confirmed: nominal hierarchy and pre-stop safety

```text
SYSTEMD_TYPE=oneshot
TIMEOUT_START_SECONDS=420
TIMEOUT_STOP_SECONDS=120
RESTART=no
EXEC_STOP_POST=identity_bound_recovery
OPERATOR_WAIT_LIMIT_SECONDS=580
REMOTE_PREFLIGHT_SECONDS=120
REMOTE_EXECUTE_SECONDS=660
MAC_SSH_MAX_SECONDS=920
PRE_OLD_STOP_MONOTONIC_GUARD_SECONDS=160
NOMINAL_START_WINDOW_REMAINING_AT_GUARD_SECONDS=260
```

The `execute_transaction` monotonic timer begins before `LiveOps.preflight`. Following R4 protected seal verification and stopped-shadow create/verify, *before* calling `ops.stop_old`, it requires elapsed time ≤160s and records a fail-closed `CUTOVER_TIME_BUDGET_TOO_LOW_BEFORE_OLD_STOP` if this fails. Tests inject 161s with zero `stop_old` calls, uncommitted journal, no candidate ID, and accept exactly 160s. Good source evidence for avoiding cutover when time is already exhausted.

The source still requires all original R2/R3 forensic/identity authorities, six-bind and logging/network parity, independent R4 roots and one-shot journal, and Broker identity/start/restart unchanged. The successful actual T1 cutover or rollback has not been verified.

## A6-1 — OPEN_PRELIVE_BLOCKER: 120s stop budget does not bound serial worst-case recovery

The R4 one-shot has `TimeoutStopSec=120` and invokes `fresh_manager_recovery.py --systemd-stop-post` after startup failure. In `recover_original`, the complete candidate-is-running recovery path may sequentially await:

1. `docker stop` of running candidate: `deploy.STOP_TIMEOUT_SECONDS + 15 = 45` seconds.
2. `docker rename` failed candidate: `_run_docker` defaults to 30 seconds.
3. `docker rename` parked original Manager back to original name: another default 30 seconds.
4. In `controlled_window.resume_original_manager`, `docker start` original Manager: timeout 30 seconds.
5. `resume_original_manager` stable-running observation: monotonic deadline 45 seconds, with original and Broker validation.

Sequential declared maximum **45 + 30 + 30 + 30 + 45 = 180 seconds**, before additional Docker inspect calls, broker checks or file I/O. Not every path requires all these steps; fast normal recovery may fit in 120s. However the code **does not guarantee** a complete recovery within systemd's declared 120s stop budget. If the systemd stop-post command itself exceeds that budget, recovery may be interrupted before the original Manager is restored or verified. This is an actionable timing design inconsistency, not evidence that the failure happened on T1.

The tests `test_fresh_manager_recovery.py` call `supervised_stop_post` with mocked Docker operations and confirm identity-bound restoration/failure signaling, but do not simulate actual wall-clock exhaustion or a systemd stop-post timeout. Passing 141 synthetic tests does not close this risk.

## A6-2 — OPEN_PRELIVE_BLOCKER: 580s monitor does not prove worst-case systemd failure completion

In `fresh_manager_systemd_unit.py`, `TimeoutStartSec=420` and `TimeoutStopSec=120` coexist with default `TimeoutStartFailureMode=terminate` (no override). systemd's documented behavior for startup timeout may include graceful SIGTERM followed by a **further wait up to the stop timeout** before a final kill, before cleanup; `ExecStopPost` is invoked even after startup failure. The service may therefore take more than the assumed single 420+120=540 budget in a slow or unresponsive case. `fresh_manager_operator.WAIT_LIMIT_SECONDS=580` has only 40s margin over 540 and cannot be claimed to cover every timeout/shutdown/recovery path merely from source arithmetic.

Authoritative general systemd service man page: https://github.com/systemd/systemd/blob/main/man/systemd.service.xml (ExecStopPost failure invocation; TimeoutStartFailureMode=terminate and TimeoutStopSec). This documents possible lifecycle behavior, **not** a T1-observed result; actual systemd version and phase timings on T1 have not been checked in this review. On operator wait expiration, code returns `SYSTEMD_TRANSACTION_WAIT_TIMEOUT`, leaving real unit/rollback outcome potentially unresolved; this is fail-closed but may require separate read-only incident forensics.

The tests assert numeric hierarchy `operator >= 420+120+30` and `remote >= operator+60`. They do not model separate grace and ExecStopPost time allowances under process unresponsiveness and do not measure real systemd STOP lifetime. A stricter finite budget contract and phase-aware tests are required before a justified GO.

## Review matrix and CI

```text
A1_R3_FULL_INSPECT_DIGEST_FALSE_POSITIVE=CLOSED_SOURCE
A2_R4_INDEPENDENT_NONREPLAYABLE_STATE=CLOSED_SOURCE
A3_IDENTITY_BOUND_FRESH_MANAGER_ROLLBACK=CLOSED_SOURCE_NOT_HOST_VALIDATED
A4_SIX_MOUNTS_SECURITY_LOGGING_OOM=CLOSED_SOURCE
A5_IMMUTABLE_11_BLOBS_ALL_BOUND=CLOSED_PASS
A6_PRESTOP_160S_GUARD=CLOSED_SOURCE
A6_1_STOPPOST_BUDGET_LT_DECLARED_RECOVERY_WAIT=OPEN_PRELIVE_BLOCKER
A6_2_STOP_FAILURE_GRACE_NOT_EXPLICITLY_BUDGETED=OPEN_PRELIVE_BLOCKER
FINAL_R4_PRELIVE_DECISION=NO_GO
SOURCE_REPAIR_GATE_CI=37951125296_141_PASS
SOURCE_REPAIR_MANAGER_CI=37951125303_PASS
SOURCE_REPAIR_PUBLIC_SAFETY_CI=37951125401_PASS
PR_HEAD_REVIEW_BASE_CI=37951380611_141_PASS;37951380893_MANAGER_PASS;37951380962_SAFETY_PASS
```

Source/CI green is not evidence of a coherent worst-case recovery or systemd stop-post lifetime. There is no current live T1 state refresh; only earlier read-only evidence that old Manager and Broker were original/running, R2 protected state and R3 seal retained, and R3 transaction absent.

## Required next gate — source-only A6 correction, not live deployment

```text
NEXT_ONE_GATE=N3W_P4_T1_R4_A6_STOPPOST_RECOVERY_WORST_CASE_AND_SYSTEMD_SHUTDOWN_BUDGET_SOURCE_REPAIR
REVIEW_RESULT=NO_GO
R4_LIVE_AUTHORIZATION=false
T1_MUTATION_IN_THIS_GATE=false
R4_DEPLOYMENT_ATTEMPTED=false
R4_MAC_ONE_SHOT_COMMAND_NOT_RELEASED=true
R2_R3_FORENSIC_SEAL_JOURNAL_SHADOW=KEEP
R5_OLD_MANAGER_ARCHIVE_AND_RW=KEEP
BROKER_MUTATION=false
BOARD_BOOT=false
SETUP_SECRET_IMPORT=false
MERGE=false
```

A narrowly scoped source-only repair should explicitly account for all Docker action/inspect/restart/health deadlines on the longest rollback path, systemd startup timeout termination grace and ExecStopPost lifecycle, and finite operator/remote/SSH bounds; consider global per-phase deadlines rather than blindly increasing all waits. Add timeout injection covering **time-consuming but individually successful** Docker actions whose combined duration exceeds stop-post allowance, and a synthetic systemd terminate-grace + ExecStopPost path. Preserve `Restart=no`, fail-closed/no-replay, original Manager/Broker identity checks, old data and historical R2/R3 forensic records. Only then repeat exact CI and independent review; a separately explicit user approval is required for any subsequent real T1 cutover.
