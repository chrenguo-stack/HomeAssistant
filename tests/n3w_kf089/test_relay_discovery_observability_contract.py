import json
import importlib.util
import shutil
import subprocess
import sys
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
    assert "kSchemaVersion = 3U" in header
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
    assert "discovery_rejected" in DIAG_H.read_text(encoding="utf-8")


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
    assert values["schema_version"] == 3
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
