#include <cassert>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

#include "n3w_simple_product_runtime.h"

using namespace esphome::greenhouse_n3w_core;

namespace {

struct FakeClock final : SimpleProductClock {
  uint64_t value{1000};
  uint64_t now_ms() const override { return value; }
};

struct FakeRandom final : SimpleProductRandom {
  uint8_t seed{1};
  bool fill(uint8_t *data, std::size_t size) override {
    if (data == nullptr || size == 0) return false;
    for (std::size_t i = 0; i < size; ++i) data[i] = seed++;
    return true;
  }
};

struct InstalledPeer {
  MacAddress mac{};
  LinkKey lmk{};
  uint8_t channel{0};
};

struct FakePort final : SimpleProductPort {
  uint8_t channel{0};
  std::vector<std::vector<uint8_t>> broadcasts;
  std::vector<std::pair<MacAddress, std::vector<uint8_t>>> encrypted;
  std::vector<InstalledPeer> installed;
  std::vector<MacAddress> removed;
  std::vector<std::pair<std::string, std::string>> direct;
  std::vector<std::pair<std::string, std::string>> relay;
  bool direct_success{true};
  bool broadcast_success{true};
  bool encrypted_success{true};
  bool relay_success{true};
  bool channel_success{true};
  FakeClock *channel_clock{nullptr};
  uint64_t channel_advance_ms{0};
  std::vector<uint8_t> channel_set_attempts;

  bool set_radio_channel(uint8_t value) override {
    channel_set_attempts.push_back(value);
    if (!channel_success || !valid_radio_channel(value)) {
      return false;
    }
    channel = value;
    if (channel_clock != nullptr) {
      channel_clock->value += channel_advance_ms;
    }
    return true;
  }
  bool broadcast_control(const uint8_t *data, std::size_t size) override {
    broadcasts.emplace_back(data, data + size);
    return broadcast_success;
  }
  bool install_encrypted_peer(
      const MacAddress &mac,
      const LinkKey &lmk,
      uint8_t value) override {
    installed.push_back({mac, lmk, value});
    return true;
  }
  bool remove_peer(const MacAddress &mac) override {
    removed.push_back(mac);
    return true;
  }
  bool send_encrypted_peer(
      const MacAddress &mac,
      const uint8_t *data,
      std::size_t size) override {
    encrypted.push_back({mac, std::vector<uint8_t>(data, data + size)});
    return encrypted_success;
  }
  bool publish_direct(const std::string &topic, const std::string &payload) override {
    direct.push_back({topic, payload});
    return direct_success;
  }
  bool publish_relay(const std::string &topic, const std::string &payload) override {
    relay.push_back({topic, payload});
    return relay_success;
  }
};

struct RecordingDiagnosticSink final : SimpleProductDiagnosticSink {
  uint32_t advertisement_attempts{0};
  uint32_t advertisement_successes{0};
  uint32_t advertisement_failures{0};
  uint32_t direct_path_successes{0};
  uint32_t direct_path_failures{0};
  uint32_t compact_rx{0};
  uint32_t compact_state_reject{0};
  uint32_t compact_child_binding_failure{0};
  uint32_t compact_decode_success{0};
  uint32_t compact_decode_failure{0};
  uint32_t compact_forward_attempts{0};
  uint32_t compact_forward_success{0};
  uint32_t compact_forward_failure{0};

  void on_runtime_start(uint8_t, uint8_t) override {}
  void on_scan_attempt(uint8_t, uint64_t) override {}
  void on_scan_result(uint8_t, bool, uint8_t, int32_t, uint64_t) override {}
  void on_direct_path_result(bool success, uint64_t) override {
    if (success) {
      ++direct_path_successes;
    } else {
      ++direct_path_failures;
    }
  }
  void on_discovery_rx(bool, uint64_t) override {}
  void on_challenge_tx(bool, uint64_t) override {}
  void on_challenge_rx(bool, uint64_t) override {}
  void on_accept_tx(bool, uint64_t) override {}
  void on_accept_rx(bool, uint64_t) override {}
  void on_relay_active(uint64_t) override {}
  void on_relay_telemetry(bool, uint64_t) override {}
  void on_relay_advertisement(bool submitted, uint64_t) override {
    ++advertisement_attempts;
    if (submitted) {
      ++advertisement_successes;
    } else {
      ++advertisement_failures;
    }
  }
  void on_broadcast_completion(bool, uint64_t) override {}
  void on_compact_rx(uint64_t) override { ++compact_rx; }
  void on_compact_state_rejected(uint64_t) override { ++compact_state_reject; }
  void on_compact_child_binding_failure(uint64_t) override {
    ++compact_child_binding_failure;
  }
  void on_compact_decode(bool success, uint64_t) override {
    (success ? ++compact_decode_success : ++compact_decode_failure);
  }
  void on_compact_forward_attempt(uint64_t) override { ++compact_forward_attempts; }
  void on_compact_forward_submit(bool success, uint64_t) override {
    (success ? ++compact_forward_success : ++compact_forward_failure);
  }
};

ProvisionedPeerStateV2 make_state(const std::string &node_id, uint8_t app_key_byte) {
  ProvisionedPeerStateV2 state;
  state.system_id = "gh-system-01";
  state.node_id = node_id;
  state.peer_trust_generation = 7;
  state.system_peer_key.fill(0xA5);
  state.n3w_key_epoch = 3;
  state.n3w_application_key.fill(app_key_byte);
  assert(state.valid());
  return state;
}

}  // namespace

int main() {
  const MacAddress offline_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0x0C};
  const auto offline_state = make_state("node_offline", 0x33);

  {
    FakeClock invalid_clock;
    FakeRandom invalid_random;
    FakePort invalid_port;
    SimpleProductRuntime invalid_runtime(
        &invalid_port, &invalid_clock, &invalid_random);
    assert(
        invalid_runtime.start(
            offline_state,
            offline_mac,
            0,
            SimpleProductStartMode::DIRECT) ==
        SimpleProductError::INVALID_ARGUMENT);
  }

  {
    FakeClock offline_clock;
    FakeRandom offline_random;
    FakePort offline_port;
    SimpleProductRuntime offline(
        &offline_port, &offline_clock, &offline_random);
    assert(
        offline.start(
            offline_state,
            offline_mac,
            0,
            SimpleProductStartMode::DISCOVERY) == SimpleProductError::NONE);
    assert(offline.path_state() == LocalPathState::DISCOVERY);
    assert(offline.direct_channel_hint() == 0);
    assert(offline_port.channel == 1);

    offline_clock.value += 250;
    assert(offline.tick() == SimpleProductError::NONE);
    assert(offline_port.channel == 6);

    assert(offline.update_direct_channel_hint(11));
    assert(offline.note_direct_recovery_probe(true) == SimpleProductError::NONE);
    assert(offline.path_state() == LocalPathState::DISCOVERY);

    // The second successful probe would normally commit Direct. A concrete
    // channel-restore failure must leave the logical path in Discovery rather
    // than creating DIRECT + DIRECT_PROBE and permanently suppressing sends.
    offline_port.channel_success = false;
    assert(
        offline.note_direct_recovery_probe(true) ==
        SimpleProductError::RADIO_FAILED);
    assert(offline.path_state() == LocalPathState::DISCOVERY);
    assert(offline_port.channel == 6);

    // A failed commit resets Direct-recovery hysteresis; two new successful
    // probes are required before Direct is committed.
    offline_port.channel_success = true;
    assert(offline.note_direct_recovery_probe(true) == SimpleProductError::NONE);
    assert(offline.path_state() == LocalPathState::DISCOVERY);
    assert(offline.note_direct_recovery_probe(true) == SimpleProductError::NONE);
    assert(offline.path_state() == LocalPathState::DIRECT);
    assert(offline_port.channel == 11);
  }

  // Gateway evidence contract: local advertisement attempts/submission are
  // distinct from the lower-level broadcast completion oracle. If gateway
  // ad_submit_success > 0 but broadcast_done_success == 0, investigate the
  // lower-level ESP-NOW completion path; if discovery_rx > 0, continue
  // challenge/accept adjudication. Diagnostics must not change direct
  // scheduling, bytes, path state, or tick results.
  {
    FakeClock enabled_clock;
    FakeRandom enabled_random;
    FakePort enabled_port;
    RecordingDiagnosticSink enabled_sink;
    SimpleProductRuntime enabled_runtime(
        &enabled_port, &enabled_clock, &enabled_random);
    enabled_runtime.set_diagnostic_sink(&enabled_sink);
    assert(enabled_runtime.start(offline_state, offline_mac, 6) ==
           SimpleProductError::NONE);
    enabled_runtime.set_relay_capable(true);
    std::vector<SimpleProductError> enabled_results;
    for (uint64_t now = 1000; now < 21000; now += 250) {
      enabled_clock.value = now;
      enabled_results.push_back(enabled_runtime.tick());
    }
    assert(enabled_sink.advertisement_attempts == 10);
    assert(enabled_sink.advertisement_successes == 10);
    assert(enabled_sink.advertisement_failures == 0);
    assert(enabled_port.broadcasts.size() == 10);
    assert(enabled_runtime.path_state() == LocalPathState::DIRECT);

    FakeClock disabled_clock;
    FakeRandom disabled_random;
    FakePort disabled_port;
    SimpleProductRuntime disabled_runtime(
        &disabled_port, &disabled_clock, &disabled_random);
    assert(disabled_runtime.start(offline_state, offline_mac, 6) ==
           SimpleProductError::NONE);
    disabled_runtime.set_relay_capable(true);
    std::vector<SimpleProductError> disabled_results;
    for (uint64_t now = 1000; now < 21000; now += 250) {
      disabled_clock.value = now;
      disabled_results.push_back(disabled_runtime.tick());
    }
    assert(disabled_results == enabled_results);
    assert(disabled_port.broadcasts == enabled_port.broadcasts);
    assert(disabled_runtime.path_state() == enabled_runtime.path_state());

    FakeClock failed_clock;
    FakeRandom failed_random;
    FakePort failed_port;
    failed_port.broadcast_success = false;
    RecordingDiagnosticSink failed_sink;
    SimpleProductRuntime failed_runtime(
        &failed_port, &failed_clock, &failed_random);
    failed_runtime.set_diagnostic_sink(&failed_sink);
    assert(failed_runtime.start(offline_state, offline_mac, 6) ==
           SimpleProductError::NONE);
    failed_runtime.set_relay_capable(true);
    for (uint64_t now = 1000; now < 21000; now += 250) {
      failed_clock.value = now;
      const SimpleProductError result = failed_runtime.tick();
      assert(result == ((now - 1000) % 2000 == 0
                            ? SimpleProductError::RADIO_FAILED
                            : SimpleProductError::NONE));
    }
    assert(failed_sink.advertisement_attempts == 10);
    assert(failed_sink.advertisement_successes == 0);
    assert(failed_sink.advertisement_failures == 10);
    assert(failed_port.broadcasts.size() == 10);
    assert(failed_runtime.path_state() == LocalPathState::DIRECT);
  }

  FakeClock child_clock;
  FakeClock relay_clock;
  FakeRandom child_random;
  FakeRandom relay_random;
  FakePort child_port;
  FakePort relay_port;

  const MacAddress child_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0x0B};
  const MacAddress relay_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0x0A};
  const auto child_state = make_state("node_child", 0x11);
  const auto relay_state = make_state("node_relay", 0x22);

  SimpleProductRuntime child(&child_port, &child_clock, &child_random);
  SimpleProductRuntime relay(&relay_port, &relay_clock, &relay_random);
  RecordingDiagnosticSink relay_sink;
  relay.set_diagnostic_sink(&relay_sink);
  assert(child.start(child_state, child_mac, 6) == SimpleProductError::NONE);
  assert(relay.start(relay_state, relay_mac, 6) == SimpleProductError::NONE);

  const std::string direct_json =
      R"({"schema":"gh.telemetry/1","node_id":"node_child","boot_id":"boot_0000000000000001","seq":1})";
  assert(child.send_telemetry(direct_json, "boot_0000000000000001", 1) == SimpleProductError::NONE);
  assert(child_port.direct.size() == 1);

  child_port.direct_success = false;
  for (uint32_t seq = 2; seq <= 4; ++seq) {
    const SimpleProductError result = child.send_telemetry(
        direct_json, "boot_0000000000000001", seq);
    assert(result == SimpleProductError::MQTT_FAILED || result == SimpleProductError::NONE);
  }
  assert(child.path_state() == LocalPathState::DISCOVERY);
  assert(child_port.channel == 6);

  relay_clock.value = 2000;
  assert(relay.tick() == SimpleProductError::NONE);
  assert(!relay_port.broadcasts.empty());
  const auto discovery = relay_port.broadcasts.back();
  assert(child.on_radio_receive(relay_mac, discovery.data(), discovery.size(), 6) ==
         SimpleProductError::NONE);
  assert(!child_port.broadcasts.empty());

  const auto challenge = child_port.broadcasts.back();
  assert(relay.on_radio_receive(child_mac, challenge.data(), challenge.size(), 6) ==
         SimpleProductError::NONE);
  assert(relay.relay_child_count() == 1);
  assert(!relay_port.broadcasts.empty());

  const auto accept = relay_port.broadcasts.back();

  // Accept verification must not commit RelayActive until the concrete radio
  // can be fixed on the authenticated Relay channel.
  const std::size_t installed_before_accept = child_port.installed.size();
  child_port.channel_success = false;
  assert(child.on_radio_receive(relay_mac, accept.data(), accept.size(), 6) ==
         SimpleProductError::RADIO_FAILED);
  assert(child.path_state() == LocalPathState::DISCOVERY);
  assert(!child.active_relay().has_value());
  assert(child_port.installed.size() == installed_before_accept);

  child_port.channel_success = true;
  const std::size_t channel_sets_before_accept =
      child_port.channel_set_attempts.size();
  assert(child.on_radio_receive(relay_mac, accept.data(), accept.size(), 6) ==
         SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);
  assert(child.active_relay().has_value());
  assert(child_port.channel_set_attempts.size() ==
         channel_sets_before_accept + 1);
  assert(child_port.channel_set_attempts.back() == 6);
  assert(child_port.channel == 6);
  assert(!child_port.installed.empty());
  assert(!relay_port.installed.empty());
  assert(child_port.installed.back().lmk == relay_port.installed.back().lmk);

  assert(child.update_direct_channel_hint(11));
  assert(child.note_direct_recovery_probe(true) == SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);
  child_port.channel_clock = &child_clock;
  child_port.channel_advance_ms = 2;
  const uint64_t commit_deadline = child_clock.value + 1;
  const auto late_commit =
      child.commit_direct_recovery_before(commit_deadline);
  assert(!late_commit.committed);
  assert(late_commit.error == SimpleProductError::STATE_REJECTED);
  assert(late_commit.completed_at_ms >= commit_deadline);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);
  assert(child.active_relay().has_value());
  assert(child_port.channel == 11);
  child_port.channel_advance_ms = 0;
  assert(child.rebind_radio_state() == SimpleProductError::NONE);
  assert(child_port.channel == 6);
  assert(child.active_relay().has_value());

  // A bounded Direct probe tears down concrete ESP-NOW state. Rebinding must
  // restore both the Relay channel and the authenticated encrypted peer.
  const std::size_t installed_before_rebind = child_port.installed.size();
  child_port.channel = 1;
  assert(child.rebind_radio_state() == SimpleProductError::NONE);
  assert(child_port.channel == 6);
  assert(child_port.installed.size() == installed_before_rebind + 1);
  assert(child_port.installed.back().mac == relay_mac);

  relay.set_relay_capable(true);
  child_port.direct_success = true;
  const std::string relay_json =
      R"({"schema":"gh.telemetry/1","node_id":"node_child","boot_id":"boot_0000000000000001","seq":5})";
  assert(child.send_telemetry(relay_json, "boot_0000000000000001", 5) ==
         SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);
  assert(child_port.encrypted.size() == 1);
  const auto &encoded = child_port.encrypted.back().second;
  assert(relay.on_radio_receive(child_mac, encoded.data(), encoded.size(), 6) ==
         SimpleProductError::NONE);
  assert(relay_port.relay.size() == 1);
  assert(relay_port.relay.back().first ==
         "gh/v1/gh-system-01/ingress/gateway/node_relay/node_child/frame");
  assert(relay_port.relay.back().second.find("N3W2") != std::string::npos ||
         !relay_port.relay.back().second.empty());
  assert(relay_sink.compact_rx == 1);
  assert(relay_sink.compact_decode_success == 1);
  assert(relay_sink.compact_forward_attempts == 1);
  assert(relay_sink.compact_forward_success == 1);

  const MacAddress unknown_mac{0x02, 0x00, 0x00, 0x00, 0x00, 0x09};
  assert(relay.on_radio_receive(unknown_mac, encoded.data(), encoded.size(), 6) ==
         SimpleProductError::PACKET_REJECTED);
  assert(relay_sink.compact_child_binding_failure == 1);

  std::vector<uint8_t> malformed = encoded;
  malformed[3] ^= 0x01;
  assert(relay.on_radio_receive(child_mac, malformed.data(), malformed.size(), 6) ==
         SimpleProductError::PACKET_REJECTED);
  assert(relay_sink.compact_decode_failure == 1);

  relay_port.relay_success = false;
  assert(relay.on_radio_receive(child_mac, encoded.data(), encoded.size(), 6) ==
         SimpleProductError::MQTT_FAILED);
  assert(relay_sink.compact_forward_attempts == 2);
  assert(relay_sink.compact_forward_failure == 1);

  // KF-092: synchronous submit acceptance is not delivery success. Only an
  // actual completion for the current Relay destination changes hysteresis.
  const MacAddress broadcast_mac{0xff, 0xff, 0xff, 0xff, 0xff, 0xff};
  assert(child.note_relay_delivery_result(broadcast_mac, false) ==
         SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);
  assert(child.note_relay_delivery_result(unknown_mac, false) ==
         SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);

  assert(child.note_relay_delivery_result(relay_mac, false) ==
         SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);
  assert(child.note_relay_delivery_result(relay_mac, true) ==
         SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);
  assert(child.note_relay_delivery_result(relay_mac, false) ==
         SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);

  // Immediate submit failure counts as the next Relay failure without waiting
  // for an asynchronous completion.
  child_port.encrypted_success = false;
  assert(child.send_telemetry(relay_json, "boot_0000000000000001", 6) ==
         SimpleProductError::RADIO_FAILED);
  assert(child.path_state() == LocalPathState::DISCOVERY);
  assert(!child.active_relay().has_value());
  child_port.encrypted_success = true;

  // Reacquire the Relay and prove two consecutive actual MAC failures drive
  // the existing relay_failures_to_discovery hysteresis.
  relay_clock.value = 4000;
  assert(relay.tick() == SimpleProductError::NONE);
  const auto discovery2 = relay_port.broadcasts.back();
  assert(child.on_radio_receive(relay_mac, discovery2.data(), discovery2.size(), 6) ==
         SimpleProductError::NONE);
  const auto challenge2 = child_port.broadcasts.back();
  assert(relay.on_radio_receive(child_mac, challenge2.data(), challenge2.size(), 6) ==
         SimpleProductError::NONE);
  const auto accept2 = relay_port.broadcasts.back();
  assert(child.on_radio_receive(relay_mac, accept2.data(), accept2.size(), 6) ==
         SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);

  assert(child.note_relay_delivery_result(relay_mac, false) ==
         SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);
  assert(child.note_relay_delivery_result(relay_mac, false) ==
         SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::DISCOVERY);
  assert(!child.active_relay().has_value());

  assert(child.note_direct_recovery_probe(true) == SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::DISCOVERY);
  assert(child.note_direct_recovery_probe(true) == SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::DIRECT);
  assert(!child.active_relay().has_value());

  // KF-096 successor: a bounded Relay restore exhaustion must be able to
  // abandon a stale Relay binding, enter Discovery, and later recover Direct.
  child_port.direct_success = false;
  for (uint32_t seq = 7; seq <= 9; ++seq) {
    (void) child.send_telemetry(
        direct_json, "boot_0000000000000001", seq);
  }
  assert(child.path_state() == LocalPathState::DISCOVERY);

  relay_clock.value = 6000;
  assert(relay.tick() == SimpleProductError::NONE);
  const auto discovery3 = relay_port.broadcasts.back();
  assert(child.on_radio_receive(relay_mac, discovery3.data(), discovery3.size(), 6) ==
         SimpleProductError::NONE);
  const auto challenge3 = child_port.broadcasts.back();
  assert(relay.on_radio_receive(child_mac, challenge3.data(), challenge3.size(), 6) ==
         SimpleProductError::NONE);
  const auto accept3 = relay_port.broadcasts.back();
  assert(child.on_radio_receive(relay_mac, accept3.data(), accept3.size(), 6) ==
         SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::RELAY_ACTIVE);
  assert(child.active_relay().has_value());

  assert(child.reset_to_discovery_after_radio_fault() ==
         SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::DISCOVERY);
  assert(!child.active_relay().has_value());

  child_port.direct_success = true;
  assert(child.note_direct_recovery_probe(true) == SimpleProductError::NONE);
  assert(child.path_state() == LocalPathState::DISCOVERY);
  child_port.channel_clock = &child_clock;
  child_port.channel_advance_ms = 0;
  const auto timely_commit =
      child.commit_direct_recovery_before(child_clock.value + 1000);
  assert(timely_commit.error == SimpleProductError::NONE);
  assert(timely_commit.committed);
  assert(timely_commit.completed_at_ms < child_clock.value + 1000);
  assert(child.path_state() == LocalPathState::DIRECT);


  // Backlog retries must not compress Direct path hysteresis. TRANSPORT_ONLY
  // retries preserve the queued payload without counting as fresh business
  // path-health observations; RECORD_PATH_RESULT keeps the original policy.
  {
    FakeClock accounting_clock;
    FakeRandom accounting_random;
    FakePort accounting_port;
    SimpleProductRuntime accounting_runtime(
        &accounting_port, &accounting_clock, &accounting_random);
    assert(
        accounting_runtime.start(
            make_state("node_accounting", 0x44),
            MacAddress{0x02, 0x00, 0x00, 0x00, 0x00, 0x44},
            6,
            SimpleProductStartMode::DIRECT) == SimpleProductError::NONE);
    accounting_port.direct_success = false;
    const std::string accounting_json =
        R"({"schema":"gh.telemetry/1","seq":1})";
    for (uint32_t seq = 1; seq <= 5; ++seq) {
      assert(
          accounting_runtime.send_telemetry(
              accounting_json,
              "boot_0000000000000001",
              seq,
              TelemetryPathAccounting::TRANSPORT_ONLY) ==
          SimpleProductError::MQTT_FAILED);
      assert(accounting_runtime.path_state() == LocalPathState::DIRECT);
    }
    for (uint32_t seq = 6; seq <= 8; ++seq) {
      const SimpleProductError result =
          accounting_runtime.send_telemetry(
              accounting_json,
              "boot_0000000000000001",
              seq,
              TelemetryPathAccounting::RECORD_PATH_RESULT);
      assert(
          result == SimpleProductError::MQTT_FAILED ||
          result == SimpleProductError::NONE);
    }
    assert(accounting_runtime.path_state() == LocalPathState::DISCOVERY);
  }

  // Regression for PR #437 / physical failure evidence 5747743275.
  // Model the transition hold FIFO as already full. TRANSPORT_ONLY backlog
  // work must not advance hysteresis, while each new Direct/no-MQTT business
  // sample must advance it before queue admission can reject the newest item.
  {
    FakeClock liveness_clock;
    FakeRandom liveness_random;
    FakePort liveness_port;
    RecordingDiagnosticSink liveness_sink;
    SimpleProductRuntime liveness_runtime(
        &liveness_port, &liveness_clock, &liveness_random);
    liveness_runtime.set_diagnostic_sink(&liveness_sink);
    assert(
        liveness_runtime.start(
            make_state("node_full_buffer_liveness", 0x55),
            MacAddress{0x02, 0x00, 0x00, 0x00, 0x00, 0x55},
            11,
            SimpleProductStartMode::DIRECT) == SimpleProductError::NONE);

    constexpr std::size_t simulated_hold_capacity = 24;
    std::size_t simulated_hold_depth = simulated_hold_capacity;
    liveness_port.direct_success = false;
    const std::string json =
        R"({"schema":"gh.telemetry/1","seq":100})";

    for (uint32_t sample = 0; sample < 3; ++sample) {
      // Background queue service is transport-only. Even repeated failed
      // transport polls cannot compress the three-business-sample threshold.
      for (uint32_t poll = 0; poll < 5; ++poll) {
        assert(
            liveness_runtime.send_telemetry(
                json,
                "boot_0000000000000001",
                100 + (sample * 10) + poll,
                TelemetryPathAccounting::TRANSPORT_ONLY) ==
            SimpleProductError::MQTT_FAILED);
        assert(liveness_runtime.path_state() == LocalPathState::DIRECT);
      }

      const TelemetryAdmissionPlan plan =
          plan_business_telemetry_admission(
              liveness_runtime.path_state(), false);
      assert(plan.record_direct_unavailable);
      assert(
          plan.front_accounting ==
          TelemetryPathAccounting::TRANSPORT_ONLY);

      // The queue is intentionally full: admission would reject newest, but
      // path health is recorded before that capacity decision in the component.
      assert(simulated_hold_depth == simulated_hold_capacity);
      assert(
          liveness_runtime.note_direct_result(false) ==
          SimpleProductError::NONE);
      assert(simulated_hold_depth == simulated_hold_capacity);

      if (sample < 2) {
        assert(liveness_runtime.path_state() == LocalPathState::DIRECT);
      }
    }

    assert(liveness_runtime.path_state() == LocalPathState::DISCOVERY);
    assert(liveness_sink.direct_path_failures == 3);
    assert(liveness_sink.direct_path_successes == 0);
  }

  return 0;
}
