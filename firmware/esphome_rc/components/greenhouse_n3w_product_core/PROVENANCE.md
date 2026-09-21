# greenhouse_n3w_product_core provenance

Status: SOURCE_FORK_STAGE_B

This component is an independent production successor forked from the merged
PR #437 product source. The frozen PR #437 lab component remains unchanged at
`firmware/esphome_rc/components/greenhouse_n3w_core`.

## Source authority

- repository main at fork: `8165cc441abd45f4d46f7439fa57edee1470c917`
- merged PR #437 source head: `4270f24a92a87dd5239d781ebba624c2f34b7fc2`
- merged PR #437 source tree: `a2f445bf2ea60ba9994a7a467f6492975d399c4f`
- PR #437 merge commit: `b9acaaad50b17c9cdb51c219330e612c383628f0`

## Pure lab modules intentionally not copied

- `n3w_lab_diagnostics.h/.cpp`
- `n3w_phase4_physical_harness.h/.cpp`
- `n3w_rtc_breadcrumb.h/.cpp`

The successor uses `n3w_product_noop_diagnostics.h` only as a zero-state,
zero-log compatibility surface for instrumentation calls still present in the
frozen product state-machine source. It is not an NVS/logging diagnostic
implementation.

## Stage-B embedded diagnostic prune

The production successor now also removes the ESP-NOW observations that existed
only to support physical-session debugging:

- bounded `ESP-NOW diagnostic receive` logs;
- bounded broadcast-completion diagnostic logs;
- the diagnostic receive/broadcast log counters;
- pre-send current-channel / encrypted-peer-channel readback controlled by
  `observe_context`;
- component-side ESP-NOW diagnostic hooks for receive drops, peer install,
  broadcast/unicast completion, and unicast submit context.

The ESP-NOW business behavior remains present: receive metadata still carries
RSSI/channel to the product runtime, MAC completion ownership remains intact,
pending-unicast accounting remains intact, and synchronous send success/failure
continues to drive the existing product state machine.

## Still outside this stage

This fork does **not** yet:
- integrate F1.0-RC2 sensors or telemetry;
- define the final production firmware target;
- prove the final binary is de-harnessed;
- modify the frozen PR #437 component or Phase-4 physical harness.

Unchanged product files are copied by exact Git blob identity from the source
authority wherever no production adapter or diagnostic-prune change is required.
