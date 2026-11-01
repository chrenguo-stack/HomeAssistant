# N3-W KF-089 ID24 Manager Relay DynSec ACL Repair — PREPARE progress

Status: `HOST_ONLY_PREPARATION_IN_PROGRESS`

This document records the durable public-safe state of the in-progress gate:

```text
PREPARE_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_PACKAGE
```

No T1 access, board access, RF execution, live Dynamic Security mutation, Broker mutation, credential change, or PR merge is authorized by this document.

## Proven predecessor

```text
BOARD_SIDE_RELAY_CHAIN=PROVEN
ID22R2_RESULT=STOP_T1_MANAGER_RELAY_ACCEPTANCE
ID23_EXECUTOR_RESULT=STOP
ID23_POSTEXEC_OFFLINE_ADJUDICATION=PASS
MANAGER_RELAY_DYNSEC_SOURCE_CONTRACT_DEFECT=PROVEN
LIVE_T1_MANAGER_DYNSEC_ROLE_MATCHES_SOURCE_DEFECT=PROVEN
ROOT_CAUSE=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
```

## Source repair

The Manager service identity plan now grants only the exact runtime Relay subscription topic:

```text
gh/v1/<system_id>/ingress/gateway/+/+/frame
```

with:

```text
subscribePattern
publishClientReceive
unsubscribePattern
```

No broader `ingress/gateway/#` permission is introduced.

## ID24 package

Repository-versioned package paths:

```text
tools/execution_packages/n3w/kf089/id24_manager_relay_dynsec_acl_repair/TASK.md
tools/execution_packages/n3w/kf089/id24_manager_relay_dynsec_acl_repair/executor.py
tools/execution_packages/n3w/kf089/id24_manager_relay_dynsec_acl_repair/manifest.json
tools/execution_packages/n3w/kf089/id24_manager_relay_dynsec_acl_repair/remote_dynsec_acl_mutator.py
tests/execution_packages/n3w/kf089/id24_manager_relay_dynsec_acl_repair/test_executor.py
.github/workflows/n3w-kf089-id24-manager-relay-dynsec-acl-repair-ci.yml
```

The hardened transaction contract requires:

```text
FRESH_PRECHANGE_DYNSEC_SNAPSHOT=true
PRECHANGE_SNAPSHOT_SHA256=true
ACTIVE_MANAGER_EXACT_RUNTIME_MATCH=true
EXACT_TARGET_ACL_COUNT=3
DEFAULT_SUBSCRIBE_DENY_PRESERVED=true
DEFAULT_PUBLISH_CLIENT_RECEIVE_DENY_PRESERVED=true
NO_BROADER_RELAY_GRANTS=true
NO_DUPLICATE_TARGET_ACLS=true
ROLLBACK_ON_ANY_POSTMUTATION_FAILURE=true
ROLLBACK_AUTHORITY=LIVE_DYNSEC_READBACK_MATCHES_PROVEN_PRESTATE
MANAGER_RESTART=false
BROKER_RESTART=false
AUTO_RETRY=false
```

## Current gate boundary

```text
NEXT_ONE_GATE=PREPARE_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_PACKAGE
GATE_STATE=IN_PROGRESS
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
READY_FOR_T1_REPAIR_AUTHORIZATION=false
```

The gate can advance to `READY_FOR_T1_REPAIR_AUTHORIZATION=true` only after the repair draft PR exists and the exact head passes its dedicated CI and public-repository safety checks. No live repair follows automatically.
