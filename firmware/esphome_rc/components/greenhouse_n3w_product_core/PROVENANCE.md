# greenhouse_n3w_product_core provenance

Status: SOURCE_FORK_STAGE_A

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

## Stage-A scope

This fork does **not** yet:
- remove the limited diagnostic logging/readback embedded in `n3w_espnow_driver.*`;
- integrate F1.0-RC2 sensors or telemetry;
- define the final production firmware target;
- claim binary de-harness proof;
- modify the frozen PR #437 component or Phase-4 physical harness.

Unchanged product files are copied by exact Git blob identity from the source
authority wherever no Stage-A adapter change is required.
