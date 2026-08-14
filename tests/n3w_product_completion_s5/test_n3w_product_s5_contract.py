import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "docs/decisions/n3w-product-completion-s5-two-board-isolated-physical-20260814.json"
BOARD_DIR = ROOT / "firmware/esphome_rc/board_lab/n3w_product_completion_s5"
RUNTIME_DIR = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_product_runtime"


def test_decision_record_bounds_this_round_before_physical_execution():
    decision = json.loads(DECISION.read_text())
    assert decision["base_sha"] == "38c3b692d4ebe90d0040c732b6c0313fdfdc1ef6"
    assert decision["status"] == "minimal_s3_s4_board_integration_compile_ci_candidate"
    assert decision["safety_boundary"]["flash_executed"] is False
    assert decision["safety_boundary"]["espnow_rf_execution_started"] is False
    assert "physical_board_flash" in decision["current_round"]["not_claimed"]


def test_child_and_relay_compile_the_same_inert_generic_component():
    child = (BOARD_DIR / "child.yml").read_text()
    relay = (BOARD_DIR / "relay.yml").read_text()
    for profile in (child, relay):
        assert "greenhouse_n3w_product_runtime:" in profile
        assert "execution_enabled: false" in profile
        assert "!env_var S5_BUILD_PATH" in profile
    assert "role: child" in child
    assert "role: relay" in relay


def test_public_profiles_have_no_fixed_peer_or_environment_identity():
    combined = "\n".join(
        line
        for path in BOARD_DIR.glob("*.yml")
        for line in path.read_text().splitlines()
        if not line.lstrip().startswith("#")
    )
    forbidden = (
        "peer_mac",
        "node_id",
        "gateway_id",
        "lmk",
        "wifi:",
        "mqtt:",
        "api:",
        "ota:",
    )
    assert not any(token in combined.lower() for token in forbidden)


def test_manager_boundary_is_wired_to_runtime_authorization():
    header = (RUNTIME_DIR / "n3w_product_runtime.h").read_text()
    implementation = (RUNTIME_DIR / "n3w_product_runtime.cpp").read_text()
    integration = (RUNTIME_DIR / "n3w_product_integration.cpp").read_text()
    assert "ProductManagerIntegrationPort" in header
    assert "ProductRuntimeCoordinator" in header
    assert "request_peer_authorization" in implementation
    assert "install_authorized_peer" in implementation
    assert "execution_enabled_" in integration
