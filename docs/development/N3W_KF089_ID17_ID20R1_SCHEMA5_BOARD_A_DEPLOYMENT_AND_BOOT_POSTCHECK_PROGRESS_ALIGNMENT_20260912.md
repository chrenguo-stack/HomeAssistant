# N3-W KF-089 ID17–ID20R1 Schema-v5 Board A Deployment and Boot Postcheck Progress Alignment

Updated: 2026-09-12  
Status: `PUBLIC_SAFE_PROGRESS_ARCHIVE`

This document records the public-safe KF-089 evidence progression from the ID17 Board A slot-state read-only preclaim through the ID20R1 Schema-v5 boot postcheck. It does not replace raw private evidence. Raw NVS images, full canonical board identities, private host paths, and other sensitive physical evidence remain private/local.

Fresh exact repository, runtime, and physical evidence takes precedence if later evidence proves drift.

## 1. Frozen source and image authority

```text
PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
DIAGNOSTIC_SCHEMA_VERSION=5
SCHEMA5_FIRMWARE_SIZE=1115648
SCHEMA5_FIRMWARE_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
BOARD_A_ROLLBACK_APP1_SHA256=5a3004647de0ef71e7be5664863a62b76a47c0cfdb32e38b07a296ca379f7562
```

The product behavior authority did not change during ID17–ID20R1. The work in these gates was evidence recovery, bounded Board A deployment, OTA selection change, and boot/runtime validation.

## 2. Predecessor evidence boundary

Before ID17, the durable evidence boundary was:

```text
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PROVEN
KF089_AUTHENTICATED_RELAY_ACQUISITION=PROVEN

BOARD_B_SCHEMA5=PROVEN
BOARD_B_PATH_STATE=RELAY_ACTIVE
BOARD_B_RELAY_TELEMETRY_ATTEMPTS=44
BOARD_B_RELAY_TELEMETRY_SUBMIT_SUCCESS=44
BOARD_B_UNICAST_COMPLETION_COUNT=44
BOARD_B_UNICAST_COMPLETION_SUCCESS=41
BOARD_B_UNICAST_COMPLETION_FAILURE=3

BOARD_A_SCHEMA_VERSION=3
A_COMPACT_RX=NOT_PROVEN
A_COMPACT_DECODE=NOT_PROVEN
A_COMPACT_FORWARD=NOT_PROVEN

KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
FIRST_UNPROVEN_STAGE=BETWEEN_B_UNICAST_COMPLETION_AND_A_COMPACT_RX
```

Board B had already proven RelayActive and unicast completion. The blocker was that the historical Board A capture was only diagnostic Schema v3 and therefore did not expose the Schema-v5 compact receive/decode/wrap/forward counters.

## 3. ID17 — Board A slot-state read-only preclaim

Execution package authority:

```text
PR=392
EXECUTION_PACKAGE_COMMIT=645f06a8bb0dc3873d7309f7a24d7e99862eca26
RESULT=PASS
REPLAY_PERMITTED=false
```

ID17 performed a read-only ROM-download inspection of Board A and proved:

```text
SELECTED_SLOT=1
INACTIVE_SLOT=0
ACTIVE_OTA_SEQ=4
ACTIVE_OTA_STATE=2
ACTIVE_SLOT_EXACT_SCHEMA5=false
INACTIVE_SLOT_EXACT_SCHEMA5=false
SCHEMA5_EXACT_SLOTS=[]
NEXT_ROUTE=PREPARE_BOARD_A_INACTIVE_SLOT_SCHEMA5_DEPLOYMENT_PACKAGE
```

No firmware write, NVS write, otadata write, application boot, RF execution, Board B access, or T1 access occurred in ID17.

## 4. ID18 — exact Schema-v5 deployment to inactive app0

Execution package authority:

```text
PR=393
EXECUTION_PACKAGE_COMMIT=b796acc305a06610b34c1d0d0e35fcf2b37336ff
RESULT=PASS
REPLAY_PERMITTED=false
```

ID18 used a bounded direct-ROM write path to write only the inactive app0 payload. The stock high-level write-flash path was not used; whole-image mutation retry and `flash_finish` were not used.

PASS proved:

```text
PRE_SELECTED_SLOT=1
PRE_ACTIVE_OTA_SEQ=4
PRE_ACTIVE_OTA_STATE=2

POST_APP0_EXACT_SCHEMA5=true
POST_APP0_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
POST_SELECTED_SLOT=1
POST_ACTIVE_OTA_SEQ=4
POST_ACTIVE_OTA_STATE=2

OTADATA_BYTE_IDENTICAL=true
APP1_HASH_IDENTICAL=true
APP1_SHA256=5a3004647de0ef71e7be5664863a62b76a47c0cfdb32e38b07a296ca379f7562
OTA_SLOT_SWITCH_EXECUTED=false
APPLICATION_BOOTED=false
```

ID18 therefore established an exact Schema-v5 image in app0 while preserving the selected rollback app1 and the complete OTA selection metadata.

## 5. ID19 — slot-switch-only mutation

Execution package authority:

```text
PR=394
EXECUTION_PACKAGE_COMMIT=643df426a03a20b319d8faa2a9d62eda9c56d6a6
RESULT=PASS
REPLAY_PERMITTED=false
```

ID19 changed only the bounded OTA selection metadata required to select app0 on the next normal boot. It did not rewrite either app payload and did not boot the application.

PASS proved:

```text
PRE_SELECTED_SLOT=1
PRE_ACTIVE_OTA_SEQ=4
PRE_ACTIVE_OTA_STATE=2

POST_SELECTED_SLOT=0
POST_ACTIVE_OTA_SEQ=5
POST_ACTIVE_OTA_STATE=2
POST_ACTIVE_COPY_INDEX=0

APP0_EXACT_SCHEMA5_UNCHANGED=true
APP1_HASH_UNCHANGED=true
NON_TARGET_OTADATA_SECTOR_UNCHANGED=true
OTADATA_EXACT_PLAN_MATCH=true

APP0_WRITE_EXECUTED=false
APP1_WRITE_EXECUTED=false
APPLICATION_BOOTED=false
RESET_AFTER_SWITCH=false
```

The next normal Board A boot was therefore bound to exact Schema-v5 app0 while the app1 rollback payload remained preserved.

## 6. ID20R1 — one normal Schema-v5 boot and read-only postcheck

Execution package authority:

```text
PR=395
EXECUTION_PACKAGE_COMMIT=88c7d29a1c6f9fc2b17e371b0c6dd95f8867ab61
AUTHORIZATION=N3W_KF089_ID20_BOARD_A_SCHEMA5_BOOT_POSTCHECK_20260912_20R1
RESULT=PASS
REPLAY_PERMITTED=false
```

ID20R1 authorized exactly one normal Board A boot, followed by a fresh ROM-download re-entry and a read-only postcheck. Board B and other compact senders were isolated for the clean baseline. No controlled Relay experiment, T1 access, flash write, NVS write, or otadata write occurred.

The operator interlock elapsed for approximately 177.7 seconds, exceeding the 45-second minimum. The postcheck proved:

```text
APPLICATION_BOOTED=true
SCHEMA5_APPLICATION_BOOT_PROVEN=true
FRESH_ROM_REENTRY_ATTESTED=true

SELECTED_SLOT=0
ACTIVE_OTA_SEQ=5
ACTIVE_OTA_STATE=2
APP0_EXACT_SCHEMA5=true
APP1_ROLLBACK_HASH_EXACT=true

DIAGNOSTIC_SCHEMA_VERSION=5
BOOT_SESSION_CHANGED_FROM_ID16=true
SNAPSHOT_UPTIME_MS=60371
RUNTIME_START_MODE=0
PATH_STATE=0
CURRENT_CHANNEL=11
DIRECT_CHANNEL_HINT=11
```

The live Direct runtime also produced internally consistent relay-advertisement/broadcast evidence:

```text
RELAY_ADVERTISEMENT_ATTEMPTS=26
RELAY_ADVERTISEMENT_SUBMIT_SUCCESS=26
RELAY_ADVERTISEMENT_SUBMIT_FAILURE=0
BROADCAST_COMPLETION_COUNT=26
BROADCAST_COMPLETION_SUCCESS=26
BROADCAST_COMPLETION_FAILURE=0
RELAY_ACTIVE_COUNT=0
RELAY_TELEMETRY_ATTEMPTS=0
```

Most importantly, before any new A/B Relay traffic, all Schema-v5 compact receive/processing counters were proven to be exactly zero:

```text
compact_rx_count=0
compact_state_reject_count=0
compact_child_binding_failure=0
compact_decode_success=0
compact_decode_failure=0
compact_wrap_failure=0
compact_forward_attempts=0
compact_forward_submit_success=0
compact_forward_submit_failure=0
```

This establishes a clean receiver-side before-state for the next A/B Relay experiment.

## 7. Current adjudication boundary

The combined ID15/ID17–ID20R1 evidence now proves:

```text
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PROVEN
KF089_AUTHENTICATED_RELAY_ACQUISITION=PROVEN

B_RELAY_ACTIVE=PROVEN
B_RELAY_TELEMETRY_SUBMISSION=PROVEN
B_UNICAST_TX_COMPLETION=PROVEN

A_SCHEMA5_APPLICATION_BOOT=PROVEN
A_SCHEMA5_RUNTIME_ALIVE=PROVEN
A_SCHEMA5_DIRECT_RUNTIME=PROVEN
A_SCHEMA5_COMPACT_BASELINE_ZERO=PROVEN

A_COMPACT_RX_UNDER_RELAY_TRAFFIC=NOT_YET_PROVEN
A_COMPACT_DECODE_UNDER_RELAY_TRAFFIC=NOT_YET_PROVEN
A_COMPACT_FORWARD_UNDER_RELAY_TRAFFIC=NOT_YET_PROVEN

KF089_END_TO_END_RELAY_TELEMETRY=NOT_YET_PROVEN
FIRST_UNPROVEN_STAGE=A_COMPACT_RX_UNDER_RELAY_TRAFFIC
```

The next experiment is now diagnosable stage-by-stage:

```text
B unicast completion
-> A compact_rx_count
-> state/capability gate
-> child binding
-> compact decode
-> wrap
-> forward attempt
-> MQTT/forward submit
```

A nonzero transition at each Schema-v5 counter can therefore be compared against the clean ID20R1 zero baseline.

## 8. Current physical/public-safe boundary

```text
BOARD_A_APP0_EXACT_SCHEMA5=true
BOARD_A_SELECTED_SLOT=0
BOARD_A_ACTIVE_OTA_SEQ=5
BOARD_A_ACTIVE_OTA_STATE=2
BOARD_A_SCHEMA5_APPLICATION_BOOT=PROVEN
BOARD_A_SCHEMA5_RUNTIME_ALIVE=PROVEN
BOARD_A_SCHEMA5_COMPACT_BASELINE_ZERO=PROVEN
BOARD_A_POSTCHECK_END_STATE=ROM_DOWNLOAD_MODE

BOARD_B_PHYSICAL_ACCESS_DURING_ID17_TO_ID20R1=false
BOARD_B_LAST_RELEVANT_SCHEMA5_RELAY_EVIDENCE=ID15
```

A fresh physical preclaim must still be performed before the next A/B experiment. USB device paths remain locators only and are never canonical board identity authority.

## 9. Execution package PR status

At this progress freeze, the execution package PRs remain intentionally open and unmerged:

```text
PR392_ID17_HEAD=645f06a8bb0dc3873d7309f7a24d7e99862eca26
PR393_ID18_HEAD=b796acc305a06610b34c1d0d0e35fcf2b37336ff
PR394_ID19_HEAD=643df426a03a20b319d8faa2a9d62eda9c56d6a6
PR395_ID20R1_HEAD=88c7d29a1c6f9fc2b17e371b0c6dd95f8867ab61
```

Their open/unmerged state does not invalidate the physical evidence produced from the exact authorized commits. No merge is implied by this archive.

## 10. Next route

```text
NEXT_ROUTE=PREPARE_KF089_SCHEMA5_TWO_BOARD_RELAY_VALIDATION_PACKAGE
```

The next phase should first materialize and CI-validate a versioned two-board Relay validation execution package. Only after exact-head review should a fresh, separate physical authorization be requested.

The later physical validation should preserve a clean before/after evidence model and capture both Board B transmission/completion counters and Board A Schema-v5 compact receive/decode/wrap/forward counters around the same bounded Relay traffic window.
