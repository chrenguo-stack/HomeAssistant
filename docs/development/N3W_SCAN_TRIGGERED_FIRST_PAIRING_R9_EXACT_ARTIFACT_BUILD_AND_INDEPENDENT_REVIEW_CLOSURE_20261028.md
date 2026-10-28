# N3W Scan-Triggered First Pairing R9 — Exact Artifact Build + Independent Review Closure

Date: 2026-10-28

Gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R9_EXACT_ARTIFACT_BUILD_AND_INDEPENDENT_REVIEW_CLOSURE_20261028_01`

## 1. Scope

This document closes R9 exact artifact production and independent artifact/source review.

Included:
- exact-source and build-branch rebind;
- formal exact firmware artifact production;
- artifact metadata capture;
- independent GitHub artifact download outside the build workspace;
- outer/inner digest validation;
- ZIP member safety;
- manifest/source/member binding validation;
- downloaded binary marker review;
- R10 artifact eligibility classification.

Not included:
- T1 access/mutation;
- board access/flashing;
- live runtime mutation;
- physical QR/LCD/Wi-Fi/TLS acceptance;
- merge.

## 2. Exact authorities

Repository:

`chrenguo-stack/HomeAssistant`

R9 exact source head:

`e299c937a7b89bb8a7b9a7432186ba46a416cd44`

R9 exact source tree:

`e6e8290bdea3d9b09a70c598b4c3a9f5551540a7`

R9 build workflow head:

`d6c3e09464c7bcb8e30bdcbbc7a1cdc8fbcec303`

Fresh build-branch continuity:

```text
ahead_by=1
behind_by=0
changed_files=1
changed_path=.github/workflows/n3w-scan-first-pair-r9-exact-artifact-build.yml
```

No product source file was changed by the build branch.

Repository main remained unchanged at:

`2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e`

## 3. Formal build run

Workflow run:

`40612774339`

Build job:

`122568077610`

Formal artifact workflow completed successfully.

Completed PASS:
- exact source/tree/critical blob binding;
- Python 3.11 toolchain setup;
- ESPHome 2026.4.3;
- pinned font archive digest verification;
- R4-R8 focused gates;
- exact N3-W target config;
- hardware SPI binding;
- exact production target compile;
- ESP-IDF 5.5.4 verification;
- binary de-harness proof;
- registration binary positive controls;
- release bundle freeze;
- artifact upload.

## 4. External font inputs

R9 additionally bound the external BDF font archives used by the display build.

Frozen release:

`2026.07.01`

Archive SHA-256:

```text
fusion-pixel 10 px:
0f28b5850fa9b4b0f8dbb7c40f671a3574a97236a848d1e0ecf6ed302ae659c3

fusion-pixel 12 px:
c461c312720e005f5a49843a965842e8749f196f00f97facf1ad926f330296df

ark-pixel 16 px:
c0b5e3afecf6ebadbb10d36d712d3ff828d58657382004a1fe4eae45db31ec01
```

Exact extracted BDF hashes recorded in the manifest:

```text
FUSION_10_BDF_SHA256=a9fecdecbe42c93e8d6c0642cf1a1fabe29e7c4dcdab43b4540fb23cc7e006b1
FUSION_12_BDF_SHA256=aea441a489b18a93bb417bba33a31917b1bef90167b01ed9a63e2e9df3e144f8
ARK_16_BDF_SHA256=449aff01631d6b585826ec2a1bbdbf0667c9b5dffa0d3f8311c906c720384fc0
```

## 5. GitHub Actions artifact authority

Artifact ID:

`12783234959`

Artifact name:

`n3w-scan-first-pair-r9-e299c937-exact-source`

Artifact size:

`4484150 bytes`

GitHub artifact digest:

`sha256:6b31001da3a4dff44f8c8cf605b885bcafcfd084d35969351938aa4904cc9995`

Created:

`2026-10-28T01:09:54Z`

Expires:

`2026-11-27T01:09:52Z`

The artifact is not expired at closure time.

## 6. Independent download

The GitHub Actions artifact was independently downloaded through the GitHub artifact API after the build job completed.

The independent review did not reuse:
- the Actions build workspace;
- temporary build directories;
- copied build outputs from the workflow runner.

Downloaded outer ZIP SHA-256:

`6b31001da3a4dff44f8c8cf605b885bcafcfd084d35969351938aa4904cc9995`

This exactly matches the GitHub-reported artifact digest.

Therefore:

`OUTER_DIGEST_MATCH=PASS`

## 7. Outer artifact ZIP

Outer ZIP contains exactly:

```text
n3w-scan-first-pair-r9-e299c937-exact-source.zip
n3w-scan-first-pair-r9-e299c937-exact-source.zip.sha256
```

Outer ZIP safety checks:
- no path traversal;
- no absolute path;
- no duplicate member;
- no directory member;
- no symlink/special member.

Result:

`OUTER_ZIP_SAFETY=PASS`

## 8. Inner release bundle

Inner release bundle:

`n3w-scan-first-pair-r9-e299c937-exact-source.zip`

Size:

`4483623 bytes`

SHA-256:

`b30bede249c90d4a50c9d3d779219bf9bf84a91960ec2a67332ef895e6a07dc1`

The sidecar independently matches the recomputed digest.

Result:

```text
INNER_RELEASE_DIGEST_MATCH=PASS
INNER_SHA256_SIDECAR_MATCH=PASS
```

## 9. Inner member set

Exact member set:

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

Independent safety review confirmed:
- exactly eight members;
- flat regular files only;
- no duplicate names;
- no path traversal;
- no absolute path;
- no symlink/special members;
- fixed 1980-01-01 ZIP timestamp;
- ZIP_STORED for every member.

Result:

```text
INNER_MEMBER_SET_MATCH=PASS
INNER_ZIP_SAFETY=PASS
DETERMINISTIC_ZIP_METADATA=PASS
```

## 10. Manifest authority

Manifest schema:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R9_EXACT_ARTIFACT_V1`

Manifest SHA-256:

`8db79ea5c7ac3b3c4b97a7852bf39447ff2f14d45880d4c5a0d8e4d5805cdf05`

Independent review verified:
- source head;
- source tree;
- target path/blob;
- telemetry/transport/display blobs;
- product component;
- portal;
- TLS bootstrap transport;
- pairing client;
- pairing NVS;
- R8 test anchors;
- font fetch script;
- font release/archive hashes;
- Python/ESPHome/ESP-IDF versions;
- R4-R8 PASS markers;
- de-harness PASS;
- registration positive controls PASS;
- hardware SPI PASS.

Result:

`MANIFEST_SOURCE_BINDING_MATCH=PASS`

## 11. Physical member hashes

Independent recomputation:

```text
firmware.bin
size=1460144
sha256=fe11f5a81ce83e97fc0834114486a9cace26624977f9c4e0104c71687f4cc7be

firmware.ota.bin
size=1460144
sha256=fe11f5a81ce83e97fc0834114486a9cace26624977f9c4e0104c71687f4cc7be

firmware.factory.bin
size=1525680
sha256=b734c343b3caf725c3991e6dc408b471a607f0c10cfe641346a78228b65c3bbf

bootloader.bin
size=22576
sha256=1f107afc1cbfe6ae993f450a38f41dff33e672ed8c8f69b5a2cc1a15194e7ad3

partitions.bin
size=3072
sha256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

ota_data_initial.bin
size=8192
sha256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

flash_args
size=167
sha256=5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713
```

Every independently computed size/hash exactly matches the manifest.

Result:

`MANIFEST_MEMBER_SIZE_HASH_MATCH=PASS`

## 12. Downloaded binary marker review

Independent review ran printable-string checks directly on the downloaded:
- `firmware.bin`;
- `firmware.factory.bin`.

Required positive controls found in both:
- `gh.telemetry/1`;
- `air_temperature_c`;
- `gh.registration.portal-action/1`;
- `gh.registration.confirm/1`;
- `/api/v1/register/start`.

Forbidden markers absent:
- `Phase4PhysicalHarness`;
- `N3wLabDiagnostics`;
- `N3wRtcBreadcrumb`;
- `n3w_phase4_physical_harness`;
- `n3w_lab_diagnostics`;
- `n3w_rtc_breadcrumb`;
- `n3w_rtc_breadcrumb_`;
- `gh_n3w_diag`;
- `N3W_DIAG_DISCOVERY`;
- `PHASE4_LAB_TELEMETRY`;
- `phase4_source_harness`;
- `phase4_lab_diagnostics`.

Result:

```text
DOWNLOADED_BINARY_FORBIDDEN_MARKERS=PASS
DOWNLOADED_BINARY_POSITIVE_CONTROLS=PASS
```

## 13. Hardware SPI binding

The exact build revalidated:

```text
interface: hardware
interface_index: 0
```

The manifest records:

`HARDWARE_SPI_BUILD_BINDING=PASS`

R9 does not claim physical electrical margin.

## 14. flash_args guard

Downloaded `flash_args` contains:

```text
--flash_mode dio --flash_freq 80m --flash_size 8MB
0x0 bootloader/bootloader.bin
0x10000 gh.bin
0x8000 partition_table/partition-table.bin
0x9000 ota_data_initial.bin
```

The flat release ZIP does not contain:
- `bootloader/bootloader.bin`;
- `gh.bin`;
- `partition_table/partition-table.bin`.

Therefore the frozen R10 guard is confirmed:

`R10_BLIND_FLAT_BUNDLE_FLASH_ARGS_EXECUTION=false`

R10 must use either:
- the exact bound `firmware.factory.bin`; or
- a separately reviewed normalized component address/file map.

## 15. Review state

PR #708:
- open;
- draft;
- unmerged;
- no review threads;
- no reviews.

Build branch still remains exactly one workflow-only commit above the R9 source.

No artifact identity drift was observed after build completion.

## 16. Final closure result

```text
GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R9_EXACT_ARTIFACT_BUILD_AND_INDEPENDENT_REVIEW_CLOSURE_20261028_01

R9_SOURCE_HEAD=e299c937a7b89bb8a7b9a7432186ba46a416cd44
R9_SOURCE_TREE=e6e8290bdea3d9b09a70c598b4c3a9f5551540a7

R9_BUILD_WORKFLOW_HEAD=d6c3e09464c7bcb8e30bdcbbc7a1cdc8fbcec303
R9_WORKFLOW_RUN_ID=40612774339
R9_BUILD_JOB_ID=122568077610

R9_ARTIFACT_ID=12783234959
R9_ARTIFACT_NAME=n3w-scan-first-pair-r9-e299c937-exact-source
R9_ARTIFACT_DIGEST=sha256:6b31001da3a4dff44f8c8cf605b885bcafcfd084d35969351938aa4904cc9995
R9_ARTIFACT_SIZE=4484150

R9_RELEASE_BUNDLE_SHA256=b30bede249c90d4a50c9d3d779219bf9bf84a91960ec2a67332ef895e6a07dc1
R9_MANIFEST_SHA256=8db79ea5c7ac3b3c4b97a7852bf39447ff2f14d45880d4c5a0d8e4d5805cdf05

FIRMWARE_BIN_SHA256=fe11f5a81ce83e97fc0834114486a9cace26624977f9c4e0104c71687f4cc7be
FIRMWARE_FACTORY_BIN_SHA256=b734c343b3caf725c3991e6dc408b471a607f0c10cfe641346a78228b65c3bbf

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

NEW_R9_BLOCKER_COUNT=0
SOURCE_REPAIR_REQUIRED=false

R9_EXACT_ARTIFACT_BUILD=PASS
R9_INDEPENDENT_REVIEW=PASS
R10_ARTIFACT_ELIGIBLE=true

T1_ACCESS=false
BOARD_ACCESS=false
LIVE_MUTATION=false
PHYSICAL_ACCEPTANCE=false
MERGE=false
```

## 17. R10 boundary

R10 may use only this exact reviewed artifact identity.

Before any board mutation, R10 must separately prove:
- live T1 runtime is the reviewed R1-R3-capable production runtime;
- Manager healthy;
- trusted-product-LAN authority healthy;
- no active predecessor transaction;
- idle 47112 CLOSED;
- exact artifact bytes are still available and hashes match.

No physical action is authorized by this document.
