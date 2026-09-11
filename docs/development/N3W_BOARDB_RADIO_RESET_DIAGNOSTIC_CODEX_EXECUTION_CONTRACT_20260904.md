# N3-W Board B Radio / Reset Diagnostic — Codex Execution Contract

Date: 2026-09-04

This contract is subordinate to `N3W_BOARDB_RADIO_RESET_DIAGNOSTIC_INSTRUMENTATION_GATE_20260904.md`.

## Executor model

```text
EXECUTOR=CODEX_LOW_ORDER
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
SCOPE_EXPANSION=false
AUTO_REPAIR=false
```

Codex may compile and execute the exact bounded steps below. It must stop on any failed binding or failed oracle and return evidence without inventing a repair.

## Repository preclaim

Expected branch:

```text
BRANCH=diag/n3w-boardb-radio-reset-observability-20260904
REQUIRED_ANCESTOR=b683fc62a4126b6f6a0e945db8db68c2584e0e2d
REQUIRED_GATE_COMMIT=f73457706878633b315eef27f1bca048817240ca
```

Preclaim:

```bash
set -euo pipefail
repo="${HOME}/HomeAssistant-local-test"
cd "$repo"

git fetch origin --prune

git status --porcelain=v1
# MUST be empty. Otherwise STOP / DIRTY_WORKTREE.

git switch diag/n3w-boardb-radio-reset-observability-20260904 2>/dev/null || \
  git switch --track origin/diag/n3w-boardb-radio-reset-observability-20260904

git pull --ff-only origin diag/n3w-boardb-radio-reset-observability-20260904

head="$(git rev-parse HEAD)"
git merge-base --is-ancestor b683fc62a4126b6f6a0e945db8db68c2584e0e2d "$head"
git merge-base --is-ancestor f73457706878633b315eef27f1bca048817240ca "$head"

printf 'DIAG_BRANCH_HEAD=%s\n' "$head"
printf 'WORKTREE_CLEAN=true\n'
printf 'BASE_MAIN_ANCESTOR=true\n'
printf 'GATE_COMMIT_ANCESTOR=true\n'
```

No Board/T1/USB operation is allowed before the source/build gates below pass.

## Allowed repository mutations

Exactly these paths may change in the implementation commit:

```text
firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h
tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py
```

No other path may change.

## Required C++ diagnostic implementation

Modify `firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h` only as follows.

### 1. Additional includes

Immediately after:

```cpp
#include "esphome/core/log.h"
```

add:

```cpp
#ifdef USE_MQTT
#include "esphome/components/mqtt/mqtt_client.h"
#endif
#ifdef USE_WIFI
#include "esphome/components/wifi/wifi_component.h"
#endif
#ifdef USE_ESP32
#include "esp_system.h"
#include "esp_wifi.h"
#endif
```

### 2. Boot reset-reason logging

At the beginning of `GreenhouseN3wCore::setup()`, before any existing product-state work, add:

```cpp
#ifdef USE_ESP32
    ESP_LOGI(
        "n3w_diag",
        "N3W_DIAG_BOOT reset_reason=%d idf=%s",
        static_cast<int>(esp_reset_reason()),
        esp_get_idf_version());
#endif
```

After the existing call to:

```cpp
    SimpleProductComponent::setup();
```

add:

```cpp
    diag_log_state_(true);
```

### 3. Periodic/state-change logging

Replace the existing `loop()` body:

```cpp
  void loop() override {
    SimpleProductComponent::loop();
  }
```

with:

```cpp
  void loop() override {
    SimpleProductComponent::loop();
    diag_log_state_(false);
  }
```

### 4. Adapter-boundary diagnostic overrides

Immediately after `phase4_source_harness_ready()` and before the recovery-only comment, add:

```cpp
  void on_espnow_receive_with_metadata(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      const EspNowReceiveMetadata &metadata) override {
    ESP_LOGI(
        "n3w_diag",
        "N3W_DIAG_ESPNOW_RX kind=%s src=%02x:%02x:%02x:%02x:%02x:%02x size=%u channel=%u rssi=%d path=%u",
        diag_frame_kind_(data, size),
        static_cast<unsigned>(source[0]),
        static_cast<unsigned>(source[1]),
        static_cast<unsigned>(source[2]),
        static_cast<unsigned>(source[3]),
        static_cast<unsigned>(source[4]),
        static_cast<unsigned>(source[5]),
        static_cast<unsigned>(size),
        static_cast<unsigned>(metadata.channel),
        static_cast<int>(metadata.rssi_dbm),
        diag_path_value_());
    SimpleProductComponent::on_espnow_receive_with_metadata(
        source, data, size, metadata);
  }

  void on_espnow_send_result(
      const MacAddress &destination,
      bool success) override {
    ESP_LOGI(
        "n3w_diag",
        "N3W_DIAG_ESPNOW_TX_DONE dst=%02x:%02x:%02x:%02x:%02x:%02x success=%s path=%u",
        static_cast<unsigned>(destination[0]),
        static_cast<unsigned>(destination[1]),
        static_cast<unsigned>(destination[2]),
        static_cast<unsigned>(destination[3]),
        static_cast<unsigned>(destination[4]),
        static_cast<unsigned>(destination[5]),
        success ? "true" : "false",
        diag_path_value_());
    SimpleProductComponent::on_espnow_send_result(destination, success);
  }

  bool set_radio_channel(uint8_t channel) override {
    uint8_t before_channel = 0;
    uint8_t after_channel = 0;
    const int before_rc = diag_read_channel_(&before_channel);
    const bool wifi_before = diag_wifi_connected_();
    const bool accepted = SimpleProductComponent::set_radio_channel(channel);
    const int after_rc = diag_read_channel_(&after_channel);

    ++diag_channel_attempts_;
    if (!accepted) ++diag_channel_failures_;
    const uint64_t now = now_ms();
    const bool log_failure =
        !accepted &&
        (diag_channel_failures_ <= 8 ||
         now - diag_last_channel_failure_log_ms_ >= 250);
    if (accepted || log_failure) {
      if (!accepted) diag_last_channel_failure_log_ms_ = now;
      ESP_LOGI(
          "n3w_diag",
          "N3W_DIAG_CHANNEL request=%u wifi_connected=%s accepted=%s before_rc=%d before=%u after_rc=%d after=%u attempts=%u failures=%u path=%u",
          static_cast<unsigned>(channel),
          wifi_before ? "true" : "false",
          accepted ? "true" : "false",
          before_rc,
          static_cast<unsigned>(before_channel),
          after_rc,
          static_cast<unsigned>(after_channel),
          static_cast<unsigned>(diag_channel_attempts_),
          static_cast<unsigned>(diag_channel_failures_),
          diag_path_value_());
    }
    return accepted;
  }

  bool broadcast_control(
      const uint8_t *data,
      std::size_t size) override {
    const char *kind = diag_frame_kind_(data, size);
    const bool accepted = SimpleProductComponent::broadcast_control(data, size);
    ESP_LOGI(
        "n3w_diag",
        "N3W_DIAG_ESPNOW_TX_SUBMIT kind=%s mode=broadcast size=%u accepted=%s path=%u",
        kind,
        static_cast<unsigned>(size),
        accepted ? "true" : "false",
        diag_path_value_());
    return accepted;
  }

  bool send_encrypted_peer(
      const MacAddress &peer_mac,
      const uint8_t *data,
      std::size_t size) override {
    const bool accepted =
        SimpleProductComponent::send_encrypted_peer(peer_mac, data, size);
    ESP_LOGI(
        "n3w_diag",
        "N3W_DIAG_ESPNOW_TX_SUBMIT kind=compact mode=unicast dst=%02x:%02x:%02x:%02x:%02x:%02x size=%u accepted=%s path=%u",
        static_cast<unsigned>(peer_mac[0]),
        static_cast<unsigned>(peer_mac[1]),
        static_cast<unsigned>(peer_mac[2]),
        static_cast<unsigned>(peer_mac[3]),
        static_cast<unsigned>(peer_mac[4]),
        static_cast<unsigned>(peer_mac[5]),
        static_cast<unsigned>(size),
        accepted ? "true" : "false",
        diag_path_value_());
    return accepted;
  }

  bool publish_direct(
      const std::string &topic,
      const std::string &payload) override {
    const bool accepted = SimpleProductComponent::publish_direct(topic, payload);
    ESP_LOGI(
        "n3w_diag",
        "N3W_DIAG_DIRECT_PUBLISH accepted=%s wifi_connected=%s mqtt_connected=%s path=%u",
        accepted ? "true" : "false",
        diag_wifi_connected_() ? "true" : "false",
        diag_mqtt_connected_() ? "true" : "false",
        diag_path_value_());
    return accepted;
  }
```

Do not log `topic` or `payload`.

### 5. Protected diagnostic helpers

Immediately after the existing `protected:` line and before `persisted_runtime_state_present_()`, add:

```cpp
  static bool diag_wifi_connected_() {
#ifdef USE_WIFI
    return wifi::global_wifi_component != nullptr &&
           wifi::global_wifi_component->is_connected();
#else
    return false;
#endif
  }

  static bool diag_mqtt_connected_() {
#ifdef USE_MQTT
    return mqtt::global_mqtt_client != nullptr &&
           mqtt::global_mqtt_client->is_connected();
#else
    return false;
#endif
  }

  static int diag_read_channel_(uint8_t *channel) {
    if (channel == nullptr) return -1;
    *channel = 0;
#ifdef USE_ESP32
    wifi_second_chan_t secondary = WIFI_SECOND_CHAN_NONE;
    return static_cast<int>(esp_wifi_get_channel(channel, &secondary));
#else
    return -1;
#endif
  }

  static const char *diag_frame_kind_(
      const uint8_t *data,
      std::size_t size) {
    if (data == nullptr || size == 0) return "invalid";
    SimpleRelayDiscovery discovery;
    if (decode_simple_relay_discovery(data, size, &discovery) ==
        SimpleRuntimeError::NONE) {
      return "relay_discovery";
    }
    SimplePeerChallenge challenge;
    if (decode_simple_peer_challenge(data, size, &challenge) ==
        SimpleRuntimeError::NONE) {
      return "peer_challenge";
    }
    SimplePeerAccept accept;
    if (decode_simple_peer_accept(data, size, &accept) ==
        SimpleRuntimeError::NONE) {
      return "peer_accept";
    }
    CompactTelemetryFrameV2 compact;
    if (decode_compact_telemetry_frame_v2(data, size, &compact) ==
        CompactTelemetryError::NONE) {
      return "compact";
    }
    return "unknown";
  }

  unsigned diag_path_value_() const {
    return runtime_ready()
               ? static_cast<unsigned>(path_state())
               : 255U;
  }

  void diag_log_state_(bool force) {
    const uint64_t now = now_ms();
    const bool wifi_connected = diag_wifi_connected_();
    const bool mqtt_connected = diag_mqtt_connected_();
    const unsigned path = diag_path_value_();
    uint8_t channel = 0;
    const int channel_rc = diag_read_channel_(&channel);
    const bool changed =
        !diag_state_initialized_ || wifi_connected != diag_last_wifi_connected_ ||
        mqtt_connected != diag_last_mqtt_connected_ ||
        path != diag_last_path_ || channel != diag_last_channel_ ||
        channel_rc != diag_last_channel_rc_;
    if (force || changed || now - diag_last_state_log_ms_ >= 5000) {
      ESP_LOGI(
          "n3w_diag",
          "N3W_DIAG_STATE wifi_connected=%s mqtt_connected=%s runtime_ready=%s path=%u channel_rc=%d channel=%u rx_dropped=%u channel_attempts=%u channel_failures=%u",
          wifi_connected ? "true" : "false",
          mqtt_connected ? "true" : "false",
          runtime_ready() ? "true" : "false",
          path,
          channel_rc,
          static_cast<unsigned>(channel),
          static_cast<unsigned>(rx_dropped_.load(std::memory_order_relaxed)),
          static_cast<unsigned>(diag_channel_attempts_),
          static_cast<unsigned>(diag_channel_failures_));
      diag_last_state_log_ms_ = now;
    }
    diag_state_initialized_ = true;
    diag_last_wifi_connected_ = wifi_connected;
    diag_last_mqtt_connected_ = mqtt_connected;
    diag_last_path_ = path;
    diag_last_channel_ = channel;
    diag_last_channel_rc_ = channel_rc;
  }
```

### 6. Diagnostic member state

Immediately before the existing member:

```cpp
  bool phase4_source_harness_enabled_{false};
```

add:

```cpp
  bool diag_state_initialized_{false};
  bool diag_last_wifi_connected_{false};
  bool diag_last_mqtt_connected_{false};
  unsigned diag_last_path_{255U};
  uint8_t diag_last_channel_{0};
  int diag_last_channel_rc_{-1};
  uint32_t diag_channel_attempts_{0};
  uint32_t diag_channel_failures_{0};
  uint64_t diag_last_state_log_ms_{0};
  uint64_t diag_last_channel_failure_log_ms_{0};
```

## Required source-contract test

Create `tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py` with:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h"
PRODUCT = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp"
RUNTIME_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.h"
RUNTIME_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.cpp"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_boardb_diagnostic_observability_markers_present():
    core = text(CORE)
    for marker in (
        "N3W_DIAG_BOOT",
        "N3W_DIAG_STATE",
        "N3W_DIAG_CHANNEL",
        "N3W_DIAG_ESPNOW_TX_SUBMIT",
        "N3W_DIAG_ESPNOW_TX_DONE",
        "N3W_DIAG_ESPNOW_RX",
        "N3W_DIAG_DIRECT_PUBLISH",
        "esp_reset_reason()",
        "esp_get_idf_version()",
        "decode_simple_relay_discovery",
        "decode_simple_peer_challenge",
        "decode_simple_peer_accept",
        "decode_compact_telemetry_frame_v2",
    ):
        assert marker in core


def test_diagnostic_branch_does_not_change_known_transport_policy():
    product = text(PRODUCT)
    runtime_h = text(RUNTIME_H)
    runtime_cpp = text(RUNTIME_CPP)

    assert "std::vector<uint8_t> allowed_channels{1, 6, 11};" in runtime_h
    assert "uint32_t scan_dwell_ms{250};" in runtime_h
    assert "(void) runtime_.tick();" in product
    assert "return radio_.set_channel(channel) == DriverError::NONE;" in product
    assert "next_scan_switch_ms_ = now_ms + policy_.scan_dwell_ms;" in runtime_cpp


def test_diagnostic_logging_does_not_emit_payload_or_topic():
    core = text(CORE)
    start = core.index("bool publish_direct(")
    end = core.index("protected:", start)
    body = core[start:end]
    assert "topic.c_str()" not in body
    assert "payload.c_str()" not in body
```

## Source-only validation

After editing:

```bash
set -euo pipefail
cd "${HOME}/HomeAssistant-local-test"

changed="$(git diff --name-only)"
printf '%s\n' "$changed"

python3 - <<'PY'
from pathlib import Path
allowed = {
    "firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h",
    "tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py",
}
import subprocess
paths = set(subprocess.check_output(["git", "diff", "--name-only"], text=True).splitlines())
if paths != allowed:
    raise SystemExit(f"unexpected changed paths: {sorted(paths)}")
PY

git diff --check
python3 -m pytest -q tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py
python3 -m pytest -q tests/n3w_phase4/test_phase4_source_contract.py
```

Then run any existing focused host/source tests that cover the N3-W simple product runtime and ESP-NOW driver if discoverable in the repository. Do not repair unrelated failures.

## Compile gate

Use the already established ESPHome 2026.4.3 environment. Do not install or upgrade toolchains in this gate.

```bash
set -euo pipefail
cd "${HOME}/HomeAssistant-local-test/firmware/esphome_rc/board_lab/n3w_phase4_physical"
esphome config generic.yml
esphome compile generic.yml
```

Required compile result:

```text
ESPHOME_VERSION=2026.4.3
CONFIG_PASS=true
COMPILE_PASS=true
```

If config or compile fails: STOP. No Board access.

## Commit / push gate

Only after source tests and compile PASS:

```bash
set -euo pipefail
cd "${HOME}/HomeAssistant-local-test"

git diff --check
git status --short

git add \
  firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h \
  tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py

git commit -m "diag: instrument Board B radio and reset observability"
git push origin diag/n3w-boardb-radio-reset-observability-20260904

printf 'DIAGNOSTIC_SOURCE_COMMIT=%s\n' "$(git rev-parse HEAD)"
```

Do not merge this branch into `main`.

## Board B flash preclaim

Before any serial write, Codex must rediscover the exact currently attached Board B serial device from the current physical-session evidence. It must not assume a stale `/dev/cu.*` path.

Required preclaim:

```text
BOARD_B_UNIQUE_SERIAL_TARGET=true
BOARD_A_ACCESS=false
BOARD_C_ACCESS=false
T1_MUTATION=false
NVS_ERASE=false
FACTORY_RESET=false
FLASH_TARGET=BOARD_B_ONLY
```

If Board B cannot be uniquely bound, STOP.

## Flash rule

Use the compiled ESPHome image for `generic.yml` and the exact Board B serial target. Flash only the application image using the normal ESPHome/esptool path already proven for this board. Explicitly prohibited:

```text
esptool erase_flash
NVS erase
partition erase
factory reset
credential rotation
pairing reset
```

If the local established procedure uses `esphome run generic.yml --device <BOARD_B_SERIAL>`, that is allowed only after verifying it does not invoke an erase/reset workflow beyond normal firmware flashing.

## Immediate serial capture

Start/continue serial logging before the first post-flash boot and preserve ROM/bootloader/application output. The evidence file must remain private and must not be committed if it contains hardware identifiers or private runtime material.

Required first markers:

```text
N3W_DIAG_BOOT reset_reason=...
N3W_DIAG_STATE ...
N3W_DIAG_DIRECT_PUBLISH ...
```

## Stationary Wi-Fi-Good baseline

Do not move Board B yet. Keep A/C unchanged. Observe Board B for at least 90 seconds in the known Wi-Fi-Good location.

Required closure:

```text
DIAGNOSTIC_FIRMWARE_BOOTED=true
RESET_REASON_LOG_PRESENT=true
DIRECT_BASELINE_RESTORED=true
MQTT_CONNECTED=true
BOARD_B_CURRENT_IDENTITY_PRESERVED=true
BOARD_B_CREDENTIAL_GENERATION_UNCHANGED=true
BOARD_B_APPLICATION_KEY_EPOCH_UNCHANGED=true
BOARD_B_PEER_TRUST_GENERATION_UNCHANGED=true
UNPLANNED_REBOOT_DURING_BASELINE=false
```

The lifecycle-generation checks must be read-only and use the same current authority/evidence path previously established for Board B. Do not print secrets.

If baseline is not PASS: STOP and return evidence.

## Physical diagnostic attempt

Only if the stationary baseline is PASS:

1. Board A and Board C remain stationary and powered.
2. Move Mac + Board B + Board B independent power together; do not unplug USB/diagnostic/power wiring.
3. Do not enable Mac hotspot.
4. Reach a location that genuinely removes Board B Direct Wi-Fi while retaining the possibility of ESP-NOW reachability to Board A.
5. Hold for 60 seconds.
6. Return Mac + Board B to Wi-Fi Good without disconnecting power or USB.
7. Continue serial capture for at least 60 seconds after Direct recovery.

Primary evidence is the diagnostic log, not physical distance.

## Final executor closure

Return exactly these adjudication fields plus concise evidence excerpts/timestamps:

```text
=== N3W BOARD B RADIO RESET DIAGNOSTIC CLOSURE ===

DIAGNOSTIC_SOURCE_COMMIT=<sha>
SOURCE_SCOPE_EXACT=true|false
SOURCE_TESTS_PASS=true|false
COMPILE_PASS=true|false
BOARD_B_FLASH_PASS=true|false
BOARD_B_NVS_ERASED=false

RESET_REASON_LOG_PRESENT=true|false
BASELINE_90S_PASS=true|false
BASELINE_UNPLANNED_REBOOT=false|true|UNKNOWN

WIFI_LOSS_STIMULUS_ACHIEVED=true|false|UNKNOWN
DIRECT_TO_DISCOVERY_OBSERVED=true|false|UNKNOWN
RADIO_OWNERSHIP_CONFLICT_OBSERVED=true|false|UNKNOWN
CHANNEL_SWITCH_FAILURE_OBSERVED=true|false|UNKNOWN
ESPNOW_ASYNC_TX_FAILURE_OBSERVED=true|false|UNKNOWN
HANDSHAKE_STAGE_REACHED=NONE|DISCOVERY|CHALLENGE|ACCEPT|RELAY_ACTIVE|UNKNOWN
RELAY_TRANSITION_OBSERVED=true|false|UNKNOWN

BOARD_B_UNPLANNED_REBOOT=true|false
RESET_REASON=<esp_reset_reason numeric/name if known>|NONE|UNKNOWN
RESET_CAUSE_CLASSIFIED=true|false

PRODUCT_REPAIR_REQUIRED=true|false|UNKNOWN

STOP_AFTER_GATE=true
=== END ===
```

Codex must STOP after this closure. It must not implement radio arbitration, reconnect suppression, same-channel-first discovery, async-send semantic changes, or any other product repair in the same execution.