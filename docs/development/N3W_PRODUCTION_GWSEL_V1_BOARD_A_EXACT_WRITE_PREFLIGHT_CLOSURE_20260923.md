# N3-W Production Gateway Selection V1
## Board A Exact-Write Preflight Closure — 2026-09-23

Status: `CLOSED_PASS`

## Gate

```text
TASK=N3W_PRODUCTION_GWSEL_V1_BOARD_A_EXACT_WRITE_PREFLIGHT_20260923_01
BOARD_LABEL=A
READ_ONLY=true
FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false
```

## Exact executor authority

```text
EXECUTOR_BRANCH=
exec/n3w-production-gwsel-v1-three-board-exact-write-preparation-20260923

EXECUTOR_HEAD=
33e6658244146d890887876ba18f32dd61a879b5

EXECUTOR_TREE=
42c207566981de2d8841275771be736b76236aad

EXECUTOR_CI_RUN=
35819186201

EXECUTOR_CI_RESULT=SUCCESS
```

## Exact artifact authority

```text
ARTIFACT_ID=
10693728323

ARTIFACT_OUTER_SHA256=
e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814

RELEASE_BUNDLE_SHA256=
f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598
```

## Fresh Board A preflight evidence

```text
BOARD_A_SINGLE_USB_TARGET=PASS
BOARD_A_TEMPORARY_RESET_READONLY_AUTHORIZATION=true

BOARD_A_EXACT_WRITE_PREFLIGHT=PASS
BOARD_A_EXACT_WRITE_PREFLIGHT_EXIT_CODE=0

BOARD_A_HARDWARE_ID_SHA256=
f1f1e36fe4784a26b936d6a2bc5d239ab531f5683aca91356a5e39f3f566b1eb

BOARD_A_FROZEN_IDENTITY_MATCH=PASS

CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false

PARTITION_TABLE_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

CURRENT_OTADATA_SHA256=
8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3

BOARD_A_FRESH_PARTITION_BINDING=PASS
BOARD_A_FRESH_SECURITY_BINDING=PASS
BOARD_A_EXACT_ARTIFACT_BINDING=PASS
BOARD_A_MINIMAL_WRITE_ROUTE_BINDING=PASS
```

The current OTA-data value is boot-selection state only and is not used as silicon
identity.

## Frozen future write route

This preflight is bound to the already CI-validated minimal route:

```text
WRITE 0x9000  ota_data_initial.bin
WRITE 0x10000 firmware.bin

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FACTORY_IMAGE_WRITE=false
FULL_FLASH_ERASE=false
```

This closure does not authorize that write.

## Mutation boundary

The fresh preflight used ROM/esptool read-only inspection, including partition-table
and OTA-data readback.

```text
ROM_READ_ONLY_ACCESS_EXECUTED=true
FLASH_READ=true
FLASH_WRITE=false
NVS_WRITE=false
PARTITION_TABLE_WRITE=false
BOOTLOADER_WRITE=false
FACTORY_IMAGE_WRITE=false
FULL_FLASH_ERASE=false
PERSISTENT_BOARD_MUTATION=false
WRITE_AUTHORIZATION_GRANTED=false
```

ROM/esptool access may reset or enter the bootloader, but the terminal evidence does
not independently prove that an ephemeral reset occurred:

```text
EPHEMERAL_RESET_OCCURRED=NOT_DIRECTLY_OBSERVED
```

## Private single-use preflight state

The operator command created a private local preflight state:

```text
BOARD_A_EXACT_WRITE_PREFLIGHT_PRIVATE_STATE=CREATED
PREFLIGHT_MAX_AGE_SECONDS=900
REPLAY_PERMITTED=false
```

It is not a permanent write token. A future write must load it within its freshness
window, then freshly revalidate the board and artifact again before claiming the
single-use authorization.

If the state expires, is missing, or is otherwise invalid:

```text
AUTO_RECREATE_AND_WRITE=false
WRITE_WITH_STALE_PREFLIGHT=false
STOP_FOR_NEW_READONLY_PREFLIGHT=true
```

## Closure

```text
N3W_PRODUCTION_GWSEL_V1_BOARD_A_EXACT_WRITE_PREFLIGHT=CLOSED_PASS

BOARD_A_FRESH_IDENTITY_BINDING=PASS
BOARD_A_FRESH_PARTITION_BINDING=PASS
BOARD_A_FRESH_SECURITY_BINDING=PASS
BOARD_A_EXACT_ARTIFACT_BINDING=PASS
BOARD_A_MINIMAL_WRITE_ROUTE_BINDING=PASS

FLASH_READ=true
FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false

STOP=true
```

## Next ONE gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_GWSEL_V1_BOARD_A_EXACT_WRITE_20260923_01

BOARD_LABEL=A
BOARD_ACCESS_REQUIRED=true
EXPLICIT_BOARD_A_WRITE_AUTHORIZATION_REQUIRED=true
PREFLIGHT_MAX_AGE_SECONDS=900
AUTO_EXECUTE=false
```

The next gate may mutate Board A only after a separate explicit write authorization.
