from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
HELPER = (
    ROOT
    / "firmware/esphome_rc/board_lab/n3w_boot_session_recovery/recovery_floor_helper.yml"
)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_recovery_helper_is_inert_network_free_and_default_noop() -> None:
    config = text(HELPER)
    lowered = config.lower()

    assert 'recovery_floor_hex: "0000000000000000"' in config
    assert "phase4_source_harness: false" in config
    assert "phase4_product_runtime: false" in config
    assert "priority: -200.0" in config
    assert "kRecoveryFloor == 0ULL" in config
    assert "Recovery floor unset; no write executed" in config
    assert "provision_boot_session_recovery_floor" in config
    assert "BSR_RECOVERY_FLOOR_WRITE=%s" in config

    for forbidden in (
        "\nwifi:",
        "\nmqtt:",
        "\napi:",
        "\nota:",
        "\ncaptive_portal:",
        "\nweb_server:",
    ):
        assert forbidden not in lowered


def test_recovery_surface_is_missing_only_and_product_execution_guarded() -> None:
    core = text(CORE / "greenhouse_n3w_core.h")

    start = core.index("bool provision_boot_session_recovery_floor(uint64_t floor)")
    end = core.index("bool take_telemetry_identity", start)
    body = core[start:end]

    assert "floor == 0" in body
    assert "phase4_product_runtime_enabled_" in body
    assert "phase4_source_harness_enabled_" in body
    assert "runtime_ready()" in body
    assert "boot_session_manager_.ready()" in body
    assert "preexisting != StoreStatus::MISSING" in body
    assert "boot_session_manager_.provision_recovery_floor" in body
    assert "verify_status != StoreStatus::OK || verified != floor" in body
    assert "return true;" in body

    setter_start = core.index("void set_phase4_product_runtime_enabled(bool enabled)")
    setter_end = core.index("Phase4PhysicalHarness *phase4_harness", setter_start)
    setter = core[setter_start:setter_end]
    assert "phase4_product_runtime_enabled_ = enabled" in setter
    assert "set_activation_enabled(enabled)" in setter


def test_recovery_store_stays_on_existing_boot_state_namespace_and_key() -> None:
    store = text(CORE / "n3w_esp32_nvs.h")

    assert 'namespace_name = "gh_n3w"' in store
    assert 'key_name = "boot_state"' in store
    assert "class NvsBootSessionStore final : public BootSessionStore" in store
