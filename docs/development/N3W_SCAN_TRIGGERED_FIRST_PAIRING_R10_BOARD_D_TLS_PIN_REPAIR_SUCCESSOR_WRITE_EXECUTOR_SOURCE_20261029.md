# N3-W R10 Board D TLS-pin repair successor write executor source — 2026-10-29

## Gate

N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_BOARD_D_TLS_PIN_REPAIR_SUCCESSOR_WRITE_EXECUTOR_SOURCE_20261029_01

This gate prepares source only.

BOARD_ACCESS=false
BOARD_WRITE=false
T1_ACCESS=false
T1_MUTATION=false
MERGE_TO_MAIN=false

## Fresh artifact authority

The successor executor is bound to the repaired Board D physical-acceptance artifact:

- product source: ff750b3801a282af1667b5fa63481e2333e301b3
- acceptance source: f99342f9639fa234d85c509ddf6cf41fef91d691
- acceptance tree: 6c53b4ef480f67d984cc9b3c8cfa0886d706dde4
- artifact tooling head: 117e8cfecdf1fa46f26dbf0887bc13c4c2fc6860
- workflow run: 40833980176
- artifact ID: 12879548794
- GitHub outer artifact SHA256: 115e5c3869e6032186bf186b6a3930cb3f16a41e6b25a344b50b7ee90314e2ed
- inner release ZIP SHA256: 4861075a10191b780675bbf72d4bdb75e7076afefec3883bd5417c3a0def112a
- manifest SHA256: df09e7a84ec0b381c6c9a7ce656bbabfa6662d81deb660efd05b12e8b2429299
- firmware.bin SHA256: 81617c4c89dd6bc2faa33cda40fc1ba05b5fb7ec4905eff11d5a8a9ab4bf7c6d

The old artifact ID 12864962159, old run 40798244418, old outer SHA and old one-shot authorization are historical evidence only and cannot be replayed.

## Current Board D predecessor state

Board D was already written successfully with the previous R10 physical-acceptance image.

Therefore the successor preflight must not require the older R9 application slot SHA.

The expected current predecessor application slot is:

9d3b7b9d6b277e06cb6eb7f3155e9c777025b0d5cdb6e40feec47d46435eafbd

The older R9 slot SHA:

6e777334cd8dec12523ec5e2daa6ce2909a4d581531218b0d9cec26803f68079

is not accepted by the successor executor.

The protected bootloader baseline remains the previously frozen erase-span SHA because the prior R10 write did not write the bootloader.

## New normalized target slot

The new firmware.bin is 1466720 bytes.

The executor pads it with 0xFF to the exact OTA slot size 0x3C0000 / 3932160 bytes.

- padding size: 2465440 bytes
- padding SHA256: 4a24f29180c0749847a8783808807cc6894d9f7d0e72defb8c6ab3600b538e5d
- normalized target slot SHA256: 5901a6ff149ac9da8041057617df989526b41018a44a1647f8175254fda044fc

Both app0 and app1 must receive this same exact normalized image.

## Write scope

The selected route remains intentionally narrow:

- 0x009000: artifact OTA data
- 0x010000: normalized app0
- 0x3D0000: normalized app1

The executor never writes:

- bootloader
- partition table
- phy_init
- NVS
- factory image directly
- raw flash_args
- full-flash erase
- erase-region

Before authorization claim it must prove Board D identity, ESP32-C6, 8 MB flash, security state, current predecessor slots, partition continuity and PHY disposition, then capture and validate fresh backups.

## One-shot authorization

The old write confirmation is not accepted.

The successor confirmation is:

N3W_R10_BOARD_D_TLS_PIN_REPAIR_PHYSICAL_ACCEPTANCE_WRITE_AUTHORIZED

Preflight uses a new TLS-pin-repair-specific confirmation string.

Authorization is consumed atomically before the first write command and is never replayable.

## Rollback

If write or post-write verification fails after claim, rollback restores only the fresh prewrite copies of:

- OTA data
- app0
- app1

Then it rechecks all touched ranges, protected ranges and Board D identity.

A successful rollback does not restore authorization replayability.

## Physical boundary

This source gate does not authorize Board access.

A later physical gate must separately authorize the read-only preflight and exactly one write attempt. There is no automatic retry.
