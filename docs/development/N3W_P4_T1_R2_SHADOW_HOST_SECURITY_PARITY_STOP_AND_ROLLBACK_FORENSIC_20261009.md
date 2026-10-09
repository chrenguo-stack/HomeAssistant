# N3-W P4 T1 R2 production attempt — stopped shadow HostConfig parity and original Manager safety

## Exact T1 results from Mac read-only forensics

```text
GATE=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_LIVE_DEPLOY_R2
R2_OPERATOR_FINAL=T1_FRESH_MANAGER=STOP:FRESH_MANAGER_SYSTEMD_TRANSACTION_FAILED
SYSTEMD_LOAD=loaded
SYSTEMD_ACTIVE=failed
SYSTEMD_RESULT=exit-code
SYSTEMD_EXEC_MAIN_STATUS=1
R2_PRIVATE_ROOT_COUNT=1
TRANSACTION_STATE_PRESENT=true
TRANSACTION_PHASE=FRESH_SOURCES_PREPARED_EMPTY
TRANSACTION_COMMITTED=false
ROLLBACK_RESULT=PASS
ROLLBACK_PHASE=ORIGINAL_MANAGER_RESTORED
CANDIDATE_ID_RECORDED=false
ORIGINAL_INSPECT_READ=PASS
MANAGER_EXISTS=true
MANAGER_RUNNING=true
MANAGER_IS_ORIGINAL=true
PARKED_OLD_EXISTS=false
FAILED_CANDIDATE_EXISTS=false
SHADOW_EXISTS=true
SHADOW_RUNNING=false
BROKER_EXISTS=true
BROKER_RUNNING=true
BROKER_ID_UNCHANGED=true
BROKER_START_UNCHANGED=true
BROKER_RESTART_COUNT_UNCHANGED=true
SYSTEMD_JOURNAL_CODES=P4_FRESH_MANAGER_DEPLOY=STOP:CANDIDATE_HOST_SECURITY_PARITY_FAILED,ORIGINAL_MANAGER_ROLLBACK=PASS
R2_REAL_DEPLOY=FAIL_CLOSED_BEFORE_OLD_MANAGER_STOP
LIVE_CANDIDATE_MANAGER_STARTED=false
SHADOW_TEST_CONTAINER_STILL_PRESENT_STOPPED=true
FRESH_RW_SOURCES_CREATED_PRIVATE=true
R5_ROLLBACK_BACKUP_AND_OLD_RW_SOURCES=RETAIN
NO_RETRY=true
```

All these results are user-provided raw sanitized probe output. No private IP/host paths or secrets copied into repo.

## Code-path analysis

Exact nine-file R2 source is `fd98c06d02037cba4f18043afeac62cd75893108`. In `fresh_manager_deploy.execute_transaction`:

- `TransactionState.create` is before creating fresh sources.
- `ops.prepare_fresh` creates three isolated fresh RW roots and advances `FRESH_SOURCES_PREPARED_EMPTY`.
- `ops.shadow_create_and_verify` creates a **stopped** shadow and compares it against the original Docker inspect. The failure comes from `cutover_contract._verify_candidate_matches_origin`'s `HOST_COMPARE` loop:
  `require(new_host.get(name) == old_host.get(name), "CANDIDATE_HOST_SECURITY_PARITY_FAILED")`.
- Because `_create` raises before `shadow_create_and_verify` reaches `docker rm SHADOW`, the stopped shadow is retained for forensics. Transaction never advances to `SHADOW_CREATE_AND_COMPARE_STOPPED` or `ops.stop_old`. The old Manager **was not stopped**.
- systemd `ExecStopPost` runs `fresh_manager_recovery.recover_original`, finds the intact running original by identity and validates broker, writes rollback `PASS`. This is a verified safe current running state; it does not imply an old Manager restart occurred.
- HostConfig mismatch key **not yet known**. Could be Docker defaults, an omitted `docker create` option, logging normalization or a materially different security setting. No broad weakening of parity is allowed without exact evidence.

## STOP and next gate

```text
CURRENT_PHASE=R2_READONLY_HOSTCONFIG_DIFF_FORENSIC
THIRD_LIVE_PRODUCTION_ATTEMPT_AUTHORIZED=false
DO_NOT_REPLAY_R1_OR_R2=true
DO_NOT_REMOVE_STOPPED_SHADOW=true
DO_NOT_DELETE_FRESH_RW_OR_R5_BACKUP=true
DO_NOT_RESET_SYSTEMD_OR_DOCKER=true
DO_NOT_TOUCH_BROKER_OR_BOARD=true
DO_NOT_IMPORT_SETUP_SECRET=true
NO_PR_MERGE=true
```

Next: run **one read-only command** comparing only `HOST_COMPARE` fields between original running `greenhouse-manager` and stopped `greenhouse-manager-p4-shadow`. Output field names, safe booleans/numbers/known option keys and types, **not** environment variables, raw labels, host bind source paths, secrets, complete Docker inspect or private file contents. Correlate exact mismatch with `docker create` source and make a narrowly scoped source-only fix + regression tests; preserve the shadow and transaction evidence. Require separate exact authorization before any additional live production mutation because R2 reached transaction journal claim.
