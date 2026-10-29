# N3-W R10 Board D physical-acceptance write executor source repair — 2026-10-29

## Scope

```text
TASK=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_BOARD_D_PHYSICAL_ACCEPTANCE_WRITE_EXECUTOR_SOURCE_REPAIR_20261029_01

PRODUCT_SOURCE_HEAD=44d3320877a0a47c3dd728182fae2f209bffbc0f
ACCEPTANCE_SOURCE_HEAD=faf07839fcef221f9defb296eadcc7c090e12d4e
ACCEPTANCE_SOURCE_TREE=dc26f11617b721da316e7815b5330b8d8c1f3474

ARTIFACT_RUN_ID=40798244418
ARTIFACT_ID=12864962159
ARTIFACT_NAME=n3w-r10-physical-acceptance-faf07839
ARTIFACT_OUTER_SHA256=b57a5af10c23344e8e03250857455898eb60640e3e18c62022af9c2b9ab7f6da
ARTIFACT_INNER_SHA256=91b3e47b16025ec9fdf73500e463ecc0db4121ea0dc9dcc12325e88e7e7c347b
ARTIFACT_MANIFEST_SHA256=1aa0da0be83d461d92274fef0f37420032a05d7b3e25803ad236e3bb6883ef44

BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5

BOARD_ACCESS=false
BOARD_WRITE=false
NVS_WRITE=false
T1_ACCESS=false
T1_MUTATION=false
MERGE=false
```

This gate prepares source only. It does not consume physical authorization.

## Selected physical route

The successor R10 physical-acceptance image is explicitly non-production and differs from the closed product source by exactly one target substitution:

```text
battery_low_threshold: "-1.00"
```

The exact write route is intentionally narrower than the previous R9 normalization route:

```text
0x009000  all-FF OTA data
0x010000  normalized acceptance app0, full 0x3C0000 slot
0x3D0000  same normalized acceptance app1, full 0x3C0000 slot
```

The normalized acceptance slot is:

```text
SIZE=0x3C0000
SHA256=9d3b7b9d6b277e06cb6eb7f3155e9c777025b0d5cdb6e40feec47d46435eafbd
```

The executor does **not** write:

- bootloader;
- partition table;
- phy_init;
- NVS;
- factory image;
- raw flash_args;
- full-flash erase;
- explicit erase-region.

## Fresh Board D baseline requirements

Before the write authorization is claimed, the executor must:

1. prove exactly one selected `/dev/cu.usbmodem*` target;
2. prove ESP32-C6, 8 MB flash, Secure Boot disabled and Flash Encryption disabled;
3. match the frozen Board D hardware identity;
4. match the current R9 bootloader erase-span SHA-256:
   `e88f39529dd195f7f792c4be45d435c0c205c64e5147cf31be125d9344d600ae`;
5. match the frozen partition table;
6. prove phy_init remains all-FF;
7. capture fresh backups of OTA data, app0 and app1;
8. require both current app slots to still equal the previous R9 normalized slot:
   `6e777334cd8dec12523ec5e2daa6ce2909a4d581531218b0d9cec26803f68079`;
9. capture protected snapshots of bootloader span, partition sector, phy_init and NVS;
10. validate every backup before claiming the write authorization.

Any mismatch stops before authorization consumption and before flash write.

## One-shot authorization

The write confirmation token is new and does not reuse any previous physical authorization:

```text
N3W_R10_BOARD_D_PHYSICAL_ACCEPTANCE_WRITE_AUTHORIZED
```

After fresh backup validation, the executor atomically claims the preflight and marks:

```text
authorization_claimed=true
authorization_consumed=true
replay_permitted=false
```

The authorization is consumed before the first write command.

## Post-write acceptance

The executor reads back and requires exact continuity for:

- bootloader erase span: unchanged from fresh prewrite;
- OTA data: exact all-FF acceptance artifact member;
- app0 full slot: exact normalized acceptance SHA-256;
- app1 full slot: exact normalized acceptance SHA-256;
- partition sector: unchanged;
- phy_init: unchanged;
- NVS: unchanged;
- Board D hardware identity: unchanged.

Both app-slot tails after `firmware.bin` must be all-FF, proving no old application bytes remain.

## Rollback

If write or post-write validation fails after authorization claim, rollback restores only the three touched fresh backup ranges:

- OTA data;
- app0;
- app1.

It then re-reads all touched and protected ranges and Board D identity. Bootloader is never part of the write or rollback command.

A rollback PASS does not make the failed physical attempt replayable.

## Physical boundary

This source gate does not authorize or perform any Board D access. A later exact physical gate must separately authorize:

1. read-only preflight;
2. one write attempt using this route;
3. no automatic retry.

After a successful write the board should remain in the flasher stub. Normal application boot and the real phone first-registration attempt remain a separate successor physical gate.
