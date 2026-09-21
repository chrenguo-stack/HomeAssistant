from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
LAB = ROOT / "firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml"
PROD = (
    ROOT
    / "firmware/esphome_rc/board_lab/n3w_production_core_compile/generic.yml"
)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_lab_target_keeps_pr437_observability_contract() -> None:
    lab = text(LAB)

    assert "phase4_source_harness: true" in lab
    assert "phase4_product_runtime: true" in lab
    assert "phase4_lab_diagnostics: true" in lab
    assert "PHASE4_PAIRING_QR_PAYLOAD" in lab
    assert "PHASE4_LAB_TELEMETRY" in lab
    assert '\\"phase4_lab\\":true' in lab


def test_production_compile_probe_has_no_phase4_lab_switch_or_synthetic_telemetry() -> None:
    prod = text(PROD)

    assert "product_runtime: true" in prod
    assert "phase4_source_harness" not in prod
    assert "phase4_product_runtime" not in prod
    assert "phase4_lab_diagnostics" not in prod
    assert "PHASE4_" not in prod
    assert "phase4_lab" not in prod
    assert "interval:" not in prod
    assert "submit_telemetry_json" not in prod
    assert "measurements" not in prod


def test_codegen_only_enables_lab_macro_for_explicit_lab_configuration() -> None:
    source = text(CORE / "__init__.py")

    assert 'CONF_PRODUCT_RUNTIME = "product_runtime"' in source
    assert 'LAB_BUILD_FLAG = "GREENHOUSE_N3W_ENABLE_PHASE4_LAB"' in source
    assert "lab_enabled = (" in source
    assert "config[CONF_PHASE4_SOURCE_HARNESS]" in source
    assert "config[CONF_PHASE4_LAB_DIAGNOSTICS]" in source
    assert 'cg.add_build_flag(f"-D{LAB_BUILD_FLAG}=1")' in source
    assert "config[CONF_PRODUCT_RUNTIME] or config[CONF_PHASE4_PRODUCT_RUNTIME]" in source


def test_phase4_harness_and_rtc_surface_are_guarded_from_production_core() -> None:
    core = text(CORE / "greenhouse_n3w_core.h")

    assert "#ifdef GREENHOUSE_N3W_ENABLE_PHASE4_LAB" in core
    assert '#include "n3w_phase4_physical_harness.h"' in core
    assert '#include "n3w_rtc_breadcrumb.h"' in core
    assert "Phase4PhysicalHarness phase4_harness_" in core
    assert "N3wRtcBreadcrumbSnapshot previous_rtc_breadcrumb_" in core

    include_guard = (
        '#ifdef GREENHOUSE_N3W_ENABLE_PHASE4_LAB\n'
        '#include "n3w_phase4_physical_harness.h"\n'
        '#include "n3w_rtc_breadcrumb.h"\n'
        "#endif"
    )
    assert include_guard in core


def test_lab_diagnostic_implementation_has_production_noop_surface() -> None:
    header = text(CORE / "n3w_lab_diagnostics.h")
    source = text(CORE / "n3w_lab_diagnostics.cpp")

    assert "#ifdef GREENHOUSE_N3W_ENABLE_PHASE4_LAB" in header
    assert "class N3wLabDiagnostics final : public SimpleProductDiagnosticSink" in header
    assert "Production build stub" in header
    assert "bool enabled() const { return false; }" in header
    assert "#ifdef GREENHOUSE_N3W_ENABLE_PHASE4_LAB" in source


def test_lab_only_espnow_observability_is_compile_time_guarded() -> None:
    header = text(CORE / "n3w_espnow_driver.h")
    source = text(CORE / "n3w_espnow_driver.cpp")

    assert "#ifdef GREENHOUSE_N3W_ENABLE_PHASE4_LAB" in header
    assert "diagnostic_receive_logs_" in header
    assert "diagnostic_broadcast_logs_" in header

    assert "Production builds skip these extra readbacks" in source
    assert "ESP-NOW diagnostic receive" in source
    assert "ESP-NOW diagnostic broadcast completion" in source

    # Lab-only channel/peer readback must sit behind the build gate.
    guarded_observation = (
        "#ifdef GREENHOUSE_N3W_ENABLE_PHASE4_LAB\n"
        "  // Lab-only observation is requested by the diagnostic harness."
    )
    assert guarded_observation in source


def test_product_transport_behavior_files_remain_separate_from_lab_gate() -> None:
    # The de-harness gate must not replace the product state machine or its
    # validated recovery policy. This test intentionally checks that the
    # product implementation still exists as ordinary source, outside a new
    # alternate production implementation.
    component = text(CORE / "n3w_simple_product_component.cpp")
    recovery = text(CORE / "n3w_direct_recovery_policy.cpp")

    assert "flush_telemetry_queue_" in component
    assert "begin_direct_probe_" in component
    assert "restore_relay_radio_" in component
    assert "RelayDirectRecoverySchedule" in recovery
