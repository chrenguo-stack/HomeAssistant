# N3W KF-089 Board B ID08 normal boot with fixed USB re-enumeration observer authorization — 2026-09-11

User explicitly authorized one bounded normal-boot observation gate after the USB re-enumeration observer timeout defect was repaired and host-only tests passed.

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_NORMAL_BOOT_WITH_FIXED_REENUM_OBSERVER_20260911_08
AUTHORIZATION_GRANTED=true
REPLAY_PERMITTED=false
TARGET_ROLE=BOARD_B
PURPOSE=NORMAL_BOOT_AND_SCHEMA_V5_OBSERVATION
```

Authorized actions only:

1. Start the repaired USB re-enumeration observer before boot.
2. Confirm the observer is ready.
3. Perform exactly one normal product reset/boot of Board B.
4. Follow USB Serial/JTAG disappearance/re-enumeration using stable USB metadata and bounded timeouts.
5. Observe for a maximum of 60 seconds.
6. Classify boot/product/N3-W/Schema-v5 evidence and stop.

Explicitly forbidden:

```text
FLASH_WRITE=false
OTADATA_WRITE=false
APP0_WRITE=false
FIRMWARE_REFLASH=false
NVS_MUTATION=false
ROLLBACK=false
SECOND_BOOT=false
AUTO_RETRY=false
BOARD_A_ACCESS=false
T1_MUTATION=false
```

The authorization is consumed when the one normal reset/boot is issued. Any ambiguity or observer failure after that point must STOP without a second reset or retry.
