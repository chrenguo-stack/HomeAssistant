# N3-W KF-089 Observability Baseline Harness Blocker — 2026-09-07

Status: `PUBLIC_SAFE_CURRENT_BLOCKER`

## Scope

This record archives the public-safe outcome of the first two-board observability refresh/baseline attempt and its successor correlation-recovery attempts. It does not change product source, firmware, T1, Broker, Manager, Home Assistant, provisioning state, credentials or keys.

Stable product/source authority:

```text
PRODUCT_SOURCE_AUTHORITY=483ff1c662dc74d6e12529e27a69819e68160f9e
PRODUCT_SOURCE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
OBSERVABILITY_FIRMWARE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
DIAGNOSTIC_SCHEMA_VERSION=3
```

## Board A partial refresh result

Board A was safely refreshed inactive-slot-first to the new observability image in app1 and exact readback verified:

```text
BOARD_A_INITIAL_SLOT=0
BOARD_A_FIRST_TARGET_SLOT=1
BOARD_A_APP1_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
BOARD_A_FIRST_TARGET_VERIFY=PASS
BOARD_A_BOOT_SELECTION_SWITCHED=PASS
```

The new firmware then booted and produced a healthy local Direct diagnostic baseline on the exact physical ESP32-C6 target:

```text
BOARD_A_RUNTIME_MODE_DIRECT=true
BOARD_A_CURRENT_CHANNEL=11
BOARD_A_DIRECT_CHANNEL_HINT=11
BOARD_A_CHANNEL_11_RUNTIME_BINDING=PASS
BOARD_A_CHANNEL_11_ENVIRONMENT_BINDING=PASS
AP_MUTATION_OBSERVED=false
BOARD_A_DIAG_SCHEMA=3
BOARD_A_SCAN_ATTEMPTS=0
BOARD_A_SCAN_FAILURES=0
BOARD_A_ADVERTISEMENT_ATTEMPTS=35
BOARD_A_ADVERTISEMENT_SUBMIT_SUCCESS=35
BOARD_A_ADVERTISEMENT_SUBMIT_FAILURE=0
BOARD_A_BROADCAST_COMPLETION_COUNT=35
BOARD_A_BROADCAST_COMPLETION_SUCCESS=35
BOARD_A_BROADCAST_COMPLETION_FAILURE=0
```

Channel 11 is in the frozen discovery allowlist `{1,6,11}`. The earlier test-plan assumption that the Direct channel had to remain 1 was therefore retired as an environment-specific stale expectation, not a product failure.

At this boundary Board A app0 had not yet been rewritten to the new image and Board B had not yet been refreshed. Do not infer both slots or both boards already run the observability image.

## Missing T1 correlation was not a product failure

The historical T1 correlation attempt could not recover enough surviving canonical evidence for the already-completed Board A local baseline. The result was therefore frozen as `UNRECOVERED`, not `FAIL`.

A subsequent fresh-correlation attempt stopped before the observation window because the executor had no live T1 observer in its local execution scope.

Exact sanitized classification:

```text
PREVIOUS_EXECUTION_LAST_COMPLETED_PHASE=P0_BOARD_A_PRIVATE_IDENTITY_BINDING
PREVIOUS_EXECUTION_FIRST_UNEXECUTED_PHASE=P1_SERIAL_OBSERVATION
PREVIOUS_STOP_REASON_RAW_CLASS=T1_OBSERVER_UNAVAILABLE
PREVIOUS_STOP_REASON=No live T1 observer; local ports 1883/8883 had no listener and no running T1 container
```

This proves only that no local Mac-side live T1 oracle was available. It does not prove the actual remote T1 host/runtime was unavailable. Existing project guards already require explicit current-runtime/current-endpoint authority and proven SSH/remote Manager observation paths; localhost must not silently substitute for T1.

## Serial-open harness blocker

The only collector located for the attempted live serial observation was a setup-secret handoff capture helper with only best-effort preconfigured DTR/RTS deassertion. It was not proven passive for this ESP32-C6 native USB Serial/JTAG path.

The preclaim then observed:

```text
SAFE_SERIAL_COLLECTOR_FOUND=PARTIAL
SERIAL_OPEN_SUCCEEDED=true
SERIAL_OPEN_TRIGGERED_RESET=true
SERIAL_CLOSE_TRIGGERED_RESET=false
SAFE_SERIAL_OBSERVATION_PRECLAIM=FAIL
```

Therefore opening the serial device with that collector is intrusive on the current hardware/host path and must not be used as a non-mutating runtime oracle until a genuinely passive method is independently proven.

The resulting application reset is classified as a physical-harness event. It does not invalidate the previously proven Board A channel-11/local diagnostic behavior and is not evidence of a product crash.

## Diagnostic NVS contract

The schema-v3 lab firmware intentionally persists sanitized diagnostics to:

```text
namespace=gh_n3w_diag
key=snapshot
```

Therefore future physical contracts must distinguish:

```text
HOST_NVS_MUTATION=false
PRODUCT_NVS_MUTATION=false
LAB_DIAGNOSTIC_NVS_MUTATION=EXPECTED
```

A blanket `NVS_MUTATION=false` is not compatible with normal operation of this lab target.

## Recommended route correction

Do not spend the next physical boundary trying to force a live serial collector to be passive unless live serial becomes strictly necessary.

The lab observability design already contains a durable, boot-session-bound NVS snapshot specifically suitable for post-test evidence recovery. The preferred successor route is therefore:

1. recover the actual remote T1 read-only observer authority rather than probing localhost;
2. observe Board A Direct telemetry on the real T1 for a fresh bounded window without opening serial;
3. after the window, power Board A fully off and enter ROM Download Mode directly without another application boot;
4. read only `gh_n3w_diag/snapshot` with the committed sanitized parser;
5. bind its `boot_session` to the T1 boot identity/session from the same window;
6. use the durable snapshot to prove Direct path, working channel, zero scan activity, advertisement submission and broadcast completion;
7. if PASS, write the still-old Board A app0 while already in controlled ROM mode, preserving product NVS;
8. continue Board B inactive-first refresh using the same serial-free T1 + durable-diagnostic baseline method.

This route avoids an already-observed intrusive serial-open path and uses the observability mechanism added by PR #370 for its intended purpose.

## Current classification

```text
PRODUCT_FAILURE=false
KF089_STARTUP_GATE_REPAIR=PASS
BOARD_A_NEW_APP1_REFRESH=PASS
BOARD_A_LOCAL_DIRECT_DIAGNOSTIC_BASELINE=PASS
BOARD_A_T1_ACCEPTANCE_BINDING=UNRECOVERED
BOARD_A_BOTH_SLOTS_EXACT_MAIN=NOT_YET_PROVEN
BOARD_B_OBSERVABILITY_REFRESH=NOT_EXECUTED
SERIAL_LIVE_OBSERVER=HARNESS_BLOCKED
LOCALHOST_T1_OBSERVER=INVALID_SCOPE
AUTONOMOUS_RELAY_DISCOVERY=NOT_PROVEN
```

## Next safe gate

```text
NEXT_GATE=KF089_REMOTE_T1_AND_DURABLE_DIAG_BASELINE_RECOVERY
```

The successor must first prove the remote T1 read-only observation path without board mutation. Only then should it run a serial-free Board A fresh correlation window and post-window durable diagnostic read.
