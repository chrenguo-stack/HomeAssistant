# N3-W KF-089 Remote T1 Window + Contract Stop — 2026-09-07

Status: `PUBLIC_SAFE_CURRENT_BOUNDARY`

## Scope

This record archives the successful recovery of the actual remote T1 live observer and the subsequent safe stop caused by a contradictory task contract. It does not change product source, firmware, T1, Broker, Manager, Home Assistant, provisioning state, credentials or keys.

Stable product/source authority:

```text
PRODUCT_SOURCE_AUTHORITY=483ff1c662dc74d6e12529e27a69819e68160f9e
PRODUCT_SOURCE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
OBSERVABILITY_FIRMWARE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
DIAGNOSTIC_SCHEMA_VERSION=3
```

Repository main at the completed execution boundary was:

```text
REPOSITORY_MAIN=88aa864ad681c87358ea2a31f85315e3491bfc6c
```

Later documentation-only descendants do not change the frozen product/source or artifact authority.

## Remote T1 observer recovered

The earlier local-Mac observer failure was corrected by rebinding the actual remote T1 authority. The following were proven read-only:

```text
REMOTE_T1_AUTHORITY_FOUND=PASS
REMOTE_T1_SSH_BINDING=PASS
REMOTE_T1_RUNTIME_BINDING=PASS
T1_DOCKER_SERVER_REACHABLE=true
T1_MANAGER_PRESENT=true
T1_MANAGER_RUNNING=true
T1_BROKER_PRESENT=true
T1_BROKER_RUNNING=true
REMOTE_T1_LIVE_OBSERVER_AVAILABLE=true
REMOTE_T1_OBSERVER_TYPE=MANAGER_CANONICAL_ACCEPTANCE
```

This confirms that the prior `No live T1 observer` result was a local observer-scope problem and not a remote T1 outage.

## Board A fresh remote T1 window

Board A private identity was rebound and current Direct telemetry was visible through the actual remote Manager/canonical path:

```text
BOARD_A_PRIVATE_IDENTITY_BINDING=PASS
BOARD_A_CURRENT_T1_DIRECT_LIVE=true
WINDOW_START=2026-09-07T12:44:53Z
WINDOW_END=2026-09-07T12:46:23Z
T1_DIRECT_ACCEPTED_COUNT=18
T1_DIRECT_REJECTED_COUNT=0
T1_DIRECT_DUPLICATE_COUNT=0
T1_SEQ_FIRST=289
T1_SEQ_LAST=306
T1_INGRESS_SOURCE=direct
BOARD_A_T1_ACCEPTANCE_BINDING=PASS
```

Therefore the Board A Direct path is independently proven live through T1 during this bounded 90-second window. This evidence does not require a live serial observer.

## Task-contract contradiction and safe stop

The task boundary globally stated:

```text
FLASH_WRITE=false
```

while a later phase required writing the Board A `app0` application partition. These requirements are incompatible. The executor therefore stopped safely before any NVS read or flash write.

The following remained unexecuted:

```text
BOARD_A_POWER_OFF_TIME=NOT_EXECUTED
DIRECT_ROM_ENTRY=NOT_EXECUTED
DIAG_SCHEMA=NOT_EXECUTED
DIAG_BOOT_SESSION=NOT_EXECUTED
BOARD_A_DIAG_SESSION_BINDING=NOT_EXECUTED
BOARD_A_DURABLE_DIAG_BINDING=NOT_EXECUTED
BOARD_A_APP0_SHA256=NOT_EXECUTED
BOARD_A_BOTH_SLOTS_EXACT_MAIN=NOT_EXECUTED
POST_NORMALIZATION_DIRECT_ACCEPTED=NOT_EXECUTED
```

Classification:

```text
PRODUCT_FAILURE=false
REMOTE_T1_OBSERVER_RECOVERY=PASS
BOARD_A_T1_ACCEPTANCE_BINDING=PASS
DURABLE_DIAG_BINDING=PENDING
BOARD_A_APP0_NORMALIZATION=PENDING
STOP_CLASS=TASK_CONTRACT_CONTRADICTION
```

The safe stop preserved the explicit no-write boundary and must not be interpreted as a product or T1 failure.

## Corrected successor structure

Do not combine the durable-diagnostic proof and the application-slot write under one contradictory global write policy.

Use two explicit successor boundaries:

1. **Serial-free durable diagnostic closure — read-only flash/NVS capture only.** Run a fresh remote-T1 Direct window, power Board A off, enter ROM Download directly without an intervening normal application boot, read only the NVS partition, extract only `gh_n3w_diag/snapshot`, bind its `boot_session` to the exact T1 boot session, and adjudicate the Board A Direct baseline. No application partition write is allowed in this boundary.
2. **Board A app0 normalization — explicit application-partition write authorization.** Only after the durable diagnostic baseline passes, write the frozen `efae17f4...` image to app0, verify exact readback, keep product NVS untouched, and perform a remote-T1 Direct post-check.

This separation removes the contract contradiction and preserves exact evidence attribution.

## Current frozen classification

```text
PRODUCT_FAILURE=false
KF089_STARTUP_GATE_REPAIR=PASS
BOARD_A_NEW_APP1_REFRESH=PASS
BOARD_A_LOCAL_DIRECT_DIAGNOSTIC_BASELINE=PASS
BOARD_A_T1_ACCEPTANCE_BINDING=PASS
BOARD_A_DURABLE_DIAG_BINDING=NOT_YET_PROVEN
BOARD_A_BOTH_SLOTS_EXACT_MAIN=NOT_YET_PROVEN
BOARD_B_OBSERVABILITY_REFRESH=NOT_EXECUTED
AUTONOMOUS_RELAY_DISCOVERY=NOT_PROVEN
```

## Next safe gate

```text
NEXT_GATE=KF089_BOARD_A_SERIAL_FREE_DURABLE_DIAG_CLOSURE
```

This successor must not include any application flash write. If it passes, the following gate may explicitly authorize Board A app0 normalization.