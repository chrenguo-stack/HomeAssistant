# N3-W KF-089 Board B Local-Host Runtime Preclaim Specification — 2026-09-11

Status: `SPEC_FROZEN_HOST_ONLY_NO_DEVICE_ACCESS`  
Scope: the user's Mac execution host only, before any Board B / USB / serial access.  
This specification authorizes no physical action and no PR merge.

## 1. Gate

```text
GATE=LOCAL_HOST_RUNTIME_PRECLAIM_AND_PHYSICAL_AUTHORIZATION
PHASE=P0_LOCAL_HOST_RUNTIME_PRECLAIM

HOST_FILESYSTEM_READ_ALLOWED=true
PRIVATE_EVIDENCE_WRITE_ALLOWED=true
NETWORK_READ_ALLOWED=true
GITHUB_READ_ALLOWED=true

USB_ENUMERATION_ALLOWED=false
SERIAL_ENUMERATION_ALLOWED=false
SERIAL_OPEN=false
BOARD_RESET=false
FLASH_READ=false
FLASH_WRITE=false
OTADATA_WRITE=false
RF_EXECUTION=false
T1_ACCESS=false
```

P0 ends before any device enumeration or serial open. A PASS only makes a later explicit physical authorization eligible; it does not consume or imply one.

## 2. Frozen authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REVIEWED_IMPLEMENTATION_HEAD=b8eb0aec6d26d3905e8bc861625c1e20f1c40ba3
TOOL_GIT_BLOB=e7b0019cdb9673fbf4e23653dec561ea40ff757c
TEST_GIT_BLOB=5b4405b178384e2f3326c6ad0a3a963508d723e4
TOOL_VERSION=0.2.2-review
TOOL_MODE=BOARD_B_RECOVERY_ONLY

ESP_IDF_TAG=v5.5.4
ESP_IDF_COMMIT=735507283d5b2f9fb363a1901172dbd9e847945d
ESPTOOL_VERSION=5.2.0
ESPTOOL_WRAPPER_SHA256=a8461ddc0852eb1d00cf9d13bfc7698a3cad92871e51f2c4d1ff7ee2561150be

FIRMWARE_SOURCE_COMMIT=5d58727f5040281ee2beb9597f66a6a2da9bac57
FIRMWARE_SOURCE_TREE=b27b2968ea4e0b3bcb5f8312c3d31d391bd8d3ed
FIRMWARE_BIN_SIZE=1115648
FIRMWARE_BIN_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
```

Any mismatch means STOP. This gate does not repair or substitute an authority.

## 3. Required P0 checks

### P0.1 Repository and reviewed source

Freshly read GitHub and prove:

```text
FRESH_MAIN=<sha>
OTA_GUARD_PR_385_STATE=OPEN_OR_MERGED_EXACTLY_AS_OBSERVED
REVIEWED_IMPLEMENTATION_HEAD_EXISTS=true
TOOL_GIT_BLOB_MATCH=true
TEST_GIT_BLOB_MATCH=true
```

Materialize the exact reviewed tool/test into a private temporary execution directory outside any Git worktree. Recompute Git object blob IDs from bytes; filename equality is insufficient.

### P0.2 Local Python / esptool runtime

Find the Python interpreter that will later execute the Guard. Do not install or upgrade anything during P0. It must prove:

```text
PYTHON_EXECUTABLE=<private local path>
PYTHON_VERSION=3.11.x
ESPTOOL_VERSION=5.2.0
```

If no existing compatible environment is available, STOP with `LOCAL_TOOLCHAIN_MISSING`; do not silently install packages.

### P0.3 ESP-IDF wrapper

Locate an existing local ESP-IDF v5.5.4 wrapper if available. Preferred proof:

```text
IDF_GIT_HEAD=735507283d5b2f9fb363a1901172dbd9e847945d
WRAPPER=<IDF_PATH>/components/esptool_py/esptool/esptool.py
WRAPPER_SHA256=a8461ddc0852eb1d00cf9d13bfc7698a3cad92871e51f2c4d1ff7ee2561150be
```

If an existing IDF clone is not available, P0 may materialize the exact 269-byte wrapper from the exact official ESP-IDF commit into the private execution directory and verify its SHA-256. This is host filesystem preparation only, not physical access.

### P0.4 Guard `check-toolchain`

Create a fresh empty private evidence subdirectory outside all Git worktrees and invoke only:

```text
n3w_ota_guard.py --python <EXACT_PYTHON> --esptool <EXACT_WRAPPER> check-toolchain --evidence-dir <PRIVATE_DIR>
```

Required results:

```text
TOOLCHAIN_RUNTIME_BINDING=PASS
CHIP_NAME=ESP32-C6
FLASH_SECTOR_SIZE=0x1000
FLASH_WRITE_SIZE=0x400
WRITE_BLOCK_ATTEMPTS=1
ESPTOOL_VERSION=5.2.0
ESPTOOL_WRAPPER_SHA256=EXPECTED
```

Record module file SHA-256 values privately. Paths and module hashes may be summarized publicly only if they contain no private user path; raw local absolute paths stay private.

### P0.5 Exact local Schema-v5 firmware artifact

Locate the already-built Schema-v5 `firmware.bin` without touching any board. First check previously known build/evidence locations and project build caches. Do not rebuild automatically in P0.

Required:

```text
LOCAL_FIRMWARE_ARTIFACT_EXISTS=true
LOCAL_FIRMWARE_BIN_SIZE=1115648
LOCAL_FIRMWARE_BIN_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
LOCAL_FIRMWARE_ARTIFACT_BINDING=PASS
```

If the exact artifact cannot be found or the hash differs, STOP. A deterministic rebuild/materialization, if needed, is a separate host-only gate and must not be silently folded into this P0.

### P0.6 Private evidence directory

Create one new execution root with mode best-effort 0700, outside the repository/worktree. It must be new/empty before use. Files should be best-effort 0600.

The private evidence root may contain:

- local absolute paths;
- Python/runtime paths;
- module hashes;
- local firmware path and SHA;
- the expected full Board B hardware identity;
- the later authorization record.

It must not be committed to public GitHub.

### P0.7 Expected Board B identity binding — no device access

Recover the expected Board B full hardware identity only from already-existing private evidence / prior trusted local handoff. Do **not** enumerate USB or query a board in P0.

Required private result:

```text
EXPECTED_BOARD_B_IDENTITY_SOURCE=EXISTING_PRIVATE_TRUSTED_EVIDENCE
EXPECTED_BOARD_B_IDENTITY_BOUND=true
```

If the expected identity cannot be recovered unambiguously from private trusted evidence, STOP and request explicit operator rebinding. Never infer identity from a USB path.

Public GitHub closure must not contain the full raw identity. It may state only `EXPECTED_BOARD_B_IDENTITY_BOUND=true`.

## 4. Strict forbidden actions in P0

The executor must not run or invoke anything whose purpose is to inspect or open physical devices, including but not limited to:

```text
ls /dev/cu.*
ls /dev/tty.*
system_profiler SPUSBDataType
ioreg USB enumeration
esptool read-mac
esptool read-flash
serial open
USB open
board reset
DTR/RTS toggle
```

It also must not:

```text
install_or_upgrade_python_packages=true
rebuild_firmware=true
flash_any_partition=true
write_otadata=true
access_T1=true
change_GitHub_source=true
merge_PR=true
```

Any accidental physical-device access is a gate failure and must be reported.

## 5. P0 PASS criteria

P0 is PASS only if all are true:

```text
REVIEWED_SOURCE_BLOB_BINDING=PASS
LOCAL_PYTHON_BINDING=PASS
LOCAL_ESPTOOL_RUNTIME_BINDING=PASS
LOCAL_ESP_IDF_WRAPPER_BINDING=PASS
LOCAL_GUARD_CHECK_TOOLCHAIN=PASS
LOCAL_FIRMWARE_ARTIFACT_BINDING=PASS
PRIVATE_EVIDENCE_ROOT=PASS
EXPECTED_BOARD_B_IDENTITY_BOUND=true

USB_ACCESS=false
SERIAL_OPEN=false
BOARD_ACCESS=false
FLASH_READ=false
FLASH_WRITE=false
OTADATA_WRITE=false
RF_EXECUTION=false
```

There is no partial PASS.

## 6. P0 STOP classes

Use the first true class and stop:

```text
SOURCE_AUTHORITY_DRIFT
LOCAL_PYTHON_UNSUPPORTED
LOCAL_TOOLCHAIN_MISSING
LOCAL_ESPTOOL_VERSION_MISMATCH
LOCAL_IDF_WRAPPER_MISMATCH
GUARD_TOOLCHAIN_BINDING_FAIL
LOCAL_FIRMWARE_ARTIFACT_NOT_FOUND
LOCAL_FIRMWARE_ARTIFACT_HASH_MISMATCH
PRIVATE_EVIDENCE_ROOT_UNSAFE
EXPECTED_BOARD_B_IDENTITY_UNRECOVERED
UNEXPECTED_PHYSICAL_DEVICE_ACCESS
```

P0 performs no automatic remediation after a STOP.

## 7. P0 closure schema

The executor returns a public-safe closure exactly in this shape (local paths and raw board identity redacted):

```text
=== N3W KF089 BOARD B LOCAL HOST RUNTIME PRECLAIM CLOSURE ===

GATE=LOCAL_HOST_RUNTIME_PRECLAIM_AND_PHYSICAL_AUTHORIZATION
PHASE=P0_LOCAL_HOST_RUNTIME_PRECLAIM

FRESH_MAIN=<sha>
OTA_GUARD_PR_385_STATE=<state>
REVIEWED_IMPLEMENTATION_HEAD=b8eb0aec6d26d3905e8bc861625c1e20f1c40ba3
REVIEWED_SOURCE_BLOB_BINDING=<PASS|FAIL>

LOCAL_PYTHON_VERSION=<version|NOT_PROVEN>
LOCAL_PYTHON_BINDING=<PASS|FAIL|NOT_PROVEN>
LOCAL_ESPTOOL_VERSION=<version|NOT_PROVEN>
LOCAL_ESPTOOL_RUNTIME_BINDING=<PASS|FAIL|NOT_PROVEN>
LOCAL_ESP_IDF_WRAPPER_BINDING=<PASS|FAIL|NOT_PROVEN>
LOCAL_GUARD_CHECK_TOOLCHAIN=<PASS|FAIL|NOT_PROVEN>

LOCAL_FIRMWARE_ARTIFACT_EXISTS=<true|false|NOT_PROVEN>
LOCAL_FIRMWARE_BIN_SIZE=<integer|NOT_PROVEN>
LOCAL_FIRMWARE_BIN_SHA256=<sha256|NOT_PROVEN>
LOCAL_FIRMWARE_ARTIFACT_BINDING=<PASS|FAIL|NOT_PROVEN>

PRIVATE_EVIDENCE_ROOT=<PASS|FAIL|NOT_PROVEN>
EXPECTED_BOARD_B_IDENTITY_BOUND=<true|false|NOT_PROVEN>
EXPECTED_BOARD_B_IDENTITY_SOURCE=<class|NOT_PROVEN>

USB_ACCESS=false
SERIAL_OPEN=false
BOARD_ACCESS=false
FLASH_READ=false
FLASH_WRITE=false
OTADATA_WRITE=false
RF_EXECUTION=false

P0_RESULT=<PASS|STOP>
FIRST_FAILED_STAGE=<NONE|class>
STOP_REASON=<NONE|public-safe reason>

PHYSICAL_AUTHORIZATION_GRANTED=false
PHYSICAL_AUTHORIZATION_CONSUMED=false

NEXT_ONE_GATE=<PHYSICAL_AUTHORIZATION_DECISION|HOST_ONLY_REMEDIATION>

=== END ===
```

## 8. Authorization decision after P0 PASS

Only after P0 returns PASS may the high-level model prepare a proposed one-time physical authorization. The authorization must bind at minimum:

```text
TARGET_ROLE=BOARD_B
TARGET_IDENTITY=PRIVATE_EXPECTED_IDENTITY
TOOL_BLOB=e7b0019cdb9673fbf4e23653dec561ea40ff757c
FIRMWARE_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
ALLOWED_INITIAL_ACCESS=FRESH_ROM_IDENTITY_AND_EXACT_READBACKS
APP0_WRITE_ALLOWED=false
OTADATA_MUTATION_ALLOWED=ONLY_AFTER_ALL_RUNTIME_GATES_PASS
OTADATA_MUTATION_COUNT_MAX=1
OTADATA_ENTRY_WRITE_SIZE=32
MUTATION_RETRY=false
AUTO_ROLLBACK=false
```

The user must explicitly grant that exact authorization in a later turn. P0 itself never grants or consumes it.

## 9. GitHub/public evidence rule

After P0, commit only a public-safe closure/result document. Never commit:

- raw full Board B MAC or other private device identity;
- local absolute paths;
- raw Flash/otadata/app0 data;
- private evidence directory contents;
- credentials or keys.

The durable team-shared result should contain the PASS/STOP disposition, hashes/versions that are safe to publish, the first failed class if any, and the next gate.
