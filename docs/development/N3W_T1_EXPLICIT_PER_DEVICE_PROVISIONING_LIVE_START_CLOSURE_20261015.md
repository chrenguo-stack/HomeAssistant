# N3-W T1 Explicit Per-Device Provisioning Live Start Closure — 2026-10-15

```text
TASK=N3W_T1_EXPLICIT_PER_DEVICE_PROVISIONING_LIVE_START_20261015_01
RESULT=CLOSED_PASS

REPOSITORY=chrenguo-stack/HomeAssistant
PR=545
PRE_EXECUTION_PR_HEAD=058616a2886bd2e97dea14ec2ab1297c8f0ca577
DEPLOYED_RELEASE_SOURCE_HEAD=6ac82ae0872b05644e59470ffef7307dad14d359

AUTHORIZATION=N3W_T1_EXPLICIT_PER_DEVICE_PROVISIONING_LIVE_START_20261015_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false

START_EXECUTED_EXACTLY_ONCE=true
START_COMMAND_EXIT=0
START_JSON_CAPTURE=NOT_AVAILABLE:LOCAL_RESULT_PARSER_SYNTAX_ERROR_AFTER_REMOTE_START
SECOND_START_EXECUTED=false

POST_START_TRANSACTION_JSON_PRESENT=true
POST_START_FIRSTBOOT_COMPLETE_JSON_PRESENT=true

VERIFY_EXECUTED=true
VERIFY_STATUS=PASS
VERIFY_STATE=DEVICE_READY
VERIFY_RELEASE_ID=6ac82ae0872b05644e59470ffef7307dad14d359
VERIFY_EXIT=0
VERIFY_PARSE_EXIT=0
SYSTEM_ID_PRESENT=true
HOST_INSTANCE_ID_PRESENT=true
SECRET_VALUES_INCLUDED=false

TRANSACTION_JSON_PRESENT=true
FIRSTBOOT_COMPLETE_JSON_PRESENT=true

VERIFY_PRODUCTION_SERVICE_START=false
VERIFY_BOARD_ACCESS=false

BROKER_ACTIVATION_ACTIVE=inactive
SERVICES_ACTIVATION_ACTIVE=inactive
CERTIFICATE_LIFECYCLE_TIMER_ACTIVE=inactive

BROKER_ACTIVATION_ENABLED=not-found
SERVICES_ACTIVATION_ENABLED=not-found
CERTIFICATE_LIFECYCLE_TIMER_ENABLED=not-found

PRODUCTION_SERVICE_START=false
F4_ENTERED=false
BOARD_ACCESS=false
USB_SERIAL_FLASH_NVS_RF_ENTERED=false
MERGE=false

LIVE_RUNTIME_MUTATION=true:EXPLICIT_PROVISIONING_ONLY
TARGET_LOCATOR=PRIVATE_USER_CONTEXT_NOT_PERSISTED
```

## 1. Result

The explicit per-device provisioning Gate is **CLOSED_PASS**.

The exact product `start` command was executed once and returned exit code 0. Immediately after that invocation,
both durable lifecycle records existed:

```text
/var/lib/n3w-t1-provisioning/transaction.json
/var/lib/n3w-t1-provisioning/FIRSTBOOT_COMPLETE.json
```

That durable creation claimed and consumed the one-shot authorization. No second `start` was executed and replay
is permanently forbidden.

A local result-formatting helper supplied in chat contained a Python quoting syntax defect, so it failed to parse
the already-completed start JSON and conservatively printed `STOP_NONPASS_START`. This was an execution-wrapper
evidence-capture defect, not a T1 provisioning failure. The remote product command itself had already returned
`START_EXIT=0`, and durable transaction/completion state was present.

The follow-up verify-only command then independently returned:

```text
VERIFY_STATUS=PASS
VERIFY_STATE=DEVICE_READY
VERIFY_RELEASE_ID=6ac82ae0872b05644e59470ffef7307dad14d359
VERIFY_PRODUCTION_SERVICE_START=false
VERIFY_BOARD_ACCESS=false
VERIFY_EXIT=0
VERIFY_PARSE_EXIT=0
```

The verify result also proved that a product SYSTEM_ID and host instance identity are present without recording
their private values in public GitHub.

## 2. Stopped-boundary postcheck

The bounded postcheck confirms the provisioning Gate did not cross into F4:

```text
BROKER_ACTIVATION_ACTIVE=inactive
SERVICES_ACTIVATION_ACTIVE=inactive
CERTIFICATE_LIFECYCLE_TIMER_ACTIVE=inactive

BROKER_ACTIVATION_ENABLED=not-found
SERVICES_ACTIVATION_ENABLED=not-found
CERTIFICATE_LIFECYCLE_TIMER_ENABLED=not-found

PRODUCTION_SERVICE_START=false
F4_ENTERED=false
BOARD_ACCESS=false
```

The `not-found` enablement results are consistent with the already-established R4 staged boundary where later
activation units are intentionally absent until the separate activation package.

## 3. Authorization closure

```text
AUTHORIZATION_CLAIM_EVENT=DURABLE_TRANSACTION_CREATED
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false

ALLOWED_FUTURE_PROVISIONING_PATH=VERIFY_ONLY_WHILE_DEVICE_READY
SECOND_START_FORBIDDEN=true
DELETE_TRANSACTION_TO_REGAIN_UNPROVISIONED=false
```

No rollback to `UNPROVISIONED` is permitted by deleting transaction/completion records.

## 4. Scope closure

This Gate did not enter:

```text
F4 service activation / end-to-end acceptance
board access
USB
serial
Flash
NVS
RF
PR merge
```

No private T1 locator, raw SYSTEM_ID, host identity, credential, key or secret value is stored in this closure.

## 5. Classification of the local parser defect

```text
PRODUCT_DEFECT=false
T1_RUNTIME_DEFECT=false
PROVISIONING_SOURCE_DEFECT=false
LOCAL_EVIDENCE_WRAPPER_DEFECT=true
NEW_KNOWN_FAILURE_REQUIRED=false
```

Reason: the parser failed locally after the remote start had returned success; the product state subsequently
verified as `DEVICE_READY`. The defect does not reopen provisioning source work and does not authorize replay.

## 6. Stop and next stage

```text
CURRENT_STAGE=EXPLICIT_PER_DEVICE_PROVISIONING_CLOSED_PASS
CURRENT_STOP_POINT=AFTER_DEVICE_READY_BEFORE_F4
NEXT_STAGE=F4_SERVICE_ACTIVATION_AND_END_TO_END_ACCEPTANCE_PREPARATION

AUTO_EXECUTE_NEXT_GATE=false
NEW_AUTHORIZATION_REQUIRED=true

STOP=true
```
