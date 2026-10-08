# N3-W Clean Product First-Pair Setup-Secret Handoff and Runtime Identity — Clean-Board Physical Acceptance Preexecution — 2026-10-07

```text
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_PHYSICAL_ACCEPTANCE_PREEXECUTION_20261007_01
STATUS=CLOSED_PASS
PREEXECUTION_DESIGN=PASS
BOARD_ACCESS=false
BOARD_WRITE=false
FLASH_ERASE=false
FLASH_WRITE=false
T1_MUTATION=false
BROKER_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
RECOVERY_FLOOR_EXECUTION=false
MERGE=false
```

## 1. Fresh authority binding

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_STATE=OPEN_DRAFT
PR_BASE=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75

SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
SOURCE_REPAIR=CLOSED_PASS

BUILD_RUN_ID=37594598870
ARTIFACT_ID=11469977052
ARTIFACT_NAME=n3w-clean-product-first-pair-handoff-f1rc2-629f096-exact-source
ARTIFACT_OUTER_SHA256=8587c7bf130f2f17e81b4e4f7652780f372f6a61697cc240e72a6af7392a7dc8
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c
FIRMWARE_BIN_SHA256=4e4442808fdff7fc3ca16eb379bd06741a9eea3364e31f1365be5e6bee325c65
FIRMWARE_FACTORY_BIN_SHA256=658645083ed2d83d6951abeb5f894dbde7d7124030c8bc1815683ed2bf24e914
BOOTLOADER_BIN_SHA256=985d0e0c5029d55d6cfab66470fe367200fd3e4e367e6a69ef1b557704c89fd5
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
OTA_DATA_INITIAL_BIN_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

The previous artifact bound to source `157448b...` is historical evidence only and is forbidden for resumed clean-product acceptance.

The board used in the blocked P4 attempt is also historical blocker evidence and is forbidden as the new clean candidate.

## 2. What this physical acceptance must prove

The repaired final product route must prove all of the following without engineering bypasses:

```text
A. one genuinely clean ESP32-C6 candidate is proven clean before any write
B. silicon binding and runtime product identity remain separate authorities
C. Manager identity history is snapshotted before the first product boot
D. the full replacement exact artifact is written and read back exactly
E. Wi-Fi provisioning uses the normal production path
F. LCD page 5 exposes the real GHN3W2 first-pair QR after Manager hello acceptance
G. the optically scanned hardware/pairing identity equals the unique new Manager pending transaction
H. Setup Secret enters Manager only through pairing.sock via import-payload --payload-stdin
I. pairing reaches Manager COMMIT without serial/NVS extraction, direct SQLite writes or repair pairing
J. the KF-050 controlled interruption occurs after COMMIT but before first accepted canonical production telemetry
K. reboot recovers with a valid initial boot session and at least two strictly advancing canonical telemetry samples
L. healthy Direct MQTT is frozen against real T1 address A
M. real T1 address relocates A -> B without board identity/Wi-Fi changes
N. the same running Manager discovers B and the node performs RAM-only Broker retarget
O. canonical telemetry continues without pairing repair or replay/high-water clearing
P. one cold start while T1 remains at B rediscovers B and advances boot session monotonically
```

## 3. Security and evidence invariants

The following remain non-negotiable:

```text
SETUP_SECRET_PUBLIC_LOGGING=false
SETUP_SECRET_PUBLIC_EVIDENCE=false
SETUP_SECRET_ARGV=false
RAW_PAIRING_PAYLOAD_PUBLIC_EVIDENCE=false
SERIAL_SECRET_CAPTURE_FOR_FINAL_ACCEPTANCE=false
RAW_NVS_SECRET_EXTRACTION_FOR_FINAL_ACCEPTANCE=false
PAIRING_SOCKET_AUTHORITY=true
DIRECT_SQLITE_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
LEGACY_RECOVERY_HELPER=false
RECOVERY_FLOOR_EXECUTION=false
CURRENT_BLOCKED_BOARD_REUSE_AS_CLEAN=false
```

The raw optically scanned `GHN3W2` payload is private execution material. It must not be pasted into ChatGPT, GitHub, shell argv, public logs or evidence documents.

Public evidence may contain only hashes, state classifications and secret-free results.

## 4. Identity model for the new run

The old assumption that a ROM/base-MAC-derived locator is the Manager product identity is permanently removed from acceptance.

```text
SILICON_BINDING_SHA256=preboot physical board binding only
PRODUCT_HARDWARE_ID_SHA256=runtime product identity only
PAIRING_ID_SHA256=current first-pair transaction only
```

The acceptance sequence must use two time-separated authorities:

### Preboot authority

Before the first product firmware boot, take a read-only Manager snapshot containing only the SHA-256 set of all known hardware identities:

```text
SNAPSHOT_SCHEMA=n3w.kf050.runtime-identity-snapshot/1
RAW_HARDWARE_IDS_PUBLIC=false
MANAGER_MUTATION=false
MANAGER_REPLAY_MUTATION=false
```

### Runtime authority

After the first product boot and Manager hello:

1. optically scan the LCD `GHN3W2` QR;
2. privately derive `PRODUCT_HARDWARE_ID_SHA256` and `PAIRING_ID_SHA256`;
3. require exactly one Manager pending identity newly appearing relative to the preboot snapshot;
4. require scanned hardware ID hash to match that unique new pending identity;
5. require scanned pairing ID hash to match that pending transaction;
6. require no prior approved NODE_ID, credential assignment, retirement ownership or replay binding for the new product identity.

Any ambiguity is STOP/INVALID, not PASS.

## 5. Staged execution model

No later stage may repair, erase or hide a failure from an earlier stage.

### Stage P1 — new clean-board eligibility, read-only

This stage may connect exactly one new candidate ESP32-C6 to the Mac for read-only ROM/eFuse/flash inspection.

It must not erase or write flash.

Required predicates:

```text
CANDIDATE_IS_BLOCKED_P4_BOARD=false
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
SILICON_BINDING_UNIQUE=true
SILICON_BINDING_NOT_HISTORICAL_BOARD_A=true
SILICON_BINDING_NOT_HISTORICAL_BOARD_B=true
SILICON_BINDING_NOT_BLOCKED_P4_BOARD=true
OLD_N3W_PEER_STATE_ABSENT=true
OLD_N3W_BROKER_STATE_ABSENT=true
OLD_N3W_PENDING_PAIRING_STATE_ABSENT=true
OLD_N3W_BOOT_STATE_ABSENT=true
OLD_N3W_SETUP_OR_PAIRING_RESIDUE_ABSENT=true
PRODUCT_HARDWARE_ID_SHA256=DEFERRED_UNTIL_RUNTIME_QR_MANAGER_BINDING
```

Relevant production storage names remain:

```text
gh_n3w_v2/peer
gh_n3w_v2/broker
gh_n3w_v2/pair_ack
gh_n3w_v2/pair_intent
gh_n3w_v2/setup
gh_n3w_v2/pair_epoch
gh_n3w/boot_state
```

If historical N3-W state is present or persistent state cannot be classified unambiguously:

```text
CLEAN_BOARD_ELIGIBILITY=FAIL_OR_INVALID
ERASE_TO_MANUFACTURE_CLEAN_STATE=false
STOP=true
```

### Stage P2 — fresh T1 / Broker-A preparation and preboot Manager snapshot

After P1 passes, perform a fresh T1 readback before deciding whether mutation is needed.

The initial baseline must prove:

```text
PAIRING_ADVERTISED_HOST_MODE=auto
REAL_T1_ADDRESS=A
NODE_CREDENTIAL_BROKER_HOST=A
BROKER_TCP_TLS_A_8883=PASS
MANAGER_DISCOVERY_AUTO_SOURCE=A
```

If T1/Broker/Manager preparation requires mutation, it must occur only in this stage and under its own exact authorization.

Before the board's first product boot, freeze:

```text
MANAGER_CONTAINER_ID
MANAGER_STARTED_AT
MANAGER_RESTART_COUNT
BROKER_CONTAINER_ID
BROKER_STARTED_AT
BROKER_RESTART_COUNT
TLS_CA_AND_SERVER_NAME_HASH
MANAGER_PREBOOT_IDENTITY_SNAPSHOT
MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SHA256
```

The real LAN address A and raw Manager identity set remain private evidence.

Once formal first-pair execution begins, Manager/Broker restart counts are frozen.

### Stage P3 — full exact flash with no product boot

Only after P1 PASS and P2 readiness may the board be mutated.

Use only the replacement artifact bound above.

The full flash layout is:

```text
FLASH_MODE=dio
FLASH_FREQ=80m
FLASH_SIZE=8MB
0x0000  bootloader.bin
0x8000  partitions.bin
0x9000  ota_data_initial.bin
0x10000 firmware.bin
```

Requirements:

```text
FULL_CHIP_ERASE=true
FOUR_REGION_WRITE=true
AFTER_WRITE=no-reset
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
READBACK_VERIFY_BOOTLOADER=PASS
READBACK_VERIFY_PARTITIONS=PASS
READBACK_VERIFY_OTADATA=PASS
READBACK_VERIFY_FIRMWARE=PASS
```

A full erase here is a formal initialization action only because P1 has already proven the board clean. The erase is never itself clean-state evidence.

### Stage P4 — first boot, optical pairing and KF-050 interruption acceptance

The first normal product boot begins only after the P2 Manager identity snapshot exists and P3 readback has passed.

#### P4-A — normal Wi-Fi provisioning

Use the production Wi-Fi provisioning QR/path only.

No serial pairing payload extraction is permitted.

#### P4-B — Manager hello and LCD pairing QR

After Wi-Fi joins:

```text
MANAGER_DISCOVERY=PASS
PAIRING_TCP_47112=PASS
HELLO_ACCEPTED=PASS
LCD_PAGE_5_PAIRING_QR_VISIBLE=true
PAIRING_QR_SOURCE=production_lcd
```

The QR must be optically scanned from the physical LCD.

#### P4-C — private identity binding before secret import

The scanned payload must remain private.

Before importing the Setup Secret:

```text
NEW_PENDING_IDENTITY_COUNT=1
PRODUCT_HARDWARE_ID_SHA256_MATCHES_NEW_PENDING=true
PAIRING_ID_SHA256_MATCHES_PENDING_TRANSACTION=true
PREBOOT_PRODUCT_IDENTITY_ABSENT=true
PRIOR_NODE_ID_HISTORY=false
PRIOR_CREDENTIAL_HISTORY=false
PRIOR_RETIREMENT_OWNERSHIP=false
PRIOR_REPLAY_BINDING=false
RUNTIME_IDENTITY_BINDING=PASS
```

If any item is ambiguous or mismatched:

```text
PAIRING_IMPORT=false
STOP=true
```

#### P4-D — normal product Setup Secret handoff

Only after P4-C PASS may the private scanned payload be fed over stdin to:

```text
greenhouse-manager-pairing import-payload --payload-stdin
```

The command must reach the existing Manager-owned `pairing.sock`.

The raw payload must not appear in argv, terminal transcript, GitHub evidence or ChatGPT.

Required:

```text
PAIRING_SOCKET_AUTHORITY=true
SETUP_SECRET_ARGV=false
DIRECT_SQLITE_WRITE=false
IMPORT_ACCEPTED=true
```

#### P4-E — Manager COMMIT and controlled interruption

After import, require pairing to reach the normal committed/approved credential state.

Then prove that no canonical production telemetry for the new identity has yet been accepted.

Only inside that window may the operator perform one controlled node power interruption.

```text
PAIRING_COMMIT=PASS
CANONICAL_TELEMETRY_COUNT_BEFORE_INTERRUPT=0
INTERRUPTION_AFTER_COMMIT=true
INTERRUPTION_BEFORE_FIRST_CANONICAL=true
```

If the first canonical telemetry is already accepted, the interruption attempt is INVALID rather than product FAIL.

Do not erase or re-pair the same board merely to retry a missed window.

#### P4-F — reboot recovery

After the controlled reboot:

```text
PAIRING_REPAIR=false
NVS_REPAIR=false
LEGACY_RECOVERY_HELPER=false
INITIAL_BOOT_SESSION_VALID=true
INITIAL_CANONICAL_TELEMETRY_COUNT>=2
INITIAL_CANONICAL_SEQ_STRICTLY_ADVANCES=true
KF050_FIRST_PAIR_INTERRUPTION_ACCEPTANCE=PASS
```

### Stage P5 — healthy Direct baseline on A

After P4 passes:

```text
DURABLE_BROKER_HOST=A
DIRECT_MQTT_TO_A=PASS
MANAGER_CANONICAL_BASELINE=PASS
MANAGER_CONTAINER_ID_FROZEN=true
BROKER_CONTAINER_ID_FROZEN=true
MANAGER_RESTART_COUNT_FROZEN=true
BROKER_RESTART_COUNT_FROZEN=true
BOARD_PRODUCT_IDENTITY_FROZEN=true
```

Keep the board powered and on the same Wi-Fi network for P6.

### Stage P6 — real T1 address relocation A -> B

The stale-Broker oracle remains a real T1 LAN address relocation.

Forbidden substitutes:

```text
BOARD_NVS_BROKER_EDIT=false
OLD_A_ALIAS=false
NAT_FORWARDER_FOR_A=false
DNS_ONLY_REWRITE=false
FAKE_DISCOVERY_RESPONSE=false
```

Before mutation, the relocation stage must prove B is conflict-free and rollback remains possible.

Required runtime result:

```text
OLD_A_UNREACHABLE=PROVEN
MANAGER_DISCOVERY_FROM_SAME_RUNNING_MANAGER=PASS
DISCOVERY_RESPONSE_SOURCE_EQUALS_B=true
DISCOVERY_CANDIDATE_HOST_EQUALS_B=true
RAM_ONLY_BROKER_RETARGET_TO_B=PASS
MQTT_TLS_RECONNECT_TO_B=PASS
BROKER_CANDIDATE_PROMOTION=PASS
DURABLE_BROKER_HOST_REMAINS_A=true
PAIRING_REPAIR=false
MANAGER_REPLAY_CLEAR=false
MANAGER_HIGH_WATER_CLEAR=false
MANAGER_RESTART_DURING_RELOCATION=false
BROKER_RESTART_DURING_RELOCATION=false
```

Product acceptance ceiling remains 120 seconds from the valid relocation trigger to usable Broker B recovery.

After promotion, observe up to 180 seconds and require at least two Manager-accepted canonical advances.

### Stage P7 — cold start while T1 remains at B

Perform exactly one controlled node reboot with T1 still at B.

Required:

```text
BOARD_DURABLE_BROKER_STILL_A=true
NODE_REDODISCOVERS_B_WITHOUT_REPAIR_PAIRING=true
BOOT_SESSION_MONOTONICALLY_ADVANCES=true
CANONICAL_TELEMETRY_CONTINUES=true
MANAGER_RESTARTED=false
BROKER_RESTARTED=false
```

Only after P7 passes may clean-product stale-Broker acceptance be closed.

## 6. Operator STOP points

The execution must stop for explicit physical operator action at these boundaries:

```text
STOP_1=after P1 read-only clean-board eligibility
STOP_2=after P2 T1/Manager preboot snapshot and before board erase/write
STOP_3=after P3 exact readback and before first normal product boot
STOP_4=after LCD pairing QR is visible and before private QR intake
STOP_5=after runtime identity binding PASS and before Setup Secret import
STOP_6=after Manager COMMIT with canonical count zero, waiting for CUT_POWER_NOW
STOP_7=after P4 reboot recovery and >=2 canonical advances
STOP_8=before real T1 A->B relocation
STOP_9=after P6 relocation acceptance
STOP_10=before P7 cold start
```

No operation after a STOP point is implicitly authorized by an earlier physical action.

## 7. PASS / FAIL / INVALID rules

```text
PASS=all predicates for the authorized stage are proven
FAIL=authority/environment are valid and product behavior violates a frozen predicate
INVALID=timing, identity, artifact or environment evidence is ambiguous
STOP=prerequisite is not proven or a new mutation class would begin
```

The following may never be used to convert FAIL/INVALID into PASS:

```text
erasing a non-clean board
reusing the blocked P4 board as a fresh candidate
serial Setup Secret extraction
raw NVS Setup Secret extraction
re-pairing after a failed first-pair attempt
editing durable Broker state
clearing Manager replay/high-water
lowering boot counters
legacy recovery-floor helpers
retaining old T1 A as an alias
restarting Manager/Broker during relocation
extending timing ceilings after failure
```

## 8. Full-channel fallback remains separate

This clean-product route uses simple stable Wi-Fi for stale-Broker acceptance.

```text
CLEAN_PRODUCT_STALE_BROKER_ACCEPTANCE=PENDING
FULL_CHANNEL_FALLBACK_PHYSICAL_RF_ACCEPTANCE=PENDING
DUAL_AP_FULL_CHANNEL_TEST_MIXED_INTO_THIS_GATE=false
```

A PASS on either axis does not imply a PASS on the other.

## 9. Gate disposition

```text
PREEXECUTION_DESIGN=PASS
REPLACEMENT_EXACT_ARTIFACT_READY=true
CLEAN_PRODUCT_FIRST_PAIR_PRODUCT_PATH_READY=true
RUNTIME_IDENTITY_BINDING_PATH_READY=true

BOARD_ACCESS=false
BOARD_WRITE=false
FLASH_ERASE=false
FLASH_WRITE=false
T1_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
MERGE=false

NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_20261007_01
STOP=true
```

The successor gate is read-only. It may inspect one new candidate board but may not erase/write flash and may not mutate T1.
