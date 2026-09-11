# N3W KF-089 Board B ID04 read-only state recovery STOP — 2026-09-11

## Result

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_OTADATA_READONLY_STATE_RECOVERY_20260911_04
AUTHORIZATION_CLAIMED=true
BOARD_B_SERIAL_OPENED=true
ROM_CONNECTION_ESTABLISHED=false
BOARD_B_IDENTITY=NOT_PROVEN
IDENTITY_MISMATCH_PROVEN=false
OTADATA_READ=NOT_EXECUTED
FLASH_WRITE=false
NORMAL_BOOT=false
RESULT=STOP
STOP_REASON=esptool 5.2.0 could not connect to ESP32-C6: No serial data received; no retry performed.
```

## Adjudication

The serial device could be opened, but the ESP32-C6 ROM loader did not return synchronization data. Therefore the result must not be interpreted as a Board B identity mismatch; identity was not actually recovered in ID04.

The persistent otadata state remains UNKNOWN. ID04 is consumed and must not be replayed.

## Next safe gate

The next physical gate should be a bounded ROM-entry state transition followed by the same read-only classification:

1. perform exactly one controlled transition into ESP32-C6 ROM download mode, without allowing a normal product boot;
2. fresh-read and verify Board B identity;
3. read exactly 0x2000 bytes at otadata offset 0x9000;
4. compare against the frozen ID03 pre-image and host-computed expected post-image;
5. classify PRECHANGE_EXACT, EXPECTED_POSTCHANGE_EXACT, PARTIAL_OR_OTHER, or UNKNOWN;
6. stop.

No flash write, otadata mutation, rollback, normal boot, Board A access, or T1 mutation is included in this next gate.