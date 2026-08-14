import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
S1 = ROOT / "docs/decisions/n3w-product-completion-s1-contract-freeze-20260814.json"
S2 = ROOT / "docs/decisions/n3w-product-completion-s2-hostonly-core-stage-entry-20260814.json"
HEADER = (
    ROOT
    / "firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_product_core.h"
)
SOURCE = (
    ROOT
    / "firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_product_core.cpp"
)


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def test_s1_freezes_exact_eight_product_contracts() -> None:
    doc = load(S1)
    assert doc["status"] == "FROZEN"
    assert len(doc["contracts"]) == 8
    assert all(contract["status"] == "FROZEN" for contract in doc["contracts"].values())
    assert doc["contracts"]["factory_neutrality"]["factory_peer_identity_material_allowed"] is False
    assert doc["contracts"]["runtime_peer_security"]["system_wide_shared_lmk"] is False
    assert doc["contracts"]["runtime_peer_security"]["manager_authorization_required"] is True
    assert doc["contracts"]["auto_path_state_machine"]["manual_path_command_required"] is False
    assert doc["contracts"]["dynamic_node_addition"]["new_node_requires_old_node_reflash"] is False


def test_real_t1_final_acceptance_remains_required() -> None:
    acceptance = load(S1)["acceptance"]
    assert acceptance["host_only_or_vm_may_be_final_acceptance"] is False
    assert acceptance["physical_t1_required"] is True
    assert acceptance["preferred_t1_target"] == "spare_non_production_t1"
    assert acceptance["real_esp32c6_required"] is True
    assert acceptance["real_wifi_espnow_required"] is True


def test_s2_is_host_only_orchestration_not_radio_or_manager_integration() -> None:
    doc = load(S2)
    assert doc["mode"] == "HOST_ONLY_CORE_DEVELOPMENT"
    scope = doc["implementation_scope"]
    assert scope["wifi_direct_failure_detector"] is True
    assert scope["candidate_table"] is True
    assert scope["manager_verified_eligibility_filter"] is True
    assert scope["automatic_path_state_machine"] is True
    assert scope["simulated_dynamic_discovery"] is True
    assert scope["runtime_pairwise_crypto"] is False
    assert scope["espnow_radio_driver_integration"] is False
    assert scope["manager_api_integration"] is False
    assert scope["product_firmware_activation"] is False
    assert all(value is False for value in doc["safety_boundary"].values())


def test_core_contains_complete_product_path_states_and_fail_closed_eligibility() -> None:
    text = HEADER.read_text() + SOURCE.read_text()
    for token in (
        "DIRECT_DEGRADED",
        "DISCOVERY",
        "RELAY_AUTH",
        "RELAY_ACTIVE",
        "REDISCOVERY",
        "DIRECT_RECOVERY",
        "manager_verified",
        "registered",
        "same_system",
        "direct_uplink",
        "relay_capable",
        "low_battery",
        "overloaded",
        "retired",
        "revoked",
    ):
        assert token in text


def test_core_has_no_factory_fixed_peer_or_manual_path_command_literals() -> None:
    text = HEADER.read_text() + SOURCE.read_text()
    forbidden = (
        "gateway_t1",
        "PATH DIRECT",
        "PATH RELAY",
        "peer_lmk",
        "factory_lmk",
        "system_wide_lmk",
        "esptool",
        "espota",
    )
    for token in forbidden:
        assert token not in text
