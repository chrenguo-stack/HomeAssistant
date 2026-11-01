# N3-W KF-099 Physical Validation Closure — 2026-09-28

Status: `PHYSICAL_VALIDATION_PASS_KNOWN_FAILURE_GUARDED`

## Scope

This record closes the physical-validation boundary for KF-099 after the rejected-hello client control-flow source repair was merged and an exact repaired firmware was bound and written to Board B.

This gate does not authorize or execute pairing repair. It validates only the no-authorization rejected-hello behavior: the Board must keep retrying hello with the same pairing transaction, must not enter `/v2/pairing/begin`, and must not cause durable registration or credential mutation.

Raw packet capture and local state snapshots remain private evidence. This document records only public-safe hashes, counts, and state results.

## Repository and repaired source authority

```text
REPOSITORY_MAIN_BEFORE_CLOSURE=3c51f60ef7ddcd8ad4ea7c984e01bf5886ed159d

KF099_REPAIR_PR=500
KF099_REPAIR_MERGE_COMMIT=c578bcb2e31f50771b6b08c231704da6bf36b729
KF099_SOURCE_CI=14_OF_14_PASS

PRODUCT_SOURCE_HEAD=c578bcb2e31f50771b6b08c231704da6bf36b729
PRODUCT_SOURCE_TREE=1678c7fa571db9b8f47b7b8a03dbd332620d1e19
TARGET_CONFIG=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
TARGET_BLOB_SHA=37654481747b21ca51ccecc246bf84ca437ab7a9
PAIRING_CLIENT_BLOB_SHA=79f050b189d89960889006c195ca5881bed7a277
```

The repaired client maps `rejected + transaction_disposition=continue` to WAIT, preserves the current pairing ID, returns `NOT_READY`, and stops before `/begin`. The Manager security boundary remains unchanged.

## Exact firmware artifact and Board B deployment

```text
ARTIFACT_RUN_ID=36399176674
ARTIFACT_ID=10959875986
ARTIFACT_NAME=n3w-kf099-c578bcb-boardb-exact-source
ARTIFACT_ZIP_SHA256=56abb5267ee1786f77930837d6a660745ee64f320d1c6ad64aac7c852aa115cb

APPLICATION_SHA256=d0875ca692f7bd4349fd7d8bcdab69318e6c8b737b69a48f667b6e72cb89cb60
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

BOARD_B_WRITE_EXECUTOR_PR=503
BOARD_B_WRITE_EXECUTOR_MAIN=3c51f60ef7ddcd8ad4ea7c984e01bf5886ed159d
BOARD_B_ROM_IDENTITY_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
BOARD_B_WRITE=PASS
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
```

The observed application and OTA-data hashes after the write matched the exact bound artifact. The one-shot physical write authorization was consumed and was not replayed.

## Passive physical observation

A 90-second passive TCP/47112 observation was performed after the exact repaired firmware was running on Board B. No repair authorization was granted.

```text
OBSERVATION_SECONDS=90
CAPTURE_BYTES=33216
CAPTURE_SHA256=c3e7bb5e02d861e4b36073216d0e0c7a0dd7322ee433241ac090965c5a13d055
TCP47112_PACKET_COUNT=216
TCP_CONNECTION_COUNT=18
IP_FRAGMENTED_PACKET_COUNT=0

PAIRING_PROTOCOL_HARDWARE_ID_SHA256=cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0

TARGET_HELLO_COUNT=18
TARGET_HELLO_DISTINCT_NONCE_COUNT=18
TARGET_HELLO_PAIRING_ID_UNIQUE_COUNT=1
PAIRING_ID_SHA256=142d1e0c9fc035645ce38e4681add39ba3ed5b3b0d60e14a4a1dfa398ab2472e

REPAIR_INTENT_REQUIRED_RESULT_COUNT=18
OTHER_TARGET_HELLO_RESULT_COUNT=0

TARGET_BEGIN_COUNT=0
GLOBAL_BEGIN_PATH_COUNT=0
RAW_BEGIN_STREAM_COUNT=0

CLIENT_STREAM_GAP_COUNT=0
CLIENT_UNPARSED_PAYLOAD_CONNECTION_COUNT=0
CLIENT_INCOMPLETE_REQUEST_COUNT=0
CLIENT_CAPTURE_COMPLETE=true
```

All 18 target hello requests used the same pairing ID while using 18 distinct hello nonces. All 18 matching Manager hello results were rejected with `reason=repair_intent_required` and no target or global `/v2/pairing/begin` request was observed.

The pairing ID hash matches the predecessor rejected-hello transaction recorded during KF-098/KF-099 diagnosis. This demonstrates that the repaired Board stayed on the existing pairing transaction rather than generating a new pairing ID while waiting.

## Manager continuity and durable-state check

The Manager remained on the accepted exact runtime image for the full observation. Before/after read-only SQLite snapshots were taken from the running Manager container.

```text
MANAGER_RUNNING=true
MANAGER_CONTINUITY=true
MANAGER_EXACT_IMAGE=true
MANAGER_RUNTIME_IMAGE=sha256:b806e7c8b97cc757965161a989f954df09427aa7d2700a6503e56e49cc8f9e4f

REGISTRATION_TARGET_ROW_COUNT_BEFORE=24
REGISTRATION_TARGET_ROW_COUNT_AFTER=24
REGISTRATION_TARGET_STATE_SHA256_BEFORE=742f966a6b075151c1b7654c24bfb234e97d51ed1abe39f2ed69ab73f2f8c33d
REGISTRATION_TARGET_STATE_SHA256_AFTER=742f966a6b075151c1b7654c24bfb234e97d51ed1abe39f2ed69ab73f2f8c33d
REGISTRATION_TARGET_UNCHANGED=true

CREDENTIAL_TARGET_ROW_COUNT_BEFORE=1
CREDENTIAL_TARGET_ROW_COUNT_AFTER=1
CREDENTIAL_TARGET_STATE_SHA256_BEFORE=58f181f3be1657eab2e062ff156fbedb1cb82eca3d2909b826491432f6af9aec
CREDENTIAL_TARGET_STATE_SHA256_AFTER=58f181f3be1657eab2e062ff156fbedb1cb82eca3d2909b826491432f6af9aec
CREDENTIAL_TARGET_UNCHANGED=true
```

The Manager was not restarted, and the target registration and credential state were byte-content-equivalent at the public-safe row-hash level before and after the observation.

## Closure criteria

The source-repair document required five physical conditions before KF-099 could move to GUARDED.

```text
HELLO_REACHES_MANAGER=PASS
MANAGER_REPAIR_INTENT_REQUIRED_WITHOUT_AUTHORIZATION=PASS
BEGIN_SUPPRESSION=PASS
PAIRING_TRANSACTION_PRESERVED=PASS
DURABLE_REGISTRATION_CREDENTIAL_STATE_UNCHANGED=PASS

HELLO_REJECT_BOUNDARY_PROVEN=true
PAIRING_ID_PRESERVED=true
BEGIN_SUPPRESSED=true

PAIRING_REPAIR_AUTHORIZATION=false
T1_RUNTIME_MUTATION=false
OBSERVATION_BOARD_MUTATION=false

KF099_PHYSICAL_VALIDATION=PASS
KF099_ROUTE_STATUS=CLOSED_PASS
KF099_KNOWN_FAILURE_STATUS=GUARDED

KF098_REOPEN=false
KF098_ROUTE_STATUS=CLOSED_PASS
```

## Disposition

KF-099 is closed as a validated product defect with an active regression guard.

The physical evidence demonstrates the intended WAIT behavior only while the Manager continues to reject hello for lack of repair authorization. It does not authorize repair and does not claim that a later authorized repair transaction has been physically exercised by this gate.

Any later identity-preserving repair execution is a separate gate and must retain the existing one-shot authorization and durable-state safety boundaries.
