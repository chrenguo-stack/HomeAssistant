from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
TARGET = ROOT / "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml"
TRANSPORT = ROOT / "firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml"
WORKFLOW = ROOT / ".github/workflows/n3w-board-d-r4-production-deharness-ci.yml"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_product_runtime_enables_compile_time_deharness() -> None:
    init = text(CORE / "__init__.py")
    assert "production_deharness = (" in init
    assert "config[CONF_PRODUCT_RUNTIME]" in init
    assert "and not config[CONF_PHASE4_SOURCE_HARNESS]" in init
    assert "and not config[CONF_PHASE4_PRODUCT_RUNTIME]" in init
    assert "and not config[CONF_PHASE4_LAB_DIAGNOSTICS]" in init
    assert "if not production_deharness:" in init
    assert 'cg.add_build_flag("-DGH_N3W_PRODUCTION_DEHARNESS=1")' in init

    target = text(TARGET)
    transport = text(TRANSPORT)
    assert "n3w_product_transport.yml" in target
    assert "product_runtime: true" in transport
    assert "phase4_lab_diagnostics: true" not in transport


def test_production_component_uses_noop_diagnostics_stub() -> None:
    header = text(CORE / "n3w_simple_product_component.h")
    stub = text(CORE / "n3w_product_diagnostics_stub.h")

    assert "#ifdef GH_N3W_PRODUCTION_DEHARNESS" in header
    assert '#include "n3w_product_diagnostics_stub.h"' in header
    assert "using ActiveN3wDiagnostics = N3wProductDiagnosticsStub;" in header
    assert "runtime_.set_diagnostic_sink(nullptr);" in header
    assert "class N3wProductDiagnosticsStub final" in stub
    assert "gh_n3w_diag" not in stub
    assert "N3W_DIAG_DISCOVERY" not in stub


def test_lab_translation_units_are_not_auto_compiled_in_production() -> None:
    assert not (CORE / "n3w_lab_diagnostics.cpp").exists()
    assert not (CORE / "n3w_phase4_physical_harness.cpp").exists()
    assert not (CORE / "n3w_rtc_breadcrumb.cpp").exists()

    diagnostics = text(CORE / "n3w_diag_support.cpp")
    phase4 = text(CORE / "n3w_phase4_support.cpp")
    rtc = text(CORE / "n3w_rtc_support.cpp")
    core_header = text(CORE / "greenhouse_n3w_core.h")

    assert not (CORE / "n3w_lab_diagnostics_impl.h").exists()
    assert not (CORE / "n3w_phase4_physical_harness_impl.h").exists()
    assert not (CORE / "n3w_rtc_breadcrumb_impl.h").exists()
    assert 'static const char *const TAG = "gh_n3w_diag";' in diagnostics
    assert "Phase4PhysicalHarness::prepare_source_only" in phase4
    assert "RTC_NOINIT_ATTR" in rtc
    assert diagnostics.startswith("#ifndef GH_N3W_PRODUCTION_DEHARNESS\n")
    assert phase4.startswith("#ifndef GH_N3W_PRODUCTION_DEHARNESS\n")
    assert rtc.startswith("#ifndef GH_N3W_PRODUCTION_DEHARNESS\n")
    assert diagnostics.rstrip().endswith("#endif")
    assert phase4.rstrip().endswith("#endif")
    assert rtc.rstrip().endswith("#endif")
    assert '#include "n3w_phase4_physical_harness.h"' in core_header
    assert '#include "n3w_rtc_breadcrumb.h"' in core_header


def test_deharness_ci_fails_explicitly_when_forbidden_marker_is_found() -> None:
    workflow = text(WORKFLOW)
    assert 'for file in /tmp/n3w-symbols.txt "$MAP" /tmp/n3w-app-strings.txt /tmp/n3w-factory-strings.txt; do' in workflow
    assert 'if grep -Fq "$marker" "$file"; then' in workflow
    assert 'echo "FORBIDDEN_MARKER_PRESENT=$marker"' in workflow
    assert 'echo "FORBIDDEN_MARKER_FILE=$file"' in workflow
    assert "exit 1" in workflow
    assert '! grep -Fq "$marker"' not in workflow
