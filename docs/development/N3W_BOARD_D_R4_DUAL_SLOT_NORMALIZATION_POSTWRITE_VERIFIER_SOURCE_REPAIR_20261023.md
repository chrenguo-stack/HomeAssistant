# N3W Board D R4 dual-slot normalization postwrite verifier source repair

## 1. Task

`N3W_BOARD_D_R4_DUAL_SLOT_NORMALIZATION_POSTWRITE_VERIFIER_SOURCE_REPAIR_20261023_01`

Source-only repair after the first authorized Board D R4 dual-slot normalization write.

## 2. Scope

```text
REPOSITORY_MUTATION=true
BOARD_ACCESS=false
FLASH_WRITE=false
NVS_WRITE=false
LIVE_MUTATION=false
MERGE=false
```

The production write route remains unchanged:

```text
0x000000 bootloader.bin
0x009000 ota_data_initial.bin
0x010000 normalized_slot.bin
0x3D0000 normalized_slot.bin
```

Partition table, phy_init and NVS remain protected and are not write targets.

## 3. Physical evidence that triggered this repair

The authorized live write consumed its one-shot preflight and the `write-flash` command returned success. The first postwrite bootloader readback then failed with esptool return code 2.

Read-only recovery proved:

```text
R4_BOOTLOADER=PASS
R4_PARTITION_TABLE=PASS
R4_OTADATA=PASS
R4_APP0_FULL_SLOT=PASS
R4_APP1_FULL_SLOT=PASS
OLD_APPLICATION_CODE_REMAINS=false
PHY_INIT_PRESERVED=PASS
```

The postwrite NVS value was independently read through both the already-running flasher stub and ROM loader with explicit 8 MB flash size:

```text
POSTWRITE_NVS_SHA256=a61948eaf640aa878d245ef9c95a6529f28a1b2d876618e187419309e89d21a6
STUB_ROM_POSTWRITE_NVS_CROSSCHECK=PASS
NVS_WRITE_OVERRUN_EVIDENCE=false
```

The earlier preflight NVS value cannot be treated as a reliable byte-for-byte baseline because the old ROM `--no-stub read-flash` path did not explicitly bind the 8 MB flash size. Exact prewrite NVS continuity for that already-completed live write therefore remains unprovable.

No raw ROM identity is recorded in this document. The frozen public-safe Board D identity remains:

```text
HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
```

## 4. Root causes

### B1 — postwrite loader-state discontinuity

The write command leaves the target in the flasher stub, but the old verifier immediately attempted `--no-stub --before no-reset read-flash`. The real board remained in the stub and the ROM-only readback failed.

Repair:

- write command now explicitly uses `--after no-reset-stub`;
- postwrite readback stays in the running stub with `--before no-reset-no-sync --after no-reset-stub`;
- postwrite ROM identity is observed only after full flash readback, using a deliberate `default-reset` back into ROM.

### B2 — ROM read-flash did not bind the known 8 MB flash size

The old preflight/fresh-probe ROM path used `--no-stub read-flash` without an explicit flash size.

Repair:

- all ROM/no-stub flash reads now include `read-flash --flash-size 8MB`;
- stub postwrite reads do not depend on ROM flash-size configuration.

### B3 — fresh prewrite protected-region evidence was not durable

The executor freshly probed phy_init and NVS immediately before claim, but those values existed only in memory. If any postwrite step failed, the final result JSON was never created and the fresh prewrite baseline was lost.

Repair:

- claim now persists the fresh prewrite board snapshot before any write;
- the claimed evidence journals `write_flash_returned_success` immediately after the write command returns;
- successful postwrite-integrity and postwrite-identity phases are also persisted;
- a readback failure after a successful write therefore leaves durable evidence that distinguishes write completion from verifier failure.

## 5. Schema boundary

The repaired executor bumps both evidence schemas:

```text
PREFLIGHT_SCHEMA=n3w.board-d.r4-dual-slot-normalization-write-preflight/2
WRITE_SCHEMA=n3w.board-d.r4-dual-slot-normalization-write/2
```

Old /1 preflight evidence is not accepted by the repaired executor.

The one-shot confirmation label is unchanged; user authorization is still a separate live gate and cannot be inferred from source state.

## 6. Test requirements

Focused tests must prove at minimum:

- exact dual-slot write offsets and no protected-region write;
- write command ends in `no-reset-stub`;
- ROM read path uses `--no-stub` plus explicit `--flash-size 8MB`;
- stub read path uses `no-reset-no-sync` / `no-reset-stub` and no `--no-stub`;
- all seven postwrite regions use the stub path;
- fresh phy_init/NVS baselines are persisted in claimed evidence before write;
- write success is persisted before postwrite readback starts;
- simulated readback failure leaves write-success state durable and does not produce a false PASS output;
- postwrite ROM identity deliberately returns to ROM using `default-reset`;
- replay remains forbidden after claim.

## 7. Physical boundary

This repair does not authorize another Board D write.

```text
BOARD_ACCESS=false
FLASH_WRITE=false
WRITE_REPLAY_REQUIRED=false
WRITE_REPLAY_ALLOWED=false
```

The already-written Board D must not be reflashed merely to repair the verifier.
