# N3-W PR #425 Physical Validation and Probe Blackout Alignment — 2026-09-18

Status: `CURRENT_PROGRESS_ALIGNMENT`

This document aligns the current engineering conversation with GitHub after the exact PR #425 Board B artifact deployment, fresh battery Direct baseline, and same-boot Direct -> Relay physical validation.

Fresh repository/runtime/physical evidence takes precedence if later evidence proves drift.

## Authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
ALIGNMENT_BASE_MAIN=f6b9f3d60078998cd543d4e0482f5ae30f6d0dc7

FROZEN_PRODUCT_SOURCE_HEAD=096528fbf61948d6c69197f1c8994ce8e7d672f4
FROZEN_PRODUCT_SOURCE_TREE=6cfa25f5168fc720590f186871c038e3d4a5307f

PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

Repository `main` may advance because of documentation-only alignment merges. That must not redefine the frozen product source actually deployed to Board B.

## PR #425 exact artifact

PR #425:

- https://github.com/chrenguo-stack/HomeAssistant/pull/425
- title: `Fix N3-W failback commit ordering and Relay channel fixation`

Artifact build:

```text
ARTIFACT_RUN_ID=35294123841
ARTIFACT_ID=10528055066
ARTIFACT_NAME=n3w-pr425-boardb-exact-main
ESPHOME_VERSION=2026.4.3
```

Write files:

```text
firmware.bin
SIZE=1128720
SHA256=bf3af5490745f1279a4e90d57a8e96b46525ae8debaf6f806ed2ae72180836c0

ota_data_initial.bin
SIZE=8192
SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

The physical write was limited to application + otadata. Bootloader, partition table, product NVS, and full-chip erase were not performed.

## Board B deployment closure

Fresh target identity was recovered by the write transaction itself and matched the intended ESP32-C6 target.

```text
BOARD_B_PR425_DEPLOYMENT=PASS
APPLICATION_WRITE=PASS
OTADATA_WRITE=PASS
APPLICATION_HASH_VERIFY=PASS
OTADATA_HASH_VERIFY=PASS
AUTHORIZED_WRITE_CONSUMED=true
REPLAY_PERMITTED=false
```

No raw board identity values are stored in this public-safe alignment.

## Post-flash Direct baseline

After the PR #425 deployment, Manager accepted continuous Direct telemetry from Board B while Manager remained stable:

```text
BOARD_B_PR425_POSTFLASH_DIRECT_BASELINE=PASS
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
DIRECT_TELEMETRY_CONTINUOUS=true
```

Board A also remained continuously Direct-capable during the observed window.

## Battery Direct baseline

USB was then removed and Board B was deliberately power-cycled onto battery. This reboot is outside the later same-boot transition interval and is expected.

After battery startup:

```text
BOARD_B_BATTERY_DIRECT_BASELINE=PASS
NEW_BATTERY_BOOT_SESSION=true
DIRECT_TELEMETRY_CONTINUOUS=true
CADENCE_APPROX=5s
MANAGER_RESTART_COUNT=0
```

The battery boot established the anchor for the subsequent same-boot Direct -> Relay validation.

## Same-boot Direct -> Relay physical result

Board B was moved, without another power cycle, from Direct Wi-Fi coverage to the prior Relay test location. Board A remained stationary and Direct.

Observed Manager evidence:

```text
SAME_BOOT_DIRECT_TO_RELAY=PASS
FIRST_RELAY_GATEWAY=BOARD_A
UNCOMMANDED_REBOOT=false
BOARD_A_RELAY_GATEWAY_STABLE=true
MANAGER_RESTART_COUNT=0

INITIAL_MANAGER_VISIBLE_GAP_MS=30034
INITIAL_MISSING_SEQUENCE_COUNT=5
```

This is a large improvement over the earlier post-PR423 physical result of approximately 110.061 s Manager-visible Direct -> Relay blackout.

The new run therefore proves:

- same-boot Direct -> Relay functional transition;
- authenticated Relay delivery through Board A;
- Manager acceptance of Relay telemetry;
- no watchdog reboot during the transition;
- materially shorter initial Manager-visible blackout.

However, this run did not capture the low-level `n3w_u` / channel diagnostic fields used in the prior mismatch forensic. Therefore it must **not** be reported as proof that historical `ESP_ERR_ESPNOW_CHAN` can never recur.

## Newly proven steady-state defect: periodic Direct-probe blackout

After Relay became active, the Manager-visible Relay sequence repeatedly showed the same pattern:

```text
~60 s accepted Relay telemetry
-> ~15 s telemetry suppression
-> Relay resumes
-> repeat
```

At the current approximately 5 s telemetry cadence, each probe window drops approximately three business telemetry samples. The Manager-visible gap between the last accepted sample before a probe and the first accepted sample after recovery is approximately 20 s because of sample cadence.

The repeated physical pattern matched the exact deployed source constants:

```text
kRecoveryProbeIntervalMs=60000
kRecoveryProbeWindowMs=15000
kRecoveryProbeMs=2000
```

and the current telemetry entrypoint rejects sends while:

```text
radio_ownership_ == RadioOwnership::DIRECT_PROBE
```

Source path:

`firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp`

Therefore the periodic blackout is not classified as random RF loss or Manager instability. It is a product behavior caused by the current Direct-recovery probe design.

## New known failure

```text
KF096_DOMAIN=PRODUCT
KF096_STATUS=OPEN
KF096_NAME=N3-W Relay Direct-recovery probe periodic telemetry blackout
```

Root cause is source-confirmed and physical-timing-confirmed:

- Relay ownership is intentionally released for bounded Direct recovery probing.
- `DIRECT_PROBE` can last up to 15 s.
- business telemetry is rejected during `DIRECT_PROBE`.
- failed Direct probe restores Relay and schedules the next probe about 60 s later.

The repair must not be treated as a simple timeout tweak without architecture review. Direct recovery discovery speed and Relay telemetry continuity are separate product requirements.

## Current acceptance matrix

```text
KF092_STATUS=CLOSED_PASS

PR423_TASK_WDT_REPAIR_PHYSICAL_VALIDATION=PASS
PR425_BOARD_B_DEPLOYMENT=PASS
PR425_POSTFLASH_DIRECT_BASELINE=PASS
PR425_BATTERY_DIRECT_BASELINE=PASS

PR425_SAME_BOOT_DIRECT_TO_RELAY_FUNCTIONAL_RESULT=PASS
PR425_INITIAL_MANAGER_VISIBLE_GAP_MS=30034

PR425_RELAY_STEADY_STATE_CONTINUITY=FAIL
KF096_PERIODIC_DIRECT_PROBE_BLACKOUT=PROVEN

PR425_RELAY_TO_DIRECT_FAILBACK_VALIDATION=NOT_EXECUTED
OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED
```

KF-094 remains open conservatively because the post-PR425 run did not include the low-level channel/error diagnostic oracle required to prove the previously observed mismatch/error class absent. KF-095 remains guarded by source/CI and partial physical evidence, but full Relay -> Direct failback remains unexecuted.

## Current physical boundary

The latest authorized physical window ended with Board B at the Relay test location and Board A unchanged.

```text
BOARD_A_MUTATION=false
BOARD_B_FLASH_AFTER_PR425_DEPLOYMENT=false
SERIAL_OPEN=false
T1_MUTATION=false
BROKER_MANAGER_DYNSEC_MUTATION=false
```

That is the last observed state, not a perpetual live-state assertion. Fresh physical state must be re-established before any later board operation.

## Next ONE gate

```text
NEXT_ONE_GATE=N3W_PR425_RELAY_DIRECT_PROBE_TELEMETRY_BLACKOUT_SOURCE_REPAIR_20260918_01

BOARD_ACCESS_REQUIRED=false
BOARD_MUTATION=false
T1_MUTATION=false
SOURCE_REVIEW_REQUIRED=true
HOST_TEST_REQUIRED=true
```

First objective: redesign Direct recovery probing so recovery discovery does not periodically discard Relay business telemetry. Candidate approaches must be compared against single-radio constraints, failback latency, buffering semantics, and state-machine safety before any new physical mutation.

## Public/private evidence boundary

Public GitHub may store source, tests, artifact hashes, sanitized timing/acceptance results, and architecture decisions. Do not commit raw credentials, setup secrets, private keys, raw NVS, private host addresses, raw Manager/Broker logs, or raw board identity material.
