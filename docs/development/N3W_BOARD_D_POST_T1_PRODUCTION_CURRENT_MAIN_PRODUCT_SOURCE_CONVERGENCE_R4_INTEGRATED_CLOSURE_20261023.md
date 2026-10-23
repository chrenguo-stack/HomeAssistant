# N3-W Board_D current-main 产品源码收敛 R4 Integrated Closure — 2026-10-23

## 1. Closure

```text
TASK=N3W_BOARD_D_POST_T1_PRODUCTION_CURRENT_MAIN_PRODUCT_SOURCE_CONVERGENCE_R4_INTEGRATED_CLOSURE

BASE_MAIN=5ff09efb650cc3818d2c6a58d4fb4c489a21d784
R3_EXACT_PRODUCT_SOURCE_HEAD=9a2024212566d831d94b167833d5485307119d78

R4_EXACT_PRODUCT_SOURCE_HEAD=ec5f6d68e33db7757d91c807fff708ca81b075dc
R4_EXACT_PRODUCT_SOURCE_TREE=16740efa8ad24d423adc0b2de32b99d56e2d23d1
MAIN_DRIFT=false

SOURCE_CI_TOTAL=31
SOURCE_CI_SUCCESS=28
SOURCE_CI_FAILURE=3
SOURCE_CI_UNFINISHED=0
SOURCE_CI_NEW_VALID_FAILURE=0

LEGACY_STAGE2D2_BOUNDARY_FALSE_FAIL=true
LEGACY_STAGE2D3_BOUNDARY_FALSE_FAIL=true
LEGACY_STAGE2D4_BOUNDARY_FALSE_FAIL=true

R4_PRODUCTION_DEHARNESS_RUN_ID=39900913009
R4_PRODUCTION_DEHARNESS=PASS
R3_CURRENT_MAIN_CONVERGENCE=PASS
MULTI_RELAY=PASS
FULL_CHANNEL_DISCOVERY=PASS
F1RC2_FIRMWARE=PASS
BOOT_SESSION_RECOVERY_HELPER=PASS
ESP32_C6_FRAME_BOOT_KEYSTATE_CORE=PASS
GREENHOUSE_MANAGER=PASS
PUBLIC_SAFETY=PASS

INITIAL_R4_RUN_ID=39895494751
INITIAL_R4_ARTIFACT_ID=12476817266
INITIAL_ARTIFACT_BINDING=PASS
INITIAL_BINARY_DEHARNESS=FALSE_PASS
INITIAL_ARTIFACT_VALID_FOR_R4_CLOSURE=false
INITIAL_ARTIFACT_VALID_FOR_BOARD_WRITE=false
FALSE_PASS_ROOT_CAUSE=BASH_ERREXIT_NOT_TRIGGERED_FOR_COMMAND_STATUS_INVERTED_BY_BANG
FALSE_PASS_PATH_DETECTED_COUNT=1
FALSE_PASS_PATH_REPAIRED_COUNT=1

R4_BUILD_BRANCH=build/n3w-board-d-r4-f1rc2-ec5f6d68-artifact-20261023
R4_BUILD_HEAD=726d5593ab8cf7a46972153f2c30558fea76ecca
BUILD_ONLY_AHEAD_BY=1
BUILD_ONLY_FILE_COUNT=1

BINDING_SCHEMA=N3W_BOARD_D_R4_PRODUCTION_EXACT_ARTIFACT_V2
EXACT_ARTIFACT_RUN_ID=39901919230
EXACT_ARTIFACT_ID=12478974186
EXACT_ARTIFACT_NAME=n3w-board-d-r4-f1rc2-ec5f6d68-exact-source
GITHUB_ARTIFACT_SHA256=898ef722cd4af37ae5472583b1874f7724e9444e8837462d36f4e6be7eea092f
RELEASE_BUNDLE_SHA256=b55aba9c3fad85da39eab63157c3de7c42f311970bfb61f8b0e9a52ddcba7dd5
MANIFEST_SHA256=173fcc978284170e0918c94269195191be0fc8a262b758851f16ee0609a638eb

FIRMWARE_BIN_SHA256=ea50b147b7cb76bf442c0bbc7fe8d54e4abff87fa48926b9160ca903b6fa5c08
FIRMWARE_OTA_BIN_SHA256=ea50b147b7cb76bf442c0bbc7fe8d54e4abff87fa48926b9160ca903b6fa5c08
FIRMWARE_FACTORY_BIN_SHA256=c982c5d56f62ddddbba5b4734c1d9f0c36d4ce6996754157b017159ac630e2c6
BOOTLOADER_BIN_SHA256=ae9656d4a6fca0f1149d443b8ced537efe3b68af8fe600ef9ad9b8c9c7b2ca46
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
FLASH_ARGS_SHA256=5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713

SOURCE_HEAD_BINDING=PASS
SOURCE_TREE_BINDING=PASS
TARGET_BINDING=PASS
R1_R2_R3_R4_INTEGRATED_SOURCE_CONTRACTS=PASS
FULL_FIRMWARE_COMPILE=PASS
CI_FOUR_LAYER_DEHARNESS_PROOF=PASS
INDEPENDENT_RELEASE_BINARY_SCAN=PASS
EXACT_ARTIFACT_BUILD=PASS
EXACT_ARTIFACT_BINDING=PASS
DETERMINISTIC_ZIP_METADATA=PASS
RELEASE_MEMBER_COUNT=8

OPEN_NEW_FALSE_PASS_PATH_COUNT=0
R4_BLOCKER_COUNT=0
R4_CLOSURE=CLOSED_PASS

PR656_STATE=OPEN_DRAFT
PR656_TECHNICAL_MERGE_READINESS=PASS
PR656_MERGE_AUTHORIZED=false
PR656_MERGED=false
BOARD_D_PHYSICAL_GATE_AUTHORIZED=false

T1_ACCESS=false
BOARD_ACCESS=false
FLASH_MUTATION=false
NVS_MUTATION=false
RF_EXECUTION=false
MERGE=false

NEXT_ROUTE=SEPARATE_GATE_DECISION_REQUIRED
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```

## 2. What R4 closed

R4 closes the integrated current-main product-source and exact-production-artifact
stage for the Board_D route.

The exact production source is
`ec5f6d68e33db7757d91c807fff708ca81b075dc`, tree
`16740efa8ad24d423adc0b2de32b99d56e2d23d1`.

At this source:

- the formal F1.0-RC2 N3-W target compiles with ESPHome 2026.4.3 and ESP-IDF 5.5.4;
- R1 target / first-pair / telemetry surfaces remain present;
- R2 Multi-Relay Gateway Selection V1 and HINT/FAST/FULL legal-channel discovery remain PASS;
- R3 Broker Auto Safe Fallback remains in the active `greenhouse_n3w_core`;
- production compile-time de-harness excludes Phase4 physical harness, lab diagnostics and RTC breadcrumb implementation from the production image;
- non-production Recovery / Phase4 / Manager compile contexts remain functional.

No retired `greenhouse_n3w_product_core` or
`greenhouse_n3w_product_runtime` directory was restored.

## 3. False-PASS found during R4 and disposition

The first R4 artifact build, run `39895494751`, produced artifact
`12476817266`. Its release ZIP and manifest were internally bound, but independent
inspection found lab-diagnostic strings in the production firmware.

The workflow had used status-inverted commands of the form `! grep ...` under
Bash `set -e`. A matched forbidden marker therefore did not reliably terminate
the script. The artifact's de-harness PASS was a false PASS.

That V1 artifact is permanently rejected for R4 closure and Board_D write use.

The source repair sequence then exposed and closed additional real integration
problems rather than weakening the gate:

1. lab diagnostics were changed from runtime-disable-only to production
   compile-time de-harness;
2. remaining Phase4 physical harness symbols were found by the fail-closed gate;
3. lab-only source packaging was changed so ESPHome non-production builds still
   receive the implementation while production preprocesses it away;
4. malformed preprocessor guards and duplicate-definition packaging attempts were
   caught by CI and repaired;
5. the final implementation uses neutral support translation units whose complete
   lab implementation is inside `#ifndef GH_N3W_PRODUCTION_DEHARNESS`.

The final R4 production gate uses explicit:

```text
if grep -Fq "$marker" "$file"; then
  exit 1
fi
```

and scans ELF symbols, linker map, application binary strings and factory binary
strings. It does not use the rejected `! grep` pattern.

## 4. Final source CI

At exact product source `ec5f6d68...`, repository CI completed with:

- 31 workflows total;
- 28 SUCCESS;
- 3 FAILURE;
- 0 unfinished.

The three failures are the already-known Stage2D2 / Stage2D3 / Stage2D4 historical
authoring-boundary false-fails. Their functional matrices pass and they are not
required main status checks for this route.

All R4-relevant workflows passed, including:

- N3W Board_D R4 production de-harness CI;
- N3W current-main product source convergence R3 CI;
- N3W production multi-relay gateway selection V1 CI;
- N3W production relay discovery full-channel fallback V1 CI;
- F1.0-RC2 firmware CI;
- N3-W boot-session recovery helper CI;
- N3-W ESP32-C6 frame boot keystate core CI;
- greenhouse-manager CI;
- Public repository safety CI.

No new valid CI failure remains.

## 5. Exact artifact V2 build model

The build-only branch is:

`build/n3w-board-d-r4-f1rc2-ec5f6d68-artifact-20261023`

with build head:

`726d5593ab8cf7a46972153f2c30558fea76ecca`.

Comparison from exact source to build head is exactly one commit and exactly one
file:

`.github/workflows/n3w-board-d-r4-f1rc2-ec5f6d68-exact-artifact-build.yml`.

The workflow checks out the exact product source `ec5f6d68...`; the workflow
commit itself is not compiled as product source.

Run `39901919230` completed SUCCESS. Every critical step passed:

- exact source/tree/blob binding;
- R2/R3/R4 integrated source-contract recheck;
- formal F1.0-RC2 compile;
- ESP-IDF 5.5.4 verification;
- fail-closed four-layer de-harness proof;
- deterministic release freeze;
- artifact upload.

## 6. Independent artifact binding

GitHub artifact:

```text
ID=12478974186
NAME=n3w-board-d-r4-f1rc2-ec5f6d68-exact-source
GITHUB_ARTIFACT_SHA256=898ef722cd4af37ae5472583b1874f7724e9444e8837462d36f4e6be7eea092f
```

The artifact was independently downloaded after the workflow completed.

Independent checks:

- downloaded outer ZIP SHA256 exactly equals the GitHub artifact digest;
- outer ZIP contains exactly the inner release ZIP plus its SHA256 sidecar;
- sidecar digest equals independently computed inner ZIP SHA256
  `b55aba9c3fad85da39eab63157c3de7c42f311970bfb61f8b0e9a52ddcba7dd5`;
- inner ZIP contains exactly 8 members;
- every inner member has deterministic `1980-01-01 00:00:00` ZIP timestamp,
  stored compression and regular-file mode;
- manifest SHA256 is
  `173fcc978284170e0918c94269195191be0fc8a262b758851f16ee0609a638eb`;
- all seven non-manifest member sizes and SHA256 values match the manifest;
- manifest source head, source tree, formal target and critical source blob
  identities match the independently fetched GitHub source;
- direct byte scanning of `firmware.bin` and `firmware.factory.bin` found zero
  occurrences of all 12 forbidden lab markers;
- both binaries contain the positive production controls
  `gh.telemetry/1` and `air_temperature_c`.

The release artifact itself does not contain ELF or linker-map files; therefore
the independent downloaded-artifact scan applies directly to the two production
binary members, while ELF-symbol and linker-map absence is proven by the
successful fail-closed build step in run `39901919230`.

## 7. Release members

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

The exact member digests are recorded in the Closure block above.

## 8. Flash-args guard

The frozen `flash_args` member still contains build-tree-relative names such as:

```text
0x0 bootloader/bootloader.bin
0x10000 gh.bin
0x8000 partition_table/partition-table.bin
0x9000 ota_data_initial.bin
```

The flat release bundle does not contain those exact relative paths/names.
Therefore a later Board_D write gate must **not** blindly execute the bundled
`flash_args`. It must use a separately reviewed write procedure, such as the
verified factory image or an explicitly normalized offset-to-member mapping.

This is a physical-write procedure guard, not an R4 artifact-binding failure.

## 9. Final disposition

R4 is `CLOSED_PASS`.

The exact V2 artifact is cryptographically and semantically bound to the final
R4 exact product source. The initial V1 artifact remains rejected evidence only.

PR #656 is technically source/artifact ready for a separate merge decision, but
it remains an open draft and no merge authorization has been granted. R4 closure
does not itself authorize changing draft status, merging, Board_D access, flashing,
NVS mutation, RF execution or T1 access.

The next action must be entered as a separate gate/decision. This closure does not
auto-enter either PR #656 merge or Board_D physical acceptance.
