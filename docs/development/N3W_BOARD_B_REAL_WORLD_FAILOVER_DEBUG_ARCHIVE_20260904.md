# N3-W Board B Real-World Failover Debug Archive — 2026-09-04

## 1. Purpose

This document is the public-safe archive for the 2026-09-04 Board B real-world N3-W path-failover test and the diagnostic detours required to interpret the physical evidence.

It records:

- the original North Star and physical test intent;
- Board B runtime/reset observability instrumentation used by draft PR #361;
- stale build-artifact discovery and the fresh-artifact reflash proof;
- the controlled-reset / ROM Download Mode detour and its bounded disposition;
- battery-only Direct baseline and real-world spatial cold-boot attempts;
- the source-level defect that prevents a provisioned node from acquiring Relay on cold boot when Wi-Fi is unavailable;
- explicit boundaries on what has and has not been proven.

This is a public-safe engineering archive. Raw board identifiers, raw MAC addresses, local user paths, Setup Secret material, MQTT credentials, peer keys and other private identity material are intentionally excluded.

## 2. Authority and frozen revisions

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN_BASE=b683fc62a4126b6f6a0e945db8db68c2584e0e2d
MAIN_BASE_MESSAGE=Merge PR #359: docs: add three-board T1 real-world path failover test plan

DIAGNOSTIC_PR=361
DIAGNOSTIC_BRANCH=diag/n3w-boardb-radio-reset-observability-20260904
DIAGNOSTIC_HEAD=a4a8a8784de5f4b99ffd61a2cdf2f40e01ee0a41
DIAGNOSTIC_PR_STATE=DRAFT_OPEN_UNMERGED

PHYSICAL_TARGET=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
ESPHOME_VERSION=2026.4.3
ESPTOOL_VERSION=5.3.1
```

PR #361 remained diagnostic-only throughout this work. No radio-ownership repair, Wi-Fi reconnect policy repair, channel-policy repair, async-send semantic repair, credential rotation, NVS reset, Board A/C mutation or T1 mutation was performed as part of the diagnostic instrumentation branch.

## 3. North Star and expected real-world behavior

```text
NORTH_STAR=N3W_THREE_BOARD_T1_REAL_WORLD_PATH_FAILOVER_VALIDATION
SCENARIO=PHYSICAL_WIFI_COVERAGE_LOSS_AND_AUTOMATIC_RELAY_RECOVERY
```

Original target behavior:

1. Board B runs normally over Direct Wi-Fi.
2. Board B loses real Wi-Fi coverage without synthetic network blocking.
3. Board B discovers an ESP-NOW-capable nearby node, expected Board A in this topology.
4. Board B telemetry reaches T1 through Relay.
5. After Wi-Fi returns, the node can later recover Direct operation.

The valid spatial target is conceptually:

```text
ZONE_C_VALID =
    DIRECT_WIFI_UNAVAILABLE
    AND
    BOARD_B_TO_RELAY_GATEWAY_ESPNOW_REACHABLE
```

No fixed distance is itself a PASS condition.

## 4. First movement attempt: Wi-Fi loss not achieved, reboot observed

The first Board-B-only movement attempt did not produce a valid Wi-Fi-loss stimulus.

Frozen result:

```text
WIFI_LOSS_STIMULUS_ACHIEVED=false
RELAY_TRANSITION_OBSERVED=false
BOARD_B_UNPLANNED_REBOOT=true
REBOOT_CAUSE=UNKNOWN
```

Evidence showed Board B Direct telemetry continuing during the sampled movement window, while a new boot session appeared. Therefore the event proved a restart of the firmware/process lifetime but did not prove power loss, watchdog, panic, brownout, software reset or ESP-NOW Discovery as the cause.

This was correctly treated as a diagnostic detour rather than a Relay product failure.

## 5. Diagnostic observability instrumentation

Draft PR #361 added bounded observability only.

Required markers included:

```text
N3W_DIAG_BOOT
N3W_DIAG_STATE
N3W_DIAG_CHANNEL
N3W_DIAG_ESPNOW_TX_SUBMIT
N3W_DIAG_ESPNOW_TX_DONE
N3W_DIAG_ESPNOW_RX
N3W_DIAG_DIRECT_PUBLISH
```

The periodic state line was later extended to include:

```text
uptime_ms=<value>
boot_reset_reason=<esp_reset_reason numeric>
idf=<esp-idf version>
```

The instrumentation delegated to existing product behavior and did not intentionally modify the runtime state machine.

The PR CI rerun for `a4a8a8784de5f4b99ffd61a2cdf2f40e01ee0a41` completed successfully across all triggered workflows before the next Board B reflash gate.

## 6. Stale upload artifact incident

### 6.1 Symptom

A normal Board B upload returned PASS, but six post-flash `N3W_DIAG_STATE` lines still used the old format and lacked:

```text
uptime_ms
boot_reset_reason
idf
```

This contradicted the exact source at `a4a8a878...`, where the new format was present.

### 6.2 Adjudication

```text
SOURCE_BINDING=PASS
CI_BINDING=PASS
BOARD_B_UPLOAD_TRANSPORT=PASS
BOARD_B_RUNTIME_FORMAT=OLD
FLASHED_BINARY_SOURCE_BINDING=FAIL
```

The most likely explanation was reuse of an older ESPHome build artifact from the worktree used by `upload`; however the stale-artifact cause was not declared proven until a fresh build was explicitly bound.

### 6.3 Fresh artifact proof

A new disposable build worktree was created at exact commit `a4a8a878...`.

Fresh build proof:

```text
FRESH_FIRMWARE_ELF_FOUND=true
FRESH_FIRMWARE_BIN_FOUND=true
BINARY_N3W_DIAG_STATE_PRESENT=true
BINARY_UPTIME_FIELD_PRESENT=true
BINARY_BOOT_RESET_REASON_FIELD_PRESENT=true
BINARY_IDF_FIELD_PRESENT=true
FRESH_BUILD_SEMANTICS_BINDING=PASS

FIRMWARE_BIN_SHA256=f747dcf1010ac43c3d6ff10e28d9c773881dd3116cf73bab79f08f49e4072b22
FIRMWARE_ELF_SHA256=ac61df4455cd08977039023533dd3ea8155bb4a44e3001ff81d10fc32706b1e8
SOURCE_TO_BUILD_BINDING=PASS
UPLOAD_SOURCE_ARTIFACT_UNCHANGED=true
```

After upload from that same fresh build worktree:

```text
PERIODIC_RESET_ORACLE_PRESENT=true
RUNTIME_NEW_FORMAT_PROVEN=true
POST_FLASH_DIRECT_RESTORED=true
POST_FLASH_MQTT_CONNECTED=true
```

This closed the source→artifact→board binding gap for the diagnostic firmware.

## 7. Controlled RESET detour: ROM Download Mode proven

### 7.1 Post-reset symptom

Exactly one controlled RESET/EN action was executed after the fresh-artifact runtime had restored Direct operation.

After reset:

- USB re-enumerated;
- no ROM/bootloader/application log was captured by the normal monitor path;
- no new periodic `N3W_DIAG_STATE` appeared within the bounded window;
- T1 Manager received no Board B telemetry for an extended post-reset window and only observed availability unavailable.

The evidence did not justify claiming an application crash.

### 7.2 No-reset/no-stub ROM discriminator

A single esptool `no-reset` / `no-stub` ROM read succeeded against the already-existing device state.

Frozen result:

```text
ESPTOOL_ROM_SYNC=PASS
ESPTOOL_REPORTED_CHIP=ESP32-C6
BOARD_B_IDENTITY_BINDING=PASS
ROM_DOWNLOAD_MODE_PROVEN=true
POST_RESET_FAILURE_CLASS=ROM_DOWNLOAD_MODE_AFTER_CONTROLLED_RESET
```

This proved that the post-reset Board B state was ESP32-C6 ROM Download Mode, not a running N3-W application.

### 7.3 Latched strap versus current GPIO9 level

Read-only ESP32-C6 register evidence:

```text
GPIO_STRAP_REG=0x60091038
GPIO_IN_REG=0x6009103c
GPIO_STRAP_VALUE=0x00000004
GPIO8_STRAP=HIGH
GPIO9_STRAP=LOW

CURRENT_GPIO8_LEVEL=HIGH
CURRENT_GPIO9_LEVEL=HIGH

GPIO9_LOW_AT_RESET=true
GPIO9_STILL_LOW=false
GPIO9_CURRENTLY_RELEASED=true
ROOT_CAUSE_CLASS=TRANSIENT_GPIO9_LOW_DURING_RESET
ROOT_CAUSE=UNKNOWN
```

Therefore GPIO9 was sampled low during the reset strap window and was high later. The exact transient source was not proven. The archive does not attribute the event to a button, USB host behavior, auto-download circuitry, firmware, or an external load.

### 7.4 Practical recovery and detour closure

The diagnostic detour was deliberately stopped instead of expanding further.

A single normal Board B power-cycle restored the application without erase or reflash:

```text
BOARD_B_POWER_CYCLE_RECOVERY=PASS
BOARD_B_APPLICATION_RUNTIME=PASS
BOARD_B_DIRECT_RUNTIME=PASS
WIFI_CONNECTED=true
MQTT_CONNECTED=true
RUNTIME_READY=true
CURRENT_PATH=Direct
BOARD_B_MANAGER_ACCEPTED=true

BOARD_B_CURRENT_IDENTITY_PRESERVED=true
BOARD_B_CREDENTIAL_GENERATION_UNCHANGED=true
BOARD_B_APPLICATION_KEY_EPOCH_UNCHANGED=true
BOARD_B_PEER_TRUST_GENERATION_UNCHANGED=true

GPIO9_ROOT_CAUSE_EXACT=UNRESOLVED
GPIO9_DIAGNOSTIC_REQUIRED_FOR_MAINLINE=false
ACTIVE_DETOUR=CLOSED
```

The controlled-reset ROM-mode incident is therefore an important physical-harness warning, but it is not currently classified as an N3-W runtime-source failure.

## 8. Battery-only Board B baseline

Board B was switched from Mac USB to battery power. T1 Manager became the primary runtime oracle.

A battery-only Direct baseline then ran for about ten minutes:

```text
BOARD_B_USB_CONNECTED=false
BOARD_B_POWER_SOURCE=BATTERY
BOARD_B_MANAGER_ACCEPTED=true
BOARD_B_CURRENT_PATH=Direct
BOOT_ID_STABLE=true
SEQ_MONOTONIC_ADVANCE=true
SEQ_RANGE=27..146
```

T1 did not expose `uptime_ms` through the selected Manager/replay/retained authorities. This was initially treated as a blocking oracle, then correctly re-adjudicated as unnecessary for the cold-boot route because a stable boot session plus monotonically increasing accepted sequence numbers was sufficient for the required continuity claim.

## 9. Cold-boot spatial tests

Because continuous powered movement was not practical, the real-world test was split conceptually:

```text
T1A = REAL_WORLD_COLD_BOOT_RELAY_ACQUISITION
T1B = LIVE_DIRECT_TO_RELAY_FAILOVER
```

This archive covers T1A attempts. T1B remains unproven.

### 9.1 Precondition correction: Board A

An early attempt occurred while Board A was not connected. That attempt is classified as:

```text
TEST_PRECONDITION_NOT_MET
```

It is not product evidence against Relay.

The rerun first proved Board A was healthy and Direct online through T1 read-only evidence.

### 9.2 Candidate position 1: still Direct

Board B was powered off, moved, and powered on from battery.

Observed:

```text
NEW_BOOT_SESSION_CONFIRMED=true
POSTMOVE_BOOT_ID_STABLE=true
POSTMOVE_SEQ_MONOTONIC_ADVANCE=true
DIRECT_WIFI_AVAILABLE_AT_TARGET=true
BOARD_B_MANAGER_ACCEPTED=true
BOARD_B_CURRENT_PATH=Direct
ZONE_C_VALID=false
```

This proved the position still had usable Wi-Fi coverage and therefore was not a valid Relay test zone.

### 9.3 Farther candidate: no accepted telemetry

Board B was moved farther and cold-booted again.

Observed for about two minutes:

```text
POSTMOVE_BOOT_ID=NOT_OBSERVED
NEW_BOOT_SESSION_CONFIRMED=UNKNOWN
DIRECT_WIFI_AVAILABLE_AT_TARGET=UNKNOWN
BOARD_B_TO_BOARD_A_ESPNOW_REACHABLE=UNKNOWN
RELAY_ACQUISITION_OBSERVED=false
BOARD_B_MANAGER_ACCEPTED=false
BOARD_B_CURRENT_PATH=UNKNOWN
ZONE_C_VALID=UNKNOWN
```

The replay cursor remained at the prior accepted boot session. This did not prove Relay failure because neither the new boot session nor ESP-NOW reachability was independently visible from T1.

### 9.4 Intermediate candidate: same result

The next position was chosen back toward the previously Direct-capable point. Board B was visibly powered/application-alive, Board A remained Direct online, but T1 again received no new Board B Direct or Relay telemetry.

Frozen classification:

```text
CURRENT_LOCATION_CLASS=NO_ACCEPTED_TELEMETRY_ZONE
RELAY_ACQUISITION_OBSERVED=false
BOARD_B_MANAGER_ACCEPTED=false
ZONE_C_VALID=UNKNOWN
```

At this point further spatial bracketing was stopped because source review yielded a deterministic startup blocker independent of RF range.

## 10. Product source defect proven by read-only source review

The relevant source is `n3w_simple_product_component.cpp`.

The provisioned-node loop calls `start_runtime_if_ready_()` while `runtime_ready_` is false.

The startup function currently contains the precondition:

```cpp
if (!runtime_state_loaded_ || !mqtt_configured_ || !wifi_connected()) {
  return false;
}
```

Only after that guard does the function perform the ESP-NOW setup sequence, including radio initialization, broadcast-peer preparation and `runtime_.start(...)`.

Therefore a provisioned node cold-booting where Wi-Fi cannot associate is prevented from initializing the N3-W runtime that would be required to discover and acquire Relay.

Frozen adjudication:

```text
COLD_BOOT_RELAY_ACQUISITION_SOURCE_DEFECT=PROVEN
ROOT_CAUSE=PRODUCT_RUNTIME_STARTUP_REQUIRES_WIFI_CONNECTED
FAILURE_CLASS=RUNTIME_BOOTSTRAP_ARCHITECTURE

FAILED_REQUIREMENT=
PROVISIONED_NODE_MUST_BE_ABLE_TO_ACQUIRE_RELAY_WITHOUT_CURRENT_DIRECT_WIFI
```

This conclusion does not depend on proving the exact RF reachability at the last candidate position: even with perfect ESP-NOW RF reachability, the current cold-boot startup guard prevents the Relay runtime from being initialized while Wi-Fi remains unavailable.

## 11. Important proof boundary: live failover is still unproven

The source defect proven here is specifically the provisioned-node cold-boot Relay acquisition path.

Do **not** generalize it into this stronger statement:

```text
LIVE_DIRECT_TO_RELAY_FAILOVER=FAILED
```

That behavior remains:

```text
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
```

A node that has already reached `runtime_ready_` while Wi-Fi is available follows a different runtime state path when Wi-Fi is later lost. That path still requires dedicated validation after the cold-boot startup architecture is repaired or otherwise accounted for.

## 12. Source-design findings retained for the repair phase

The earlier read-only source review also identified three design issues relevant to the successor repair design:

1. **Wi-Fi / ESP-NOW radio ownership gap** — `wifi_connected()==false` is weaker than "Wi-Fi radio is idle"; ESPHome may still be scanning/connecting when N3-W attempts channel control.
2. **Discovery channel-switch failure backoff gap** — failed channel changes can return without advancing the normal dwell deadline, while the upper component ignores the tick error, creating a possible loop-rate retry pattern.
3. **Async ESP-NOW TX completion gap** — synchronous `esp_now_send()` acceptance is not equivalent to async send success, while the product callback result was not used by the state machine.

These findings are retained as repair-design inputs. They were not proven to be the cause of the cold-boot no-telemetry observations because the earlier `wifi_connected()` startup guard blocks the runtime before those mechanisms become relevant.

## 13. Methodology findings from this diagnostic session

### 13.1 Source→artifact→board binding is mandatory

`esphome upload PASS` alone is not proof that the flashed binary corresponds to the current source HEAD.

Future physical flash gates should bind:

```text
SOURCE_SHA
  -> fresh disposable build worktree
  -> binary semantic marker
  -> firmware artifact SHA256
  -> upload from the same build worktree/artifact
  -> board runtime marker
```

### 13.2 Build worktree separation

Use two roles:

```text
AUTHORITATIVE_SOURCE_WORKTREE
  source/diff/commit only

DISPOSABLE_BUILD_WORKTREE
  test/config/compile/generated/cache side effects
```

### 13.3 Changed-path oracle must include untracked files

A reliable scope gate must evaluate the union of unstaged, staged and untracked paths. Generated ESPHome files must be provenance-classified and isolated instead of silently ignored or treated as source drift.

### 13.4 UNKNOWN propagation remains mandatory

The spatial tests repeatedly demonstrated why missing evidence must remain `UNKNOWN` rather than being serialized as `false`. No accepted telemetry could not, by itself, prove no boot, no Wi-Fi, no ESP-NOW reachability or a product Relay failure.

## 14. Raw evidence handling

The physical session produced local serial captures and private runtime evidence. Those raw materials are intentionally not copied into the public repository by this archive.

Public archive authority is the sanitized closure state recorded here plus exact public source/commit/artifact metadata. Raw board identity and private runtime material remain outside the public repository.

## 15. Current closure

```text
MAINLINE=N3W_THREE_BOARD_T1_REAL_WORLD_PATH_FAILOVER_VALIDATION

BOARD_A_DIRECT_RUNTIME_HEALTHY=true
BOARD_B_BATTERY_OPERATION_PROVEN=true
BOARD_B_DIRECT_OPERATION_PROVEN=true

CONTROLLED_RESET_ROM_DOWNLOAD_MODE=PROVEN
CONTROLLED_RESET_EXACT_GPIO9_TRANSIENT_SOURCE=UNKNOWN
CONTROLLED_RESET_DETOUR_BLOCKS_MAINLINE=false

COLD_BOOT_RELAY_ACQUISITION_SOURCE_DEFECT=PROVEN
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED

CONTINUE_SPATIAL_SEARCH_BEFORE_SOURCE_REPAIR=false
PRODUCT_SOURCE_REPAIR_REQUIRED=true
```

## 16. Next route

```text
NEXT_ROUTE=
N3W_COLD_BOOT_RELAY_STARTUP_AND_RADIO_OWNERSHIP_PRODUCT_REPAIR_DESIGN
```

Repair acceptance must preserve the existing product contracts:

- stable node identity;
- MQTT credential generation continuity;
- application-key epoch continuity;
- system peer-trust generation continuity;
- no factory-known peer MAC dependency;
- Wi-Fi available → Direct preferred;
- Wi-Fi scanning/connecting → Wi-Fi retains radio ownership;
- only an explicit handoff permits ESP-NOW Discovery channel ownership;
- provisioned cold boot with Direct unavailable can still acquire Relay;
- later Wi-Fi recovery can return to Direct.

The product repair itself is out of scope for this archive commit.
