# N3-W Current State

Updated: 2026-09-17  
Status: `CURRENT_STATE_AUTHORITY`

This is the concise public-safe authority for the current N3-W state. Fresh exact repository, runtime, and physical evidence takes precedence if later evidence proves drift.

Detailed current alignment:

`docs/development/N3W_PROGRESS_ALIGNMENT_20260917.md`

## Repository / source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
ALIGNMENT_BASE_MAIN=01389807f801341ca2240bcaf5a58e58ce9b9213
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

The fixed SHA above is the exact `main` tip used to create the 2026-09-17 alignment branch, not a permanent claim about future repository tips. Repository `main` must always be queried fresh.

Recent integrated route:

```text
PR411=MERGED   # Relay MAC async delivery feedback into path hysteresis
PR413=MERGED   # delivery feedback + reset diagnostics + physical-harness reboot policy
PR414=MERGED   # Direct-to-Relay latency observability
PR415=MERGED   # Challenge submit raw-error observability
PR416=MERGED   # controlled-channel TX for Relay Challenge
PR417=MERGED   # redacted local development environment snapshot

PR415_MAIN_MERGE=63808f35fa2534388ec2c45e9ce9e9aa7d5d2e64
PR416_HEAD=d718f49fb05125c97c97c7525636da2246668142
PR416_MAIN_MERGE=11aa3ed3c1c727427e3a67f8764772c3a9fc3398
PR417_MAIN_MERGE=01389807f801341ca2240bcaf5a58e58ce9b9213
PR416_POSTMERGE_GREENHOUSE_MANAGER_CI=PASS
```

Historical PR #410/#412 are superseded stacked/documentation vehicles and are not current source authority.

Active architecture authority remains:

`docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

Current product direction remains:

- provisioned runtime startup does not require an existing Wi-Fi association;
- Direct remains preferred;
- when Direct is unavailable, node-local bounded autonomous Relay discovery is allowed;
- official Espressif channel-control mechanisms are preferred over a full custom radio-ownership rewrite unless later evidence requires otherwise.

## Previous accepted Relay baseline

KF-089 Relay end-to-end acceptance remains closed and valid:

```text
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
KF089_END_TO_END_RELAY_TELEMETRY=PROVEN
T1_BROKER_MEDIATED_RELAY_INGRESS=PROVEN
MANAGER_RELAY_ACCEPTANCE=PROVEN
```

Historical closeout authority:

`docs/development/N3W_KF089_RELAY_END_TO_END_CLOSEOUT_20260914.md`

The accepted Manager/Broker/DynSec baseline from that route remains separate from later Board failover work. No later PR #415/#416/#417 step mutated T1, Broker, Manager, DynSec, credentials, or TLS state.

## KF-092 closure

KF-092 repaired the Relay MAC delivery-feedback contract and the physical-harness connectivity reboot policy, then passed physical causal validation and aligned A/B continuity validation.

```text
KF092_SOURCE_REPAIR=PASS
KF092_REBOOT_POLICY_REPAIR=PASS
KF092_REBOOT_POLICY_PHYSICAL_FIX=PASS
KF092_PHYSICAL_CAUSATION_PROVEN=true
KF092_POSTFIX_PHYSICAL_VALIDATION=PASS
KF092_ALIGNED_AB_LONG_DURATION_CONTINUITY=PASS
KF092_STATUS=CLOSED_PASS
```

KF-092 started from an already established Relay path and must not be re-labelled as proof of same-session Direct-to-Relay latency acceptance.

## Current same-boot Direct-to-Relay evidence

A later battery-powered Board B run proved the functional same-boot transition through Board A without an uncommanded reset:

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

This closes the question of whether Relay requires a reboot: it does not. It does **not** close latency/continuity acceptance because the Manager-visible accepted-telemetry blackout remained approximately 109 seconds.

## Current latency/root-cause result

Per-boot observability localized the dominant avoidable delay to Relay Challenge submission after a Relay advertisement had already been accepted:

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

The snapshot stores only first/last raw errors. The supported conclusion is therefore: three Challenge submissions failed; at least the first and last were raw `12397`.

For ESP-IDF 5.5.4, `12397` (`0x306D`) maps to `ESP_ERR_ESPNOW_CHAN`: current Wi-Fi channel does not match the peer channel. This proves synchronous channel-mismatch rejection for at least the first and last failed Challenge submissions; it is not evidence of over-air packet loss.

## Controlled-channel TX repair

Source-level defect:

- Relay advertisement receive validated the received channel;
- Challenge then used the normal broadcast path;
- no send-time controlled-channel operation guaranteed that the radio still matched that channel.

PR #416 changes the Challenge path to use ESP-IDF `esp_now_switch_channel_tx()` while leaving Relay advertisement on the normal broadcast path and leaving Direct/Discovery/Relay thresholds unchanged.

```text
PR416_HOST_SOURCE_TESTS=45/45_PASS
PR416_ESPHOME_VERSION=2026.4.3
PR416_ESP32C6_BUILD_ONLY=PASS
PR416_PR_CI=PASS
PR416_POSTMERGE_CI=PASS
PR416_PHYSICAL_VALIDATION=NOT_YET_RUN
```

Source integration is complete. Physical acceptance is still pending.

## Pre-deploy boundary

Before any new Board B flash, the exact ESP-IDF 5.5.4 semantics of the controlled-channel request must be reviewed rather than inferred from compile/CI alone. The review must settle at least:

- `esp_now_switch_channel_t::op_id` ownership/requirements;
- request/data-buffer lifetime after `esp_now_switch_channel_tx()` returns;
- appropriateness of the current `1500 ms` `wait_time_ms`;
- Accept receive behavior during/after the controlled-channel TX window.

No current-state documentation grants board flash authorization.

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

The broader Direct-to-Relay acceptance remains open until the integrated repair is physically re-tested and the long blackout is re-adjudicated.

## Local development environment authority

Current redacted environment authority:

`docs/development/local-environment-records/2026-09-17-macos-x86_64.json`

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

Use this record as the default environment authority. Re-run the versioned doctor only when host/venv/toolchain state changes. A task-specific Git worktree/branch/HEAD is separate and still requires fresh rebind.

## Required guards

- USB port is a locator only and is not board identity authority.
- Board-targeted mutation requires explicit operator target/connection confirmation before board access and fresh ROM silicon identity before write.
- Application serial open is not a passive runtime oracle.
- Lab diagnostic NVS writes are distinct from product NVS mutation.
- Discovery RX means decoded handler RX, not accepted advertisement.
- Schema-v5 completion counters are the device-side delivery-completion oracle; synchronous `esp_now_send(...) == ESP_OK` is not delivery success.
- Manager/Broker authority must not be selected by container name alone.
- Strict read-only gates must not create temporary files on the target.
- Current DynSec authority must be derived from the running Broker effective configuration; broad Relay grants remain forbidden.
- End-to-end Relay proof requires a bounded fresh traffic window with a clean pre-window baseline or another equally strong attribution oracle.
- Consumed one-shot authorizations are never replayable.
- Historical board/runtime evidence is not a claim about real-time physical state after the operator leaves the experiment.

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_CHALLENGE_CONTROLLED_CHANNEL_TX_PREDEPLOY_IDF_SEMANTICS_REVIEW_20260917_01
PHYSICAL_AUTHORIZATION_REQUIRED=false
T1_AUTHORIZATION_REQUIRED=false
```

This next gate is read-only/source-level and must complete before any Board B flash or physical validation of PR #416.

## Frozen broader acceptance

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=FROZEN_PASS
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
KF092_STATUS=CLOSED_PASS
```

Public GitHub stores source, tests, hashes, sanitized closures, architecture decisions, sanitized runtime alignment, and redacted local-environment records. Raw NVS, credentials, private board identities, private host addresses/paths, raw Manager logs, and raw Dynamic Security snapshots remain private/local.
