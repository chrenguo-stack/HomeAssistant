# N3W KF-089 Board B ID06 normal boot + Schema-v5 observation authorization — 2026-09-11

User explicitly requested execution of the next step after ID05 proved that Board B otadata exactly matches the expected post-change image.

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_NORMAL_BOOT_SCHEMA_V5_OBSERVATION_20260911_06
AUTHORIZATION_GRANTED=true
REPLAY_PERMITTED=false
TARGET_ROLE=BOARD_B
PURPOSE=SINGLE_NORMAL_PRODUCT_BOOT_AND_BOUNDED_SCHEMA_V5_OBSERVATION
```

Frozen prior state:

```text
BOARD_B_IDENTITY=PASS
APP0_BINDING=PASS
PERSISTENT_OTADATA_STATE=EXPECTED_POSTCHANGE_EXACT
TARGET_SLOT_SELECTION_STATE=POSTCHANGE_EXACT
SECOND_OTADATA_MUTATION_REQUIRED=false
ROLLBACK_REQUIRED=false
```

Authorized actions only:

1. Exit ROM-download condition and perform exactly one controlled normal product boot of Board B.
2. Observe the boot/runtime through the existing safe serial/log path for a bounded interval.
3. Determine whether the board reaches the Schema-v5 product runtime and report the strongest directly observed evidence.
4. Stop after bounded observation.

Explicitly forbidden:

```text
FLASH_WRITE=false
OTADATA_WRITE=false
APP0_WRITE=false
SECOND_MUTATION=false
ROLLBACK=false
FIRMWARE_REFLASH=false
PAIRING_OR_KEY_CHANGE=false
BOARD_A_ACCESS=false
T1_MUTATION=false
AUTO_SECOND_BOOT=false
AUTO_RETRY=false
```

Observation must not claim Schema-v5 PASS unless direct runtime evidence supports it. If normal boot does not occur or runtime evidence is incomplete, report FAIL or NOT_PROVEN rather than performing another reset/boot.

The authorization is consumed at the first host-initiated transition that causes Board B to leave ROM download mode for the authorized normal product boot.
