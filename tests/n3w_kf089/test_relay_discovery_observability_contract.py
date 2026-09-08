import json
import importlib.util
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import esphome


ROOT = Path(__file__).parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
RUNTIME = CORE / "n3w_simple_product_runtime.cpp"
COMPONENT = CORE / "n3w_simple_product_component.cpp"
DRIVER = CORE / "n3w_espnow_driver.cpp"
DIAG_H = CORE / "n3w_lab_diagnostics.h"
DIAG_CPP = CORE / "n3w_lab_diagnostics.cpp"
UTILITY = ROOT / "tools/n3w_read_diag_snapshot.py"


def test_diagnostic_namespace_and_schema_are_lab_only():
    header = DIAG_H.read_text(encoding="utf-8")
    source = DIAG_CPP.read_text(encoding="utf-8")
    assert '"gh_n3w_diag"' in header
    assert '"snapshot"' in header
    assert "kSchemaVersion = 4U" in header
    assert "NVS_READWRITE" in source
    assert "gh_n3w_v2" not in source


def test_diagnostics_are_explicit_and_disabled_by_default():
    init = (CORE / "__init__.py").read_text(encoding="utf-8")
    core = (CORE / "greenhouse_n3w_core.h").read_text(encoding="utf-8")
    generic = (
        ROOT / "firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml"
    ).read_text(encoding="utf-8")
    assert 'cv.Optional(CONF_PHASE4_LAB_DIAGNOSTICS, default=False)' in init
    assert "phase4_lab_diagnostics: true" in generic
    product_setter = core.split("void set_phase4_product_runtime_enabled", 1)[1].split(
        "void set_phase4_lab_diagnostics_enabled", 1
    )[0]
    assert "set_lab_diagnostics_enabled" not in product_setter


def test_snapshot_has_required_channel_and_path_fields():
    header = DIAG_H.read_text(encoding="utf-8")
    for field in (
        "runtime_start_mode",
        "path_state",
        "current_channel",
        "scan_attempts",
        "scan_successes",
        "scan_failures",
        "channel_attempts",
        "channel_successes",
        "channel_failures",
        "last_requested_channel",
        "last_observed_channel",
        "boot_session",
        "snapshot_uptime_ms",
        "channel_set_attempts",
        "channel_set_successes",
        "channel_set_failures",
        "relay_advertisement_attempts",
        "relay_advertisement_submit_success",
        "relay_advertisement_submit_failure",
        "broadcast_completion_count",
        "broadcast_completion_success",
        "broadcast_completion_failure",
        "discovery_reject_state",
        "discovery_reject_pending",
        "discovery_reject_packet_invalid",
        "discovery_reject_trust_generation",
        "discovery_reject_self",
        "discovery_reject_channel_mismatch",
        "last_discovery_rejection_reason",
        "last_discovery_packet_channel",
        "last_discovery_rx_channel",
    ):
        assert field in header


def test_raw_esp_error_and_readback_are_preserved():
    driver = DRIVER.read_text(encoding="utf-8")
    assert "last_channel_error_raw" in driver
    assert "esp_wifi_set_channel" in driver
    assert "esp_wifi_get_channel" in driver
    assert "static_cast<int32_t>(set_result)" in driver


def test_runtime_tick_return_semantics_remain_unchanged():
    source = COMPONENT.read_text(encoding="utf-8")
    assert "(void) runtime_.tick();" in source


def test_runtime_start_and_channel_observation_are_instrumented():
    runtime = RUNTIME.read_text(encoding="utf-8")
    component = COMPONENT.read_text(encoding="utf-8")
    assert "on_runtime_start" in runtime
    assert "note_channel_result" in component
    assert "return success;" in component


def test_advertisement_and_broadcast_completion_observability_are_lab_only():
    runtime = RUNTIME.read_text(encoding="utf-8")
    component = COMPONENT.read_text(encoding="utf-8")
    assert "on_relay_advertisement(submitted" in runtime
    assert "destination == kEspNowBroadcastMac" in component
    assert "on_broadcast_completion(success" in component


def test_discovery_rx_records_accept_and_reject_stages():
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "on_discovery_rx(accepted" in runtime
    assert "on_discovery_rejected" in runtime
    assert "discovery_rejected" in DIAG_H.read_text(encoding="utf-8")


def test_discovery_rejection_reason_contract_is_stable_and_diagnostic_only():
    runtime_h = (CORE / "n3w_simple_product_runtime.h").read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    diagnostics = DIAG_CPP.read_text(encoding="utf-8")
    expected = (
        "NONE = 0",
        "STATE_NOT_DISCOVERY = 1",
        "PENDING_CHALLENGE = 2",
        "PACKET_INVALID = 3",
        "TRUST_GENERATION_MISMATCH = 4",
        "SELF_RELAY = 5",
        "CHANNEL_MISMATCH = 6",
    )
    for marker in expected:
        assert marker in runtime_h
    assert "on_discovery_rejected(" in runtime_h
    assert "(void) reason;" in runtime_h
    assert "virtual void on_discovery_rejected(" in runtime_h
    dispatch = runtime.split("if (!accepted) {", 1)[1].split("diagnostic_sink_->on_discovery_rx", 1)[0]
    assert dispatch.index("STATE_NOT_DISCOVERY") < dispatch.index("PENDING_CHALLENGE")
    assert dispatch.index("PENDING_CHALLENGE") < dispatch.index("PACKET_INVALID")
    assert dispatch.index("PACKET_INVALID") < dispatch.index("TRUST_GENERATION_MISMATCH")
    assert dispatch.index("TRUST_GENERATION_MISMATCH") < dispatch.index("SELF_RELAY")
    assert dispatch.index("SELF_RELAY") < dispatch.index("CHANNEL_MISMATCH")
    assert diagnostics.count("on_discovery_rejected(") == 1


def test_discovery_rejection_runtime_and_counter_invariants(tmp_path: Path):
    compiler = shutil.which("g++")
    assert compiler is not None
    helper = tmp_path / "n3w-discovery-rejection-host-test.cpp"
    executable = tmp_path / "n3w-discovery-rejection-host-test"
    helper.write_text(
        textwrap.dedent(
            r'''
            #include <cassert>
            #include <cstdint>
            #include <string>
            #include <vector>
            #include "n3w_simple_product_runtime.h"

            using namespace esphome::greenhouse_n3w_core;

            namespace {
            struct Clock final : SimpleProductClock {
              uint64_t now{1000};
              uint64_t now_ms() const override { return now; }
            };
            struct Random final : SimpleProductRandom {
              bool fill(uint8_t *data, std::size_t size) override {
                if (data == nullptr || size == 0) return false;
                for (std::size_t i = 0; i < size; ++i) data[i] = static_cast<uint8_t>(i + 1);
                return true;
              }
            };
            struct Port final : SimpleProductPort {
              uint8_t channel{0};
              std::vector<std::vector<uint8_t>> broadcasts;
              bool set_radio_channel(uint8_t value) override { channel = value; return valid_radio_channel(value); }
              bool broadcast_control(const uint8_t *data, std::size_t size) override {
                broadcasts.emplace_back(data, data + size); return true;
              }
              bool install_encrypted_peer(const MacAddress &, const LinkKey &, uint8_t) override { return true; }
              bool remove_peer(const MacAddress &) override { return true; }
              bool send_encrypted_peer(const MacAddress &, const uint8_t *, std::size_t) override { return true; }
              bool publish_direct(const std::string &, const std::string &) override { return true; }
              bool publish_relay(const std::string &, const std::string &) override { return true; }
            };
            struct Sink final : SimpleProductDiagnosticSink {
              uint32_t accepted{0};
              uint32_t rejected{0};
              std::vector<DiscoveryRejectReason> reasons;
              std::vector<std::pair<uint8_t, uint8_t>> channels;
              void on_runtime_start(uint8_t, uint8_t) override {}
              void on_scan_attempt(uint8_t, uint64_t) override {}
              void on_scan_result(uint8_t, bool, uint8_t, int32_t, uint64_t) override {}
              void on_discovery_rx(bool value, uint64_t) override { value ? ++accepted : ++rejected; }
              void on_discovery_rejected(DiscoveryRejectReason reason, uint8_t packet, uint8_t rx, uint64_t) override {
                reasons.push_back(reason); channels.emplace_back(packet, rx);
              }
              void on_challenge_tx(bool, uint64_t) override {}
              void on_challenge_rx(bool, uint64_t) override {}
              void on_accept_tx(bool, uint64_t) override {}
              void on_accept_rx(bool, uint64_t) override {}
              void on_relay_active(uint64_t) override {}
              void on_relay_telemetry(bool, uint64_t) override {}
              void on_relay_advertisement(bool, uint64_t) override {}
              void on_broadcast_completion(bool, uint64_t) override {}
            };
            ProvisionedPeerStateV2 state(const std::string &node) {
              ProvisionedPeerStateV2 value;
              value.system_id = "gh-system-01";
              value.node_id = node;
              value.peer_trust_generation = 7;
              value.system_peer_key.fill(0xA5);
              value.n3w_key_epoch = 3;
              value.n3w_application_key.fill(0x11);
              assert(value.valid());
              return value;
            }
            std::vector<uint8_t> discovery(const std::string &node, uint64_t generation, uint8_t channel) {
              SimpleRelayDiscovery packet;
              packet.peer_trust_generation = generation;
              packet.relay_node_id = node;
              packet.channel = channel;
              std::vector<uint8_t> encoded;
              assert(encode_simple_relay_discovery(packet, &encoded) == SimpleRuntimeError::NONE);
              return encoded;
            }
            void assert_reason(SimpleProductRuntime &runtime, Sink &sink, const MacAddress &source,
                               const std::vector<uint8_t> &packet, uint8_t rx, DiscoveryRejectReason reason) {
              const SimpleProductError result = runtime.on_radio_receive(
                  source, packet.data(), packet.size(), rx);
              assert(result == SimpleProductError::PACKET_REJECTED ||
                     result == SimpleProductError::STATE_REJECTED);
              assert(!sink.reasons.empty());
              assert(sink.reasons.back() == reason);
              assert(sink.channels.back().second == rx);
            }
            }
            int main() {
              const MacAddress local{0x02, 0, 0, 0, 0, 1};
              const MacAddress relay{0x02, 0, 0, 0, 0, 2};
              const MacAddress other{0x02, 0, 0, 0, 0, 3};
              const auto local_state = state("node_local");
              const auto valid = discovery("node_relay", 7, 6);

              Clock clock; Random random; Port port; Sink sink;
              SimpleProductRuntime runtime(&port, &clock, &random);
              runtime.set_diagnostic_sink(&sink);
              assert(runtime.start(local_state, local, 0, SimpleProductStartMode::DISCOVERY) == SimpleProductError::NONE);
              assert(runtime.on_radio_receive(relay, valid.data(), valid.size(), 6) == SimpleProductError::NONE);
              assert(sink.accepted == 1 && sink.rejected == 0 && sink.reasons.empty());
              assert(runtime.on_radio_receive(relay, valid.data(), valid.size(), 6) == SimpleProductError::STATE_REJECTED);
              assert(sink.reasons.back() == DiscoveryRejectReason::PENDING_CHALLENGE);

              Clock trust_clock; Random trust_random; Port trust_port; Sink trust_sink;
              SimpleProductRuntime trust_runtime(&trust_port, &trust_clock, &trust_random);
              trust_runtime.set_diagnostic_sink(&trust_sink);
              assert(trust_runtime.start(local_state, local, 0, SimpleProductStartMode::DISCOVERY) == SimpleProductError::NONE);
              assert_reason(trust_runtime, trust_sink, relay, discovery("node_relay", 8, 6), 6, DiscoveryRejectReason::TRUST_GENERATION_MISMATCH);

              Clock self_clock; Random self_random; Port self_port; Sink self_sink;
              SimpleProductRuntime self_runtime(&self_port, &self_clock, &self_random);
              self_runtime.set_diagnostic_sink(&self_sink);
              assert(self_runtime.start(local_state, local, 0, SimpleProductStartMode::DISCOVERY) == SimpleProductError::NONE);
              assert_reason(self_runtime, self_sink, other, discovery("node_local", 7, 6), 6, DiscoveryRejectReason::SELF_RELAY);

              Clock channel_clock; Random channel_random; Port channel_port; Sink channel_sink;
              SimpleProductRuntime channel_runtime(&channel_port, &channel_clock, &channel_random);
              channel_runtime.set_diagnostic_sink(&channel_sink);
              assert(channel_runtime.start(local_state, local, 0, SimpleProductStartMode::DISCOVERY) == SimpleProductError::NONE);
              assert_reason(channel_runtime, channel_sink, relay, valid, 11, DiscoveryRejectReason::CHANNEL_MISMATCH);

              Clock state_clock; Random state_random; Port state_port; Sink state_sink;
              SimpleProductRuntime state_runtime(&state_port, &state_clock, &state_random);
              state_runtime.set_diagnostic_sink(&state_sink);
              assert(state_runtime.start(local_state, local, 6) == SimpleProductError::NONE);
              assert_reason(state_runtime, state_sink, relay, valid, 6, DiscoveryRejectReason::STATE_NOT_DISCOVERY);

              Sink packet_sink;
              packet_sink.on_discovery_rejected(DiscoveryRejectReason::PACKET_INVALID, 0, 6, 0);
              assert(packet_sink.reasons.size() == 1);
              assert(packet_sink.reasons.back() == DiscoveryRejectReason::PACKET_INVALID);
              return 0;
            }
            '''
        ),
        encoding="utf-8",
    )
    sources = [
        CORE / "n3w_core.cpp",
        CORE / "n3w_radio.cpp",
        CORE / "n3w_simple_crypto.cpp",
        CORE / "n3w_compact_telemetry.cpp",
        CORE / "n3w_simple_runtime.cpp",
        CORE / "n3w_simple_state_host.cpp",
        CORE / "n3w_simple_product_runtime.cpp",
        helper,
    ]
    subprocess.run(
        [
            compiler, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
            "-Wno-error=unneeded-internal-declaration", "-I", str(CORE),
            *(str(source) for source in sources), "-lmbedcrypto", "-o", str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True)


def test_diagnostic_rejection_counters_are_bounded_and_exactly_once(tmp_path: Path):
    compiler = shutil.which("g++")
    assert compiler is not None
    helper = tmp_path / "n3w-diagnostic-rejection-counter-test.cpp"
    executable = tmp_path / "n3w-diagnostic-rejection-counter-test"
    helper.write_text(
        textwrap.dedent(
            r'''
            #include <cassert>
            #include <cstdint>
            #include "n3w_lab_diagnostics.h"

            using namespace esphome::greenhouse_n3w_core;

            int main() {
              N3wLabDiagnostics diagnostics;
              diagnostics.set_enabled(true);
              diagnostics.begin_boot_session();
              diagnostics.bind_boot_session(0x42, 0);
              const uint32_t before_detail = diagnostics.persist_count();
              const DiscoveryRejectReason reasons[] = {
                  DiscoveryRejectReason::STATE_NOT_DISCOVERY,
                  DiscoveryRejectReason::PENDING_CHALLENGE,
                  DiscoveryRejectReason::PACKET_INVALID,
                  DiscoveryRejectReason::TRUST_GENERATION_MISMATCH,
                  DiscoveryRejectReason::SELF_RELAY,
                  DiscoveryRejectReason::CHANNEL_MISMATCH,
              };
              for (uint8_t i = 0; i < 6; ++i) {
                diagnostics.on_discovery_rejected(reasons[i], 11, 6, 100 + i);
                assert(diagnostics.persist_count() == before_detail);
                diagnostics.on_discovery_rx(false, 100 + i);
              }
              const auto &snapshot = diagnostics.snapshot();
              assert(snapshot.schema_version == 4);
              assert(snapshot.size == sizeof(N3wLabDiagnostics::Snapshot));
              assert(snapshot.discovery_rx == 6);
              assert(snapshot.discovery_rejected == 6);
              assert(snapshot.discovery_reject_state == 1);
              assert(snapshot.discovery_reject_pending == 1);
              assert(snapshot.discovery_reject_packet_invalid == 1);
              assert(snapshot.discovery_reject_trust_generation == 1);
              assert(snapshot.discovery_reject_self == 1);
              assert(snapshot.discovery_reject_channel_mismatch == 1);
              assert(snapshot.last_discovery_rejection_reason == 6);
              assert(snapshot.last_discovery_packet_channel == 11);
              assert(snapshot.last_discovery_rx_channel == 6);
              assert(snapshot.discovery_reject_state + snapshot.discovery_reject_pending +
                     snapshot.discovery_reject_packet_invalid + snapshot.discovery_reject_trust_generation +
                     snapshot.discovery_reject_self + snapshot.discovery_reject_channel_mismatch ==
                     snapshot.discovery_rejected);
              return 0;
            }
            '''
        ),
        encoding="utf-8",
    )
    include_root = Path(esphome.__file__).resolve().parent.parent
    subprocess.run(
        [
            compiler, "-std=c++17", "-O0", "-I", str(CORE), "-I", str(include_root), str(helper),
            str(CORE / "n3w_lab_diagnostics.cpp"), "-o", str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True)


def test_handshake_tx_rx_and_verification_stages_are_distinct():
    runtime = RUNTIME.read_text(encoding="utf-8")
    for marker in (
        "on_challenge_tx",
        "on_challenge_rx",
        "on_accept_tx",
        "on_accept_rx",
        "challenge_tx_success",
        "accept_tx_success",
    ):
        assert marker in runtime or marker in DIAG_H.read_text(encoding="utf-8")


def test_peer_install_and_relay_telemetry_are_counted():
    component = COMPONENT.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "note_peer_install" in component
    assert "on_relay_telemetry" in runtime
    assert "relay_telemetry_success" in DIAG_H.read_text(encoding="utf-8")


def test_persistent_snapshot_is_bounded_and_does_not_include_identity():
    header = DIAG_H.read_text(encoding="utf-8")
    source = DIAG_CPP.read_text(encoding="utf-8")
    assert "sizeof(N3wLabDiagnostics::Snapshot) < 512U" in header
    assert "nvs_set_blob" in source
    assert "node_id" not in header
    assert "system_id" not in header
    assert "MacAddress" not in header


def test_serial_summary_is_bounded_and_redacted_by_construction():
    source = DIAG_CPP.read_text(encoding="utf-8")
    assert "N3W_DIAG_DISCOVERY" in source
    assert "kSummaryIntervalMs = 10000" in source
    for marker in (
        "ad_attempts=%u",
        "ad_submit_success=%u",
        "ad_submit_fail=%u",
        "broadcast_done=%u",
        "broadcast_done_success=%u",
    ):
        assert marker in source
    assert "node_id" not in source
    assert "system_id" not in source
    assert "secret" not in source.lower()


def test_host_utility_is_read_only_and_namespace_scoped():
    utility = UTILITY.read_text(encoding="utf-8")
    assert "gh_n3w_diag" in utility
    assert "snapshot" in utility
    assert "esptool" in utility
    assert "write_bytes" not in utility
    assert "nvs_erase" not in utility
    assert '"--port"' in utility
    assert '"--nvs-offset"' in utility
    assert '"--nvs-size"' in utility
    assert '"no_reset"' in utility


def test_host_utility_extracts_only_diagnostic_blob_from_nvs_layout():
    spec = importlib.util.spec_from_file_location("n3w_diag_reader", UTILITY)
    assert spec is not None and spec.loader is not None
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)

    payload = b"diagnostic-snapshot"
    page = bytearray(b"\xff" * reader.PAGE_SIZE)

    def mark_written(slot: int) -> None:
        bitmap_slot = slot - 2
        bitmap_index = bitmap_slot // 4
        shift = (bitmap_slot % 4) * 2
        page[reader.ENTRY_SIZE + bitmap_index] &= ~(0x03 << shift)
        page[reader.ENTRY_SIZE + bitmap_index] |= 0x02 << shift

    def write_entry(
        slot: int,
        namespace: int,
        entry_type: int,
        key: bytes,
        *,
        span: int = 1,
        chunk_index: int = 0xFF,
    ) -> memoryview:
        start = slot * reader.ENTRY_SIZE
        entry = memoryview(page)[start : start + reader.ENTRY_SIZE]
        entry[0] = namespace
        entry[1] = entry_type
        entry[2] = span
        entry[3] = chunk_index
        entry[8:24] = b"\x00" * 16
        entry[8 : 8 + len(key)] = key
        mark_written(slot)
        return entry

    write_entry(2, 0, 0x01, reader.NAMESPACE.encode())[24] = 1
    blob_index = write_entry(3, 1, 0x48, reader.KEY.encode())
    blob_index[24:28] = len(payload).to_bytes(4, "little")
    blob_index[28] = 1
    blob_index[29] = 1
    blob_data = write_entry(4, 1, 0x42, reader.KEY.encode(), span=2, chunk_index=1)
    blob_data[24:28] = len(payload).to_bytes(4, "little")
    write_entry(5, 1, 0, b"")[: len(payload)] = payload

    assert reader._extract_snapshot_from_nvs(bytes(page)) == payload


def test_diagnostics_behavioral_persistence_and_round_trip(tmp_path: Path):
    compiler = shutil.which("g++")
    assert compiler is not None
    helper = ROOT / "tests/n3w_kf089/n3w_lab_diagnostics_host_test.cpp"
    executable = tmp_path / "n3w-lab-diagnostics-host-test"
    include_root = Path(esphome.__file__).resolve().parent.parent
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O0",
            "-I",
            str(CORE),
            "-I",
            str(include_root),
            str(helper),
            str(CORE / "n3w_lab_diagnostics.cpp"),
            "-o",
            str(executable),
        ],
        check=True,
    )
    blob = tmp_path / "snapshot.bin"
    subprocess.run([str(executable), str(blob)], check=True)
    parsed = subprocess.run(
        [sys.executable, str(UTILITY), "--blob", str(blob)],
        check=True,
        capture_output=True,
        text=True,
    )
    values = json.loads(parsed.stdout)
    assert values["boot_session"] == 0x1122334455667788
    assert values["snapshot_uptime_ms"] == 179750
    assert values["schema_version"] == 4
    assert values["discovery_rejection_reason_supported"] is True
    assert values["discovery_reject_state"] == 0
    assert values["last_discovery_rejection_reason"] == 0
    assert values["scan_attempts"] == 720
    assert values["current_channel"] == 11
    assert values["direct_channel_hint"] == 0
    assert values["relay_advertisement_attempts"] == 0
    assert values["broadcast_completion_count"] == 0


def test_advertisement_behavioral_and_diagnostics_neutrality(tmp_path: Path):
    compiler = shutil.which("g++")
    assert compiler is not None
    executable = tmp_path / "n3w-phase4-runtime-host-test"
    sources = [
        CORE / "n3w_core.cpp",
        CORE / "n3w_radio.cpp",
        CORE / "n3w_simple_crypto.cpp",
        CORE / "n3w_compact_telemetry.cpp",
        CORE / "n3w_simple_runtime.cpp",
        CORE / "n3w_simple_state_host.cpp",
        CORE / "n3w_simple_product_runtime.cpp",
        ROOT / "tests/n3w_phase4/n3w_phase4_runtime_host_test.cpp",
    ]
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wno-error=unneeded-internal-declaration",
            "-I",
            str(CORE),
            *(str(source) for source in sources),
            "-lmbedcrypto",
            "-o",
            str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True)


def test_parser_v3_v4_and_unknown_schema_contract(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("n3w_diag_reader_versions", UTILITY)
    assert spec is not None and spec.loader is not None
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)

    v3 = reader.SnapshotV3()
    v3.magic = reader.MAGIC
    v3.size = reader.ctypes.sizeof(reader.SnapshotV3)
    v3.schema_version = 3
    v3_blob = tmp_path / "snapshot-v3.bin"
    v3_blob.write_bytes(bytes(v3))
    parsed_v3 = subprocess.run(
        [sys.executable, str(UTILITY), "--blob", str(v3_blob)],
        check=True,
        capture_output=True,
        text=True,
    )
    v3_values = json.loads(parsed_v3.stdout)
    assert v3_values["schema_version"] == 3
    assert v3_values["discovery_rejection_reason_supported"] is False
    assert "discovery_reject_state" not in v3_values

    v4 = reader.SnapshotV4()
    v4.magic = reader.MAGIC
    v4.size = reader.ctypes.sizeof(reader.SnapshotV4)
    v4.schema_version = 4
    v4.discovery_reject_channel_mismatch = 9
    v4.last_discovery_rejection_reason = 6
    v4.last_discovery_packet_channel = 11
    v4.last_discovery_rx_channel = 6
    v4_blob = tmp_path / "snapshot-v4.bin"
    v4_blob.write_bytes(bytes(v4))
    parsed_v4 = subprocess.run(
        [sys.executable, str(UTILITY), "--blob", str(v4_blob)],
        check=True,
        capture_output=True,
        text=True,
    )
    v4_values = json.loads(parsed_v4.stdout)
    assert v4_values["schema_version"] == 4
    assert v4_values["discovery_rejection_reason_supported"] is True
    assert v4_values["discovery_reject_channel_mismatch"] == 9
    assert v4_values["last_discovery_rejection_reason"] == 6
    assert v4_values["last_discovery_packet_channel"] == 11
    assert v4_values["last_discovery_rx_channel"] == 6

    unknown = bytearray(bytes(v4))
    unknown[4:6] = (99).to_bytes(2, "little")
    unknown_blob = tmp_path / "snapshot-unknown.bin"
    unknown_blob.write_bytes(unknown)
    assert subprocess.run(
        [sys.executable, str(UTILITY), "--blob", str(unknown_blob)],
        check=False,
    ).returncode != 0

    for schema, blob in ((3, v3_blob), (4, v4_blob)):
        wrong_size = tmp_path / f"snapshot-v{schema}-wrong-size.bin"
        wrong_size.write_bytes(blob.read_bytes() + b"\x00")
        assert subprocess.run(
            [sys.executable, str(UTILITY), "--blob", str(wrong_size)],
            check=False,
        ).returncode != 0
