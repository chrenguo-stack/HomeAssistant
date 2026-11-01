# N3-W KF-096 PR #428 Exact Artifact Build and Binding — 2026-09-18

Status: `ARTIFACT_BINDING_AUTHORITY`

Fresh repository/runtime/physical evidence takes precedence if later evidence proves drift.

## Scope

This record closes only the build-only exact-artifact gate for the merged PR #428 KF-096 source repair.

No Board A/B access, serial open, flash write, T1 mutation, Broker/Manager/DynSec mutation, credential mutation, or physical validation occurred in this gate.

## Exact product source

```text
REPOSITORY=chrenguo-stack/HomeAssistant

PR428_SOURCE_HEAD=6cae8ea1a75096aab0e625ae56828d13931f7c57
PR428_MERGE=f357db25390ffd097e9b8608293870772f9cb16c
PR428_PRODUCT_SOURCE_TREE=3fae2b22b5537e0229b0f7eeacf9f0f3b3aa9a64

REPOSITORY_MAIN_AT_ARTIFACT_GATE=e2390faf2452730264c19687bf4022df974f04bd
REPOSITORY_MAIN_TREE_AT_ARTIFACT_GATE=94566c80256db64e8cf4b0cbece9bfd0f1acc417
```

The repository main tip already includes later documentation-only alignment. The firmware artifact is intentionally bound to the PR #428 merge commit `f357db25...`, not to the later documentation-only main tip.

## Build-only workflow authority

The proven PR #425 artifact mechanism was reused: a non-product build-only branch contains only a workflow that checks out the exact product source and asserts both HEAD and tree before compiling.

```text
BUILD_BRANCH=build/n3w-pr428-boardb-artifact-20260918
WORKFLOW_SOURCE_COMMIT=ec256e8b219942d61ecf583ae558e9aef31b0482
WORKFLOW_CHANGED_PRODUCT_SOURCE=false

WORKFLOW_RUN_ID=35309484471
WORKFLOW_RESULT=SUCCESS
```

The build-only branch is exactly one commit ahead of the documentation-aligned main base and adds only:

```text
.github/workflows/n3w-pr428-boardb-artifact-build.yml
```

It must not be merged into main.

## Exact source binding inside runner

The runner successfully completed:

```text
Checkout exact PR428 merge source=PASS
Bind exact source=PASS

SOURCE_HEAD=f357db25390ffd097e9b8608293870772f9cb16c
SOURCE_TREE=3fae2b22b5537e0229b0f7eeacf9f0f3b3aa9a64

PYTHON=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF=5.5.4
TARGET=ESP32-C6
```

The physical harness build target was:

```text
firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
```

## Frozen artifact

```text
ARTIFACT_ID=10533235759
ARTIFACT_NAME=n3w-pr428-boardb-exact-source
ARTIFACT_RUN_ID=35309484471
ARTIFACT_CREATED_AT=2026-09-18T05:09:30Z
ARTIFACT_EXPIRES_AT=2026-09-25T05:09:29Z

ARTIFACT_ZIP_SIZE=723298
ARTIFACT_ZIP_SHA256=ce5f2de1a152bceb746b22b1aaca7364374ed9f91656230359fed4079776a55e
```

Frozen write candidates:

```text
firmware.bin
APPLICATION_SIZE=1133424
APPLICATION_SHA256=b3e2311818d539c2abf98e4fa9ff431069b414da6f9993f350e4a7c427929f3a

ota_data_initial.bin
OTADATA_SIZE=8192
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

The workflow manifest also records:

```text
WORKFLOW_TRIGGER_SHA=ec256e8b219942d61ecf583ae558e9aef31b0482
```

## Build resource report

```text
RAM_USED=50648
RAM_TOTAL=327680
RAM_USED_PERCENT=15.5

FLASH_USED=1133068
FLASH_TOTAL=3932160
FLASH_USED_PERCENT=28.8

TOTAL_IMAGE_SIZE_REPORTED=1133332
```

## Binding conclusion

```text
PR428_EXACT_ARTIFACT_BUILD=PASS
PR428_EXACT_ARTIFACT_BINDING=PASS

SOURCE_HEAD_MATCH=PASS
SOURCE_TREE_MATCH=PASS
TOOLCHAIN_VERSION_BINDING=PASS
APPLICATION_HASH_FROZEN=true
OTADATA_HASH_FROZEN=true
ARCHIVE_HASH_FROZEN=true
```

This is source-to-artifact proof only. It does not prove that any board runs this artifact.

## Physical / acceptance boundary

```text
BOARD_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
T1_MUTATION=false
PR428_BOARD_B_DEPLOYMENT=NOT_EXECUTED
PR428_PHYSICAL_VALIDATION=NOT_EXECUTED
KF096_STATUS=OPEN
KF094_STATUS=OPEN
KF095_STATUS=GUARDED
```

The deployed Board B remains on the PR #425 artifact until a later explicitly authorized write gate proves otherwise.

## KF-084 reproducibility guard

KF-084 remains relevant: an independently rebuilt binary from the same source is not automatically the same physical artifact.

Therefore:

- the frozen `firmware.bin` / `ota_data_initial.bin` hashes above are the physical candidate authority for the next deployment route;
- a later rebuild must not silently replace these hashes;
- if this artifact expires or is otherwise unavailable, rebuild requires a new exact-artifact build/binding record before physical use.

## Next ONE gate

```text
NEXT_ONE_GATE=N3W_KF096_PR428_BOARD_B_WRITE_TARGET_PREFLIGHT_20260918_01

BOARD_ACCESS_REQUIRED=true
PREFLIGHT_READ_ONLY=true
FLASH_WRITE=false
SERIAL_OPEN=false
T1_MUTATION=false
ARTIFACT_MUTATION=false
PHYSICAL_WRITE_AUTHORIZATION_REQUIRED_LATER=true
```

Purpose: after separate explicit authorization, freshly identify the intended Board B and prove target silicon / flash / security state plus exact artifact hash binding before any write. The preflight itself remains read-only.

## Public/private evidence boundary

Public GitHub may store source, workflow/run/artifact IDs, public-safe hashes, toolchain versions, and sanitized build/acceptance facts. Raw credentials, setup secrets, private keys, raw NVS, private host addresses, and private board identity material remain outside the public repository.
