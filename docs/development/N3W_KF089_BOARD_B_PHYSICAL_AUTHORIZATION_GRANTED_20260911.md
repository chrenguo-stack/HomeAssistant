# N3-W KF-089 Board B Physical Authorization Granted — 2026-09-11

Status: `GRANTED_NOT_YET_CLAIMED`  
Scope: one-time physical successor execution for Board B existing-app0 recovery to slot0.  
This record is public-safe and intentionally excludes the full private Board B hardware identity.

## 1. Authorization

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_20260911_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false
TARGET_ROLE=BOARD_B
EXPECTED_TARGET_IDENTITY=PRIVATE_TRUSTED_BINDING_ONLY
```

The operator explicitly granted this exact authorization in the project conversation on 2026-09-11. No other physical authorization is implied.

## 2. Frozen execution authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN_AT_ADJUDICATION=7478e0fbcf893761ab76cc9952e09e77cda22755
OTA_GUARD_PR=385
REVIEWED_IMPLEMENTATION_HEAD=b8eb0aec6d26d3905e8bc861625c1e20f1c40ba3
TOOL_GIT_BLOB=e7b0019cdb9673fbf4e23653dec561ea40ff757c
TEST_GIT_BLOB=5b4405b178384e2f3326c6ad0a3a963508d723e4
TOOL_VERSION=0.2.2-review
TOOL_MODE=BOARD_B_RECOVERY_ONLY

ESP_IDF_COMMIT=735507283d5b2f9fb363a1901172dbd9e847945d
ESPTOOL_VERSION=5.2.0
ESPTOOL_WRAPPER_SHA256=a8461ddc0852eb1d00cf9d13bfc7698a3cad92871e51f2c4d1ff7ee2561150be

FIRMWARE_BIN_SIZE=1115648
FIRMWARE_BIN_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
```

Any authority drift before claim means STOP and this authorization must not be consumed by mutation.

## 3. Claim / replay rule

The authorization must be claimed locally immediately before the first physical-device open. The executor must create a private durable authorization-claim record before opening the serial device.

```text
CLAIM_POINT=IMMEDIATELY_BEFORE_FIRST_DEVICE_OPEN
ON_FIRST_DEVICE_OPEN=AUTHORIZATION_CONSUMED_TRUE
SECOND_EXECUTION_WITH_SAME_AUTHORIZATION_ID=FORBIDDEN
```

Once the first Board B device open occurs, this authorization is consumed even if a later read-only precondition fails. Any later physical retry requires a new explicit authorization.

## 4. Allowed physical sequence

The only permitted physical sequence is:

```text
fresh ROM identity
-> exact existing app0 readback at 0x10000, length 1115648
-> SHA256 == 5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
-> full otadata pre-read at 0x9000, length 0x2000
-> Guard recovery plan
-> same mutation connection rechecks:
     expected private BASE_MAC
     app0 freshness
     exact otadata preimage freshness
-> at most one 32-byte OTA-select entry mutation at 0x9000 or 0xA000
-> full 0x2000 otadata post-readback
-> exact Guard postcondition verification
-> only after verified PASS: one normal boot
-> bounded Schema-v5 runtime observation
```

## 5. Hard prohibitions

```text
APP0_WRITE_ALLOWED=false
SECOND_APP0_FLASH_ALLOWED=false
BOOTLOADER_WRITE_ALLOWED=false
PARTITION_TABLE_WRITE_ALLOWED=false
NVS_HOST_WRITE_ALLOWED=false
GENERIC_WRITE_FLASH_ALLOWED=false
OTADATA_MUTATION_COUNT_MAX=1
OTADATA_ENTRY_WRITE_SIZE=32
MUTATION_RETRY=false
AUTO_SECOND_ATTEMPT=false
AUTO_ROLLBACK=false
```

If existing app0 size/hash does not match the frozen authority, STOP. No corrective app0 flash is allowed under this authorization.

If identity mismatches, STOP.

If any same-connection freshness check fails before mutation, STOP.

If an exception occurs after entering the mutation boundary, mutation must not be retried and the board must not be automatically booted or rolled back. Only the Guard's one bounded read-only failure-state capture is allowed.

## 6. Source/runtime precondition

Before the authorization is claimed, the Mac executor must fresh-rebind:

```text
reviewed source blob
exact Python interpreter previously proven by P0R1
esptool 5.2.0 runtime
ESP-IDF wrapper SHA256
local firmware artifact SHA256
private expected Board B identity binding
fresh empty private evidence directory
```

Any mismatch means STOP before device open.

## 7. Public/private evidence boundary

Private evidence may contain full Board B identity, absolute local paths, raw app0/otadata bytes, and authorization claim details. None of these raw values may be committed publicly.

Public closure may contain only safe hashes, sizes, stage/result classifications, mutation count, slot transition result, and booleans indicating identity binding PASS/FAIL.

## 8. Required execution closure

The executor must stop after the bounded workflow and return a public-safe closure containing at minimum:

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_20260911_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=<true|false>
AUTHORIZATION_CONSUMED=<true|false>
REPLAY_PERMITTED=false

FRESH_SOURCE_REBIND=<PASS|FAIL>
FRESH_LOCAL_TOOLCHAIN_REBIND=<PASS|FAIL>
FRESH_FIRMWARE_BINDING=<PASS|FAIL>
FRESH_PRIVATE_TARGET_IDENTITY_BINDING=<PASS|FAIL>

ROM_IDENTITY_BINDING=<PASS|FAIL|NOT_EXECUTED>
APP0_READBACK_SIZE=<integer|NOT_EXECUTED>
APP0_READBACK_SHA256=<sha256|NOT_EXECUTED>
APP0_BINDING=<PASS|FAIL|NOT_EXECUTED>
APP0_WRITE_EXECUTED=false

OTADATA_PRE_READ=<PASS|FAIL|NOT_EXECUTED>
OTADATA_PRE_SELECTED_SLOT=<app0|app1|UNKNOWN|NOT_EXECUTED>
OTADATA_MUTATION_EXECUTED=<true|false>
OTADATA_MUTATION_COUNT=<0|1>
OTADATA_POST_READ=<PASS|FAIL|NOT_EXECUTED>
OTADATA_POST_VERIFY=<PASS|FAIL|NOT_EXECUTED>
OTADATA_POST_SELECTED_SLOT=<app0|app1|UNKNOWN|NOT_EXECUTED>

NORMAL_BOOT_EXECUTED=<true|false>
SCHEMA_V5_RUNTIME_OBSERVATION=<PASS|FAIL|NOT_EXECUTED>

RESULT=<PASS|STOP>
FIRST_FAILED_STAGE=<stage|NONE>
STOP_REASON=<public-safe reason|NONE>
NEXT_ONE_GATE=<gate>
```

This authorization does not authorize merging PR #385 or #387 and does not authorize Board A access.