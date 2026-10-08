# N3-W Clean Product First-Pair Setup-Secret Handoff and Runtime Identity — Replacement Exact Artifact Build and Binding — 2026-10-07

```text
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_REPLACEMENT_EXACT_ARTIFACT_BUILD_AND_BINDING_20261007_01
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

SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
SOURCE_REPAIR=CLOSED_PASS
SOURCE_REPAIR_CI=PASS
EXACT_SOURCE_READBACK=PASS
```

The source-repair closure established `629f096a...` as the final product-code authority. All later PR #522 commits through the source-repair closure head changed only documentation, so this artifact intentionally binds to `629f096a...` rather than the later branch tip.

The previously bound artifact for `157448b...` remains valid historical P3/P4 evidence only. It is superseded for all resumed clean-product physical acceptance.

## 2. Exact production target and repaired-source binding

```text
TARGET_CONFIG=firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml
TARGET_BLOB_SHA=32a2b3cb29be4e1bce46807d8825b6a4c37999ec
TELEMETRY_BRIDGE_BLOB_SHA=ce16f2389d146f9b25e95cbb628547e11ce36bd6
TRANSPORT_BLOB_SHA=9cecdb091ca37fdcb1bbd675ecb4ef9566ae7751
DISPLAY_BLOB_SHA=04f8a4ca46a7481650dc0a8f9500e1cb634b2b53
CORE_YAML_BLOB_SHA=cc4b9dd495db1f5669508fa1728700f30b89c20f

PRODUCT_CORE_INIT_BLOB_SHA=75949b916144383ae57ebe90ece41e9f248b8cbe
PRODUCT_CORE_HEADER_BLOB_SHA=8132c86f4af91e3a2edc203cfd1ab183d0c06429
FIRST_PAIR_POLICY_BLOB_SHA=c06dd29e1c43a00be6ab3399febe941176ce0177
PAIRING_CLIENT_CPP_BLOB_SHA=4a779271046148763dd058bf8b77f921f843177a
PAIRING_CLIENT_H_BLOB_SHA=5f19651245965635d50486a40b91192fcd3e96c4
PRODUCT_COMPONENT_CPP_BLOB_SHA=02f0a8eaf31bd9f8d9a8106b108b1eb2b5bb0c8e
PRODUCT_COMPONENT_H_BLOB_SHA=f92865d175c0fa926520634a0baa71b3d54ee05f
```

This binds the replacement artifact not only to the inherited KF-050 boot-session repair but also to the clean-product first-pair LCD/QR handoff repair, pairing handoff readiness state, and pairing-identity log redaction.

## 3. Build-only authority

```text
BUILD_BRANCH=build/n3w-clean-product-first-pair-handoff-f1rc2-629f096-artifact-20261007
WORKFLOW_PATH=.github/workflows/n3w-clean-product-first-pair-handoff-f1rc2-exact-artifact-build.yml
WORKFLOW_TRIGGER_COMMIT=dd526b1d9dca767b650b7d9deecec911becd7673
WORKFLOW_TRIGGER_PARENT=629f096a32e087087ea32d30707dcc3cd6295e5d
WORKFLOW_TRIGGER_TREE=0cd351f768fdc15db9d62e2fa164c98fdcdfbf61
WORKFLOW_BLOB_SHA=380073a5efb9e326abbeb82189bcae34f7d7e310
BUILD_ONLY_DELTA=WORKFLOW_FILE_ONLY
```

A direct compare from `629f096a...` to `dd526b1d...` contains exactly one added file: the build-only workflow above.

The workflow does not compile its own branch tip. It explicitly checks out and verifies:

```text
SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
```

## 4. Toolchain and workflow result

```text
PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
WORKFLOW_RUN_ID=37594598870
WORKFLOW_RESULT=SUCCESS
```

Workflow:

```text
https://github.com/chrenguo-stack/HomeAssistant/actions/runs/37594598870
```

All exact-build steps passed:

```text
CHECKOUT_EXACT_SOURCE=PASS
BIND_EXACT_SOURCE_AND_TARGET=PASS
COMPILE_EXACT_PRODUCTION_TARGET=PASS
VERIFY_ESP_IDF_TOOLCHAIN=PASS
BINARY_DEHARNESS_PROOF=PASS
DIRECT_MQTT_RELOCATION_R2_MARKERS=PASS
KF050_FIRST_PAIR_BOOT_REPAIR_MARKERS=PASS
CLEAN_PRODUCT_FIRST_PAIR_HANDOFF_MARKERS=PASS
PAIRING_ID_LOG_REDACTION_MARKERS=PASS
FREEZE_EXACT_PRODUCTION_RELEASE_BUNDLE=PASS
UPLOAD_EXACT_PRODUCTION_RELEASE_ARTIFACT=PASS
```

## 5. Uploaded artifact authority

```text
ARTIFACT_ID=11469977052
ARTIFACT_NAME=n3w-clean-product-first-pair-handoff-f1rc2-629f096-exact-source
ARTIFACT_CREATED_AT=2026-10-07T08:37:26Z
ARTIFACT_EXPIRES_AT=2026-11-06T08:37:25Z
ARTIFACT_OUTER_SIZE=4341432
ARTIFACT_OUTER_SHA256=8587c7bf130f2f17e81b4e4f7652780f372f6a61697cc240e72a6af7392a7dc8
```

GitHub reported the same SHA-256 digest as the independently downloaded artifact bytes.

The GitHub artifact contains exactly two files:

```text
n3w-clean-product-first-pair-handoff-f1rc2-629f096-exact-source.zip
n3w-clean-product-first-pair-handoff-f1rc2-629f096-exact-source.zip.sha256
```

## 6. Deterministic release ZIP

```text
RELEASE_ZIP_SIZE=4340810
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c
RELEASE_SHA256_FILE_MATCH=PASS
RELEASE_MEMBER_COUNT=8
```

The release ZIP uses deterministic member timestamps of `1980-01-01 00:00:00` and stored compression.

The release ZIP contains exactly:

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

The downloaded manifest records:

```text
BINDING_SCHEMA=N3W_PRODUCTION_EXACT_ARTIFACT_V1
SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
SOURCE_REPAIR_R2=true
KF050_FIRST_PAIR_BOOT_REPAIR=true
CLEAN_PRODUCT_FIRST_PAIR_HANDOFF_REPAIR=true
PAIRING_ID_LOG_REDACTION=true
WORKFLOW_TRIGGER_SHA=dd526b1d9dca767b650b7d9deecec911becd7673
WORKFLOW_RUN_ID=37594598870
BINARY_DEHARNESS_PROOF=PASS
DIRECT_MQTT_RELOCATION_R2_MARKERS=PASS
KF050_FIRST_PAIR_BOOT_REPAIR_MARKERS=PASS
CLEAN_PRODUCT_FIRST_PAIR_HANDOFF_MARKERS=PASS
PAIRING_ID_LOG_REDACTION_MARKERS=PASS
PHASE4_HARNESS_PRESENT=false
LAB_DIAGNOSTICS_PRESENT=false
RTC_BREADCRUMB_PRESENT=false
```

Independent extraction recalculated every release member and matched the manifest exactly:

```text
FIRMWARE_BIN_SIZE=1412672
FIRMWARE_BIN_SHA256=4e4442808fdff7fc3ca16eb379bd06741a9eea3364e31f1365be5e6bee325c65

FIRMWARE_OTA_BIN_SIZE=1412672
FIRMWARE_OTA_BIN_SHA256=4e4442808fdff7fc3ca16eb379bd06741a9eea3364e31f1365be5e6bee325c65

FIRMWARE_FACTORY_BIN_SIZE=1478208
FIRMWARE_FACTORY_BIN_SHA256=658645083ed2d83d6951abeb5f894dbde7d7124030c8bc1815683ed2bf24e914

BOOTLOADER_BIN_SIZE=22576
BOOTLOADER_BIN_SHA256=985d0e0c5029d55d6cfab66470fe367200fd3e4e367e6a69ef1b557704c89fd5

PARTITIONS_BIN_SIZE=3072
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OTA_DATA_INITIAL_BIN_SIZE=8192
OTA_DATA_INITIAL_BIN_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

FLASH_ARGS_SIZE=167
FLASH_ARGS_SHA256=5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713
```

`firmware.bin` and `firmware.ota.bin` are byte-identical.

The production flash mapping remains:

```text
FLASH_MODE=dio
FLASH_FREQ=80m
FLASH_SIZE=8MB
0x0000  bootloader.bin
0x8000  partitions.bin
0x9000  ota_data_initial.bin
0x10000 firmware.bin
```

Compared with the prior `157448b...` artifact, `partitions.bin`, `ota_data_initial.bin` and `flash_args` remain byte-identical. The application/factory image is intentionally different because it contains the clean-product first-pair handoff repair. The rebuilt bootloader hash is also different; this gate freezes the current exact-build bootloader hash and does not require equality with a previous build.

## 8. Independent downloaded-binary proof

The independently downloaded `firmware.bin` was scanned again outside the GitHub Actions runner.

Required markers are present:

```text
Startup product identity state is partial, corrupt, or contradictory
Initial boot-session floor preparation failed code=%u
N3-W standalone Direct Broker candidate attempt started
stable Broker restored
gh.telemetry/1
air_temperature_c
Unprovisioned N3-W node ready for local pairing
GHN3W2:pending
```

Forbidden markers are absent:

```text
Unprovisioned N3-W node ready for local pairing hardware_id=%s pairing_id=%s
Phase4PhysicalHarness
N3wLabDiagnostics
N3wRtcBreadcrumb
n3w_phase4_physical_harness
n3w_lab_diagnostics
n3w_rtc_breadcrumb
GH_N3W_ENABLE_LEGACY_RADIO
```

```text
INDEPENDENT_APP_STRING_CHECK=PASS
PAIRING_ID_LOG_REDACTION_BINARY_PROOF=PASS
CLEAN_PRODUCT_PAIRING_QR_BINARY_MARKER=PASS
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

This gate proves source provenance, deterministic build output and artifact integrity only. It does not itself constitute physical acceptance.

The board used in the blocked P4 attempt remains historical blocker evidence and must not be erased/reused as a new clean-product candidate.

## 10. Gate closure

```text
EXACT_BASE_BOUND=true
SOURCE_HEAD_TREE_BOUND=true
TARGET_BLOBS_BOUND=true
FIRST_PAIR_HANDOFF_SOURCE_BLOBS_BOUND=true
BUILD_ONLY_WORKFLOW_DELTA=true
EXACT_TOOLCHAIN=PASS
EXACT_F1RC2_COMPILE=PASS
BINARY_DEHARNESS_PROOF=PASS
KF050_BINARY_MARKERS=PASS
CLEAN_PRODUCT_FIRST_PAIR_BINARY_MARKERS=PASS
PAIRING_ID_LOG_REDACTION_BINARY_PROOF=PASS
ARTIFACT_UPLOAD=PASS
INDEPENDENT_ARTIFACT_DOWNLOAD=PASS
OUTER_SHA256_BINDING=PASS
RELEASE_ZIP_SHA256_BINDING=PASS
MANIFEST_MEMBER_HASH_BINDING=PASS
BOARD_ACCESS=false
T1_MUTATION=false
MERGE=false

RESULT=CLOSED_PASS
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_PHYSICAL_ACCEPTANCE_PREEXECUTION_20261007_01
STOP=true
```

The successor gate must prepare a new clean-product physical acceptance run using this replacement artifact. It must not reuse the blocked P4 board as a clean candidate, must retain the pre-boot Manager identity snapshot / post-boot unique-new-pending identity binding contract, and must not clear Manager replay/high-water or use legacy recovery-floor helpers.
