# N3-W Progress Alignment — 2026-09-18

Status: `CURRENT_PROGRESS_ALIGNMENT`

This document aligns the current engineering conversation with GitHub after the PR #416 physical revalidation route, the watchdog/channel-ownership forensic sequence, PR #423/#424/#425, post-merge CI, and the frozen exact-main Board B artifact build.

Fresh repository/runtime/physical evidence still takes precedence if later evidence proves drift.

## Alignment authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
ALIGNMENT_PRODUCT_SOURCE_HEAD=096528fbf61948d6c69197f1c8994ce8e7d672f4
ALIGNMENT_PRODUCT_SOURCE_TREE=6cfa25f5168fc720590f186871c038e3d4a5307f
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

Important authority split:

- `096528fb...` is the frozen product-source authority for the current Board B candidate artifact.
- A later documentation-only merge may advance repository `main`; that must not silently redefine the frozen firmware source.
- Board B has **not** yet been flashed with the PR #425 exact-main artifact.

## Integrated route

```text
PR420=MERGED   merge=a1e14f7ee183ee2486453fad7a1338c3f5d5f8de
PR421=MERGED   merge=fb762e2ccb54393e7610339d05d164b7ea975bba
PR422=MERGED   merge=a01725644d9b0b4ee0a461c1579211829f1aa69e
PR423=MERGED   merge=35944fa928bb1fcf5527e476fb5dbfcfcdc11ead
PR424=MERGED   merge=664fcbe88bae76bc9fc6e5e240067e3cbae7c649
PR425=MERGED   merge=096528fbf61948d6c69197f1c8994ce8e7d672f4
```

Meaning:

- PR #421 added retained RTC watchdog breadcrumbs.
- PR #422 added Relay encrypted-unicast current-channel / peer-channel observability.
- PR #423 removed the synchronous MQTT/log-forwarding watchdog hazard in the physical harness.
- PR #424 introduced explicit single-radio ownership between Direct Wi-Fi, Relay ESP-NOW, and bounded Direct probes.
- PR #425 made Direct failback commit ordering transactional and fixed Relay channel before encrypted-peer/state commit.

KF-092 remains `CLOSED_PASS`; this route does not reopen it.

## Physical evidence before PR #424/#425

### Task watchdog defect isolated and repaired

Repeated Direct -> Relay testing had shown an uncommanded `TASK_WDT` reset during Wi-Fi loss. RTC breadcrumb evidence placed the last completed application marker after telemetry return and before the following log path.

Source forensic then proved the physical harness used synchronous ESP-IDF MQTT publish and default MQTT log forwarding. During disappearing Wi-Fi, an INFO log could synchronously enter the MQTT path and block the ESPHome main loop for approximately the network timeout window.

PR #423 changed the lab harness to:

```yaml
mqtt:
  idf_send_async: true
  log_topic: null
```

Fresh same-boot physical retest then showed:

```text
TASK_WDT_REPRODUCED=false
UNCOMMANDED_REBOOT=false
PR423_TASK_WDT_REPAIR_PHYSICAL_VALIDATION=PASS
MANAGER_RESTART_COUNT=0
```

### Remaining Direct -> Relay blackout after PR #423

The same physical retest still had a Manager-visible Direct -> Relay blackout of approximately:

```text
MANAGER_VISIBLE_GAP_MS≈110061
SAME_BOOT_DIRECT_TO_RELAY=PASS
```

The Challenge path itself no longer showed the old PR #416 synchronous-submit failure, but encrypted Relay telemetry produced fresh direct channel evidence:

```text
ENCRYPTED_UNICAST_FAILURE_COUNT=2
FIRST_FAILURE_CURRENT_CHANNEL=5
FIRST_FAILURE_PEER_CHANNEL=11
FIRST_FAILURE_RAW_ERROR=12397
RAW_ERROR_12397=ESP_ERR_ESPNOW_CHAN
LATER_FIRST_SUCCESS_CURRENT_CHANNEL=11
LATER_FIRST_SUCCESS_PEER_CHANNEL=11
```

This proved that the device could enter/approach Relay operation while the actual Wi-Fi radio was again on a different channel than the encrypted peer.

The two failures also matched the configured `relay_failures_to_discovery=2`, explaining why the runtime could be forced back into Discovery before a later successful Relay submission.

## Root cause after source forensic

Source review established that ESPHome Wi-Fi reconnect/scanning and the N3-W Relay/Discovery logic were both able to control the same ESP32-C6 2.4 GHz radio.

The evidence supports:

```text
SINGLE_RADIO_CONCURRENT_CHANNEL_OWNERSHIP=PROVEN_SOURCE_DEFECT
CURRENT_CH5_VS_PEER_CH11=PROVEN_PHYSICAL_EVIDENCE
ESP_ERR_ESPNOW_CHAN=PROVEN
```

The full 110 s blackout must still be treated as a composition of several phases; it is not correct to attribute every millisecond to one channel switch.

## PR #424 repair

PR #424 introduced explicit radio ownership:

```text
DIRECT_WIFI
RELAY_ESPNOW
DIRECT_PROBE
```

When Relay/Discovery takes ownership, ESPHome Wi-Fi automatic reconnect is disabled before the standalone ESP-NOW session starts. Failed Direct recovery probes restore standalone Relay radio state and rebind the active Relay channel/encrypted peer.

The design also intentionally schedules bounded Direct recovery probes while in Relay mode. Current constants are approximately:

```text
RECOVERY_PROBE_INTERVAL_MS=60000
RECOVERY_PROBE_WINDOW_MS=15000
RECOVERY_PROBE_POLL_MS=2000
```

During `DIRECT_PROBE`, Relay telemetry submission is paused. This is a product behavior that must be measured in later failback acceptance; it is not equivalent to continuous Relay telemetry.

## PR #425 follow-up repair

Review of PR #424 found a source-confirmed failure path:

1. Direct recovery could commit logical path state to `DIRECT`.
2. Concrete radio/channel restoration happened afterward.
3. If channel restoration failed, logical state could remain `DIRECT` while component ownership remained `DIRECT_PROBE`.
4. The telemetry entrypoint rejects `DIRECT_PROBE`, creating a possible persistent no-send state.

PR #425 changes the order:

```text
successful bounded Direct probe threshold
→ concrete Direct radio/channel restore
→ only then logical DIRECT commit
```

If concrete restore fails, Relay/Discovery state is preserved and Direct-recovery hysteresis is reset.

PR #425 also removes the active Challenge path's dependence on a new temporary off-channel operation after Relay already owns the radio. Discovery fixes the radio to the Relay channel and uses the normal ESP-NOW control path. On verified Accept, the runtime fixes the Relay channel before encrypted-peer installation and before `RelayActive` state commit.

Added host/source tests cover:

- Direct channel restore failure must not commit `DIRECT`;
- failed post-Accept channel fixation must not commit `RelayActive`;
- Relay channel fixation precedes peer/state commit;
- Challenge uses the already-owned fixed Relay channel;
- failed Direct commit resets recovery hysteresis for future retry.

## PR #425 CI closure

PR head and post-merge exact-main CI are green.

```text
PR425_HEAD=253e28b08db8ca7854ad25d72e3270decd02506d
PR425_MERGE=096528fbf61948d6c69197f1c8994ce8e7d672f4

POST_MERGE_PUBLIC_REPOSITORY_SAFETY_CI=PASS
POST_MERGE_GREENHOUSE_MANAGER_CI=PASS

PHASE4_SINGLE_RADIO_OWNERSHIP_CONTRACTS=PASS
PHASE4_SIMPLIFIED_PRODUCT_RUNTIME=PASS
ESP32C6_CHILD_BUILD=PASS
ESP32C6_RELAY_BUILD=PASS
ESP32C6_PHASE4_PHYSICAL_HARNESS_BUILD=PASS
```

Post-merge greenhouse-manager run:

```text
RUN_ID=35293249780
RESULT=PASS
```

## Frozen exact-main Board B artifact

A build-only branch was created solely to materialize the exact product source; it is not product authority and must not be merged into main.

```text
BUILD_BRANCH=build/n3w-pr425-boardb-artifact-20260918
WORKFLOW_SOURCE_COMMIT=60048df76a0845b8c0f2940a5b5290523312c61a
ARTIFACT_RUN_ID=35294123841
ARTIFACT_ID=10528055066
ARTIFACT_NAME=n3w-pr425-boardb-exact-main
```

The workflow checked out and exact-bound:

```text
SOURCE_HEAD=096528fbf61948d6c69197f1c8994ce8e7d672f4
SOURCE_TREE=6cfa25f5168fc720590f186871c038e3d4a5307f
ESPHOME_VERSION=2026.4.3
```

Frozen write artifacts:

```text
firmware.bin
SIZE=1128720
SHA256=bf3af5490745f1279a4e90d57a8e96b46525ae8debaf6f806ed2ae72180836c0

ota_data_initial.bin
SIZE=8192
SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

Build resource report:

```text
RAM_USED=50568/327680=15.4%
FLASH_USED=1128364/3932160=28.7%
```

Artifact archive digest:

```text
SHA256=b69f9f3736eca8da40cafa1b8cc63d8fb901dee99a8f3afb5724e216bffc6c62
```

## Current physical/deployment boundary

No Board B write using the PR #425 artifact has occurred.

```text
BOARD_A_MUTATION=false
BOARD_B_PR425_FLASH=false
SERIAL_OPEN=false
T1_MUTATION=false
BROKER_MANAGER_DYNSEC_MUTATION=false
```

The last known physical placement/power state from the conversation is historical context only and must be freshly confirmed before board access.

A USB device path may be used only as a locator. Any future Board B write still requires fresh ROM silicon identity and flash/security-state confirmation before mutation.

## Current acceptance matrix

```text
KF092_STATUS=CLOSED_PASS

PR423_TASK_WDT_REPAIR_SOURCE=PASS
PR423_TASK_WDT_REPAIR_PHYSICAL_VALIDATION=PASS

PR424_SINGLE_RADIO_OWNERSHIP_SOURCE_REPAIR=PASS
PR425_FAILBACK_COMMIT_ORDER_SOURCE_REPAIR=PASS
PR425_POST_ACCEPT_CHANNEL_FIXATION_SOURCE_REPAIR=PASS

PR425_POST_MERGE_CI=PASS
PR425_EXACT_MAIN_ARTIFACT_BINDING=PASS

PR425_BOARD_B_DEPLOYMENT=PENDING
PR425_DIRECT_TO_RELAY_PHYSICAL_VALIDATION=PENDING
PR425_RELAY_STEADY_STATE_PROBE_GAP_VALIDATION=PENDING
PR425_RELAY_TO_DIRECT_FAILBACK_VALIDATION=PENDING
```

## Next ONE gate

```text
NEXT_ONE_GATE=N3W_PR425_BOARD_B_WRITE_TARGET_PREFLIGHT_20260918_01
BOARD_ACCESS_REQUIRED=true
PREFLIGHT_READ_ONLY=true
FLASH_WRITE=false
SERIAL_OPEN=false
T1_MUTATION=false
```

Purpose: before any write, freshly prove that the physically connected target is the intended Board B, confirm ESP32-C6 silicon identity, expected flash size, Secure Boot / Flash Encryption state, and bind the frozen PR #425 artifact hashes to that target.

Only after a successful target preflight and a separate explicit Board B write authorization may app+otadata be written.

## Public/private evidence boundary

Public GitHub may store source, tests, public-safe artifact hashes, sanitized timing evidence, and source/CI acceptance state. It must not store raw credentials, setup secrets, private keys, raw NVS, private host addresses, or private board identity material.
