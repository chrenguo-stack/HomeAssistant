# N3W KF-089 Board B ID04 read-only otadata state recovery authorization — 2026-09-11

User explicitly authorized this one-time physical read-only gate after ID03 reached an unknown persistent otadata state.

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_OTADATA_READONLY_STATE_RECOVERY_20260911_04
AUTHORIZATION_GRANTED=true
REPLAY_PERMITTED=false
TARGET_ROLE=BOARD_B
PURPOSE=READ_ONLY_OTADATA_STATE_CLASSIFICATION
```

Authorized actions only:

1. Establish one bounded read-only connection to Board B without any flash write.
2. Freshly confirm Board B hardware identity against the existing private trusted identity.
3. Read exactly 0x2000 bytes from otadata offset 0x9000.
4. Compare the readback against the saved ID03 pre-image and the host-computed expected post-image.
5. Classify the result as PRECHANGE_EXACT, EXPECTED_POSTCHANGE_EXACT, PARTIAL_OR_OTHER, or UNKNOWN.
6. Stop immediately after classification.

Explicitly forbidden:

```text
FLASH_WRITE=false
OTADATA_WRITE=false
APP0_WRITE=false
ROLLBACK=false
NORMAL_BOOT=false
REBOOT_FOR_PRODUCT_START=false
SECOND_MUTATION=false
AUTO_RETRY=false
BOARD_A_ACCESS=false
T1_MUTATION=false
```

Important boundary:

- This authorization does not implicitly authorize a host-initiated reset, DTR/RTS boot-mode transition, power-cycle, or product boot. If a read-only connection cannot be established without such an additional physical state transition, stop and report that condition rather than expanding scope.
- The authorization is consumed at the first software open/connection to Board B under this gate.
- No result of this gate authorizes a subsequent write or boot automatically.
