# N3-W R10 Board D TLS-pin repair physical-acceptance exact artifact source — 2026-10-29

## Gate

N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_BOARD_D_TLS_PIN_REPAIR_PHYSICAL_ACCEPTANCE_EXACT_ARTIFACT_SOURCE_IMPLEMENTATION_20261029_01

This gate is repository source/CI work only.

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
BOARD_WRITE=false
EXACT_ARTIFACT_PRODUCTION_ON_NORMAL_CI=false
MERGE_TO_MAIN=false

## Product and acceptance authority

- product source: ff750b3801a282af1667b5fa63481e2333e301b3
- product tree: ee6ee5e362628fa725d57fbdf50c6608e9032b17
- acceptance source: f99342f9639fa234d85c509ddf6cf41fef91d691
- acceptance tree: 6c53b4ef480f67d984cc9b3c8cfa0886d706dde4
- acceptance source parent: exactly the product source above

The acceptance source delta is exactly one file and one added line:

firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml

battery_low_threshold: "-1.00"

The product source does not contain this bypass. The acceptance source is development/physical-acceptance only and is never production-eligible.

## Repaired registration authority carried by the Board source

The acceptance source inherits the repaired registration implementation from the product source without further registration-code changes:

- TLS trust authority: exact selected leaf SHA-256 pin
- mbedTLS auth mode: VERIFY_OPTIONAL
- pin mismatch: fatal verification callback result
- post-handshake leaf_seen + leaf_matched gate before HTTP/Setup Secret
- candidate TTL: 60 seconds
- post-selection confirmation window: fresh 60 seconds
- first countdown display: 59 seconds
- explicit user actions remain search -> select -> begin

Critical repaired source blobs are frozen in the workflow, including registration bootstrap transport, discovery header, portal cpp/h, simple product component, and R6/R8/R10 contract tests.

## Companion Manager authority

The Board artifact is cross-bound to the already closed Manager successor exact artifact:

- Manager package head: fb9b0112978545d831660c28fd95d5dfeaa784d1
- Manager artifact ID: 12877958163
- Manager artifact digest: sha256:042a7d467287b8192edacea076c7f47b2037eef7ba3b83a966369ba0ff89d93d
- Manager manifest SHA256: d31aa71635853922f816298ec0aa7aad83bb93da759c3732e3fd2b297364d406
- Manager tar SHA256: 26aebbbaa783b66ca374337d701f38692774dbc4df432a93fe712759c9eaff96
- Manager image: local/greenhouse-manager:fresh-ff750b3801a2
- Manager target product source: ff750b3801a282af1667b5fa63481e2333e301b3
- Manager candidate TTL: 60 seconds

This cross-binding prevents a repaired Board artifact from being accepted against the old 30-second Manager authority.

## CI staging

Workflow:

.github/workflows/n3w-r10-board-d-tls-pin-acceptance-artifact-ci.yml

Normal push/PR CI performs only source-contract work:

- product/acceptance lineage and one-line delta proof
- critical blob binding
- TLS pin-only semantics
- 60-second candidate TTL
- 60-second confirmation window / 59-second initial countdown
- focused R5/R6/R8/R10 tests
- no artifact production
- no Board or T1 access

Exact artifact production requires a later explicit workflow_dispatch with produce_exact_artifact=true.

The manual build checks out the exact acceptance source, installs ESPHome 2026.4.3, verifies ESP-IDF 5.5.4, materializes digest-pinned fonts, runs repaired registration contracts, compiles the exact ESP32-C6 target, proves the binary is de-harnessed and registration-capable, creates a deterministic inner release ZIP, uploads it, then redownloads and independently verifies release members and manifest bindings.

## Artifact contents

The inner release bundle contains exactly:

- MANIFEST.txt
- bootloader.bin
- firmware.bin
- firmware.factory.bin
- firmware.ota.bin
- flash_args
- ota_data_initial.bin
- partitions.bin

The manifest declares:

- PHYSICAL_ACCEPTANCE_ONLY=true
- DEVELOPMENT_ONLY=true
- PRODUCTION_ELIGIBLE=false
- LOW_BATTERY_PROTECTION_BYPASSED=true
- BOARD_WRITE_AUTHORIZED=false
- T1_MUTATION_AUTHORIZED=false

## Dual-slot boundary

This artifact source gate does not create or write normalized full-slot images. The write executor remains responsible for deriving a fresh OTA-slot-sized image from the new firmware.bin, padding the tail with 0xFF, calculating the new normalized slot SHA256, and writing the same exact normalized image to app0 and app1.

The historical #727 normalized-slot SHA and write authorization are invalid for this successor and must not be reused.

## Historical artifact non-reuse

The following historical authority remains evidence only and is explicitly not reusable:

- old acceptance source faf07839fcef221f9defb296eadcc7c090e12d4e
- old artifact run 40798244418
- old artifact ID 12864962159
- old outer SHA b57a5af10c23344e8e03250857455898eb60640e3e18c62022af9c2b9ab7f6da
- old normalized slot SHA 9d3b7b9d6b277e06cb6eb7f3155e9c777025b0d5cdb6e40feec47d46435eafbd

## Required next step

Fresh source CI and independent source review must pass before exact Board artifact dispatch.

No Board write or T1 mutation is authorized by this document.
