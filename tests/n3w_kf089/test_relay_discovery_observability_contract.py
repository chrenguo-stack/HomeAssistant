from pathlib import Path


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
    assert "kSchemaVersion = 1U" in header
    assert "NVS_READWRITE" in source
    assert "gh_n3w_v2" not in source


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
    assert "node_id" not in source
    assert "system_id" not in source
    assert "secret" not in source.lower()


def test_host_utility_is_read_only_and_namespace_scoped():
    utility = UTILITY.read_text(encoding="utf-8")
    assert "gh_n3w_diag" in utility
    assert "snapshot" in utility
    assert "serial" in utility.lower()
    assert "write_bytes" not in utility
    assert "nvs_erase" not in utility
