from __future__ import annotations

import inspect

import pytest

from greenhouse_manager.ops.n3w_boardc_p9_capture_authority import (
    AuthorityError,
    invoke_capture_with_authority,
    prepare_boardc_p9_authority,
)

ID_A = "ghw-c6-a1b2c3d4e5f6"
ID_B = "ghw-c6-102030405060"
USB_A = "a1b2c3d4e5f6"
USB_B = "102030405060"
PAIRING = "a" * 64


def test_durable_authority_a_and_usb_a_prepare_without_opening_serial() -> None:
    authority = prepare_boardc_p9_authority(ID_A, PAIRING, USB_A)
    assert authority.capture_expected_hardware_id == ID_A
    assert authority.claim_pairing_id_sha256 == PAIRING


def test_durable_authority_a_and_usb_b_fails_before_capture() -> None:
    with pytest.raises(AuthorityError, match="DURABLE_USB_IDENTITY_MISMATCH"):
        prepare_boardc_p9_authority(ID_A, PAIRING, USB_B)


def test_static_hardware_override_is_not_an_authority_api() -> None:
    parameters = inspect.signature(prepare_boardc_p9_authority).parameters
    assert "expected_hardware_id" not in parameters
    with pytest.raises(TypeError):
        prepare_boardc_p9_authority(
            ID_A, PAIRING, USB_A, expected_hardware_id=ID_B
        )


def test_capture_receives_durable_hardware_and_claim_pairing_only() -> None:
    authority = prepare_boardc_p9_authority(ID_A, PAIRING, USB_A)
    seen: dict[str, object] = {}

    def fake_capture(**kwargs: object) -> str:
        seen.update(kwargs)
        return "ok"

    assert (
        invoke_capture_with_authority(
            authority,
            fake_capture,
            port="/dev/fixture",
            output="/private/handoff",
            ack_live_serial_open_risk=True,
        )
        == "ok"
    )
    assert seen["expected_hardware_id"] == ID_A
    assert seen["expected_pairing_id_sha256"] == PAIRING


def test_capture_boundary_rejects_authority_after_usb_drift() -> None:
    authority = prepare_boardc_p9_authority(ID_A, PAIRING, USB_A)
    object.__setattr__(authority, "usb_serial_identity", USB_B)
    calls = 0

    def fake_capture(**kwargs: object) -> None:
        nonlocal calls
        calls += 1

    with pytest.raises(AuthorityError):
        invoke_capture_with_authority(
            authority,
            fake_capture,
            port="/dev/fixture",
            output="/private/handoff",
            ack_live_serial_open_risk=True,
        )
    assert calls == 0
