from __future__ import annotations

import io
import sys

import pytest

from greenhouse_manager.ops import n3w_pairing_cli as cli

HARDWARE_ID = "ghw-c6-112233445566"
PAIRING_ID = "123e4567-e89b-42d3-a456-426614174000"
SETUP_SECRET = "A" * 43
PAYLOAD = f"GHN3W2:{HARDWARE_ID}:{PAIRING_ID}:{SETUP_SECRET}"


def test_parse_complete_pairing_payload() -> None:
    hardware_id, pairing_id, setup_secret = cli._parse_pairing_payload(PAYLOAD)
    assert hardware_id == HARDWARE_ID
    assert pairing_id == PAIRING_ID
    assert setup_secret == SETUP_SECRET


@pytest.mark.parametrize(
    "value",
    [
        "",
        "GHN3W1:ghw-c6-112233445566:pairing:secret",
        "GHN3W2:ghw-c6-112233445566:pairing",
        "GHN3W2:bad id:pairing:secret",
        "GHN3W2:ghw-c6-112233445566:bad pairing!:secret",
        "GHN3W2:ghw-c6-112233445566:123e4567-e89b-42d3-a456-426614174000:short",
        "GHN3W2:ghw-c6-112233445566:123e4567-e89b-42d3-a456-426614174000:" + "A" * 42,
        "GHN3W2:ghw-c6-112233445566:123e4567-e89b-42d3-a456-426614174000:" + "A" * 44,
        "GHN3W2:ghw-c6-112233445566:123e4567-e89b-42d3-a456-426614174000:" + "!" * 43,
        "GHN3W2:ghw-c6-112233445566:pairing:bad+secret",
        "GHN3W2:ghw-c6-112233445566:pairing:secret:extra",
    ],
)
def test_parse_rejects_malformed_payload(value: str) -> None:
    with pytest.raises(cli.PairingPayloadError):
        cli._parse_pairing_payload(value)


def test_import_payload_uses_manager_socket_without_echoing_secret(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    observed: dict[str, str] = {}

    def fake_import(
        path: str,
        *,
        hardware_id: str,
        pairing_id: str,
        setup_secret: str,
    ) -> dict[str, object]:
        observed.update(
            {
                "path": path,
                "hardware_id": hardware_id,
                "pairing_id": pairing_id,
                "setup_secret": setup_secret,
            }
        )
        return {
            "accepted": True,
            "code": "accepted",
            "schema": "gh.pair.setup-secret-import-result/1",
        }

    monkeypatch.setattr(cli, "import_setup_secret_over_socket", fake_import)
    monkeypatch.setattr(sys, "stdin", io.StringIO(PAYLOAD + "\n"))

    rc = cli.main(
        [
            "import-payload",
            "--socket",
            "/tmp/pairing.sock",
            "--payload-stdin",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert observed == {
        "path": "/tmp/pairing.sock",
        "hardware_id": HARDWARE_ID,
        "pairing_id": PAIRING_ID,
        "setup_secret": SETUP_SECRET,
    }
    assert SETUP_SECRET not in captured.out
    assert SETUP_SECRET not in captured.err
    assert "GHN3W2:" not in captured.out
    assert "GHN3W2:" not in captured.err


def test_import_payload_accepts_trailing_whitespace_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, str] = {}

    def fake_import(
        path: str,
        *,
        hardware_id: str,
        pairing_id: str,
        setup_secret: str,
    ) -> dict[str, object]:
        observed.update(
            {
                "hardware_id": hardware_id,
                "pairing_id": pairing_id,
                "setup_secret": setup_secret,
            }
        )
        return {
            "accepted": True,
            "code": "accepted",
            "schema": "gh.pair.setup-secret-import-result/1",
        }

    monkeypatch.setattr(cli, "import_setup_secret_over_socket", fake_import)
    monkeypatch.setattr(sys, "stdin", io.StringIO(PAYLOAD + "\n \t\n"))

    assert cli.main(["import-payload", "--payload-stdin"]) == 0
    assert observed["hardware_id"] == HARDWARE_ID
    assert observed["pairing_id"] == PAIRING_ID
    assert observed["setup_secret"] == SETUP_SECRET


def test_import_payload_rejects_multiple_lines_without_forwarding_secret(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    called = False

    def fake_import(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal called
        called = True
        return {"accepted": True}

    monkeypatch.setattr(cli, "import_setup_secret_over_socket", fake_import)
    monkeypatch.setattr(sys, "stdin", io.StringIO(PAYLOAD + "\n" + PAYLOAD + "\n"))

    with pytest.raises(SystemExit):
        cli.main(["import-payload", "--payload-stdin"])

    captured = capsys.readouterr()
    assert called is False
    assert SETUP_SECRET not in captured.out
    assert SETUP_SECRET not in captured.err
