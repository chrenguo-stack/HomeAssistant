# N3-W Clean Product First-Pair / Runtime Identity
# P1 R2 Clean-Board Eligibility Read-Only Closure — 2026-10-08

```text
STATUS=CLOSED_PASS
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_STATE=OPEN_DRAFT
MERGE=false
```

## 1. Gate

```text
EXECUTION_ID=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_R2_20261007_01
AUTHORIZATION_CLASS=NEW_CANDIDATE_BOARD_READONLY_ACCESS_R2
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY=false
AUTO_RETRY=false
```

This closure supersedes the invalid R1 port-busy attempt for clean-board
eligibility. R1 remains historical evidence and is not replayed.

## 2. USB / ROM-mode isolation evidence

Before the successful board probe, the previous running-board state showed
intermittent macOS serial publication while the Espressif USB parent remained
present. A deliberately authorized BOOT+RESET isolation into ROM Download Mode
then produced a stable 10-second host-only observation:

```text
ROM_DOWNLOAD_MODE_USB_STABILITY=PASS
OBSERVATION_SECONDS=10
SAMPLE_COUNT=20
DISTINCT_STATE_COUNT=1

USB_PARENT_ALWAYS_PRESENT=true
IOSERIAL_ALWAYS_PRESENT=true
CU_ALWAYS_PRESENT=true
TTY_ALWAYS_PRESENT=true
```

This strongly associates the earlier serial-publication instability with the
previous running-board state, without proving the exact runtime mechanism.

```text
EXACT_RUNTIME_MECHANISM=TBD
PRODUCT_DEFECT=false
```

## 3. Preclaim and first board probe

The R2 guard required two zero-owner checks and a stable locator before crossing
the authorization claim boundary.

```text
USB_MODEM_COUNT=1
CHECK_1_OWNER_COUNT=0
CHECK_2_OWNER_COUNT=0
SAME_LOCATOR=true
PRECLAIM_PASS=true

ESPTOOL_VERSION_MAJOR=5
SECURITY_COMMAND_RC=0
CHIP=ESP32-C6
SECURE_BOOT=false
FLASH_ENCRYPTION=false
SECURITY_OUTPUT_SHA256=650681d9231b2e1308ad6ea4adda6689841b11cabad44920d9dc6316bb2d5d7f
```

## 4. Silicon binding

Raw ROM MAC remains private. Only the public-safe silicon-binding digest is
retained.

```text
SILICON_BINDING_SHA256=f9c00d136f84d1fdabb1e296608702539ed674271021b28cff2d4a23e4cd2bf7

HISTORICAL_BOARD_A_MATCH=false
HISTORICAL_BOARD_B_MATCH=false
BLOCKED_P4_BOARD_MATCH=false
SILICON_BINDING_UNIQUE=true
```

Frozen historical bindings used by the gate:

```text
BOARD_A=054df6316a48b21d216f35424aea38d10a2ca5ab62632b5611ddfe5a295ea4e5
BOARD_B=e3a489f954fdcde28e67f166fd01b536d3dd25172aecbfc3b8d056278584f9b1
BLOCKED_P4=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
```

The candidate is therefore a distinct physical board from all three frozen
historical identities.

## 5. Flash and partition-table proof

```text
FLASH_SIZE=8MB
FLASH_ID_OUTPUT_SHA256=2ebe955805d0d1468660545a80fe7082fa43905e8f4725d565d8a59a6df52128

PARTITION_TABLE_STATE=BLANK
PARTITION_TABLE_READ_SHA256=f47a8ec3e9aff2318d896942282ad4fe37d6391c82914f54a5da8a37de1300c6
PARTITION_COUNT=0
```

The 0x8000 / 0x1000 read-only partition-table window was entirely blank under
the gate parser.

## 6. NVS / old N3-W state proof

Because the partition table is blank, no NVS partition is defined by the
observed table.

```text
NVS_PARTITION_COUNT=0
NVS_KEYS_PARTITION_PRESENT=false
OLD_N3W_STATE_ABSENT=true
```

No erase was used to manufacture this result.

## 7. Identity boundary

```text
PRODUCT_HARDWARE_ID_SHA256=DEFERRED
PRODUCT_IDENTITY_STATUS=DEFERRED_UNTIL_RUNTIME_QR_MANAGER_BINDING
```

The product hardware identity is not inferred from the ROM MAC or silicon
binding. Runtime product identity remains a later LCD/Manager binding oracle.

## 8. Mutation audit

```text
APPLICATION_SERIAL_OPEN=false
FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
T1_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
AUTO_EXECUTE_P2=false
```

## 9. Closure

```text
CLEAN_BOARD_ELIGIBILITY=PASS

CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
SILICON_BINDING_UNIQUE=true
HISTORICAL_BOARD_MATCH=false
BLOCKED_P4_BOARD_MATCH=false
OLD_N3W_STATE_ABSENT=true

READY_FOR_P2=true
STOP=true
```

The candidate is eligible for the clean-product physical route.

## 10. Next ONE gate

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_T1_HEALTHY_BROKER_A_AND_MANAGER_PREBOOT_IDENTITY_SNAPSHOT_PREPARATION_20261007_01
AUTO_EXECUTE_NEXT_GATE=false
NEW_AUTHORIZATION_REQUIRED=true
```

P2 must fresh-rebind T1 / Broker-A / Manager and create the preboot identity
snapshot before any P3 erase/write. Historical T1 live state is not accepted as
fresh evidence.
