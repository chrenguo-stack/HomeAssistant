# N3-W Production De-harness and Exact Artifact Progress Alignment — 2026-09-21

Status: `CURRENT_PROGRESS_ALIGNMENT`

This document synchronizes the current GitHub authority with the completed local-chat work after PR #437 merge. It is a public-safe progress record; no private runtime locator, credential, setup secret, raw NVS, or raw board identity is included.

## 1. Current repository boundary

```text
REPOSITORY=chrenguo-stack/HomeAssistant

MAIN_AT_ALIGNMENT_START=8165cc441abd45f4d46f7439fa57edee1470c917

MERGED_PRODUCT_SOURCE_AUTHORITY=PR437
PR437_SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
PR437_SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
PR437_MERGE_COMMIT=b9acaaad50b17c9cdb51c219330e612c383628f0

PRODUCTION_SUCCESSOR_MERGED=false
PRODUCTION_SUCCESSOR_SOURCE_BRANCH=feature/n3w-production-telemetry-bridge-20260921
PRODUCTION_SUCCESSOR_SOURCE_HEAD=c1b3d9d016d06c21c9ff7070c0043163739565ca
PRODUCTION_SUCCESSOR_SOURCE_TREE=0c857fb0f830239717a2e937d176903a6acae8ac
```

The frozen PR #437 lab version remains unchanged. The production successor is intentionally independent and uses:

```text
firmware/esphome_rc/components/greenhouse_n3w_product_core/
```

The copied C++ namespace remains `esphome::greenhouse_n3w_core`; the frozen lab component and production successor must not be loaded into the same target.

## 2. De-harness source stages

### 2.1 Independent product-core fork and pure-lab prune

```text
STAGE_A_HEAD=b683d0c5c2fedfde4e8dca334544451ca7df7dbe
RESULT=PASS
```

Pure lab files are absent from the successor:

```text
n3w_lab_diagnostics.h/.cpp
n3w_phase4_physical_harness.h/.cpp
n3w_rtc_breadcrumb.h/.cpp
```

### 2.2 Embedded ESP-NOW diagnostic prune

```text
STAGE_B_HEAD=e0275f20e6a40d82e9b745514387b81a788ee9d9
RESULT=PASS
```

Removed from the successor are bounded diagnostic logging/context fields and pre-send channel readback. Receive RSSI/channel metadata, synchronous send result, MAC completion ownership, pending-unicast accounting, Direct/Discovery/Relay behavior, recovery scheduling, callback quiescence, and Option-B queue semantics remain preserved.

## 3. Dual-core compile proof

PR #463:

```text
PR=463
HEAD=69e6abea4760feb1987cc5bdfd5eeddb7f329cbe
STATE=OPEN
MERGED=false
CI=12_OF_12_SUCCESS
DEDICATED_RUN_ID=35602419394

FROZEN_PR437_PHASE4_LAB_COMPILE=PASS
PRODUCTION_CORE_PROBE_COMPILE=PASS
```

This proves the frozen lab target still compiles and the independent product core compiles in a minimal ESP32-C6 target.

## 4. F1.0-RC2 production target

```text
TARGET_STAGE_HEAD=f77d533065d593e6fe7f4da7f74381172127be5e
TARGET_CONFIG=firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml
TRANSPORT_PACKAGE=firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml
```

The target inherits the existing F1.0-RC2 whole-device hardware/sensor/display/power/OTA/API/Wi-Fi baseline and adds the independent N3-W product core. The N3-W MQTT client is inert at boot and reserved for authenticated runtime configuration.

PR #464:

```text
PR=464
HEAD=858af39c7a57231618c6de306a7b37aa6dc5cc0d
STATE=OPEN
MERGED=false
CI=12_OF_12_SUCCESS
DEDICATED_RUN_ID=35604223868

F1RC2_N3W_CONFIG_VALIDATION=PASS
```

## 5. Real F1.0-RC2 telemetry bridge

```text
TELEMETRY_BRIDGE_HEAD=c1b3d9d016d06c21c9ff7070c0043163739565ca
TELEMETRY_BRIDGE=firmware/esphome_rc/f1_0_rc2/packages/n3w_product_telemetry.yml

TELEMETRY_INTERVAL=60s
CAP_HASH=sha256:fed2dec764f4146d
```

The bridge reuses the existing F1.0-RC2 N1 measurement vocabulary and quality semantics, but N3-W owns `boot_id` and `seq`:

```text
F1.0-RC2 real sensors / derived values
        |
        v
gh.telemetry/1 builder
        |
        +-- take_telemetry_identity()
        |
        v
submit_telemetry_json()
        |
        +-- Direct MQTT
        +-- Option-B queue
        +-- ESP-NOW Relay
```

All 15 existing Home Assistant measurement keys are retained, with quality values `ok`, `warming`, `stale`, `fault`, and `not_present`.

The bridge respects the N3-W 1024-byte plaintext ceiling by omitting missing numeric values while preserving quality state, rounding to the existing product precision, dropping duplicated optional power-battery fields if necessary, then dropping optional `fw_version` if necessary. Oversize payloads still fail closed.

PR #465:

```text
PR=465
HEAD=80672521c870e10c0c01b9f497f44d722bff3203
STATE=OPEN
MERGED=false
CI=12_OF_12_SUCCESS
DEDICATED_RUN_ID=35606499168

TELEMETRY_BRIDGE_SOURCE_CONTRACT=PASS
F1RC2_N3W_TELEMETRY_CONFIG_VALIDATION=PASS
```

## 6. Full firmware compile

PR #466:

```text
PR=466
HEAD=ace8463deaed5a8f09ff5d3bdfdc9a78cfee3983
STATE=OPEN
MERGED=false
CI=12_OF_12_SUCCESS
DEDICATED_RUN_ID=35607941530

FULL_FIRMWARE_COMPILE=PASS
LINKED_FIRMWARE_BIN=PASS
FIRMWARE_BYTES=1388928
TEMPORARY_BUILD_SHA256=3c78f7ddac001c1e6627267a4b2a4a12041fd175887ea414c8cc0bc721b475c2
```

The temporary CI binary above is evidence of successful compile/link only. It is not the final bound artifact.

## 7. Binary de-harness proof

PR #467:

```text
PR=467
HEAD=29d060e03b9bd86d85acf072fddd1f6c30ae3f1a
STATE=OPEN
MERGED=false
CI=12_OF_12_SUCCESS
DEDICATED_RUN_ID=35610733175

BINARY_DEHARNESS_PROOF=PASS
FORBIDDEN_MARKER_COUNT=12
PHASE4_HARNESS_PRESENT=false
LAB_DIAGNOSTICS_PRESENT=false
RTC_BREADCRUMB_PRESENT=false

ELF_POSITIVE_CONTROLS=GreenhouseN3wCore,SimpleProductComponent
BINARY_POSITIVE_CONTROLS=gh.telemetry/1,air_temperature_c
```

The proof inspected demangled `firmware.elf` symbols, `firmware.map`, and printable strings from the actual `firmware.bin`. Positive controls prevent an empty/non-N3-W image from passing.

The independent de-harness rebuild produced the same size but a different temporary SHA-256:

```text
FIRMWARE_BYTES=1388928
TEMPORARY_DEHARNESS_BUILD_SHA256=20b149d39ee25d8d06b8d535aa3c691ec5e1b959c4974837787ac8641d90097f
```

Therefore KF-084 remains relevant: a rebuild from the same source must never silently replace an already bound physical candidate.

## 8. Exact production artifact build and binding

The exact-artifact branch is build-only and is exactly one workflow commit above the product source:

```text
BUILD_BRANCH=build/n3w-production-f1rc2-c1b3d9d-artifact-20260921
BUILD_BRANCH_HEAD=433b91c19bf436a832021d821bda53261b7e3532
PRODUCT_SOURCE_HEAD=c1b3d9d016d06c21c9ff7070c0043163739565ca
PRODUCT_SOURCE_TREE=0c857fb0f830239717a2e937d176903a6acae8ac
PRODUCT_SOURCE_CHANGED=false
```

Exact source/blob binding:

```text
TARGET_BLOB_SHA=32a2b3cb29be4e1bce46807d8825b6a4c37999ec
TELEMETRY_BRIDGE_BLOB_SHA=ce16f2389d146f9b25e95cbb628547e11ce36bd6
TRANSPORT_BLOB_SHA=aa39d4b083f2db1b30a76efb1afef156db355a35
PRODUCT_CORE_INIT_BLOB_SHA=7e86aa2f3fb1bff6f5813e431da501970263e33a

PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
```

Workflow/artifact authority:

```text
WORKFLOW_RUN_ID=35612622035
WORKFLOW_RESULT=SUCCESS

ARTIFACT_ID=10644667734
ARTIFACT_NAME=n3w-production-f1rc2-c1b3d9d-exact-source
ARTIFACT_CREATED_AT=2026-09-21T14:34:42Z
ARTIFACT_EXPIRES_AT=2026-10-21T14:34:41Z
GITHUB_ARTIFACT_SIZE=4269260
GITHUB_ARTIFACT_SHA256=02fbe69f78511f33dec150dee635925dd4decf81048de3adfc6db8af4acc7a72
```

The GitHub artifact was independently downloaded. Its outer digest matches GitHub metadata.

The outer artifact contains the frozen release ZIP plus its SHA-256 sidecar. The inner release bundle is the candidate that may be referenced by a later physical write gate:

```text
RELEASE_BUNDLE=n3w-production-f1rc2-c1b3d9d-exact-source.zip
RELEASE_BUNDLE_SIZE=4268748
RELEASE_BUNDLE_SHA256=93d830368b74e0dae904a9f5c4450378694575c68b917e749b480455662ff065
RELEASE_MEMBER_COUNT=8
MANIFEST_SHA256=b0483fe6990a50bbb0715c55a24dc01eb1ce6ddd13ae2d22bc7283f78301a744
```

Release members:

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

Bound write-candidate hashes:

```text
FIRMWARE_BIN_SIZE=1388928
FIRMWARE_BIN_SHA256=8bcd89aaf0be64188f8f98a64795fe78d573ae82dd2dd360c7ff459f80e58efa

FIRMWARE_OTA_BIN_SIZE=1388928
FIRMWARE_OTA_BIN_SHA256=8bcd89aaf0be64188f8f98a64795fe78d573ae82dd2dd360c7ff459f80e58efa

FIRMWARE_FACTORY_BIN_SIZE=1454464
FIRMWARE_FACTORY_BIN_SHA256=434a3996ea8dc74c4a356f54d8a9405202f17b500680a66f5d49a2089cf67774

BOOTLOADER_BIN_SIZE=22576
BOOTLOADER_BIN_SHA256=07865c91e04285282a43188ef326af650b9ecb28c7de74b50006c4917cdea445

PARTITIONS_BIN_SIZE=3072
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OTADATA_SIZE=8192
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56c876732fd3782c62f

FLASH_ARGS_SIZE=167
FLASH_ARGS_SHA256=5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713
```

Independent binding result:

```text
INDEPENDENT_ARTIFACT_DOWNLOAD=PASS
OUTER_DIGEST_MATCH_GITHUB_METADATA=PASS
INNER_RELEASE_DIGEST_MATCH_BUILD_LOG=PASS
INNER_SHA256_SIDECAR_MATCH=PASS
INNER_MEMBER_SET_MATCH=PASS
MANIFEST_SOURCE_BINDING_MATCH=PASS
MANIFEST_MEMBER_SIZE_HASH_MATCH=PASS

N3W_PRODUCTION_EXACT_ARTIFACT_BUILD=PASS
N3W_PRODUCTION_EXACT_ARTIFACT_BINDING=PASS
```

PR #467 conversation comment `5762317062` also records the public-safe exact binding closure.

## 9. Physical deployment boundary

No production-successor physical write has occurred.

```text
PRODUCTION_SUCCESSOR_BOARD_B_DEPLOYMENT=NOT_EXECUTED
BOARD_ACCESS_DURING_DEHARNESS=false
FLASH_WRITE_DURING_DEHARNESS=false
T1_MUTATION_DURING_DEHARNESS=false
```

Board B remains on the already validated PR #437 product source/artifact:

```text
CURRENTLY_DEPLOYED_BOARD_B_SOURCE=4270f24a92a87dd5239d781ebba624c2f34b7fc2
CURRENTLY_DEPLOYED_BOARD_B_ARTIFACT_ID=10619047221
```

Any later physical write requires fresh target preflight and new explicit physical authorization. Historical write authorization must not be replayed.

## 10. Flash-args guard

The frozen release bundle is flat, but the copied ESPHome `flash_args` contains build-tree-relative paths such as:

```text
bootloader/bootloader.bin
gh.bin
partition_table/partition-table.bin
```

Therefore a later write gate must not blindly execute that `flash_args` file in the flat release directory.

Before any flash operation, the write route must either:

- use the bound `firmware.factory.bin` through a separately reviewed procedure; or
- independently normalize and verify the multi-image address/file mapping against the frozen hashes.

## 11. Current stop point

```text
CURRENT_ROUTE=PR437_POSTMERGE_PRODUCTION_FIRMWARE_CONVERGENCE
CURRENT_SUCCESSOR_MERGED=false
CURRENT_SUCCESSOR_SOURCE_HEAD=c1b3d9d016d06c21c9ff7070c0043163739565ca
CURRENT_SUCCESSOR_EXACT_ARTIFACT_ID=10644667734
CURRENT_SUCCESSOR_RELEASE_SHA256=93d830368b74e0dae904a9f5c4450378694575c68b917e749b480455662ff065

SOURCE_DEHARNESS=PASS
F1RC2_TARGET_CONFIG=PASS
REAL_TELEMETRY_BRIDGE=PASS
FULL_FIRMWARE_COMPILE=PASS
BINARY_DEHARNESS_PROOF=PASS
EXACT_ARTIFACT_BUILD=PASS
EXACT_ARTIFACT_BINDING=PASS

PRODUCTION_SUCCESSOR_PHYSICAL_PREFLIGHT=NOT_EXECUTED
PRODUCTION_SUCCESSOR_FLASH=NOT_EXECUTED
PRODUCTION_SUCCESSOR_PHYSICAL_ACCEPTANCE=NOT_EXECUTED

NEXT_CANDIDATE_GATE=N3W_PRODUCTION_BOARD_B_WRITE_TARGET_PREFLIGHT_20260921_01
NEXT_GATE_AUTHORIZED=false
```

## 12. Team workspace completeness

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

The exact binary artifact itself is retained by GitHub Actions until its recorded expiry. If it expires before physical use, it must not be replaced by an assumed-equivalent rebuild; a new exact-artifact build/binding gate is required.
