# N3-W Progress Alignment — 2026-09-17

Status: `CURRENT_PROGRESS_ALIGNMENT`

This document aligns the live engineering conversation with the repository state after PR #416 and the local-development-environment record in PR #417. Fresh exact repository/runtime/physical evidence takes precedence if later evidence proves drift.

## Alignment base

```text
REPOSITORY=chrenguo-stack/HomeAssistant
ALIGNMENT_BASE_MAIN=01389807f801341ca2240bcaf5a58e58ce9b9213
ALIGNMENT_BASE_TREE=f17e1c95714b5ba79361a6f939252023eba55747
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

The fixed SHA above is the exact `main` tip at alignment-branch creation. It is not a permanent claim about future repository tips.

## Repository integration completed in this route

```text
PR411=MERGED
PR411_SCOPE=Relay MAC async delivery feedback into path hysteresis

PR413=MERGED
PR413_SCOPE=Relay MAC delivery feedback + reset diagnostics + physical-harness connectivity reboot disablement

PR414=MERGED
PR414_SCOPE=Direct-to-Relay latency observability

PR415=MERGED
PR415_SCOPE=challenge submit raw-error observability
PR415_MAIN_MERGE=63808f35fa2534388ec2c45e9ce9e9aa7d5d2e64

PR416=MERGED
PR416_HEAD=d718f49fb05125c97c97c7525636da2246668142
PR416_MAIN_MERGE=11aa3ed3c1c727427e3a67f8764772c3a9fc3398
PR416_SCOPE=controlled-channel TX for Relay challenge
PR416_POSTMERGE_GREENHOUSE_MANAGER_CI=PASS

PR417=MERGED
PR417_MAIN_MERGE=01389807f801341ca2240bcaf5a58e58ce9b9213
PR417_SCOPE=redacted local development environment snapshot
```

Historical PR #410 and PR #412 contain superseded stacked/documentation state and are not current source authority. Their historical evidence remains useful provenance, but current authority is the merged `main` lineage plus this alignment/current-state documentation.

## KF-092 closure carried forward

The Relay MAC delivery-feedback defect and the physical-harness connectivity reboot policy were both closed before the current Direct-to-Relay latency investigation.

```text
KF092_SOURCE_REPAIR=PASS
KF092_REBOOT_POLICY_REPAIR=PASS
KF092_REBOOT_POLICY_PHYSICAL_FIX=PASS
KF092_PHYSICAL_CAUSATION_PROVEN=true
KF092_POSTFIX_PHYSICAL_VALIDATION=PASS
KF092_ALIGNED_AB_LONG_DURATION_CONTINUITY=PASS
KF092_STATUS=CLOSED_PASS
```

KF-092 closure must not be relabelled as proof of the current same-session Direct-to-Relay latency acceptance; it started from an established Relay path.

## Current same-boot Direct-to-Relay evidence

A later Board B battery-powered run proved Direct -> Relay in the same boot without a reset, with Board A acting as the Relay gateway.

```text
LAST_DIRECT_TIME=2026-09-16T15:52:41.519+08:00
LAST_DIRECT_SEQ=49
FIRST_RELAY_TIME=2026-09-16T15:54:30.526+08:00
FIRST_RELAY_SEQ=71
SAME_BOOT_DIRECT_TO_RELAY=PASS
UNCOMMANDED_REBOOT_DURING_TRANSITION=false
REBOOT_REQUIRED_FOR_RELAY=false
MANAGER_VISIBLE_GAP_MS=109007
MISSING_SEQUENCE_RANGE=50..70
MISSING_SEQUENCE_COUNT=21
```

This proves the functional same-boot path. It does not close continuity/latency acceptance because the accepted-telemetry blackout remained approximately 109 seconds.

## Latency localization

Current per-boot latency observability localized most of the avoidable delay to Relay Challenge submission after an accepted Relay advertisement:

```text
wifi_down_to_first_relay_tx_ms=102542
direct_fail_first_to_first_relay_tx_ms=100017
first_scan_to_first_accepted_relay_ad_ms=15766
relay_ad_seen_to_successful_challenge_tx_ms=70132
challenge_tx_to_accept_rx_ms=17
accept_rx_to_relay_active_ms=0
relay_active_to_first_relay_tx_ms=4100
```

The same run reported:

```text
challenge_submit_failure_count=3
challenge_submit_first_driver_error=11
challenge_submit_last_driver_error=11
challenge_submit_first_error_raw=12397
challenge_submit_last_error_raw=12397
```

The diagnostic snapshot stores only first/last raw errors. Therefore the supported conclusion is: three Challenge submissions failed; at least the first and last failures were the same raw error.

For ESP-IDF 5.5.4, raw `12397` (`0x306D`) maps to `ESP_ERR_ESPNOW_CHAN`: the current Wi-Fi channel does not match the peer channel. This proves synchronous `esp_now_send()` channel-mismatch rejection for at least the first and last failed Challenge submissions; it is not evidence of over-air packet loss.

## Source defect and repair state

The source-level defect was that the Relay advertisement receive path validated the received channel, then sent the Challenge through the normal broadcast path without a send-time controlled-channel operation. Shared Wi-Fi reconnect/scanning can move the same radio across channels while disconnected/reconnecting, so receive-time channel knowledge alone is insufficient for the later Challenge submission.

PR #416 changes only the Challenge send path to use ESP-IDF controlled-channel TX via `esp_now_switch_channel_tx()`. Relay advertisement remains on the normal broadcast path and Direct/Discovery/Relay policy thresholds remain unchanged.

Validation already completed:

```text
PR416_HOST_SOURCE_TESTS=45/45_PASS
PR416_ESPHOME_VERSION=2026.4.3
PR416_ESP32C6_BUILD_ONLY=PASS
PR416_PR_CI=PASS
PR416_POSTMERGE_CI=PASS
PR416_PHYSICAL_VALIDATION=NOT_YET_RUN
```

The source repair is integrated; physical acceptance of that repair is still pending.

## Pre-deploy review still required

Before a new Board B flash, review the exact ESP-IDF 5.5.4 semantics of the controlled-channel request rather than assuming host compile/CI proves live behavior. The review must settle at least:

- `esp_now_switch_channel_t::op_id` ownership/requirements;
- whether the request/data buffer may be released immediately after `esp_now_switch_channel_tx()` returns;
- whether using the full existing Challenge timeout (`1500 ms`) as `wait_time_ms` is appropriate;
- whether the expected Accept receive path remains valid during/after the controlled-channel TX window.

No new board flash is authorized by this alignment document.

## Current acceptance matrix

```text
DIRECT_BASELINE=PASS
SAME_BOOT_DIRECT_TO_RELAY_FUNCTIONAL_PATH=PASS
REBOOT_DEPENDENCY=false
LATENCY_OBSERVABILITY=PASS
CHALLENGE_CHANNEL_MISMATCH_ROOT_CAUSE=PROVEN_FOR_FIRST_AND_LAST_FAILED_SUBMISSIONS
TELEMETRY_CONTINUITY_ACCEPTANCE=FAIL
CONTROLLED_CHANNEL_TX_SOURCE_INTEGRATION=PASS
CONTROLLED_CHANNEL_TX_PHYSICAL_VALIDATION=PENDING
LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
HOME_ASSISTANT_ENTITY_UPDATE=SEPARATE_OPEN_ITEM
```

The mainline Direct-to-Relay item is therefore not closed merely because the functional transition works: the long blackout must be re-tested with the integrated repair.

## Local development environment authority

PR #417 established the redacted local-development-environment record:

`docs/development/local-environment-records/2026-09-17-macos-x86_64.json`

Current recorded host/tool authority:

```text
PROJECT_VENV=~/.venvs/greenhouse-homeassistant-dev
PYTHON=3.11.9
PYTEST=8.4.2
RUFF=0.15.22
PAHO_MQTT=2.1.0
PIP_CHECK=PASS
ESPHOME=2026.4.3
ESPHOME_DEPLOYMENT=pipx_isolated
ESPHOME_CLI=~/.local/bin/esphome
LOCAL_ENVIRONMENT_STATUS=accepted_for_local_development
```

Use that record as the default environment authority. Re-run the versioned doctor only when the host, virtual environment, or toolchain changes; do not repeatedly rediscover unchanged environment facts during ordinary N3-W gates.

A task-specific Git worktree/branch/HEAD remains a separate fresh-rebind concern and must not be inferred from the environment snapshot.

## Current safety boundary

```text
BOARD_A_MUTATION_DURING_PR415_PR416_PR417_ROUTE=false
BOARD_B_FLASH_AFTER_PR416=false
T1_MUTATION_DURING_PR415_PR416_PR417_ROUTE=false
BROKER_DYNSEC_MUTATION_DURING_PR415_PR416_PR417_ROUTE=false
```

Last-proven board/runtime evidence is historical experiment evidence, not a claim about real-time physical state after the operator leaves the experiment.

## Next one gate

```text
NEXT_ONE_GATE=N3W_CHALLENGE_CONTROLLED_CHANNEL_TX_PREDEPLOY_IDF_SEMANTICS_REVIEW_20260917_01
```

That gate is read-only/source-level. It must complete before any Board B flash or physical validation of PR #416.
