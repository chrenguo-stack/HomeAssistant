# N3-W Scan-Triggered First Pairing R10 — Board D R9 Dual-Slot Normalization Route Design

Date: 2026-10-28

Gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_BOARD_D_R9_DUAL_SLOT_NORMALIZATION_ROUTE_DESIGN_20261028_01`

## 1. Scope and stop boundary

This is a source/design-only successor gate after the real Board D read-only preflight stopped with:

```text
R10_READONLY_PREFLIGHT=STOP_ROUTE_REVIEW_REQUIRED
T1_PREFLIGHT=PASS
BOARD_PREFLIGHT=PASS
ARTIFACT_BINDING=PASS
HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
PHY_ALL_FF=true
APP0_R9_MATCH=false
APP1_R9_MATCH=false
DIRECT_FACTORY_ROUTE_ELIGIBLE=false
FLASH_WRITE=false
NVS_WRITE=false
T1_MUTATION=false
WRITE_AUTHORIZATION_CONSUMED=false
```

This gate does not:
- access Board D;
- open a serial port;
- access T1;
- write flash or NVS;
- consume any physical write authorization;
- retry the blocked direct-factory route;
- merge any pull request.

The observed STOP is accepted as a correct fail-closed result. It is not classified as a board hardware failure.

## 2. Authority and current evidence

Physical preflight source authority:

```text
R10_READONLY_PREFLIGHT_HEAD=44a3faefff70b89032fd7b2bfbf64733b175b123
R10_READONLY_PREFLIGHT_BRANCH=exec/n3w-r10-physical-readonly-preflight-20261028
R10_READONLY_PREFLIGHT_EXECUTOR_BLOB=4f1711bc96faacf18edd56bbed753ecee0f3d29c
```

Exact R9 artifact authority:

```text
R9_SOURCE_HEAD=e299c937a7b89bb8a7b9a7432186ba46a416cd44
R9_SOURCE_TREE=e6e8290bdea3d9b09a70c598b4c3a9f5551540a7
R9_WORKFLOW_HEAD=d6c3e09464c7bcb8e30bdcbbc7a1cdc8fbcec303
R9_WORKFLOW_RUN_ID=40612774339
R9_ARTIFACT_ID=12783234959
R9_ARTIFACT_NAME=n3w-scan-first-pair-r9-e299c937-exact-source
R9_OUTER_SHA256=6b31001da3a4dff44f8c8cf605b885bcafcfd084d35969351938aa4904cc9995
R9_INNER_SHA256=b30bede249c90d4a50c9d3d779219bf9bf84a91960ec2a67332ef895e6a07dc1
R9_MANIFEST_SHA256=8db79ea5c7ac3b3c4b97a7852bf39447ff2f14d45880d4c5a0d8e4d5805cdf05
```

Board D public-safe identity:

```text
BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
```

This identity exactly matches the Board D identity frozen in the historical R4 dual-slot normalization route. That historical match supports reuse of the route structure, but it does not prove that the current app0/app1 bytes are R4. No current app version is inferred from the public preflight result.

## 3. Independent R9 byte derivation

Artifact 12783234959 was freshly downloaded and independently rehashed in this design gate.

Exact members relevant to the successor route:

```text
BOOTLOADER_SIZE=22576
BOOTLOADER_SIZE_HEX=0x5830
BOOTLOADER_SHA256=1f107afc1cbfe6ae993f450a38f41dff33e672ed8c8f69b5a2cc1a15194e7ad3

PARTITION_TABLE_SIZE=3072
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OTADATA_SIZE=8192
OTADATA_SIZE_HEX=0x2000
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
OTADATA_ALL_FF=true

R9_APPLICATION_SIZE=1460144
R9_APPLICATION_SIZE_HEX=0x1647B0
R9_APPLICATION_SHA256=fe11f5a81ce83e97fc0834114486a9cace26624977f9c4e0104c71687f4cc7be

R9_FACTORY_SIZE=1525680
R9_FACTORY_SIZE_HEX=0x1747B0
R9_FACTORY_SHA256=b734c343b3caf725c3991e6dc408b471a607f0c10cfe641346a78228b65c3bbf
```

The R9 partition geometry is unchanged from the validated Board D R4 route:

```text
PARTITION_TABLE_OFFSET=0x008000
OTADATA_OFFSET=0x009000
PHY_INIT_OFFSET=0x00B000
APP0_OFFSET=0x010000
APP1_OFFSET=0x3D0000
NVS_OFFSET=0x790000

PHY_INIT_SIZE=0x001000
OTA_SLOT_SIZE=0x3C0000
NVS_SIZE=0x070000
```

## 4. R9 normalized-slot derivation

The successor route derives a complete 0x3C0000 slot from the exact R9 `firmware.bin` followed only by 0xFF.

```text
NORMALIZED_SLOT_SIZE=3932160
NORMALIZED_SLOT_SIZE_HEX=0x3C0000

NORMALIZATION_TAIL_SIZE=2472016
NORMALIZATION_TAIL_SIZE_HEX=0x25B850
NORMALIZATION_TAIL_SHA256=a77ed5023b0caeaad43d58317f864574f4d82e9ba5af0274fb8df9df7584d209

R9_NORMALIZED_SLOT_SHA256=6e777334cd8dec12523ec5e2daa6ce2909a4d581531218b0d9cec26803f68079
```

The normalized slot is deterministic:

```text
normalized_slot = exact R9 firmware.bin || 0xFF * 0x25B850
```

Both app0 and app1 must receive this same complete slot image. Writing only the application-length prefix is forbidden because it would permit stale code/data to remain in either slot tail.

## 5. Selected successor route

The blocked route:

```text
DIRECT_R9_FACTORY_WRITE=SUPERSEDED_FOR_BOARD_D
```

The new selected design route is:

```text
SELECTED_WRITE_ROUTE=R9_DUAL_SLOT_PADDED_NORMALIZATION_BOOTLOADER_OTADATA

WRITE_BOOTLOADER=0x000000:bootloader.bin
WRITE_OTADATA=0x009000:ota_data_initial.bin
WRITE_APP0=0x010000:r9_normalized_slot.bin
WRITE_APP1=0x3D0000:r9_normalized_slot.bin

PARTITION_TABLE_WRITE=false
PHY_INIT_WRITE=false
NVS_WRITE=false
FACTORY_IMAGE_DIRECT_WRITE=false
RAW_FLASH_ARGS_DIRECT_EXECUTION=false
FULL_FLASH_ERASE=false
ERASE_REGION_COMMAND_USED=false
```

Reasons:
1. the R9 bootloader differs from the historical R4 bootloader and must be normalized to the exact R9 artifact;
2. OTA data is intentionally returned to the exact archived all-FF initial state;
3. both complete OTA application slots are normalized to the same exact R9 image plus FF tail;
4. the current partition table already passed exact R9 compatibility and is not rewritten;
5. PHY is preserved rather than rewritten;
6. NVS is preserved so this firmware normalization cannot silently become a factory reset.

## 6. Exact erase boundaries

The future executor must calculate the sector-rounded erase effect before claiming write authorization.

Expected erase ranges:

```text
bootloader  0x000000..0x006000
otadata     0x009000..0x00B000
app0        0x010000..0x3D0000
app1        0x3D0000..0x790000
```

Protected ranges:

```text
partition table  0x008000..0x009000
phy_init         0x00B000..0x00C000
NVS              0x790000..0x800000
```

Any write/erase overlap with a protected range is a preclaim STOP.

The bootloader is 0x5830 bytes and occupies a 0x6000 sector-rounded erase span. The exact expected postwrite contents of that touched span are the R9 bootloader bytes followed by 0xFF through 0x6000:

```text
BOOTLOADER_ERASE_SPAN_SIZE=0x6000
BOOTLOADER_ERASE_SPAN_SHA256=e88f39529dd195f7f792c4be45d435c0c205c64e5147cf31be125d9344d600ae
```

This strengthens the historical R4 proof by checking the whole bootloader erase span, not only the bootloader member length.

## 7. Existing private backup is not sufficient for this route

The completed direct-factory readonly preflight captured:
- the factory-image erase span through 0x175000;
- the full app1 slot;
- full NVS.

That evidence is valid for the blocked direct-factory route, but it does not cover the remainder of app0 that the successor route will now overwrite.

Therefore:

```text
OLD_PREFLIGHT_BACKUP_VALID_AS_HISTORICAL_EVIDENCE=true
OLD_PREFLIGHT_BACKUP_SUFFICIENT_FOR_SUCCESSOR_ROLLBACK=false
FRESH_PREWRITE_BACKUP_REQUIRED=true
```

Immediately before any future R9 dual-slot write, a new executor must privately capture every actual erase/write range:
- bootloader full erase span 0x000000 + 0x006000;
- OTA data 0x009000 + 0x002000;
- app0 full slot 0x010000 + 0x3C0000;
- app1 full slot 0x3D0000 + 0x3C0000.

It must also independently read/hash the protected:
- partition table;
- PHY init;
- NVS.

All raw backups remain private and must not be committed to GitHub.

## 8. Fresh preclaim contract

A later executor may claim write authorization only after fresh proof of all of the following:

1. exact artifact ID/name and current availability;
2. exact outer ZIP SHA256;
3. exact inner ZIP SHA256 and sidecar;
4. exact member set, sizes and SHA256;
5. exact manifest binding;
6. deterministic R9 normalized-slot size/hash;
7. exact all-FF OTA-data semantics;
8. esptool major version 5;
9. target reports ESP32-C6;
10. physical flash is 8 MB;
11. Secure Boot disabled;
12. Flash Encryption disabled;
13. target hardware ID hash equals the frozen Board D hash;
14. exactly one selected serial target;
15. current partition table equals the exact R9 partition table;
16. current PHY remains acceptable for the frozen route; current design expectation is all-FF as already observed;
17. full fresh prewrite backups of every touched erase range exist and are hashed;
18. full fresh NVS backup exists and is hashed;
19. write-range calculations exactly match the frozen ranges above;
20. no T1/product runtime repair is mixed into the board-write claim.

Any mismatch stops before authorization claim.

## 9. Write-command semantics

The successor source must preserve the validated R4 command semantics while rebinding every artifact value to R9:

```text
--before no-reset
--after no-reset

write-flash
--flash-mode keep
--flash-freq keep
--flash-size keep
```

The command must include exactly four write segments:
- R9 bootloader at 0x000000;
- exact archived all-FF OTA data at 0x009000;
- R9 normalized slot at 0x010000;
- the same R9 normalized slot at 0x3D0000.

It must not include:
- partition table;
- PHY;
- NVS;
- firmware.factory.bin;
- raw release flash_args;
- erase-flash;
- erase-region.

The application must not be allowed to boot between write and postwrite integrity proof.

## 10. Postwrite preboot acceptance

Before the application can boot, the executor must freshly read back and prove:

```text
BOOTLOADER_ERASE_SPAN_SHA256=e88f39529dd195f7f792c4be45d435c0c205c64e5147cf31be125d9344d600ae
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
APP0_FULL_SLOT_SHA256=6e777334cd8dec12523ec5e2daa6ce2909a4d581531218b0d9cec26803f68079
APP1_FULL_SLOT_SHA256=6e777334cd8dec12523ec5e2daa6ce2909a4d581531218b0d9cec26803f68079
```

It must also prove:
- partition table exact R9 hash and unchanged;
- PHY SHA256 unchanged from fresh prewrite;
- NVS SHA256 unchanged from fresh prewrite;
- Board D hardware identity unchanged;
- Secure Boot / Flash Encryption state unchanged.

Only then may:

```text
OLD_APPLICATION_CODE_REMAINS=false
R9_CODE_NORMALIZATION=PASS
```

be asserted.

A successful esptool return code alone is never completion evidence.

## 11. Rollback authority

Because the successor route touches more bytes than the blocked direct-factory route, rollback authority must also expand.

If write execution or immediate postwrite/preboot proof fails:
1. do not boot the application;
2. restore the exact fresh prewrite bytes for every touched erase range;
3. verify every restored range;
4. verify protected partition table / PHY / NVS continuity;
5. stop.

If rollback cannot be proven exact:

```text
ROLLBACK_RESULT=ROLLBACK_INCOMPLETE
AUTO_RETRY=false
```

If R9 code normalization passes and the application is allowed to boot, later first-registration failure does not authorize automatic firmware rollback or NVS clearing. Preserve the state and stop for root-cause review.

## 12. Product-state boundary after code normalization

This route normalizes executable firmware only. It deliberately preserves NVS.

Therefore:

```text
R9_DUAL_SLOT_NORMALIZATION_IS_FACTORY_RESET=false
R9_DUAL_SLOT_NORMALIZATION_PROVES_UNREGISTERED_STATE=false
```

After the first controlled boot, the existing R10 physical acceptance rules still apply:
- Wi-Fi must reconnect;
- the node must be genuinely unregistered;
- no higher-priority pending final-ACK recovery may exist;
- registration QR must be available;
- idle state must not automatically register with T1.

If Board D is already provisioned or has an incompatible NVS/product state, physical acceptance stops. NVS erase/reset is not authorized inside this route.

## 13. Authorization treatment

The previously granted one-shot authorization was bound to the original R10 physical acceptance/direct-factory route. The real preflight stopped before any write, so it remains unconsumed.

However, this successor route materially changes the write set from one partial factory-image write to bootloader + OTA data + two full application slots.

Therefore:

```text
PREVIOUS_WRITE_AUTHORIZATION_CONSUMED=false
PREVIOUS_WRITE_AUTHORIZATION_VALID_FOR_SUCCESSOR_ROUTE=false
AUTHORIZATION_SCOPE_EXPANSION_FORBIDDEN=true
NEW_EXPLICIT_ONE_SHOT_AUTHORIZATION_REQUIRED=true
```

A future successor authorization must bind:
- exact artifact 12783234959;
- exact R9 normalized-slot SHA256;
- exact Board D hardware identity hash;
- exact four-segment write route;
- exact protected ranges;
- one write/verification run;
- no automatic retry.

Consumption occurs immediately before the first write command is issued. Once claimed, failure does not make the authorization replayable.

## 14. Source implementation requirements

The next source gate should create a new R9-specific executor rather than modify or invoke the historical R4 executor in place.

Recommended source target:

```text
tools/execution_packages/n3w/scan_first_pairing/r10_board_d_r9_dual_slot_normalization_write/executor.py
tests/execution_packages/n3w/scan_first_pairing/r10_board_d_r9_dual_slot_normalization_write/test_executor.py
.github/workflows/n3w-r10-board-d-r9-dual-slot-normalization-write-ci.yml
```

Minimum focused tests:
1. exact R9 artifact/member binding;
2. deterministic normalized slot derivation;
3. exact normalized-slot SHA;
4. exact four write segments;
5. exact erase ranges;
6. protected partition/PHY/NVS non-overlap;
7. no factory image direct write;
8. no raw flash_args;
9. no erase-flash/erase-region;
10. exact Board D identity freeze;
11. wrong target rejection;
12. stale/wrong partition rejection;
13. PHY disposition guard;
14. complete fresh backup requirement for all touched ranges;
15. NVS backup/continuity requirement;
16. stale preclaim rejection;
17. one-shot authorization claim;
18. complete bootloader erase-span readback;
19. complete app0 readback;
20. complete app1 readback;
21. app-slot tail FF proof;
22. partition/PHY/NVS continuity;
23. postwrite Board D identity continuity;
24. failure before claim leaves authorization unconsumed;
25. failure after claim forbids replay;
26. rollback verifies all restored touched ranges;
27. wrong confirmation label rejected before mutation.

## 15. Design result

```text
CURRENT_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_BOARD_D_R9_DUAL_SLOT_NORMALIZATION_ROUTE_DESIGN_20261028_01

REAL_PREFLIGHT_STOP_ACCEPTED=true
BOARD_D_HARDWARE_FAILURE_PROVEN=false
DIRECT_FACTORY_ROUTE=BLOCKED_SUPERSEDED
R9_DUAL_SLOT_ROUTE_DESIGNED=true
R9_NORMALIZED_SLOT_SHA256=6e777334cd8dec12523ec5e2daa6ce2909a4d581531218b0d9cec26803f68079

BOARD_ACCESS=false
T1_ACCESS=false
FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_CONSUMED=false
MERGE=false

CURRENT_GATE_RESULT=CLOSED_PASS_DESIGN_ONLY
```

Next one gate:

```text
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_BOARD_D_R9_DUAL_SLOT_NORMALIZATION_WRITE_EXECUTOR_SOURCE_REPAIR_20261028_01
```

That next gate is source/tests/CI only. It does not authorize a Board D write. A new explicit one-shot physical write authorization is required only after the successor executor closes source review and exact CI.
