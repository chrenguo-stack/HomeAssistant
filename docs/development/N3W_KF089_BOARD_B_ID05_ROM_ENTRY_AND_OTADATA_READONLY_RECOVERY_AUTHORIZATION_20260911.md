# N3W KF-089 Board B ID05 ROM-entry + otadata read-only recovery authorization — 2026-09-11

User explicitly authorized this one-time bounded physical gate after ID04 could open the serial port but could not establish a ROM connection.

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_ROM_ENTRY_AND_OTADATA_READONLY_RECOVERY_20260911_05
AUTHORIZATION_GRANTED=true
REPLAY_PERMITTED=false
TARGET_ROLE=BOARD_B
PURPOSE=CONTROLLED_ROM_ENTRY_PLUS_READ_ONLY_OTADATA_STATE_CLASSIFICATION
```

Authorized actions only:

1. Perform one controlled physical state transition whose sole purpose is to place Board B into ESP32-C6 ROM download mode.
2. Establish one bounded ROM connection.
3. Freshly confirm Board B hardware identity against the existing private trusted identity.
4. Read exactly 0x2000 bytes from otadata offset 0x9000.
5. Compare the readback byte-for-byte against the saved ID03 pre-image and the host-computed expected post-image.
6. Classify the result as PRECHANGE_EXACT, EXPECTED_POSTCHANGE_EXACT, PARTIAL_OR_OTHER, or UNKNOWN.
7. Stop immediately after classification.

Explicitly forbidden:

```text
FLASH_WRITE=false
OTADATA_WRITE=false
APP0_WRITE=false
SECOND_MUTATION=false
ROLLBACK=false
NORMAL_PRODUCT_BOOT=false
AUTO_RETRY=false
BOARD_A_ACCESS=false
T1_MUTATION=false
```

Safety boundary:

- The ROM-entry transition is authorized only to enable this read-only inspection; it must not be used to boot the product firmware.
- After ROM connection is established, no additional reset/reboot/power-cycle is authorized inside this gate.
- The authorization is consumed at the first deliberate ROM-entry/board-open action under ID05.
- If ROM entry or identity verification fails, stop. Do not retry automatically.
- No result of this gate authorizes a later write, rollback, or product boot automatically.
