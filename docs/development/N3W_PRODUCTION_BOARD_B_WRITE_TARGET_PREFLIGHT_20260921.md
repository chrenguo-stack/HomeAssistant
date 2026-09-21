# N3-W Production Board B Write Target Preflight — 2026-09-21

Status: `PREFLIGHT_EXECUTOR_PREPARED`

## Scope

```text
GATE=N3W_PRODUCTION_BOARD_B_WRITE_TARGET_PREFLIGHT_20260921_01
PREFLIGHT_READ_ONLY=true
FLASH_WRITE=false
NVS_WRITE=false
PARTITION_TABLE_WRITE=false
BOOTLOADER_WRITE=false
T1_MUTATION=false
APPLICATION_SERIAL_OPEN=false
```

This gate prepares and then runs a bounded ROM/esptool read-only preflight before any future production-firmware write.

## Candidate artifact authority

```text
PRODUCT_SOURCE=c1b3d9d016d06c21c9ff7070c0043163739565ca
PRODUCT_TREE=0c857fb0f830239717a2e937d176903a6acae8ac

ARTIFACT_ID=10644667734
ARTIFACT_NAME=n3w-production-f1rc2-c1b3d9d-exact-source
GITHUB_ARTIFACT_SIZE=4269260
GITHUB_ARTIFACT_SHA256=02fbe69f78511f33dec150dee635925dd4decf81048de3adfc6db8af4acc7a72

RELEASE_BUNDLE=n3w-production-f1rc2-c1b3d9d-exact-source.zip
RELEASE_BUNDLE_SIZE=4268748
RELEASE_BUNDLE_SHA256=93d830368b74e0dae904a9f5c4450378694575c68b917e749b480455662ff065

FIRMWARE_BIN_SIZE=1388928
FIRMWARE_BIN_SHA256=8bcd89aaf0be64188f8f98a64795fe78d573ae82dd2dd360c7ff459f80e58efa
FIRMWARE_FACTORY_BIN_SIZE=1454464
FIRMWARE_FACTORY_BIN_SHA256=434a3996ea8dc74c4a356f54d8a9405202f17b500680a66f5d49a2089cf67774
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

The executor validates the downloaded GitHub artifact outer ZIP, the inner release ZIP, its SHA256 sidecar, all eight release members, and the exact manifest before touching the board.

## Historical identity defect and redesign

The repository-frozen hardware-identity hash used by the old PR #437 executor is not reusable.

Historical evidence is:

```text
AUTOMATED_BOARD_IDENTITY_MATCH=FAIL
OPERATOR_TARGET_CONFIRMATION=PASS
OPERATOR_IDENTITY_OVERRIDE=true
IDENTITY_OVERRIDE_REUSABLE=false
RAW_BOARD_IDENTITY_PUBLIC=false
```

Therefore this preflight explicitly does **not** copy the old `EXPECTED_HARDWARE_ID_SHA256` and does **not** inherit the one-time operator override.

The new target binding is:

```text
operator confirms the physically connected target is Board B
+
fresh ROM silicon identity -> public-safe SHA256 only
+
fresh exact readback of the currently deployed PR437 application
+
fresh partition table readback
+
ESP32-C6 / 8MB Flash / security-state checks
+
exact production candidate artifact binding
```

The current deployed application used as the read-only physical continuity oracle is:

```text
CURRENT_DEPLOYED_SOURCE=4270f24a92a87dd5239d781ebba624c2f34b7fc2
CURRENT_DEPLOYED_ARTIFACT_ID=10619047221
CURRENT_APPLICATION_OFFSET=0x10000
CURRENT_APPLICATION_SIZE=1145984
CURRENT_APPLICATION_SHA256=b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843
```

This does not claim the historical automated identity mapping was correct. It creates a fresh short-lived binding for the currently connected target.

## Read-only board checks

The executor uses esptool v5 with `--no-stub` to perform:

```text
get-security-info
flash-id
read-flash 0x8000 0xC00
read-flash 0x10000 1145984
```

Expected results:

```text
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false

PARTITION_TABLE_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

CURRENT_APPLICATION_SHA256=
b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843
```

No raw ROM MAC is stored in the public closure; only the derived public-safe identity hash is emitted.

The ROM/esptool probe may transiently reset the target while entering/leaving ROM mode. It performs no persistent Flash/NVS write.

## Fail-closed conditions

Preflight stops before any future write authority if any of the following is true:

- operator target-confirmation token is absent or wrong;
- artifact outer or inner hash/member/manifest binding differs;
- target is not ESP32-C6;
- Flash is not 8 MB;
- Secure Boot or Flash Encryption is not proven disabled;
- partition-table hash differs;
- current application readback does not match the exact currently deployed PR #437 image;
- esptool major version is not 5.

## Output

On PASS the executor writes a private local JSON closure (mode 0600) containing:

- fresh public-safe ROM identity hash;
- hashed port locator;
- chip/Flash/security state;
- partition-table binding;
- current deployed application readback binding;
- production candidate artifact binding;
- preflight timestamp and 900-second validity window;
- explicit `write_authorization_granted=false`.

A successful preflight is not authorization to flash.

## Current execution boundary

```text
PREFLIGHT_EXECUTOR_SOURCE=PREPARED
PREFLIGHT_EXECUTOR_CI=NOT_YET_PROVEN
BOARD_PREFLIGHT_EXECUTION=NOT_YET_EXECUTED
FLASH_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false
```
