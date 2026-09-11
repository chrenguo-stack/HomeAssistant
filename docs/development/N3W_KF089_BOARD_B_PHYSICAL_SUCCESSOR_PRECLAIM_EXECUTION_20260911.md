# N3-W KF-089 Board B Physical Successor Host-Only Preclaim Execution — 2026-09-11

Status: `HOST_ONLY_PRECLAIM_PASS_LOCAL_PHYSICAL_HOST_NOT_YET_BOUND`  
Scope: GitHub/source/toolchain reproducibility preclaim only. No Board B, USB/serial, Flash, RF, T1, Broker, Manager, or Home Assistant access occurred.

## 1. Gate result

```text
GATE=HOST_ONLY_PHYSICAL_SUCCESSOR_PRECLAIM_EXECUTION
HOST_ONLY_PHYSICAL_SUCCESSOR_PRECLAIM_EXECUTION=PASS
GITHUB_REPRODUCIBLE_TOOLCHAIN_PRECLAIM=PASS

LOCAL_PHYSICAL_HOST_RUNTIME_PRECLAIM=NOT_EXECUTED
LOCAL_FIRMWARE_ARTIFACT_BINDING=NOT_EXECUTED
PHYSICAL_AUTHORIZATION_GRANTED=false
PHYSICAL_EXECUTION=false

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH_READ=false
FLASH_WRITE=false
OTADATA_WRITE=false
RF_EXECUTION=false
```

This result proves that the reviewed Board-B-recovery-only source and its expected ESP-IDF/esptool host contract can be reproduced and validated on an isolated GitHub Actions runner. It does **not** prove the user's eventual Mac physical-execution environment, local firmware artifact bytes, local USB target, or Board B identity/state.

## 2. Fresh repository rebind

Fresh at preclaim execution/closure:

```text
REPOSITORY=chrenguo-stack/HomeAssistant
FRESH_MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
FRESH_MAIN_TREE=91d2e4767887dad86525cf521e476d4a1234551a

OTA_GUARD_PR=385
OTA_GUARD_PR_STATE=OPEN
OTA_GUARD_PR_HEAD=7072a69939c9bef29e576d7e5f90800a3af7b867
REVIEWED_IMPLEMENTATION_HEAD=b8eb0aec6d26d3905e8bc861625c1e20f1c40ba3
```

PR #385 remains unmerged. This preclaim does not authorize its merge.

## 3. Reviewed OTA Guard binding

```text
TOOL_PATH=tools/n3w_ota_guard.py
TEST_PATH=tests/tools/test_n3w_ota_guard.py
TOOL_VERSION=0.2.2-review
TOOL_MODE=BOARD_B_RECOVERY_ONLY

TOOL_GIT_BLOB=e7b0019cdb9673fbf4e23653dec561ea40ff757c
TEST_GIT_BLOB=5b4405b178384e2f3326c6ad0a3a963508d723e4
REVIEWED_SOURCE_BLOB_BINDING=PASS
R2_FINAL_RESULT=PASS
```

The CI materialized both files from the exact reviewed implementation commit and recomputed Git blob object IDs over the fetched bytes. Both matched the frozen blob authorities exactly.

No fresh-deploy/app0-write path is introduced by this preclaim. Board B remains protected by the no-second-app0-flash contract.

## 4. Official ESP-IDF / esptool authority

```text
ESP_IDF_TAG=v5.5.4
ESP_IDF_COMMIT=735507283d5b2f9fb363a1901172dbd9e847945d
ESPTOOL_VERSION=5.2.0
ESPTOOL_WRAPPER_PATH=components/esptool_py/esptool/esptool.py
ESPTOOL_WRAPPER_SHA256=a8461ddc0852eb1d00cf9d13bfc7698a3cad92871e51f2c4d1ff7ee2561150be
ESP_IDF_WRAPPER_BINDING=PASS
```

The exact ESP-IDF wrapper was fetched by commit and its SHA-256 matched. The runtime package reported esptool 5.2.0.

Guard runtime binding proved:

```text
CHIP_NAME=ESP32-C6
FLASH_SECTOR_SIZE=0x1000
FLASH_WRITE_SIZE=0x400
WRITE_BLOCK_ATTEMPTS=1
TOOLCHAIN_RUNTIME_BINDING=PASS
```

The high-level esptool write-attempt value remains irrelevant to mutation because the reviewed Guard bypasses the high-level `write_flash` mutation path.

## 5. Host regression

```text
PYTHON=3.11.16_ON_GITHUB_RUNNER
PY_COMPILE_WARNINGS_AS_ERRORS=PASS
TARGETED_TEST_COUNT=45
TARGETED_TEST_RESULT=PASS
REVIEWED_HOST_REGRESSION=PASS
```

The suite covers the R2 safety contract, including no app0-write surface, identity/app0/otadata freshness gates, one-attempt direct mutation semantics, authorization-id requirement, mutation-boundary evidence, and bounded read-only failure-state capture.

## 6. CI and durable evidence

```text
PRECLAIM_WORKFLOW=.github/workflows/n3w-kf089-board-b-successor-preclaim-ci.yml
PRECLAIM_WORKFLOW_SOURCE_COMMIT=5069ec5ac878d2012f6a63523e8e35adfa688fe1
PRECLAIM_RUN_ID=34588075833
PRECLAIM_JOB_ID=103226779864
PRECLAIM_JOB_RESULT=PASS

ARTIFACT_NAME=n3w-kf089-board-b-host-only-preclaim
ARTIFACT_ID=10194435339
ARTIFACT_SIZE_BYTES=1266
ARTIFACT_SHA256=37082df0660952904e4f101fa46688b9d3d6b6adb8bb34b63e6a7739553d2169
ARTIFACT_EXPIRES=2026-10-11T10:12:48Z
```

The artifact contains the public-safe preclaim summary and the GitHub-runner `toolchain-binding.json`. It contains no Board B raw identity, serial path, Flash dump, credential, or private runtime evidence.

At workflow-source head `5069ec5ac878d2012f6a63523e8e35adfa688fe1`, 12 pull-request workflows were observed completed with no failure, cancelled, queued, or in-progress result.

## 7. Firmware authority and remaining local-artifact boundary

Frozen firmware authority remains:

```text
SOURCE_COMMIT=5d58727f5040281ee2beb9597f66a6a2da9bac57
SOURCE_TREE=b27b2968ea4e0b3bcb5f8312c3d31d391bd8d3ed
FIRMWARE_BIN_SIZE=1115648
FIRMWARE_BIN_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
DIAGNOSTIC_SCHEMA_VERSION=5
```

This host-only CI did not materialize the user's local `firmware.bin`; therefore:

```text
FIRMWARE_AUTHORITY_METADATA_REBOUND=PASS
LOCAL_FIRMWARE_ARTIFACT_BYTES_VERIFIED=false
```

Before any physical authorization is consumed, the local physical host must prove that the exact local artifact to be compared with Board B has the frozen size and SHA-256 above.

## 8. What this gate does not prove

The GitHub runner is not the user's Mac and has no physical Board B connection. Therefore the following remain deliberately unclaimed:

```text
LOCAL_MAC_PYTHON_BINDING=NOT_PROVEN
LOCAL_MAC_ESP_IDF_WRAPPER_BINDING=NOT_PROVEN
LOCAL_MAC_ESPTOOL_RUNTIME_BINDING=NOT_PROVEN
LOCAL_PRIVATE_EVIDENCE_DIRECTORY=NOT_PROVEN
LOCAL_FIRMWARE_ARTIFACT_BINDING=NOT_PROVEN
BOARD_B_USB_LOCATOR=NOT_PROVEN
BOARD_B_FRESH_ROM_IDENTITY=NOT_PROVEN
BOARD_B_CURRENT_OTADATA=NOT_PROVEN
BOARD_B_EXISTING_APP0_SHA256=NOT_PROVEN
```

No physical authorization should be granted on the basis of GitHub CI alone.

## 9. Next one gate

```text
NEXT_ONE_GATE=LOCAL_HOST_RUNTIME_PRECLAIM_AND_PHYSICAL_AUTHORIZATION
```

This next gate must start **host-only on the user's Mac**. Before any serial/USB board access it must bind:

1. exact OTA Guard reviewed source/blob;
2. exact Python interpreter used for execution;
3. exact ESP-IDF v5.5.4 wrapper path and SHA-256;
4. esptool runtime version 5.2.0, module hashes, flash constants, and single-block retry binding;
5. exact local Schema-v5 firmware artifact size + SHA-256;
6. a fresh empty private evidence directory outside the Git worktree;
7. the expected Board B identity privately, without publishing raw identity to GitHub;
8. a new one-time, non-replayable physical authorization identifier and its exact permitted mutation scope.

Only after that local host preclaim is PASS and the user explicitly grants that authorization may the physical executor open the Board B serial/USB target.

## 10. Future physical execution invariant

Once separately authorized, the physical path remains:

```text
fresh ROM identity
-> existing app0 exact readback (0x10000 + 1115648)
-> frozen SHA256 match
-> full 0x2000 otadata pre-read
-> recovery plan
-> same-connection identity + app0 + otadata-preimage freshness
-> exactly one 32-byte OTA-select mutation
-> full 0x2000 post-readback + exact verify
-> only then one normal boot
```

Any app0 mismatch, identity mismatch, preimage mismatch, unknown OTA state, source/toolchain drift, or ambiguous condition means STOP. There is no second app0 flash, automatic mutation retry, automatic rollback, or automatic boot after an uncertain mutation.

## 11. Frozen disposition

```text
HOST_ONLY_PHYSICAL_SUCCESSOR_PRECLAIM_EXECUTION=PASS
GITHUB_REPRODUCIBLE_TOOLCHAIN_PRECLAIM=PASS
LOCAL_PHYSICAL_HOST_RUNTIME_PRECLAIM=NOT_EXECUTED
PHYSICAL_AUTHORIZATION_GRANTED=false
BOARD_ACCESS=false

NEXT_ONE_GATE=LOCAL_HOST_RUNTIME_PRECLAIM_AND_PHYSICAL_AUTHORIZATION
```

This document authorizes neither PR #385/#387 merge nor physical Board B access.