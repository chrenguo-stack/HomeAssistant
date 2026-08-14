import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "docs/decisions/n3w-product-completion-s3-disconnected-espnow-runtime-stage-entry-20260814.json"
RUNTIME_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_product_runtime/n3w_product_runtime.h"
RUNTIME_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_product_runtime/n3w_product_runtime.cpp"
DRIVER_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_espnow_driver.h"
DRIVER_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_espnow_driver.cpp"
S1 = ROOT / "docs/decisions/n3w-product-completion-s1-contract-freeze-20260814.json"


def load(path: Path):
    return json.loads(path.read_text())


def test_stage_boundary_and_frozen_s1_contracts():
    s3 = load(DECISION)
    s1 = load(S1)
    assert s1["status"] == "FROZEN"
    assert len(s1["contracts"]) == 8
    assert s1["contracts"]["runtime_peer_security"]["manager_authorization_required"] is True
    assert s1["contracts"]["runtime_peer_security"]["system_wide_shared_lmk"] is False
    assert s1["contracts"]["dynamic_node_addition"]["new_node_requires_old_node_peer_injection"] is False

    assert s3["status"] == "IMPLEMENTED_CANDIDATE"
    assert s3["stage"] == "S3_DISCONNECTED_ESPNOW_DISCOVERY_RUNTIME"
    assert s3["scope"]["disconnected_scan"] is True
    assert s3["scope"]["dynamic_advertisement"] is True
    assert s3["scope"]["candidate_collection"] is True
    assert s3["scope"]["runtime_peer_installation"] is True
    assert all(value is False for value in s3["execution_boundary"].values())
    assert s3["acceptance"]["final_product_acceptance_requires_physical_t1"] is True


def test_discovery_is_untrusted_and_secret_free():
    s3 = load(DECISION)
    security = s3["security_boundary"]
    assert security["advertisement_is_trusted_identity"] is False
    assert security["advertisement_contains_secret"] is False
    assert security["advertisement_alone_may_activate_relay"] is False
    assert security["manager_authorization_required_before_peer_activation"] is True
    assert security["runtime_generates_pairwise_lmk"] is False
    assert security["system_wide_shared_lmk_introduced"] is False
    assert security["manager_unreachable_new_peer_behavior"] == "FAIL_CLOSED"

    source = RUNTIME_H.read_text() + RUNTIME_CPP.read_text()
    assert "ProductDiscoveryAdvertisement" in source
    assert "advertisement_generation" in source
    assert "gateway_id" in source
    assert "manager_authorized" in source
    assert "same_system" in source
    for forbidden in (
        "set_peer_mac(",
        "peer_mac_text_",
        "lmk_hex_",
        "PATH RELAY",
        "PATH DIRECT",
        "SYSTEM_ROOT_KEY",
        "NODE_AUTH_KEY",
    ):
        assert forbidden not in source


def test_driver_extension_is_backward_compatible_and_metadata_aware():
    header = DRIVER_H.read_text()
    source = DRIVER_CPP.read_text()
    assert "virtual void on_espnow_receive(" in header
    assert "on_espnow_receive_with_metadata" in header
    assert "EspNowReceiveMetadata" in header
    assert "prepare_broadcast_peer" in header
    assert "send_broadcast" in header
    assert "info->rx_ctrl->rssi" in source
    assert "info->rx_ctrl->channel" in source
    assert "peer.encrypt = false" in source
    assert "kEspNowBroadcastMac" in source


def test_s4_authority_is_not_implemented_in_s3():
    s3 = load(DECISION)
    deferred = s3["s4_deferred_integration"]
    assert all(deferred.values())
    source = RUNTIME_CPP.read_text()
    # S3 consumes verified eligibility/authorization supplied by S4; it does
    # not mint authorizations or derive credentials itself.
    assert "apply_manager_eligibility" in source
    assert "install_authorized_peer" in source
    assert "authorization.valid_shape()" in source
    assert "HKDF" not in source
    assert "X25519" not in source
    assert "cryptography" not in source


def test_self_review_hardening_and_compile_only_validation_are_recorded():
    s3 = load(DECISION)
    hardening = s3["self_review_hardening"]
    assert all(hardening.values())
    validation = s3["validation"]
    assert validation["host_cpp_compile_werror"] is True
    assert validation["host_behavior_simulation"] is True
    assert validation["product_contract_tests"] is True
    assert validation["exact_nine_file_scope_gate"] is True
    assert validation["esp32c6_compile_only_driver_validation"] is True
    assert validation["physical_board_execution"] is False
    assert validation["rf_execution"] is False


def test_existing_protocol_reliability_remains_authoritative():
    s3 = load(DECISION)
    preserved = s3["preserved_baseline"]
    assert preserved["existing_n3w_protocol_reliability_baseline_preserved"] is True
    assert preserved["pr315_pr316_reopened"] is False
    assert preserved["existing_receipt_ack_retry_semantics_authoritative"] is True
    assert preserved["manual_path_command_required"] is False
    assert preserved["factory_fixed_peer_binding_added"] is False
