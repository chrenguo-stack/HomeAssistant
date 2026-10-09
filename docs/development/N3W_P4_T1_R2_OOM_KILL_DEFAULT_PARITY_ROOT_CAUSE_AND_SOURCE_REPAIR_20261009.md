# N3-W P4 T1 — R2 shadow OomKillDisable default normalization: exact root cause and source-only repair

## 1. Real T1 read-only authority

After R2 operator `STOP:FRESH_MANAGER_SYSTEMD_TRANSACTION_FAILED`, the user captured Docker `HostConfig` comparison for the original running `greenhouse-manager` versus retained stopped `greenhouse-manager-p4-shadow`.

```text
ORIGINAL_RUNNING=true
SHADOW_STOPPED=true
DIFF_FIELD=OomKillDisable
OLD_OOM_KILL_DISABLE=None
SHADOW_OOM_KILL_DISABLE=False
HOST_CONFIG_DIFF_COUNT=1
READ_ONLY_HOST_PARITY_FORENSIC=COMPLETE
```

Existing R2 forensic authority separately proved:

```text
TRANSACTION_PHASE=FRESH_SOURCES_PREPARED_EMPTY
TRANSACTION_COMMITTED=false
CANDIDATE_ID_RECORDED=false
SYSTEMD_EXEC_RESULT=FAILED
SYSTEMD_JOURNAL_CODE=P4_FRESH_MANAGER_DEPLOY=STOP:CANDIDATE_HOST_SECURITY_PARITY_FAILED
ROLLBACK_RESULT=PASS
ROLLBACK_PHASE=ORIGINAL_MANAGER_RESTORED
ORIGINAL_MANAGER_ID_STILL_RUNNING=true
BROKER_ID_START_RESTART_UNCHANGED=true
PARKED_OLD_MANAGER=false
FAILED_CANDIDATE=false
SHADOW_EXISTS_STOPPED=true
```

The original Manager stop phase was **not reached**. This `PASS` is a verified original-running recovery invariant, not evidence that the old Manager was stopped and restarted. No real Manager replacement has succeeded.

## 2. Scope and exact logic

Docker's `OomKillDisable` unset (`None`) and explicit false (`False`) both do not disable OOM killing. The old-vs-new Docker inspect discrepancy here is a default representation mismatch, not evidence of changed process memory protection.

The original `cutover_contract._verify_candidate_matches_origin` compared all `HOST_COMPARE` fields using raw `==`; `None != False`, so it rejected the stopped shadow.

**Only** the `OomKillDisable` comparison is changed. For that single field:
- Both original and candidate must individually be exactly `None` or `False` (not `True`, integer `0`, or other values).
- The four allowed pairs (`None/None`, `None/False`, `False/None`, `False/False`) pass.
- Any `True`, even if `True/True`, remains forbidden by the pre-existing create contract and by parity verification.
- Every other HostConfig security, mount, logging, network, image, environment and restart parameter remains strictly checked; shadow and running-candidate verification share the same parity gate.

## 3. New source code and CI

```text
TASK=N3W_P4_T1_R2_OOM_KILL_DISABLE_PARITY_SOURCE_REPAIR
PR=540_OPEN_DRAFT
SOURCE_REPAIR_COMMIT=016c9fda97285cf0c86ad3d66a0ddad93206caa9
REGRESSION_TEST_COMMIT=9f7a382ec5f0afb794fd84d9052e09f98a84071d
SYNTHETIC_CI_RUN=37942250182
SYNTHETIC_RESULT=111_PASS
GREENHOUSE_MANAGER_CI_RUN=37942249947
GREENHOUSE_MANAGER_CI=PASS
PUBLIC_SAFETY_CI_RUN=37942249931
PUBLIC_SAFETY_CI=PASS
LIVE_T1_CHANGES_IN_THIS_REPAIR=false
OLD_MANAGER_RESTART=false
BROKER_MUTATION=false
BOARD_ACCESS=false
SETUP_SECRET_IMPORT=false
SOURCE_REPAIR_STATUS=CLOSED_PASS_SOURCE_ONLY
```

New tests exercise all four allowed default combinations, forbid `True` in either/both positions, and forbid integer `0` to prevent accidental Python bool/int equality admission. Existing regression tests continue to reject unrelated security and logging drift.

## 4. Important next-gate blocker, no blind retry

R2 wrote a one-shot root-private `fresh-manager-deploy-state-private.json` and created the three fresh RW directories. Its stopped shadow exists, and the systemd one-shot service is `failed`/`loaded`. By design, the prior Mac launcher refuses an existing stage, and the deployment preflight refuses an existing transaction state, fresh runtime base, shadow name and occupied systemd unit.

**Therefore, source repair PASS does not make the previous launcher replayable.** Do not delete the transaction file or shadow, overwrite R2 staging, reset systemd, or remove any old private state as a workaround. The R2 authorization already entered a transaction claim; it is not unconditional third-attempt authorization.

Proposed separate next source-only gate: design and review a **R2 forensic-seal / bounded cleanup / R3 fresh transaction** procedure. First prove exact original Manager and Broker identities and original-running safety, read-only R2 journal `rollback_result=PASS`, no candidate ID, stopped shadow's exact image and expected fresh bindings, and no parked/failed candidate. Archive R2 transaction evidence under the R5 root-private directory, not GitHub, before any change. Prepare a new isolated R3 transaction stage and journal, rather than silently erasing R2. Any shadow removal, systemd unit cleanup, new Manager cutover, or private-data mutation requires **a new explicit, exact authorization**, with fail-closed STOP and rollback validation.

```text
NEXT_ONE_GATE=N3W_P4_T1_R2_FORENSIC_SEAL_AND_R3_RESUME_DESIGN_SOURCE_ONLY
THIRD_LIVE_ATTEMPT_AUTHORIZED=false
R2_LIVE_STATUS=STOP_SAFE_ORIGINAL_RUNNING
R3_DEPLOYMENT=NOT_STARTED
NO_AUTO_RETRY=true
```
