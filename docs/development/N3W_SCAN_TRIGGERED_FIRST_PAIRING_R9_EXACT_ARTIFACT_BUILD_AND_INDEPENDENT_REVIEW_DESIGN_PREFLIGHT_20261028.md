# N3W Scan-Triggered First Pairing R9 — Exact Artifact Build + Independent Review Design Preflight

Date: 2026-10-28

Gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R9_EXACT_ARTIFACT_BUILD_AND_INDEPENDENT_REVIEW_DESIGN_PREFLIGHT_20261028_01`

## 1. Gate scope

This gate is design / preflight only.

Allowed:
- fresh repository / PR / exact-source rebind;
- read-only source and prior artifact-process review;
- exact-artifact workflow design;
- artifact member/binding schema design;
- independent artifact/source review design;
- R10 pre-physical boundary design;
- docs-only GitHub archive.

Not allowed:
- formal R9 artifact production;
- GitHub artifact publication in this gate;
- T1 access or mutation;
- board access or flashing;
- live runtime mutation;
- production service start;
- merge;
- physical acceptance.

R9 remains the frozen stage:

```text
R9 = exact artifact build and independent source review
```

R10 remains separately authorized physical acceptance.

## 2. Fresh authority rebind

Repository:

`chrenguo-stack/HomeAssistant`

Repository main remains exactly:

`2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e`

Fresh compare:
- status: identical;
- ahead: 0;
- behind: 0.

R8 exact repository/source authority:

`e299c937a7b89bb8a7b9a7432186ba46a416cd44`

R8 exact source tree:

`e6e8290bdea3d9b09a70c598b4c3a9f5551540a7`

R8 implementation:
- PR #705;
- open;
- draft;
- unmerged;
- exact-head CI PASS.

R8 docs-only closure:
- PR #706;
- head `b6e74bc80fc7ecb422a6eb51c5244e6e2b581c45`.

R9 product artifact authority is the exact R8 repository head
`e299c937a7b89bb8a7b9a7432186ba46a416cd44`.

The R8 docs-only closure commit does not redefine artifact source authority.

## 3. Why R9 uses the R8 exact repository head

R8 changed only test/CI files relative to the R7 product source.

Therefore the product firmware bytes are unchanged from R7, but R9 must still bind the final artifact to the exact repository state that passed the complete R8 E2E/safety gate.

Frozen rule:

```text
R9_SOURCE_HEAD=e299c937a7b89bb8a7b9a7432186ba46a416cd44
R9_SOURCE_TREE=e6e8290bdea3d9b09a70c598b4c3a9f5551540a7

R8_TEST_GATE_INCLUDED_IN_SOURCE_AUTHORITY=true
R7_PRODUCT_FIRMWARE_BYTES_UNCHANGED_BY_R8=true
```

Do not silently fall back to the earlier R7 SHA merely because the firmware subtree is byte-identical.

## 4. T1 / Manager artifact boundary

Fresh compare of current main to the R8 exact head shows no changed production files under:
- `host/greenhouse-manager/src/**`;
- T1 host production tooling;
- deployment tooling.

The R8 exact-head differences from main are:
- node firmware source;
- tests;
- CI;
- documentation.

Therefore the T1/Manager production source required by R1-R3 is already part of current main authority.

R9 does **not** build a new T1 Manager image solely for scan-triggered first pairing.

Frozen result:

```text
R9_NEW_T1_MANAGER_ARTIFACT_REQUIRED=false
R9_NODE_FIRMWARE_EXACT_ARTIFACT_REQUIRED=true
```

This does not authorize assuming the live T1 already runs the correct build.

R10 preflight must independently prove the actual T1 runtime contains the required R1-R3 production behavior/source authority before any physical pairing test.

If that runtime binding cannot be proven:
- STOP physical acceptance;
- do not improvise a source copy;
- perform a separately designed/authorized exact T1 runtime deployment gate.

## 5. Existing exact-artifact precedent

R9 must reuse the proven exact-artifact pattern from the earlier production firmware closure.

The precedent established:
- build-only branch exactly one workflow commit above product source;
- workflow checks out exact product source SHA, not workflow branch contents;
- exact source/tree/blob assertions before compilation;
- pinned Python / ESPHome / ESP-IDF toolchain;
- binary de-harness proof;
- deterministic release ZIP;
- SHA-256 sidecar;
- GitHub Actions artifact;
- independent artifact download and revalidation.

R9 must preserve those properties.

## 6. R9 build-branch topology

Recommended build branch:

`build/n3w-scan-first-pair-r9-e299c937-artifact-20261028`

Recommended workflow path:

`.github/workflows/n3w-scan-first-pair-r9-exact-artifact-build.yml`

The branch must be created directly from:

`e299c937a7b89bb8a7b9a7432186ba46a416cd44`

The branch must contain exactly one additional commit and exactly one changed file:

```text
SOURCE_HEAD=e299c937a7b89bb8a7b9a7432186ba46a416cd44

BUILD_BRANCH_HEAD=<workflow-only commit>

compare SOURCE_HEAD..BUILD_BRANCH_HEAD:
  ahead_by=1
  behind_by=0
  changed_files=1
  changed_path=.github/workflows/n3w-scan-first-pair-r9-exact-artifact-build.yml
```

Any production-source change on the build branch invalidates R9 artifact production.

## 7. Workflow checkout rule

The workflow must explicitly checkout:

`e299c937a7b89bb8a7b9a7432186ba46a416cd44`

It must not build:
- the PR synthetic merge SHA;
- `main`;
- the workflow branch HEAD;
- a moving branch;
- a tag created after build.

Required assertion:

```bash
test "$(git rev-parse HEAD)" = "e299c937a7b89bb8a7b9a7432186ba46a416cd44"
test "$(git rev-parse HEAD^{tree})" = "e6e8290bdea3d9b09a70c598b4c3a9f5551540a7"
```

The workflow trigger SHA is recorded separately as provenance and must never be confused with product source SHA.

## 8. Exact target

Formal firmware target remains:

`firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml`

Exact target blob:

`176ef5a2839ba8d58b4675c5f5097eba5c662236`

R9 must use:

```text
RC2_CONFIG=f1_0_rc2_n3w_target.yml
```

No alternate YAML, debug target, physical harness target, or Board-specific temporary configuration is eligible.

## 9. Critical source blob anchors

The source head/tree is the complete authority.

For human-readable and machine-auditable binding, R9 also freezes critical blob anchors.

```text
TARGET_CONFIG
  firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml
  176ef5a2839ba8d58b4675c5f5097eba5c662236

TELEMETRY_PACKAGE
  firmware/esphome_rc/f1_0_rc2/packages/n3w_product_telemetry.yml
  ce16f2389d146f9b25e95cbb628547e11ce36bd6

TRANSPORT_PACKAGE
  firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml
  aa8dfa7e6be2ded398b8e90ab74a571e6a1b1ee2

DISPLAY_PACKAGE
  firmware/esphome_rc/f1_0_rc2/packages/display.yml
  35bb9e4b839b298b0b478ff30675b51671f61bb4

PRODUCT_COMPONENT
  firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp
  64073f3d33beaa04679c6d637fb4fca5b519652f

REGISTRATION_PORTAL
  firmware/esphome_rc/components/greenhouse_n3w_core/n3w_registration_portal.cpp
  e0333f30e4af5862e97edf5ac16b4ee941ae0508

TLS_BOOTSTRAP_TRANSPORT
  firmware/esphome_rc/components/greenhouse_n3w_core/n3w_registration_bootstrap_transport.cpp
  30a176c4b8ed66aa1d7c9adaa2576d8798fb3032

PAIRING_CLIENT
  firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_pairing_client.cpp
  d5768aed73c76f2764b8619f877d952b3da7f83e

PAIRING_NVS
  firmware/esphome_rc/components/greenhouse_n3w_core/n3w_esp32_pairing_nvs.cpp
  059380bdccfb12204ccf8cadaff2ea87422ba926
```

R8 gate anchors:

```text
R8_MANAGER_E2E_TEST_BLOB
  14b284c5114db901722ff068124ed1f4700982f0

R8_SAFETY_CONTRACT_BLOB
  d617a3a3ad834b78ad924d4b55abbb715cbbc141

R6_TLS_CONTRACT_BLOB
  d12968e9586c9e10d6cdbffbeb6296ab30bbc5ce

R7_LCD_CONTRACT_BLOB
  cc4ce758fe03b33b4a59619afbc2674f203f403e
```

The workflow must fail if any frozen blob anchor does not match.

## 10. Toolchain binding

Freeze:

```text
PYTHON_MAJOR_MINOR=3.11
ESPHOME_VERSION=2026.4.3
EXPECTED_ESP_IDF_VERSION=5.5.4
```

The workflow must:
1. install exactly ESPHome 2026.4.3;
2. compile the formal target;
3. inspect PlatformIO's ESP-IDF version file after toolchain resolution;
4. fail unless ESP-IDF resolves exactly to 5.5.4.

Do not accept a future ESPHome or IDF version without a new R9 design delta.

## 11. Required pre-build source gates

Before compiling the formal artifact, the exact-source workflow must rerun the focused gates needed to prove the artifact source is still the reviewed source.

Minimum:
- R4 portal/source contract;
- R5 discovery/multi-T1 contract;
- R6 TLS bootstrap contract;
- R7 LCD state/hardware-SPI contract;
- R8 E2E safety source contract;
- R8 Manager simulated E2E.

The R8 E2E is test-only and may run from:
`host/greenhouse-manager`.

A green historical PR run is not enough to produce the artifact.

## 12. Firmware compile

The exact workflow must:
- run ESPHome config validation for the formal N3-W target;
- compile the exact target;
- fail if expected outputs are absent.

Required output roots:

```text
firmware.bin
firmware.ota.bin
firmware.factory.bin
bootloader.bin
partitions.bin
ota_data_initial.bin
flash_args
firmware.elf
firmware.map
```

Only the first seven are physical release members.

ELF/map are build evidence only.

## 13. Binary de-harness proof

R9 must independently prove that no old physical/lab harness markers entered the production binary.

Retain the previously guarded forbidden-marker set, including at minimum:

```text
Phase4PhysicalHarness
N3wLabDiagnostics
N3wRtcBreadcrumb
n3w_phase4_physical_harness
n3w_lab_diagnostics
n3w_rtc_breadcrumb
n3w_rtc_breadcrumb_
gh_n3w_diag
N3W_DIAG_DISCOVERY
PHASE4_LAB_TELEMETRY
phase4_source_harness
phase4_lab_diagnostics
```

Check:
- demangled ELF symbols;
- firmware.map;
- printable strings from firmware.bin;
- printable strings from firmware.factory.bin.

Any hit is a hard blocker.

## 14. R4-R7 positive binary controls

R9 must also prove the artifact is not merely a valid generic N3-W image.

Required positive controls should include both legacy product identity and new registration feature presence.

Legacy controls:
- `GreenhouseN3wCore` symbol;
- `SimpleProductComponent` symbol;
- `gh.telemetry/1` string;
- `air_temperature_c` string.

R4-R7 registration controls should include independently verified exact strings/symbols such as:
- `RegistrationPortal`;
- `RegistrationBootstrapTransport`;
- `RegistrationDisplayController`;
- `gh.registration.portal-action/1`;
- `gh.registration.confirm/1`;
- `/api/v1/register/start`.

The implementation gate must first verify which controls are guaranteed to survive the exact compiler/linker settings.

Do not freeze a marker merely because it appears in source; it must be observed in the exact build output before closure.

## 15. Hardware-SPI source/artifact binding

R7 requires:

```yaml
interface: hardware
```

R9 source binding includes exact `display.yml` blob
`35bb9e4b839b298b0b478ff30675b51671f61bb4`.

The exact build must also retain the generated ESPHome/ESP-IDF evidence that resolves the SPI interface to hardware.

R9 does not claim physical electrical margin at 1 MHz.

That remains R10.

## 16. Release bundle member set

Inner physical release bundle must contain exactly eight files:

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

No ELF, map, test logs, source files, secrets or private keys enter the physical bundle.

## 17. Deterministic bundle construction

Use a deterministic ZIP:
- sorted member names;
- fixed timestamp 1980-01-01 00:00:00;
- fixed regular-file mode;
- ZIP_STORED unless a design delta explicitly changes it.

Recommended inner bundle name:

`n3w-scan-first-pair-r9-e299c937-exact-source.zip`

The output directory also contains:

`n3w-scan-first-pair-r9-e299c937-exact-source.zip.sha256`

The sidecar must contain the exact inner bundle SHA-256.

## 18. Manifest schema

Recommended manifest schema:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R9_EXACT_ARTIFACT_V1`

Manifest must be secret-free.

Required authority fields:

```text
BINDING_SCHEMA
SOURCE_HEAD
SOURCE_TREE
TARGET_CONFIG
TARGET_BLOB_SHA
TELEMETRY_PACKAGE_BLOB_SHA
TRANSPORT_PACKAGE_BLOB_SHA
DISPLAY_PACKAGE_BLOB_SHA
PRODUCT_COMPONENT_BLOB_SHA
REGISTRATION_PORTAL_BLOB_SHA
TLS_BOOTSTRAP_TRANSPORT_BLOB_SHA
PAIRING_CLIENT_BLOB_SHA
PAIRING_NVS_BLOB_SHA
R8_MANAGER_E2E_TEST_BLOB_SHA
R8_SAFETY_CONTRACT_BLOB_SHA
PYTHON_VERSION
ESPHOME_VERSION
ESP_IDF_VERSION
WORKFLOW_TRIGGER_SHA
WORKFLOW_RUN_ID
```

Build-evidence fields:

```text
R4_CONTRACT=PASS
R5_CONTRACT=PASS
R6_CONTRACT=PASS
R7_CONTRACT=PASS
R8_SAFETY_CONTRACT=PASS
R8_MANAGER_E2E=PASS
BINARY_DEHARNESS_PROOF=PASS
REGISTRATION_BINARY_POSITIVE_CONTROLS=PASS
HARDWARE_SPI_BUILD_BINDING=PASS
```

For every physical member:
- size;
- SHA-256.

Do not put GitHub tokens, Setup Secret, pairing ID, device credentials, private keys or live-network information in the manifest.

## 19. GitHub Actions artifact

Recommended GitHub artifact name:

`n3w-scan-first-pair-r9-e299c937-exact-source`

The uploaded GitHub artifact should contain only:
- inner release bundle;
- inner release bundle SHA-256 sidecar.

Recommended:
- `compression-level: 0`;
- `if-no-files-found: error`;
- retention 30 days, matching the previous proven route.

Artifact metadata to capture:
- workflow run ID;
- artifact ID;
- artifact name;
- created_at;
- expires_at;
- artifact size;
- GitHub-reported artifact digest.

If R10 does not occur before expiry, the expired artifact must not be replaced by an assumed-equivalent local rebuild.

A new exact-artifact build/binding gate is required.

## 20. Build-run publication rules

Artifact production is allowed only in the subsequent R9 build execution gate.

The preflight gate does not dispatch the workflow.

The implementation gate may:
- add the workflow-only commit;
- push the exact build branch;
- allow its push trigger to create the artifact.

Do not manually re-run an old artifact workflow against a changed workflow file/source authority.

Any workflow repair creates a new workflow commit and a new artifact run.

Earlier runs become superseded evidence, not the R10 candidate.

## 21. Independent artifact review must be external to build job

The artifact build job may self-check files before upload, but that is not sufficient for R9 closure.

Independent review must:
1. fresh rebind the build branch head and exact source;
2. fetch workflow run metadata;
3. fetch artifact metadata through GitHub;
4. independently download the GitHub Actions artifact;
5. compute the outer ZIP SHA-256;
6. compare it with GitHub artifact digest when GitHub supplies a SHA-256 digest;
7. inspect the outer wrapper member set;
8. extract the inner release bundle and sidecar;
9. recompute the inner release bundle SHA-256;
10. verify the sidecar;
11. inspect the inner ZIP safely;
12. verify exact inner member set;
13. verify manifest source/tree/blob bindings;
14. recompute each member size/hash against manifest;
15. directly inspect downloaded firmware.bin and firmware.factory.bin strings for forbidden markers and positive controls.

The independent reviewer must not reuse files from the build workspace.

## 22. Artifact ZIP safety review

Independent review must reject:
- path traversal;
- absolute paths;
- duplicate names;
- symlinks;
- hardlinks;
- device/FIFO/special members;
- extra unexpected members;
- missing required members.

Every inner member must be a regular flat file.

## 23. Source continuity review

R9 independent source review must separately verify:
- build branch is exactly one workflow-only commit above `e299c937...`;
- workflow itself checks out `e299c937...`;
- exact source tree matches `e6e8290...`;
- all critical blob anchors match;
- no source drift appeared after R8;
- R4-R8 focused tests remain green;
- no product source repair was hidden in the artifact workflow commit.

A valid binary hash cannot compensate for source-authority drift.

## 24. R8 continuity

R9 must preserve the exact R8 closure claims:

```text
R8_MANAGER_E2E=PASS
R8_SAFETY_CONTRACT=PASS
PRODUCTION_SOURCE_MUTATION=false
NEW_FALSE_PASS_BLOCKER_COUNT=0
```

The build workflow may rerun the tests; it may not redefine them.

## 25. Flash-args guard

The release bundle contains ESPHome's generated `flash_args`.

Historical evidence shows this file may contain build-tree-relative paths.

Therefore R10 must not blindly execute the copied `flash_args` from the flat release ZIP.

Before board write, R10 must use one of:
- the bound `firmware.factory.bin` with a separately reviewed whole-image flash procedure; or
- an independently normalized address/file map whose component hashes match the R9 manifest.

Frozen:

```text
R10_BLIND_FLAT_BUNDLE_FLASH_ARGS_EXECUTION=false
```

## 26. R10 exact-artifact authority

After R9 closure, R10 may reference only the exact independently reviewed artifact.

Required R10 inputs:

```text
R9_SOURCE_HEAD
R9_BUILD_WORKFLOW_HEAD
R9_WORKFLOW_RUN_ID
R9_ARTIFACT_ID
R9_ARTIFACT_DIGEST
R9_RELEASE_BUNDLE_SHA256
R9_MANIFEST_SHA256
FIRMWARE_FACTORY_BIN_SHA256
FIRMWARE_BIN_SHA256
```

A newly rebuilt binary with the same source SHA is not automatically equivalent to the reviewed candidate.

This preserves the existing KF-084-style artifact identity guard.

## 27. T1 pre-physical requirement

Before any R10 node write/pairing action, a separately authorized R10 preflight must prove:
- T1 is reachable through the approved access path;
- Manager runtime is healthy;
- 47110/47111/47112 product behavior corresponds to the reviewed R1-R3 production authority;
- current trusted-product-LAN authority is valid;
- no stale first-registration predecessor blocks the transaction;
- 47112 is idle CLOSED;
- no unintended existing transaction is active.

This gate does not perform those checks.

## 28. Physical acceptance boundary

R9 must not:
- flash a board;
- open/modify a T1 runtime;
- start a physical registration transaction;
- expose a Setup Secret;
- claim LCD visual acceptance;
- claim real Wi-Fi/TLS timing.

R10 remains separately authorized.

## 29. Failure classification

During R9 artifact production/review:

### Artifact-process failure
Examples:
- workflow bug;
- missing copied member;
- sidecar mismatch caused by packaging code;
- artifact upload misconfiguration.

Repair only artifact workflow/process, then produce a new run.

### Source/build blocker
Examples:
- formal target no longer compiles;
- R4-R8 focused contract fails on exact source;
- required registration positive controls are missing because feature was optimized/removed incorrectly;
- source/blob anchor mismatch;
- unexpected production-source drift.

Do not hide these with workflow changes.

### Toolchain drift
If exact ESPHome resolves a different ESP-IDF version:
- STOP;
- do not silently accept;
- produce design delta.

## 30. R9 implementation mutation allowlist

Initial R9 artifact implementation should change only:

`.github/workflows/n3w-scan-first-pair-r9-exact-artifact-build.yml`

on the dedicated build branch.

No product firmware source change is expected.

No Manager/T1 production source change is expected.

If a product-source repair becomes necessary:
- stop exact artifact nomination;
- repair in a separate source gate;
- rerun affected R4-R8 gates;
- choose a new R9 source head.

## 31. Independent review output

The R9 independent review closure must report at minimum:

```text
R9_SOURCE_HEAD=
R9_SOURCE_TREE=
R9_BUILD_WORKFLOW_HEAD=
R9_WORKFLOW_RUN_ID=
R9_ARTIFACT_ID=
R9_ARTIFACT_NAME=
R9_ARTIFACT_DIGEST=
R9_ARTIFACT_SIZE=
R9_RELEASE_BUNDLE_SHA256=
R9_MANIFEST_SHA256=

BUILD_BRANCH_WORKFLOW_ONLY=PASS
EXACT_SOURCE_CHECKOUT=PASS
CRITICAL_BLOB_BINDING=PASS
TOOLCHAIN_BINDING=PASS
R4_R8_FOCUSED_GATES=PASS
FORMAL_FIRMWARE_COMPILE=PASS
BINARY_DEHARNESS_PROOF=PASS
REGISTRATION_BINARY_POSITIVE_CONTROLS=PASS

INDEPENDENT_ARTIFACT_DOWNLOAD=PASS
OUTER_DIGEST_MATCH=PASS
INNER_RELEASE_DIGEST_MATCH=PASS
INNER_SHA256_SIDECAR_MATCH=PASS
INNER_MEMBER_SET_MATCH=PASS
ZIP_MEMBER_SAFETY=PASS
MANIFEST_SOURCE_BINDING_MATCH=PASS
MANIFEST_MEMBER_SIZE_HASH_MATCH=PASS
DOWNLOADED_BINARY_MARKER_REVIEW=PASS

NEW_R9_BLOCKER_COUNT=
SOURCE_REPAIR_REQUIRED=
R9_EXACT_ARTIFACT_BUILD=
R9_INDEPENDENT_REVIEW=
R10_ARTIFACT_ELIGIBLE=
```

## 32. Preflight result

```text
GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R9_EXACT_ARTIFACT_BUILD_AND_INDEPENDENT_REVIEW_DESIGN_PREFLIGHT_20261028_01

R9_SOURCE_HEAD=e299c937a7b89bb8a7b9a7432186ba46a416cd44
R9_SOURCE_TREE=e6e8290bdea3d9b09a70c598b4c3a9f5551540a7
MAIN_DRIFT=false

R9_NEW_T1_MANAGER_ARTIFACT_REQUIRED=false
R9_NODE_FIRMWARE_EXACT_ARTIFACT_REQUIRED=true
R10_T1_RUNTIME_BINDING_REQUIRED=true

R9_BUILD_BRANCH_MODEL=ONE_WORKFLOW_ONLY_COMMIT_ABOVE_EXACT_SOURCE
R9_ARTIFACT_MEMBER_SET_FROZEN=true
R9_MANIFEST_SCHEMA_FROZEN=true
R9_INDEPENDENT_DOWNLOAD_REQUIRED=true
R9_BUILD_WORKSPACE_SELF_REVIEW_SUFFICIENT=false

PRODUCTION_SOURCE_CHANGE_REQUIRED=false
GITHUB_ARTIFACT_PRODUCTION=false
T1_ACCESS=false
BOARD_ACCESS=false
LIVE_MUTATION=false
MERGE=false

R9_BUILD_WORKFLOW_IMPLEMENTATION_ELIGIBLE=true
PREFLIGHT_RESULT=PASS_READY_FOR_EXACT_ARTIFACT_WORKFLOW_IMPLEMENTATION
```

## 33. Next executable gate

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R9_EXACT_ARTIFACT_BUILD_WORKFLOW_IMPLEMENTATION_20261028_01`

That gate may create only the dedicated build workflow/branch and allow the exact push-triggered artifact build.

Artifact nomination and independent review remain incomplete until the build finishes and the GitHub artifact is independently downloaded and verified.
