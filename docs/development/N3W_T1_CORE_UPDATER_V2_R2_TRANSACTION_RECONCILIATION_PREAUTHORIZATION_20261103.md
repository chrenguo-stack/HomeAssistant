# N3-W T1 Core Updater V2 R2 transaction reconciliation preauthorization — 2026-11-03

## Gate

```text
TASK=N3W_T1_CORE_UPDATER_V2_R2_TRANSACTION_RECONCILIATION_PREAUTHORIZATION_20261103_01
STOP=BEFORE_EXPLICIT_ROLLBACK_RECOVERY

LIVE_T1_MUTATION=false
R2_TRANSACTION_RECONCILIATION_AUTHORIZED=false
APPLY_RETRY=false
BOARD_ACCESS=false
```

## Exact updater authority

```text
MAIN=41e3031d1fa097043374c7582e552f5a803a1f20
UPDATER_V2_REVIEWED_HEAD=43de966c70d527433a915f40b9b630227531580a
UPDATER_V2_PACKAGE_RUN=41544508199
UPDATER_V2_PACKAGE_ARTIFACT_ID=13187736541
UPDATER_V2_PACKAGE_DIGEST=sha256:e09fb86c8444e0510b0200e759551d3571496064c743b4171992d46ab73babb9
UPDATER_V2_PYZ_SHA256=e92c093c7028d57ddc1e2c9c1eeb3fb97a0791a27b262b472c75482eaa3026bf
```

## Fresh live preflight

```text
LOCAL_V2_PACKAGE_BINDING=PASS
V2_PACKAGE_ON_T1=PASS
V2_STATUS=PASS
V2_INSPECT=PASS
R2_TRANSACTION_STATUS=FAILED_EMERGENCY
R2_TRANSACTION_PHASE=ROLLBACK_FAILED
R2_RECOVERY_REQUIRED=true
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_RUNTIME_CLASS=PREDECESSOR_HEALTHY
PREDECESSOR_A_RUNTIME_IDENTITY=PASS
HOMEASSISTANT_CONTINUITY=PASS
BROKER_CONTINUITY=PASS
LISTENER_CONTRACT=PASS
MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
BROKER_RESTART_COUNT=0
```

## Authorized action if user explicitly approves

The only permitted live command is the V2 updater explicit rollback/recovery operation with the exact confirmation:

```text
T1_CORE_UPDATER_MANAGER_ROLLBACK
```

Because fresh runtime classification is already `PREDECESSOR_HEALTHY`, V2 is expected to:
- perform strict current inspect;
- verify predecessor Manager A exact runtime identity;
- verify Home Assistant stable identity/network;
- verify Broker continuity;
- update only the durable updater transaction to terminal `ROLLED_BACK`;
- report `t1_mutation=false`;
- not stop or start Manager/HA;
- not rewrite `GH_MANAGER_IMAGE`;
- not mutate Broker, HA image, host or Board.

## Required postconditions

```text
ROLLBACK_OPERATION_STATUS=PASS
TRANSACTION_STATUS=ROLLED_BACK
T1_MUTATION=false
STATUS_RECOVERY_REQUIRED=false
POST_MANAGER=PREDECESSOR_A
POST_HA_CONTINUITY=PASS
POST_BROKER_CONTINUITY=PASS
POST_LISTENER_CONTRACT=PASS
POST_RESTART_COUNTS_UNCHANGED=true
LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
```

Any STOP result, runtime mutation report, service restart, Manager binding change, HA/Broker drift, listener drift, or non-terminal transaction after the command is a hard stop.

## Forbidden

- replay R1/R2 apply authorization;
- run `apply`;
- delete or hand-edit transaction state;
- restart Manager/HA manually;
- change Manager binding;
- mutate Broker or HA images;
- access Board;
- begin a new A->B apply before post-reconciliation baseline closure.

## Required user authorization

```text
N3W_T1_CORE_UPDATER_V2_R2_TRANSACTION_RECONCILIATION_20261103_01
```

This authorization is for transaction reconciliation only. It does not authorize a Manager A->B apply.
