"""R6 registration-confirm parser source guards.

These are source contracts, not substitutes for native C++ parser tests or a
physical TLS pre-body pinning test. Full R6 acceptance stays blocked.
"""
from pathlib import Path

CORE = Path(__file__).resolve().parents[2] / "firmware/esphome_rc/components/greenhouse_n3w_core"


def source(name: str) -> str:
    return (CORE / name).read_text(encoding="utf-8")


def test_confirm_transport_is_explicitly_separate_from_protocol() -> None:
    header = source("n3w_registration_bootstrap_client.h")
    impl = source("n3w_registration_bootstrap_client.cpp")
    assert "build_registration_confirm_request" in header
    assert "parse_registration_confirm_result" in header
    assert "esp_http_client_perform" not in impl
    assert "esp_tls_conn_new" not in impl


def test_confirm_request_contains_only_server_expected_fields() -> None:
    impl = source("n3w_registration_bootstrap_client.cpp")
    for field in (
        "gh.registration.confirm/1",
        'root["manager_id"] = selected.manager_id',
        'root["system_id"] = selected.system_id',
        'root["hardware_id"] = hardware_id',
        'root["pairing_id"] = pairing_id',
        'root["setup_secret"] = setup_secret_base64url',
    ):
        assert field in impl


def test_success_requires_exact_manager_system_and_47112_contract() -> None:
    impl = source("n3w_registration_bootstrap_client.cpp")
    assert 'manager_id != selected.manager_id' in impl
    assert 'system_id != selected.system_id' in impl
    assert 'pairing_path != "/v2/pairing"' in impl
    assert 'root["pairing_port"].as<uint16_t>() != 47112U' in impl
    assert "remaining == 0 || remaining > 1800U" in impl
    assert "ipv4_literal(host)" in impl


def test_terminal_result_does_not_treat_generic_rejection_as_renewal() -> None:
    impl = source("n3w_registration_bootstrap_client.cpp")
    assert 'reason == "expired" || reason == "replay_detected"' in impl
    assert 'disposition != "terminal"' in impl
    assert "RegistrationConfirmDisposition::RENEW_PAIRING_ID" in impl
    assert "RegistrationConfirmDisposition::RETRY_SAME_PAIRING_ID" in impl
