# N3-W Board D development low-battery protection bypass — 2026-10-24

## Result

~~~text
TASK=N3W_BOARD_D_DEVELOPMENT_LOW_BATTERY_BYPASS_SOURCE_REPAIR_20261023_01
STATUS=CLOSED_PASS_ARTIFACT_READY

BASE_MAIN=dc596ad50eb2ea80ba55aa3af2413236321f1465
DEV_SOURCE_HEAD=a15daad779adde74cdead4702f017553118321f8
DEV_SOURCE_TREE=f86b8718df1225ab5f0435613f997011b8754bac

FIRMWARE_TREE_DELTA_FROM_EXACT_R4_FILES=1
FIRMWARE_TREE_DELTA_ADDITIONS=1
FIRMWARE_TREE_DELTA_DELETIONS=0
BYPASS=battery_low_threshold:-1.00

SOURCE_CI_TOTAL=14
SOURCE_CI_PASS=14
SOURCE_CI_FAIL=0

DEV_ARTIFACT_RUN_ID=40039280572
DEV_ARTIFACT_ID=12538399121
DEV_ARTIFACT_NAME=n3w-board-d-dev-low-battery-bypass-a15daad
DEV_GITHUB_ARTIFACT_SHA256=75b3206cd9d7d2a8d30ad49a0ff224981eaab770bad01dde8b6f1d69686bf88a
DEV_RELEASE_BUNDLE_SHA256=ad1529aa382ee8760008ced413a6050a4bbc3a21f8da9c8d24dc2d40d6f00213
DEV_MANIFEST_SHA256=ac13c8e1fba089da419f56cd6b393129e96a68aa270e0a63c74db4b50d85f5af
DEV_FIRMWARE_BIN_SHA256=da17489dd1ba4fdc13d52b88c03812cbc5a26d23ac2a57e2da5ab1c59a014e95
DEV_FACTORY_BIN_SHA256=26ec3ad5dd3333d2492fdf531fc0d1ae1ea8635cbb1029df60ae0e442d8b2b53

DEVELOPMENT_ONLY=true
PRODUCTION_ELIGIBLE=false
LOW_BATTERY_PROTECTION_BYPASSED=true
BOARD_D_WRITE=false
PR663_MERGE_ALLOWED=false
~~~

## Scope

The development patch changes only the N3-W target substitution:

~~~text
battery_low_threshold: "-1.00"
~~~

Battery ADC acquisition, battery voltage publication, battery percentage calculation, LCD display and the existing production low-battery implementation remain present. Since the ADC voltage cannot reach -1 V, the existing low-battery entry path cannot be triggered from battery voltage in this development image.

This is intentionally a development-only image. The production low-battery policy remains unchanged on main.

## Independent artifact validation

The GitHub artifact outer ZIP digest matches the GitHub artifact digest. The inner sidecar validates the deterministic development bundle. The inner bundle contains exactly eight members and every member digest matches the manifest.

The production exact R4 and development bundle have identical:

~~~text
partitions.bin
ota_data_initial.bin
flash_args
~~~

The bootloader sizes are identical. Its only readable difference is the build timestamp; 39 total bytes differ, including the trailing image digest/check bytes. No functional bootloader-source drift was found.

Comparing exact R4 product source `ec5f6d68...` to the development source shows exactly one firmware-tree file changed: `f1_0_rc2_n3w_target.yml`, with one added line.

## Physical boundary

No Board D write occurred in this source/artifact gate. The bypass is source/artifact-ready but not yet active on the physical board.

To avoid unnecessary flash cycles while KF-130 is open, the recommended physical order is:

1. separately authorized exact-R4 post-flash LCD reproduction;
2. preserve the immediate post-flash LCD result;
3. separately write this development artifact for ongoing bench work.

The development artifact must never be used as evidence that the original exact R4 post-flash path passes or fails.

PR #663 remains draft and must not be merged.
