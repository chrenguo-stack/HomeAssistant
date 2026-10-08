# N3-W KF-050 First-Pair Boot-Session Initialization — Exact Artifact Build and Binding — 2026-10-05

```text
TASK=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_EXACT_ARTIFACT_BUILD_AND_BINDING_20261005_01
STATUS=CLOSED_PASS
EXACT_ARTIFACT_BUILD=PASS
EXACT_ARTIFACT_BINDING=PASS
BOARD_ACCESS=false
FLASH_WRITE=false
T1_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
MERGE=false
```

## 1. Source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_STATE=OPEN_DRAFT
PR_BASE=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
PR_HEAD_BEFORE_BINDING_DOC=2ab9dea0dabd86d0a5eeafe69e58049903795086

SOURCE_HEAD=157448b621f288c5ac5038e7a1ac906cf2575a7f
SOURCE_TREE=f45ca257de0b6e41f0458346711bb4e105ba1fcc
SOURCE_REPAIR_CODE_COMMIT=fe2c2283f178e572fc8f83d0d48b320a065a3bd8
SOURCE_REPAIR_CLOSURE_COMMIT=2ab9dea0dabd86d0a5eeafe69e58049903795086
```

`2ab9dea...` is one documentation-only commit after `157448b...`; the exact product build source is therefore frozen at `157448b... / f45ca257...`.

The exact source remains stacked on the previously validated R2 Broker-relocation source. A fresh compare from R2 source `67a0460...` to `157448b...` shows the only product-source changes are the KF-050 first-pair boot initialization repair in `greenhouse_n3w_product_core.h` plus the new `n3w_first_pair_boot_policy.h`; the remaining delta is tests, CI and documentation.

## 2. Exact production target binding

```text
TARGET_CONFIG=firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml
TARGET_BLOB_SHA=32a2b3cb29be4e1bce46807d8825b6a4c37999ec
TELEMETRY_BRIDGE_BLOB_SHA=ce16f2389d146f9b25e95cbb628547e11ce36bd6
TRANSPORT_BLOB_SHA=aa39d4b083f2db1b30a76efb1afef156db355a35
PRODUCT_CORE_INIT_BLOB_SHA=75949b916144383ae57ebe90ece41e9f248b8cbe
PRODUCT_CORE_HEADER_BLOB_SHA=8132c86f4af91e3a2edc203cfd1ab183d0c06429
FIRST_PAIR_POLICY_BLOB_SHA=c06dd29e1c43a00be6ab3399febe941176ce0177
```

The target/bridge/transport/component-init blobs remain identical to the previously bound R2 production artifact. The two additional product-core hashes bind this artifact specifically to the KF-050 repair.

## 3. Build-only authority

```text
BUILD_BRANCH=build/n3w-kf050-first-pair-f1rc2-157448b-artifact-20261005
WORKFLOW_PATH=.github/workflows/n3w-kf050-first-pair-f1rc2-exact-artifact-build.yml
WORKFLOW_TRIGGER_COMMIT=c774aff49342ab83c0b03eff039e6435808bafaa
WORKFLOW_TRIGGER_PARENT=157448b621f288c5ac5038e7a1ac906cf2575a7f
WORKFLOW_BLOB_SHA=2970211bc9b33c1048c1e58699456d8bbda1d393
BUILD_ONLY_DELTA=WORKFLOW_FILE_ONLY
```

A compare of `157448b...` to `c774aff...` contains exactly one added file: the build-only workflow above. The workflow checks out `SOURCE_HEAD` explicitly rather than compiling its own branch tip.

## 4. Toolchain and workflow result

```text
PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
WORKFLOW_RUN_ID=37249933019
WORKFLOW_RESULT=SUCCESS
```

Workflow URL:

```text
https://github.com/chrenguo-stack/HomeAssistant/actions/runs/37249933019
```

All build steps passed:

```text
CHECKOUT_EXACT_SOURCE=PASS
BIND_EXACT_SOURCE_AND_TARGET=PASS
COMPILE_EXACT_PRODUCTION_TARGET=PASS
VERIFY_ESP_IDF_TOOLCHAIN=PASS
BINARY_DEHARNESS_PROOF=PASS
DIRECT_MQTT_RELOCATION_R2_MARKERS=PASS
KF050_FIRST_PAIR_BOOT_REPAIR_MARKERS=PASS
FREEZE_EXACT_PRODUCTION_RELEASE_BUNDLE=PASS
UPLOAD_EXACT_PRODUCTION_RELEASE_ARTIFACT=PASS
```

## 5. Uploaded artifact authority

```text
ARTIFACT_ID=11320812037
ARTIFACT_NAME=n3w-kf050-first-pair-f1rc2-157448b-exact-source
ARTIFACT_CREATED_AT=2026-10-05T01:07:56Z
ARTIFACT_EXPIRES_AT=2026-11-04T01:07:54Z
ARTIFACT_OUTER_SIZE=4333021
ARTIFACT_OUTER_SHA256=7f1d775bd2c15152b96ad6802e24ec64789fd1c7cd49cf66498c83eb25b8ee52
```

GitHub reported the same SHA-256 digest as the independently downloaded artifact bytes.

The GitHub artifact contains exactly:

```text
n3w-kf050-first-pair-f1rc2-157448b-exact-source.zip
n3w-kf050-first-pair-f1rc2-157448b-exact-source.zip.sha256
```

## 6. Deterministic release ZIP

```text
RELEASE_ZIP_SIZE=4332479
RELEASE_ZIP_SHA256=44610382a0e7d9c04e4445e873b9d99fd9a781d18fd497f39cb382d3fce3b3ff
RELEASE_SHA256_FILE_MATCH=PASS
```

The release ZIP uses deterministic member timestamps and stored compression. Independent download and SHA-256 calculation matches the uploaded `.sha256` file.

The release ZIP contains exactly eight files:

```text
MANIFEST.txt
bootloader.bin
firmware.bin
firmware.factory.bin
firmware.ota.bin
flash_args
ota_data_initial.bin
partitions.bin
```

## 7. Manifest and inner binary binding

```text
BINDING_SCHEMA=N3W_PRODUCTION_EXACT_ARTIFACT_V1
SOURCE_HEAD=157448b621f288c5ac5038e7a1ac906cf2575a7f
SOURCE_TREE=f45ca257de0b6e41f0458346711bb4e105ba1fcc
SOURCE_REPAIR_R2=true
KF050_FIRST_PAIR_BOOT_REPAIR=true
WORKFLOW_TRIGGER_SHA=c774aff49342ab83c0b03eff039e6435808bafaa
WORKFLOW_RUN_ID=37249933019
BINARY_DEHARNESS_PROOF=PASS
DIRECT_MQTT_RELOCATION_R2_MARKERS=PASS
KF050_FIRST_PAIR_BOOT_REPAIR_MARKERS=PASS
PHASE4_HARNESS_PRESENT=false
LAB_DIAGNOSTICS_PRESENT=false
RTC_BREADCRUMB_PRESENT=false
```

Independent extraction recalculated every member size and SHA-256 and matched `MANIFEST.txt` exactly:

```text
FIRMWARE_BIN_SIZE=1410080
FIRMWARE_BIN_SHA256=4595edea29c93b3618435035bd87e3740f3c8afd0b663dc0b21ef65de343cd6b

FIRMWARE_OTA_BIN_SIZE=1410080
FIRMWARE_OTA_BIN_SHA256=4595edea29c93b3618435035bd87e3740f3c8afd0b663dc0b21ef65de343cd6b

FIRMWARE_FACTORY_BIN_SIZE=1475616
FIRMWARE_FACTORY_BIN_SHA256=a952987c6e6aabd3205f15f60a2ee3a7b9a946635b03b1ce90578880c83f5186

BOOTLOADER_BIN_SIZE=22576
BOOTLOADER_BIN_SHA256=e36ee1eaa32780c74612ea512164fa56770744fbefa1e34df2fab36de76b4b97

PARTITIONS_BIN_SIZE=3072
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OTA_DATA_INITIAL_BIN_SIZE=8192
OTA_DATA_INITIAL_BIN_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

FLASH_ARGS_SIZE=167
FLASH_ARGS_SHA256=5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713
```

`firmware.bin` and `firmware.ota.bin` are byte-identical, as expected for this build output.

Compared with the prior R2 bound artifact, `partitions.bin`, `ota_data_initial.bin` and `flash_args` remain byte-identical. The application image is intentionally different because it contains the KF-050 repair. The rebuilt bootloader hash is also different from the prior artifact; this gate freezes the current exact-build bootloader hash and does not treat equality with a previous build as an acceptance invariant.

## 8. Independent downloaded-binary proof

The independently downloaded `firmware.bin` was scanned again outside the GitHub Actions runner.

Required production/KF-050 markers were present:

```text
Startup product identity state is partial, corrupt, or contradictory
Initial boot-session floor preparation failed code=%u
N3-W standalone Direct Broker candidate attempt started
stable Broker restored
gh.telemetry/1
air_temperature_c
```

Forbidden harness/lab markers were absent, including Phase 4 physical harness, lab diagnostics and RTC breadcrumb identifiers.

```text
INDEPENDENT_APP_STRING_CHECK=PASS
```

## 9. Physical and mutation boundary

```text
EXACT_ARTIFACT_FROZEN=true
ARTIFACT_CURRENTLY_RUNNING_ON_ANY_BOARD=NOT_CLAIMED
BOARD_ACCESS=false
FLASH_WRITE=false
OTA_WRITE=false
NVS_WRITE=false
T1_MUTATION=false
BROKER_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
CREDENTIAL_MUTATION=false
PR522_MERGE=false
```

This gate proves build provenance and artifact integrity only. It is not physical acceptance and does not authorize treating an existing historical board as a clean product-state board.

## 10. Gate closure

```text
EXACT_BASE_BOUND=true
SOURCE_HEAD_TREE_BOUND=true
TARGET_BLOBS_BOUND=true
KF050_SOURCE_BLOBS_BOUND=true
BUILD_ONLY_WORKFLOW_DELTA=true
EXACT_TOOLCHAIN=PASS
EXACT_F1RC2_COMPILE=PASS
BINARY_DEHARNESS_PROOF=PASS
KF050_BINARY_MARKERS=PASS
ARTIFACT_UPLOAD=PASS
INDEPENDENT_ARTIFACT_DOWNLOAD=PASS
OUTER_SHA256_BINDING=PASS
RELEASE_ZIP_SHA256_BINDING=PASS
MANIFEST_MEMBER_HASH_BINDING=PASS
BOARD_ACCESS=false
T1_MUTATION=false
MERGE=false

RESULT=CLOSED_PASS
NEXT_ONE_GATE=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_CLEAN_BOARD_PHYSICAL_ACCEPTANCE_PREEXECUTION_20261005_01
STOP=true
```

The successor gate may prepare the clean-board physical acceptance procedure. It must still perform an explicit target/identity/flash-safety preflight before any board write and must not reuse historical Board B state as clean-product evidence.
