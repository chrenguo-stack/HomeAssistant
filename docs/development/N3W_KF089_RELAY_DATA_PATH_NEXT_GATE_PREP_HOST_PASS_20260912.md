# N3W KF-089 relay data path next-gate host-only PASS — 2026-09-12

## Result

```text
EXACT_SOURCE_REBOUND=PASS
CURRENT_FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX

BOARD_B_REQUIRED_COUNTERS=relay_telemetry_attempts;unicast_completion_count;unicast_completion_success;unicast_completion_failure
BOARD_A_REQUIRED_COUNTERS=compact_rx_count;compact_decode_success;compact_decode_failure;compact_forward_attempts;compact_forward_submit_success;compact_forward_submit_failure;compact_state_reject_count;compact_child_binding_failure;compact_wrap_failure

FLASH_REQUIRED=false
NVS_MUTATION_REQUIRED=false
PAIRING_CHANGE_REQUIRED=false
READY_FOR_NEXT_PHYSICAL_GATE=true
RESULT=PASS
STOP_REASON=NONE
```

## Physical constraint carried forward

The established selective-RF test geometry remains the authoritative way to put Board B outside Wi-Fi coverage while Board A remains Direct. The Mac does not need to remain at Board B's out-of-coverage location. Schema-v5 diagnostics are persisted to NVS and can be read after the bounded test window using the previously validated default flasher stub, while T1/Broker evidence is observed read-only during the exact primary window.

## Expected pass signature

For N relay attempts during the exact test window:

- Board B: `relay_telemetry_attempts += N`, `unicast_completion_count += N`, `unicast_completion_success += N`, `unicast_completion_failure += 0`.
- Board A: `compact_rx_count += N`, `compact_decode_success += N`, `compact_forward_attempts += N`, `compact_forward_submit_success += N`, with decode/submit/reject counters unchanged.

This proves B asynchronous unicast completion plus A compact receive/decode/local-forward-submit. It does not, by itself, prove T1 final receipt; T1/Broker/Manager evidence remains a separate downstream boundary.

## Next host-only preclaim

Before claiming one physical authorization, verify current Board A and Board B Direct baselines from T1, T1/Broker/Manager observer readiness, the qualified selective-RF geometry, private evidence root, exact 90-second capture timing, and validated default-stub NVS readback commands for both boards. Construct the full operator-checkpoint sequence in advance so one authorization can cover the complete bounded RF capture and durable readback without repeated authorization prompts.
