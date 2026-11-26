from __future__ import annotations

from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_U4_PIN_REFRESH_AND_INSTALL_INTENT_20261126_01.py"
)


def source() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_pin_refresh_is_bound_to_exact_fresh_u4_transaction() -> None:
    text = source()
    for literal in (
        "86b2fb28429672f6bd27269a62549d774e50814e1e428d6a79a8de531eb0cea0",
        "caa61863a031f6a91b7cf1d3762d5b73b42a49b9cdff797df14387a37f139306",
        "807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2",
        "f05cf21d29808d855bbc41b2be8d5f4c5cbef6eea90de1cf0da3c2a668422a14",
        "5fbae3dedc6af008fec90efc24e75349ce82fc3a538e935806bef6ab3cbc4a36",
        "ca6d2841ac6ca037fbf0d850a2431ca684e243b7c5cd9dac133bc718a4d1a46e",
        "987189ccd61c0784db089b08e51a9ad3ff317372ad8a952dcda7a03a6d844c70",
    ):
        assert literal in text
    assert 'phase") != U4' in text
    assert 'phase") != U5' in text


def test_pin_refresh_changes_only_expiry_and_uses_durable_atomic_write() -> None:
    text = source()
    assert "refreshed = dict(pin)" in text
    assert 'refreshed["expires_at_unix"] = refreshed_expiry' in text
    assert '{k: v for k, v in refreshed_pin.items() if k != "expires_at_unix"}' in text
    assert '{k: v for k, v in pin.items() if k != "expires_at_unix"}' in text
    assert "os.fchmod(fd, 0o600)" in text
    assert "os.fchown(fd, 0, 0)" in text
    assert "os.fsync(stream.fileno())" in text
    assert "os.replace(temporary, path)" in text
    assert "os.fsync(parent)" in text


def test_install_intent_failure_restores_exact_expired_pin_only_if_still_u4() -> None:
    text = source()
    block = text.split("def restore_pin_if_still_u4", 1)[1].split("def main", 1)[0]
    assert 'current.get("phase") == U4' in block
    assert "sha256_file(TX_FILE) == EXPECTED_TX_FILE_SHA" in block
    assert "atomic_write(PIN, old_raw)" in block
    assert "sha256_file(PIN) != EXPECTED_PIN_SHA" in block
    assert "TRANSACTION_ADVANCED" in block


def test_pin_refresh_gate_stops_at_u5_without_issuing_install_authority_or_dispatching_worker() -> None:
    text = source()
    assert '"--maintenance-submit-approved-release", "INSTALL"' in text
    assert '"--release-identity", RELEASE' in text
    assert "INSTALL_AUTHORITY_ISSUED=false" in text
    assert "PRODUCT_WORKER_DISPATCH=false" in text
    assert "U6_PLUS=false" in text
    assert "NEXT_BOUNDARY=EXACT_U5_INSTALL_AUTHORITY_AND_PRODUCT_WORKER" in text
    assert "systemctl" not in text
    assert '"--resume-pending"' not in text
    assert '"docker", "load"' not in text
    assert '"docker", "rmi"' not in text
    assert '"docker", "rm"' not in text


def test_pin_refresh_requires_explicit_transaction_bound_authorization() -> None:
    text = source()
    assert 'APPROVAL_ENV = "N3W_T1_R8V13_07_FRESH_TX_A_PIN_REFRESH_INSTALL_INTENT_APPROVED"' in text
    assert "EXPLICIT_PIN_REFRESH_INSTALL_INTENT_AUTHORIZATION_REQUIRED" in text
    assert "AUTH_ID = " in text
    assert "INSTALL_INTENT_POSTCHECK=STOP" in text
    assert "DO_NOT_REPLAY_INSTALL_INTENT=true" in text
