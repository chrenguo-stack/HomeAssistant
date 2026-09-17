# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current progress alignment: `docs/development/N3W_PROGRESS_ALIGNMENT_20260917.md`  
Current local-development-environment authority: `docs/development/local-environment-records/2026-09-17-macos-x86_64.json`  
Current KF-089 Relay end-to-end closeout: `docs/development/N3W_KF089_RELAY_END_TO_END_CLOSEOUT_20260914.md`  
Current T1 runtime-convergence archive: `docs/development/N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`  
Active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

## Repository authority at 2026-09-17 alignment

```text
REPOSITORY=chrenguo-stack/HomeAssistant
ALIGNMENT_BASE_MAIN=01389807f801341ca2240bcaf5a58e58ce9b9213
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

The SHA above is the exact `main` tip at alignment-branch creation, not a permanent claim about future repository tips. Always fresh-query `main`.

Recent merged route:

```text
PR411=MERGED   # Relay MAC async delivery feedback
PR413=MERGED   # delivery feedback + reset diagnostics + harness reboot policy
PR414=MERGED   # Direct-to-Relay latency observability
PR415=MERGED   # Challenge submit raw-error observability
PR416=MERGED   # controlled-channel Challenge TX
PR417=MERGED   # local environment record

PR415_MAIN_MERGE=63808f35fa2534388ec2c45e9ce9e9aa7d5d2e64
PR416_MAIN_MERGE=11aa3ed3c1c727427e3a67f8764772c3a9fc3398
PR417_MAIN_MERGE=01389807f801341ca2240bcaf5a58e58ce9b9213
```

Historical PR #410/#412 are superseded stacked/documentation vehicles and are not current source authority.

## Accepted historical baselines

```text
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
KF089_END_TO_END_RELAY_TELEMETRY=PROVEN
T1_BROKER_MEDIATED_RELAY_INGRESS=PROVEN
MANAGER_RELAY_ACCEPTANCE=PROVEN

KF092_SOURCE_REPAIR=PASS
KF092_REBOOT_POLICY_REPAIR=PASS
KF092_REBOOT_POLICY_PHYSICAL_FIX=PASS
KF092_PHYSICAL_CAUSATION_PROVEN=true
KF092_POSTFIX_PHYSICAL_VALIDATION=PASS
KF092_ALIGNED_AB_LONG_DURATION_CONTINUITY=PASS
KF092_STATUS=CLOSED_PASS
```

KF-092 closure started from an established Relay path and does not itself prove same-session Direct-to-Relay latency acceptance.

## Current same-boot Direct-to-Relay result

```text
SAME_BOOT_DIRECT_TO_RELAY=PASS
UNCOMMANDED_REBOOT_DURING_TRANSITION=false
REBOOT_REQUIRED_FOR_RELAY=false
MANAGER_VISIBLE_GAP_MS=109007
MISSING_SEQUENCE_COUNT=21
TELEMETRY_CONTINUITY_ACCEPTANCE=FAIL
```

Functional Direct -> Relay is therefore proven, but the broader acceptance remains open because the accepted-telemetry blackout was still about 109 seconds.

## Current root-cause result

Latency observability showed three failed Challenge submissions before success. The snapshot preserves first/last raw errors:

```text
challenge_submit_failure_count=3
challenge_submit_first_driver_error=11
challenge_submit_last_driver_error=11
challenge_submit_first_error_raw=12397
challenge_submit_last_error_raw=12397
relay_ad_seen_to_successful_challenge_tx_ms=70132
```

For ESP-IDF 5.5.4, raw `12397` maps to `ESP_ERR_ESPNOW_CHAN`. At least the first and last failed Challenge submissions were therefore synchronous channel-mismatch rejection, not over-air packet loss.

## Integrated repair / pending physical validation

PR #416 changes the Challenge path to ESP-IDF controlled-channel TX using `esp_now_switch_channel_tx()` while preserving Relay advertisement on the normal broadcast path and preserving existing Direct/Discovery/Relay policy thresholds.

```text
PR416_HOST_SOURCE_TESTS=45/45_PASS
PR416_ESP32C6_BUILD_ONLY=PASS
PR416_PR_CI=PASS
PR416_POSTMERGE_CI=PASS
PR416_PHYSICAL_VALIDATION=PENDING
```

Before any new Board B flash, perform the source-level ESP-IDF semantics review recorded in `N3W_CURRENT_STATE.md` / `N3W_PROGRESS_ALIGNMENT_20260917.md`.

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

## Local development environment authority

```text
RECORD=docs/development/local-environment-records/2026-09-17-macos-x86_64.json
PROJECT_VENV=~/.venvs/greenhouse-homeassistant-dev
PYTHON=3.11.9
PYTEST=8.4.2
RUFF=0.15.22
PAHO_MQTT=2.1.0
ESPHOME=2026.4.3
ESPHOME_DEPLOYMENT=pipx_isolated
LOCAL_ENVIRONMENT_STATUS=accepted_for_local_development
```

Use this record rather than repeatedly rediscovering unchanged Python/ESPHome tooling. Task-specific Git worktree/branch/HEAD remains separate and still requires fresh rebind.

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_CHALLENGE_CONTROLLED_CHANNEL_TX_PREDEPLOY_IDF_SEMANTICS_REVIEW_20260917_01
PHYSICAL_AUTHORIZATION_REQUIRED=false
T1_AUTHORIZATION_REQUIRED=false
```

After that read-only/source-level review passes, a separate explicit authorization is required for any Board B flash or physical revalidation.

Historical archives remain historical and are not rewritten solely to erase dated intermediate states.
