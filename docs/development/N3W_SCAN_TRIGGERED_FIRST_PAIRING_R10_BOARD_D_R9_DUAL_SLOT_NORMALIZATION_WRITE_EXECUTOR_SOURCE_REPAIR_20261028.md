# N3-W Scan-Triggered First Pairing R10 — Board D R9 Dual-Slot Normalization Write Executor Source Repair

Date: 2026-10-28

Gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_BOARD_D_R9_DUAL_SLOT_NORMALIZATION_WRITE_EXECUTOR_SOURCE_REPAIR_20261028_01`

## 1. Scope

This gate implements and independently reviews the source/tests/CI for the R9-specific Board D dual-slot normalization route frozen in PR #723.

It does not access T1 or Board D, open a serial port, write flash/NVS, consume physical authorization, retry the physical run, or merge any PR.

## 2. Source authority

```text
PARENT_DESIGN_PR=723
PARENT_DESIGN_HEAD=b981cb9e6566aa56cb458702ac387945270fddeb
TARGET_PR=724

CODE_REVIEW_HEAD=c92f439a044f4ff6ce411925831a92a6b9de52ae

EXECUTOR_BLOB=8b6c7d47632747221276f98188ff9023ced448db
TEST_BLOB=6946ca139e575f10f02819aceaf3fdfb98b3e716
WORKFLOW_BLOB=3fc9522a27e40aa74e4ae54a10b1f0081cbceba3
```

## 3. Frozen R9 authority

```text
R9_SOURCE=e299c937a7b89bb8a7b9a7432186ba46a416cd44
R9_PRODUCT_TREE=e6e8290bdea3d9b09a70c598b4c3a9f5551540a7
R9_WORKFLOW_HEAD=d6c3e09464c7bcb8e30bdcbbc7a1cdc8fbcec303
R9_WORKFLOW_RUN=40612774339
R9_ARTIFACT_ID=12783234959
R9_OUTER_SHA256=6b31001da3a4dff44f8c8cf605b885bcafcfd084d35969351938aa4904cc9995
R9_INNER_SHA256=b30bede249c90d4a50c9d3d779219bf9bf84a91960ec2a67332ef895e6a07dc1
R9_MANIFEST_SHA256=8db79ea5c7ac3b3c4b97a7852bf39447ff2f14d45880d4c5a0d8e4d5805cdf05

BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5

R9_APPLICATION_SIZE=0x1647B0
R9_NORMALIZATION_TAIL_SIZE=0x25B850
R9_NORMALIZED_SLOT_SIZE=0x3C0000
R9_NORMALIZED_SLOT_SHA256=6e777334cd8dec12523ec5e2daa6ce2909a4d581531218b0d9cec26803f68079
BOOTLOADER_ERASE_SPAN_SHA256=e88f39529dd195f7f792c4be45d435c0c205c64e5147cf31be125d9344d600ae
```

## 4. Implemented write route

```text
SELECTED_WRITE_ROUTE=R9_DUAL_SLOT_PADDED_NORMALIZATION_BOOTLOADER_OTADATA

WRITE_BOOTLOADER=0x000000:exact_R9_bootloader
WRITE_OTADATA=0x009000:exact_all_FF_OTA_data
WRITE_APP0=0x010000:complete_R9_normalized_slot
WRITE_APP1=0x3D0000:complete_R9_normalized_slot

PARTITION_TABLE_WRITE=false
PHY_INIT_WRITE=false
NVS_WRITE=false
FACTORY_IMAGE_DIRECT_WRITE=false
RAW_FLASH_ARGS_DIRECT_EXECUTION=false
FULL_FLASH_ERASE=false
ERASE_REGION_COMMAND_USED=false
```

The executor calculates and freezes sector-rounded erase ranges before any authorization claim:

```text
bootloader=0x000000..0x006000
otadata=0x009000..0x00B000
app0=0x010000..0x3D0000
app1=0x3D0000..0x790000
```

Protected ranges remain outside every write:

```text
partition_table=0x008000..0x009000
phy_init=0x00B000..0x00C000
nvs=0x790000..0x800000
```

## 5. Fresh prewrite evidence and one-shot claim

Immediately before a later real write, the executor requires a fresh private backup of every actual touched range:
- complete bootloader erase span;
- OTA data;
- complete app0 slot;
- complete app1 slot.

It also captures the protected partition sector, PHY and NVS and binds their hashes.

The executor requires:
- exactly one selected USB modem target;
- ESP32-C6;
- 8 MB flash;
- Secure Boot disabled;
- Flash Encryption disabled;
- exact frozen Board D identity;
- exact R9 partition table;
- all-FF PHY disposition;
- exact artifact/member hashes;
- deterministic R9 normalized-slot hash.

The authorization claim occurs only after all fresh backups and validations pass. The claim moves the preflight state to the claimed state and records:

```text
authorization_claimed=true
authorization_consumed=true
replay_permitted=false
```

A failure before claim leaves the authorization unconsumed. A failure after claim never makes it replayable.

## 6. Durable authorization-state repair

Independent source review found one source-reliability gap after the first green implementation head: private JSON state used one `os.write()` call and directory-entry transitions were not explicitly fsynced.

That could weaken durable one-shot evidence under a short-write or abrupt-power-loss edge case.

The exact source was repaired before closure:
- private state writes now loop until all bytes are written;
- a zero-progress write stops fail-closed;
- files are fsynced;
- parent directories are fsynced after create/replace;
- authorization hard-link/unlink transitions are directory-fsynced.

Focused regression tests cover short writes, zero-progress failure and claim-directory persistence.

## 7. Postwrite proof

Before application boot is accepted, the executor requires complete readback of:
- bootloader full erase span;
- exact OTA data;
- complete app0 slot;
- complete app1 slot;
- partition sector;
- PHY;
- NVS;
- Board D identity/security.

PASS requires:
- bootloader erase-span SHA exact;
- OTA data SHA exact;
- app0/app1 complete-slot SHA equal the frozen R9 normalized-slot SHA;
- both app tails are all FF;
- partition table exact and unchanged;
- PHY unchanged;
- NVS unchanged;
- Board D identity unchanged.

A successful esptool return code alone is never accepted as completion.

## 8. Post-claim failure / rollback

If write or immediate postwrite proof fails after authorization claim:
1. authorization stays consumed and non-replayable;
2. executor verifies the fresh backup set;
3. it restores all four touched ranges from those exact backups;
4. it re-reads all restored touched ranges plus partition/PHY/NVS;
5. it rechecks Board D identity.

Only exact restoration may report rollback PASS. Otherwise result is `ROLLBACK_INCOMPLETE`.

Rollback PASS still terminates the run. It does not authorize retry.

## 9. Tests and CI

The first PR head exposed one repository-safety-only fixture problem: a synthetic test literal matched the repository MAC-address safety detector. It was repaired without product behavior change.

The following exact code-review head then closed fully:

```text
CODE_REVIEW_HEAD=c92f439a044f4ff6ce411925831a92a6b9de52ae

DEDICATED_CI_RUN=40707594208
PY_COMPILE=PASS
FOCUSED_TESTS=35_OF_35_PASS
PUBLIC_REPOSITORY_SAFETY=PASS

PR_WORKFLOW_TOTAL=12
PR_WORKFLOW_SUCCESS=12
PR_WORKFLOW_FAILURE=0
```

Independent source review also re-read the exact-head critical functions covering:
- complete prewrite backup coverage;
- protected-range exclusion;
- backup verification before claim;
- claim before first write;
- one-shot/no-replay state;
- exact four-segment write command;
- full app0/app1 and protected-region readback;
- bounded rollback and restore verification.

No new false-PASS path was found after the durability repair.

## 10. Closure

```text
SOURCE_REPAIR_RESULT=CLOSED_PASS
NEW_SOURCE_BLOCKER_COUNT=0
SOURCE_REPAIR_REQUIRED=false

BOARD_ACCESS=false
T1_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_CONSUMED=false
MERGE=false
```

The old direct-factory physical authorization remains historically unconsumed but is not valid for this changed write route. It must not be reused or scope-expanded.

A new explicit one-shot physical authorization is required before any subsequent Board D access under the new route.

Next one gate:

```text
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_BOARD_D_R9_DUAL_SLOT_NORMALIZATION_PHYSICAL_PREFLIGHT_AND_WRITE_20261028_01
```

That successor gate must first present the exact artifact, Board D identity, four write ranges, protected ranges, fresh backup scope and one-shot semantics to the user and obtain a new explicit authorization before any board access.
