# N3-W P4 — T1 Fresh Manager First One-Shot Preflight STOP and Docker LogConfig Preservation Repair (2026-10-09)

## Real Mac → T1 first execution (public-safe)

```text
TASK=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_LIVE_DEPLOY
LAUNCHER_SOURCE=0a0e163e8cc13ad8ecf8717a399f29dac0192369
FIRST_OPERATOR_RESULT=T1_FRESH_MANAGER=STOP:LOG_OPTIONS_UNSUPPORTED
SOURCE_EXACT_NINE_FILES=PASS
R5_PRIVATE_AND_LIVE_PREFLIGHT=AUTOMATED
REPORTED_BY=MAC_OPERATOR
OLD_MANAGER_STOP_PHASE_REACHED=false
SOURCE_EVIDENCE=non_mutating_preflight -> validate_create_contract -> LOG_OPTIONS_UNSUPPORTED
TRANSACTION_STATE_CLAIM_REACHED=false
RUNTIME_OLD_MANAGER_RUNNING=AWAITING_READONLY_CONFIRMATION
BROKER_RUNNING=AWAITING_READONLY_CONFIRMATION
FIRST_PRIVATE_STAGE_CREATED=true
PRODUCTION_MANAGER_REPLACEMENT=NOT_COMPLETED
AUTOMATIC_RETRY=false
```

The first attempt failed **before** `install_unit`, `systemctl start`, `docker stop`, `docker rename`, or any production container create operation. This classification follows the reviewed code path for that exact stop marker, not fresh host inspect. Its R5 root-private first stage remains in place; neither delete it nor replay the original launcher. No host sources, private IP, secret, or raw inspect data are archived.

## Cause and scoped source repair

At source authority preceding repair, `fresh_manager_deploy.validate_create_contract` required `HostConfig.LogConfig.Config` to be absent/empty, but the current live Manager has nonempty options, as proven by the returned stop code. `docker create` source also omitted explicit `--log-driver` and `--log-opt` flags. **Removing the rejection alone would silently alter runtime logging and undermine parity.**

Repair in PR #540:

1. Parse Docker `HostConfig.LogConfig` in one helper; constrain to current supported `json-file` driver, option keys matching simple safe names, string values without control characters and with bounded length. Reject malformed or unsupported configurations before stopping Manager.
2. Generate exact `docker create --log-driver` and sorted `--log-opt key=value` arguments from the current **live Docker inspect**. No hardcoded guess of actual T1 option values.
3. Maintain existing stopped-shadow and running-candidate `LogConfig` equality checking in `cutover_contract.py`.
4. Advance the staged script directory from `p4-fresh-manager-deploy-r1` to `p4-fresh-manager-deploy-r2` so the successor does not erase or replay the first stage.
5. Add synthetic regression for preserving three nonempty logging options exactly, rejecting malformed options, and detecting logging drift in shadow parity.

```text
SOURCE_REPAIR_CODE_HEAD=fd98c06d02037cba4f18043afeac62cd75893108
SOURCE_SYNTHETIC_CI_RUN=37938973508
SOURCE_SYNTHETIC_TESTS=107_PASS
PUBLIC_REPOSITORY_SAFETY_RUN=37938973771
SOURCE_TESTS=PASS
NEW_EXACT_NINE_FILE_MANIFEST=NOT_YET_FROZEN
SECOND_LIVE_ATTEMPT=NOT_AUTHORIZED_BY_SOURCE_TEST_ALONE
NEXT_REQUIRED_ACTION=ONE_SANITIZED_READONLY_T1_LOGCONFIG_AND_MANAGER_BROKER_STATUS_PROBE
```

The user-authorized one Manager replacement has not yet occurred. The first try reached neither the atomic transaction claim nor the actual Manager stop. Any resumed live attempt must bind the newly reviewed immutable nine-file source and fresh launcher, confirm current runtime, and honor the one-shot/replay boundary; no blind command retry.

## STOP

Do not invoke the previous `fresh_manager_mac_launcher.py` again. Do not manually stop/rename/remove containers, clean the original private staging directory, alter Broker, boot boards, or import Setup Secret.

The only next operator task is a single sanitized read-only T1 inspect of Manager/Broker running state, logging driver/option key names (values limited to non-secret rotation/buffering settings), and parked/failed container-name existence. On mismatch, stop and investigate; on match, finish binding the successor Mac entry and current-source review before any live mutation.
