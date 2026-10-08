# N3-W Auto Safe Fallback Gate F — Clean Product-State Progress Alignment — 2026-10-05

Status: `CLEAN_PRODUCT_STATE_FINAL_ACCEPTANCE_PREPARATION`

## Repository authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
MAIN_TREE=ee977996a4c962097684519841dce2e3bcba23f2
PR=522
PR_STATE=OPEN_DRAFT
PR_MERGED=false
PR_HEAD_BEFORE_THIS_ALIGNMENT=8a8305838c9d769eba39b0b6fdead524749bf702
PR_HEAD_BRANCH=fix/n3w-auto-safe-fallback-production-core-convergence-20261003
MERGE=false
```

## Frozen R2 product source / artifact

```text
R2_SOURCE_HEAD=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
R2_SOURCE_TREE=13354818653e27cad8891bd2f3555e4f3feccc2b
EXACT_ARTIFACT_WORKFLOW_RUN=37204582611
EXACT_ARTIFACT_ID=11303803442
EXACT_ARTIFACT_NAME=n3w-auto-safe-fallback-f1rc2-67a0460-r2-exact-source
FIRMWARE_BIN_SHA256=7a4a53f08fd9550f46637a216f8bee89903428805f5de40d1e3bec9b17bc05ef
```

## Board B physical result

Existing Board B physically proved the repaired stale-Broker fallback chain:

```text
STALE_BROKER_FAILURE=OBSERVED
BROKER_RELOCATION_DISCOVERY=PASS
MANAGER_DISCOVERY_RESPONSE=PASS
RAM_ONLY_BROKER_RETARGET=PASS
MQTT_RECONNECT=PASS
BROKER_CANDIDATE_PROMOTION=PASS
PRODUCTION_TELEMETRY_GENERATION=PASS
DIRECT_MQTT_LOCAL_SUBMISSION=PASS
BROKER_TO_MANAGER_DELIVERY=PASS
MANAGER_DIRECT_SUBSCRIPTION=PASS
```

The Board B final canonical update was rejected only because of historical boot-session compatibility state:

```text
MANAGER_HIGHEST_SESSION_HEX=dc40c82e1467cf88
BOARD_B_BOOT_STATE_MAX_HEX_AT_READ=0000000000000011
MANAGER_RESULT=stale_boot_session
KF050_COMPATIBILITY_MIGRATION_GAP=CONFIRMED
R2_SOURCE_DEFECT=false
MANAGER_DEFECT=false
```

Manager replay protection is behaving correctly and must not be relaxed or cleared.

## Product-route decision

ADR-0008 classifies pairing-epoch / recovery-floor helper flows as `LEGACY_MIGRATION_ONLY`, `ENGINEERING_MIGRATION_ONLY`, or `BOARD_LAB_ONLY`. They are not normal product recovery authority and must not be used to claim Final Product Acceptance.

The user confirmed that brand-new unused ESP32-C6 boards are available. Therefore the final Gate F route is now:

```text
BOARD_B_LEGACY_MIGRATION_ROUTE=DEFERRED_NOT_FINAL_ACCEPTANCE
CLEAN_PRODUCT_STATE_BOARD_AVAILABLE=true
FINAL_ACCEPTANCE_ROUTE=CLEAN_PRODUCT_STATE_NEW_BOARD
```

No new board has yet been selected, identified, connected, read, flashed, paired, or mutated in this route.

## Current live baseline

The latest live evidence established:

```text
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=1
BROKER_RUNNING=true
CURRENT_MANAGER_DIRECT_SUBSCRIPTION=ACTIVE
STALE_BROKER_TEST_ORACLE_ON_BOARD_B=HISTORICAL_PRIVATE_ADDRESS
T1_LIVE_MUTATION_AFTER_FORENSIC=false
```

Private LAN addresses are intentionally not committed. The new chat must derive them from fresh live read-only evidence if needed.

## Closed routes

```text
R2_TRIGGER_NOT_RUNNING=CLOSED
DISCOVERY_NOT_EMITTED=CLOSED
BROKER_DISCOVERY_FAILURE=CLOSED
TLS_SERVER_NAME_MISMATCH=CLOSED
MQTT_CREDENTIAL_MISMATCH=CLOSED
BROKER_ACL_BLOCK=CLOSED
MANAGER_DIRECT_SUBSCRIPTION_MISSING=CLOSED
R2_SOURCE_DEFECT_AFTER_R2_PHYSICAL=CLOSED
MANAGER_REPLAY_RELAXATION=FORBIDDEN
MANAGER_HIGH_WATER_CLEAR=FORBIDDEN
BOARD_B_LEGACY_RECOVERY_HELPER_AS_FINAL_ACCEPTANCE=FORBIDDEN
```

## Current STOP / next route

```text
GATE_F_FINAL_CLEAN_PRODUCT_STATE_ACCEPTANCE=PENDING
B3_CLOSED=false
MERGE=false
R3_MUTATION=false

NEXT_ONE_GATE=N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_PREEXECUTION_DESIGN_20261005_01
```

The next gate is preparation/design only. It must first determine a safe, reproducible way to create a stale-Broker condition from a truly clean product state without importing Board B historical state. It must also define exact clean-board eligibility, fresh board read-only preflight, baseline pairing, stale-address transition, end-to-end canonical acceptance, rollback, and authorization boundaries before any new-board flash write or T1 network mutation.
