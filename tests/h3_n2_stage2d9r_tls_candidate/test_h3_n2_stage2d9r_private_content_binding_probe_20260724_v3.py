from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_private_content_binding_probe_20260724_v3.py"
BROKER_CERT = (
    ROOT
    / "tests/h3_n2_stage2d9r_tls_candidate/public_pki_tlsvalid01/broker.cert.txt"
)
EXPECTED_DER_SHA256 = "988b6f82b04b0b3cf13f58a07ecd85e420e5576c167fe01ea0940d4530e20ac7"
EXPECTED_MARKER_SHA256 = "8aa4a1bcc20f55cf027d1e047286e8289682af7c261d9afb540641427bce15c7"


def load_module():
    spec = importlib.util.spec_from_file_location("stage2d9r_private_content_v3", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_broker_certificate_uses_der_digest() -> None:
    module = load_module()
    openssl = module._base.resolve_executable("openssl")
    assert module.certificate_der_sha256(openssl, BROKER_CERT) == EXPECTED_DER_SHA256
    assert hashlib.sha256(BROKER_CERT.read_bytes()).hexdigest() != EXPECTED_DER_SHA256


def test_failed_marker_binding_is_required_before_private_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    home = tmp_path / "home"
    auth = home / ".local/state/greenhouse-stage2d9r/authorizations"
    auth.mkdir(parents=True)

    monkeypatch.setattr(
        module,
        "_original_preauthorization_state",
        lambda observed_home: {"base_state_bound": observed_home == home},
    )

    captured: dict[str, object] = {}

    def fake_exact_marker(path, digest, authorization_id, status):
        captured.update(
            path=path,
            digest=digest,
            authorization_id=authorization_id,
            status=status,
        )
        return {
            "record_sha256": module.EXPECTED["u1_03_record_sha256"],
            "failure_code": "BROKER_CERTIFICATE_DIGEST_MISMATCH",
            "result_sha256": None,
        }

    monkeypatch.setattr(module._base, "exact_marker", fake_exact_marker)
    module._active_binding = {"u1_03_failed_marker_sha256": EXPECTED_MARKER_SHA256}
    try:
        state = module.preauthorization_state(home)
    finally:
        module._active_binding = None

    assert state["base_state_bound"] is True
    assert state["u1_03_failed_marker_bound"] is True
    assert state["u1_03_failure_code_bound"] is True
    assert captured["digest"] == EXPECTED_MARKER_SHA256
    assert captured["status"] == "CONSUMED_FAILED"


def test_missing_failed_marker_binding_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(module, "_original_preauthorization_state", lambda _: {})
    module._active_binding = {}
    try:
        with pytest.raises(module._base.BindingError, match="U1_03_FAILED_MARKER_BINDING_MISSING"):
            module.preauthorization_state(home)
    finally:
        module._active_binding = None
