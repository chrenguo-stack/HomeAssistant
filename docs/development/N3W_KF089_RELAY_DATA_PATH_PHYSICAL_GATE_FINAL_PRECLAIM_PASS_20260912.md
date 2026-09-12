# N3W KF-089 relay data-path physical gate final preclaim PASS — 2026-09-12

## Result

```text
SOURCE_AUTHORITY_PASS=true
T1_OBSERVER_READY=true
BOARD_A_DIRECT_CURRENT=true
BOARD_B_DIRECT_CURRENT=true
FRESH_BOOT_COUNTER_RESET_CONTRACT=PASS
A_FRESH_BOOT_BASELINE_SUFFICIENT=true
B_COLD_BOOT_BASELINE_SUFFICIENT=true
SELECTIVE_RF_ZONE_FROZEN=PASS
RF_WINDOW_SECONDS=90
B_POST_WINDOW_FLUSH_SECONDS=6
A_POST_B_OFF_FLUSH_SECONDS=10
DEFAULT_STUB_READBACK_READY=true
BOARD_B_READBACK_COMMAND_READY=true
BOARD_A_READBACK_COMMAND_READY=true
FULL_OPERATOR_SEQUENCE_READY=true
SINGLE_AUTHORIZATION_CAN_COVER_ALL=true
READY_FOR_PHYSICAL_AUTHORIZATION=true
RESULT=PASS
STOP_REASON=NONE
```

## Adjudication

All host-only preparation required for the next bounded A/B relay data-path experiment is complete. The next physical gate may be covered by one non-replayable authorization spanning the already-prepared sequence: Board A fresh normal boot and Direct baseline, Board B cold boot in the frozen selective-RF zone, one 90-second RF capture, bounded diagnostic flush intervals, Board B then Board A shutdown, and read-only Schema-v5 diagnostic NVS readback for both boards using the previously validated default-stub path.

No flash write, NVS write, pairing change, protocol change, retry-policy change, second RF capture, location search, or automatic retry is authorized by this preclaim.
