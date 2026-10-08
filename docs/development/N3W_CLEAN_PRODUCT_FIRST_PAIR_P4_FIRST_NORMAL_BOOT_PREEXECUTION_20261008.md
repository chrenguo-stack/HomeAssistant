# N3-W Clean Product First-Pair — P4 First Normal Boot Read-Only Preexecution — 2026-10-08

```text
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_FIRST_NORMAL_BOOT_PREEXECUTION_20261008_01
STATUS=READONLY_PREPARATION_COMPLETE_HOST_CHECK_PENDING
P3_PHYSICAL_RESULT=CLOSED_PASS
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_FIRST_NORMAL_BOOT_STARTED=false
P4_PRODUCT_PAIRING_STARTED=false
BOARD_ACCESS=false
BOARD_WRITE=false
T1_CONFIGURATION_MUTATION=false
MANAGER_DB_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
MANAGER_RESTART=false
BROKER_RESTART=false
AUTO_P4=false
MERGE=false
STOP=true
```

## 1. Authority and exact project baseline

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_EXPECTED_STATE=OPEN_DRAFT_UNMERGED
REPOSITORY_MAIN_AT_READONLY_REBIND=d423211b6196c2f2f0f01dff072c4f877fbe58ee

P3_PHYSICAL_CLOSURE=docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_WRITE_ONLY_OFFLINE_ARTIFACT_R2_CLOSURE_20261008.md
P3_RESULT=CLOSED_PASS
P3_AUTHORIZATION_CONSUMED=true
P3_REPLAY=false

CURRENT_SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc
CURRENT_BOARD_STATE=FOUR_REGIONS_WRITTEN_AND_EXACT_READBACK_PASS_NO_PRODUCT_BOOT
PRODUCT_SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
PRODUCT_SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
EXACT_ARTIFACT_ID=11469977052
EXACT_BUILD_RUN=37594598870
EXACT_RELEASE_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c
READBACK_BOOTLOADER=PASS
READBACK_PARTITIONS=PASS
READBACK_OTADATA=PASS
READBACK_FIRMWARE=PASS
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
```

The exact P3 closure is the only authority for the current board flash state. Previous prepared-but-not-executed or erased-unwritten entries are historical. This gate does not replay any board command.

## 2. Frozen P2 preboot runtime authority

Original P2 closure and the subsequent current clean-candidate P2 refreeze are the predecessor authority. The current live Manager/Broker/identity values must be newly observed, not assumed from the historical P2 record.

```text
MANAGER_CONTAINER_ID_SHA256=7b3c2a4de642e8a57da9d3f1652c9c35a27533c16f056736ecc89e289463bccc
MANAGER_STARTED_AT=2026-10-06T15:08:36.478286093Z
MANAGER_RESTART_COUNT=0

BROKER_RUNTIME_COMPOSE_PROJECT=n3wfc4
BROKER_RUNTIME_COMPOSE_SERVICE=broker
BROKER_CONTAINER_ID_SHA256=54a343cf903f5c73fd5b646c233e59cf0313b25d3f2caa55061fc64bc30741cd
BROKER_STARTED_AT=2026-10-06T05:01:47.110364692Z
BROKER_RESTART_COUNT=0

PAIRING_ADVERTISED_HOST_MODE=auto
NODE_CREDENTIAL_BROKER_HOST=A
T1_A_ADDRESS_SHA256=6257bd5c713a053e9efa4c9b036119a068dba2ddb8145e8288e89ad470822338

TLS_CA_SHA256=11ff133cdab8bf5f3093f6b488f8fa7e2579a1b5e383d066b1a1da56ad5dae9f
TLS_LEAF_CERT_SHA256=8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb
TLS_CA_AND_SERVER_NAME_SHA256=aae921c576258b264b60658bac022d5bcf81c3a3f641c50ba422df271f7a0947

MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SCHEMA=n3w.kf050.runtime-identity-snapshot/1
MANAGER_PREBOOT_IDENTITY_COUNT=5
MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SHA256=81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c
```

The frozen P2 SHA256 represents the preboot identity union drawn from the Manager registration lifecycle and separate credential lifecycle databases. The operator retains the raw identity set privately, not in GitHub or chat. Runtime product hardware_id is **not** inferred from the ESP32-C6 ROM/MAC silicon digest.

## 3. Read-only host preboot continuity executor

```text
READONLY_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PREBOOT_RUNTIME_CONTINUITY_READONLY_20261008_01
READONLY_GATE_SCOPE=ONE_T1_SSH_READONLY_SNAPSHOT_PLUS_ONE_NON_PAIRING_UDP_47111_DISCOVERY
READONLY_EXECUTOR_PATH=tools/execution_packages/n3w/auto_safe_fallback/p4_preboot_runtime_continuity_readonly/executor.py
READONLY_EXECUTOR_BLOB_SHA=0a588be746baa78c22e7dfa54167ad966de1e3f9
READONLY_STATIC_SCOPE_CHECK=PASS
READONLY_MAC_PYTHON_COMPILE=NOT_YET_PERFORMED
READONLY_MAC_LIVE_RESULT=PENDING_OPERATOR_EXECUTION

READONLY_OPERATOR_APPROVAL=GRANTED_TO_PREPARE_AND_CHECK
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_FIRST_NORMAL_BOOT_STARTED=false
```

The source is derived from the exact versioned P2 preboot read-only collector and adds strict continuity guards. It prompts locally for the previously validated private `root@T1` target, rejects an unexpected target SHA256, and uses one bounded SSH operation. The remote probe verifies running Manager and uniquely Compose-selected Broker, no resets, host networking/ports, effective LAN A, MQTT TLS on 8883, listener ports 47111/47112, and read-only SQLite mounts/schema.

The new preboot gate **requires exact equality**, not merely a fresh snapshot: frozen Manager/Broker IDs and StartedAt, both RestartCount=0, original LAN A digest, CA/leaf/SNI digest, stable identity snapshot count=5 and exact original preboot identity snapshot SHA256. Any drift is `STOP`, not a product defect. Only after those all pass does it issue one Mac-origin synthetic UDP discovery query and require the actual source/candidate host A.

Only hashes/boolean statuses and stage errors go to the public result. Raw LAN address, raw identities, raw discovery response, private T1 target and any credentials remain in the Mac private directory.

## 4. P4 proper — physical substage design

No product boot may occur in this read-only gate. The P4 physical stages require their own explicit operator approval after this host preflight has passed:

**P4-A normal product boot / Wi-Fi setup:** Freeze the host results, keep P3 exact board artifact, and only then perform one authorized first normal product boot. Use the product's normal Wi-Fi provisioning QR/path. Do not use serial/NVS extraction, alternate firmware, forced credentials or test harness. STOP if provisioning differs.

**P4-B Manager hello / on-device QR:** Require Manager auto discovery, TCP/47112 pairing and hello accepted. The product LCD page 5 must show the real `GHN3W2` pairing QR. Optical scan on the physical LCD is the sole QR authority. STOP after physical QR visibility and before handling the private scanned payload.

**P4-C runtime product identity binding:** On the frozen Manager preboot identity base, require exactly one unique newly created pending identity, match the optically scanned product hardware_id and pairing_id by SHA256 against that pending transaction, prove no historical NODE_ID, credential, retirement ownership or replay binding for that **product** identity. If any ambiguity, STOP before import; do not promote the ROM silicon digest into a product ID.

**P4-D Setup Secret handoff:** Only after C PASS and the corresponding separate approved private handling path, pipe the private scanned payload to `greenhouse-manager-pairing import-payload --payload-stdin` via the Manager-owned `pairing.sock`. No payload in argv, logs, GitHub, chat, direct SQLite, serial/NVS extraction, or alternate setup-secret path. For the finite pending TTL, complete host-side preparation and obtain necessary sensitive transfer authorization **before creating the pending transaction**; do not wait for another long code/build/CI gate after hello.

**P4-E Manager COMMIT and controlled interruption:** Require ordinary Manager credential COMMIT and exactly zero Manager-accepted canonical production telemetry messages for the new identity immediately before power interruption. The deliberate node-only interruption occurs strictly after COMMIT and before first accepted canonical. If the window was missed, mark the interruption trial INVALID, never call it product FAIL, and never erase/reset pairing state to replay a consumed fresh identity.

**P4-F recovery:** One controlled boot recovery must show valid durable initial boot-session, at least two strictly advancing accepted canonical telemetry samples, no pairing/NVS repair, no legacy recovery-floor helper, no replay/high-water clearing. P4 acceptance closure requires this proof.

All later P5/P6/P7 Direct baseline, real T1 relocation A→B and cold-start tests remain out of scope and separately authorized.

## 5. Explicit STOP checkpoints and constraints

```text
STOP_P4_PREBOOT=before_any_product_normal_boot
STOP_P4_QR=after_real_LCD_QR_visible_before_private_QR_intake
STOP_P4_SECRET=after_runtime_identity_binding_before_secret_import
STOP_P4_COMMIT=after_Manager_COMMIT_and_count_0_before_operator_CUT_POWER_NOW
STOP_P4_RECOVERY=after_valid_reboot_and_two_strict_canonical_advances

FULL_CHIP_ERASE_AGAIN=FORBIDDEN
FLASH_WRITE_AGAIN=FORBIDDEN
MANAGER_RESTART=false
BROKER_RESTART=false
MANAGER_DB_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
DIRECT_SQLITE_WRITE=false
AUTO_PAIRING_IMPORT=false
AUTO_P4=false
AUTO_P5=false
AUTO_P6=false
AUTO_P7=false

P4_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
CURRENT_GATE=READONLY_PREBOOT_CHECK_ONLY
STOP=true
```

## 6. Next action / evidence boundary

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PREBOOT_RUNTIME_CONTINUITY_READONLY_20261008_01
NEXT_ACTION=MAC_RUN_EXACT_READONLY_EXECUTOR_ONCE_AFTER_GIT_BLOB_AND_PYTHON_COMPILE
SUCCESS=P4_PREBOOT_PASS_TRUE_AND_MANAGER_BROKER_PREBOOT_CONTINUITY_PASS_TRUE
FAILURE=STOP_NO_RETRY_NO_PRODUCT_BOOT
P4_FIRST_BOOT_AUTHORIZATION_GRANTED=false
```

The live preboot verification is **not yet claimed PASS**. Read-only preparation and source static review are complete; operator Mac execution is needed to establish current T1 and Manager evidence. A future P4 first product boot must not be authorized/started from historical GitHub records alone.
