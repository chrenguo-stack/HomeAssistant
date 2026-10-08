from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_product_core"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def section(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def test_first_pair_boot_floor_precedes_product_pairing_setup() -> None:
    core = text(CORE / "greenhouse_n3w_product_core.h")
    body = section(core, "  void setup() override {", "  void loop() override {")

    assert "if (!product_runtime_enabled_)" in body
    classify = body.index("classify_startup_product_identity_()")
    prepare = body.index("prepare_initial_boot_floor(")
    normal_setup = body.rindex("SimpleProductComponent::setup();")
    assert classify < prepare < normal_setup
    assert "StartupProductIdentityState::INVALID_OR_PARTIAL" in body
    assert "StartupProductIdentityState::PROVEN_FRESH" in body


def test_startup_identity_classification_reads_peer_broker_and_pending_ack() -> None:
    core = text(CORE / "greenhouse_n3w_product_core.h")
    body = section(
        core,
        "  StartupProductIdentityState classify_startup_product_identity_() {",
        "  bool begin_boot_session_if_needed_() {",
    )

    assert "peer_store_.load(&peer)" in body
    assert "broker_store_.load(&broker)" in body
    assert "ack_store_.load(&pending)" in body
    assert "peer.system_id == broker.system_id" in body
    assert "peer.node_id == broker.node_id" in body
    assert "classify_startup_product_identity(" in body
    assert "startup_identity_record_state_" in body


def test_telemetry_path_no_longer_creates_missing_zero_floor() -> None:
    core = text(CORE / "greenhouse_n3w_product_core.h")
    body = section(
        core,
        "  bool begin_boot_session_if_needed_() {",
        "  bool product_runtime_enabled_{false};",
    )

    assert "boot_session_manager_.begin(&boot_session_store_, 0)" in body
    assert "provision_recovery_floor" not in body
    assert "fresh_identity_candidate_" not in core
    assert "persisted_runtime_state_present_" not in core


def test_initial_floor_policy_is_fail_closed_and_idempotent() -> None:
    policy = text(CORE / "n3w_first_pair_boot_policy.h")

    assert "StartupProductIdentityState::PROVEN_FRESH" in policy
    assert "StartupProductIdentityState::EXISTING_IDENTITY" in policy
    assert "StartupProductIdentityState::INVALID_OR_PARTIAL" in policy
    assert "manager->provision_recovery_floor(store, 0)" in policy
    assert "existing == 0 ? CoreError::NONE : CoreError::SESSION_ROLLBACK" in policy
    assert "CoreError::STORE_CORRUPT" in policy
    assert "CoreError::STORE_IO_ERROR" in policy
