# N3W KF-089 ID16 Board A-only Schema-v5 recovery

## Goal

Close the current first-unproven stage `A_COMPACT_RX` without replaying ID11 or re-reading Board B. ID16 reuses the exact private Board B NVS image captured during ID15, verifies its SHA256, decodes it host-only with the corrected `--nvs-image` parser path, and then performs one read-only Board A recovery.

## Frozen predecessor evidence

```text
ID15_AUTHORIZATION_CONSUMED=true
ID15_REPLAY_PERMITTED=false
BOARD_B_READ_MAC=PASS
BOARD_B_NVS_READ=PASS
BOARD_B_NVS_SHA256=dce0587cd47676de068c3e23b77cb8df05b11d6acf55799583f54e2d2340b422
BOARD_B_SCHEMA_VERSION=5
BOARD_B_PATH_STATE=2
BOARD_B_RELAY_ACTIVE_COUNT=1
BOARD_B_RELAY_TELEMETRY_ATTEMPTS=44
BOARD_B_RELAY_TELEMETRY_SUCCESS=44
BOARD_B_UNICAST_COMPLETION_COUNT=44
BOARD_B_UNICAST_COMPLETION_SUCCESS=41
BOARD_B_UNICAST_COMPLETION_FAILURE=3
BOARD_B_UNICAST_TX_COMPLETION=PROVEN
NEXT_UNPROVEN_STAGE=A_COMPACT_RX
```

## Physical scope

Only Board A may be physically accessed. Board B must not be connected, opened, read, reset, or otherwise touched by the executor. Its ID15 private NVS file is host-only input.

After a fresh explicit ID16 authorization, Board A must begin fully unpowered with non-USB power removed. Hold BOOT/GPIO9 low before applying USB power, keep GPIO9 low through power-on/reset and enumeration, and release BOOT only after enumeration. GPIO8 is expected high by board design. The intended state is ROM Download Boot.

After preparation: no RESET, no power-cycle, no disconnect/reconnect, no retry. Any deviation or suspected application boot is a STOP and the same physical authorization is not replayed.

## Exact Board A operation sequence

1. Host-only exact-head/worktree/parser/esptool checks.
2. Host-only SHA256 + Schema-v5 decode of the frozen ID15 Board B NVS file.
3. Verify Board A serial locator exists without opening it.
4. Claim/consume the physical authorization immediately before the first Board A target command.
5. Board A `read-mac` using ROM loader, `--before no-reset --after no-reset --no-stub`.
6. Require exactly one canonical `BASE MAC:` and suffix `F3:50`.
7. One Board A read-only NVS capture at `0x790000`, size `0x70000`, Flash size `8MB`.
8. Offline parser decode using `--nvs-image`.
9. Require Schema v5 and the Board A compact receive/forward counter set.
10. Persist closure + evidence manifest and return to the high-level model for counter adjudication.

## Required Board A counters

```text
schema_version
boot_session
snapshot_uptime_ms
path_state
compact_rx_count
compact_state_reject_count
compact_child_binding_failure
compact_decode_success
compact_decode_failure
compact_wrap_failure
compact_forward_attempts
compact_forward_submit_success
compact_forward_submit_failure
```

## Forbidden

```text
BOARD_B_PHYSICAL_ACCESS=false
SECOND_RF_CAPTURE=false
RF_EXECUTION=false
T1_ACCESS=false
T1_MUTATION=false
APPLICATION_BOOT=false
RESET_RETRY=false
AUTO_RETRY=false
FLASH_WRITE=false
NVS_WRITE=false
OTADATA_WRITE=false
PAIRING_CHANGE=false
FIRMWARE_REFLASH=false
```

## Result interpretation

The executor does not make the product-level KF-089 verdict. A successful package returns both the frozen Board B selected counters and the freshly recovered Board A selected counters to `HIGH_LEVEL_MODEL_SCHEMA_V5_COUNTER_ADJUDICATION`.

The high-level adjudication starts with:

```text
compact_rx_count == 0
  -> first unproven stage remains between B unicast completion and A compact RX

compact_rx_count > 0 && compact_decode_success == 0
  -> A received compact traffic but decode was not proven successful

compact_decode_success > 0 && compact_forward_attempts == 0
  -> failure is after decode and before forward attempt

compact_forward_attempts > 0 && compact_forward_submit_success == 0
  -> A entered MQTT relay forward but submission failed

compact_forward_submit_success > 0
  -> A-side relay forwarding is proven; correlate with already-frozen T1 ingress evidence
```
