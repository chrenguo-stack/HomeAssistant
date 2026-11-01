from __future__ import annotations

import base64
import hashlib
import json
import os
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from greenhouse_manager.ops import n3w_setup_secret_handoff_delivery_gate as gate
from greenhouse_manager.runtime.registration import RegistrationRegistry

NOW = datetime(2026, 8, 21, 1, 38, 22, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-98a316a9f350"
PAIRING_ID = "7a7ff697-4d0b-4a62-b5c5-4903721c72f6"
PAIRING_SHA256 = hashlib.sha256(PAIRING_ID.encode("ascii")).hexdigest()
SETUP_SECRET = base64.urlsafe_b64encode(bytes(range(32))).rstrip(b"=").decode()


def _hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "lcd-pairing-qr"],
        "sent_at_ms": 120345,
    }


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "registration.sqlite3"
    with RegistrationRegistry(path, pending_ttl_s=120) as registry:
        registry.observe_hello(_hello(), now=NOW)
    return path


def _common(database: Path, minimum: int = 30) -> list[str]:
    return [
        "--registration-db",
        str(database),
        "--expected-hardware-id",
        HARDWARE_ID,
        "--expected-pairing-id-sha256",
        PAIRING_SHA256,
        "--minimum-remaining-seconds",
        str(minimum),
    ]


def _handoff(tmp_path: Path) -> Path:
    path = tmp_path / "handoff.private.json"
    path.write_text(
        json.dumps(
            {
                "schema": "gh.pair.setup-secret-import/1",
                "hardware_id": HARDWARE_ID,
                "pairing_id": PAIRING_ID,
                "setup_secret": SETUP_SECRET,
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    path.chmod(0o600)
    return path


def test_pretransfer_passes_with_explicit_ttl_margin_without_exposing_identity(
    tmp_path: Path, capsys: object
) -> None:
    database = _database(tmp_path)
    database_sha256_before = hashlib.sha256(database.read_bytes()).hexdigest()

    result = gate.main(
        ["pretransfer", *_common(database, minimum=30)],
        now=NOW + timedelta(seconds=60),
    )

    assert result == 0
    stdout = capsys.readouterr().out
    assert "DELIVERY_GATE=PASS" in stdout
    assert "DELIVERY_GATE_PHASE=pretransfer" in stdout
    assert "PENDING_TTL_REMAINING_SECONDS=60" in stdout
    assert "PAIRING_ID_RAW_EXPOSED=false" in stdout
    assert PAIRING_ID not in stdout
    assert SETUP_SECRET not in stdout
    assert hashlib.sha256(database.read_bytes()).hexdigest() == database_sha256_before


def test_pretransfer_rejects_pending_session_without_required_margin(
    tmp_path: Path, capsys: object
) -> None:
    database = _database(tmp_path)

    result = gate.main(
        ["pretransfer", *_common(database, minimum=30)],
        now=NOW + timedelta(seconds=100),
    )

    assert result == 1
    stdout = capsys.readouterr().out
    assert "DELIVERY_GATE=FAIL:PENDING_TTL_MARGIN_INSUFFICIENT" in stdout
    assert PAIRING_ID not in stdout


def test_predelivery_validates_private_handoff_and_live_margin(
    tmp_path: Path, capsys: object
) -> None:
    database = _database(tmp_path)
    handoff = _handoff(tmp_path)

    result = gate.main(
        [
            "predelivery",
            *_common(database, minimum=5),
            "--handoff",
            str(handoff),
            "--expected-owner-uid",
            str(os.geteuid()),
            "--expected-owner-gid",
            str(os.getegid()),
        ],
        now=NOW + timedelta(seconds=100),
    )

    assert result == 0
    stdout = capsys.readouterr().out
    assert "DELIVERY_GATE_PHASE=predelivery" in stdout
    assert f"HANDOFF_SHA256={hashlib.sha256(handoff.read_bytes()).hexdigest()}" in stdout
    assert PAIRING_ID not in stdout
    assert SETUP_SECRET not in stdout


def test_predelivery_rejects_nonprivate_handoff_without_exposing_secret(
    tmp_path: Path, capsys: object
) -> None:
    database = _database(tmp_path)
    handoff = _handoff(tmp_path)
    handoff.chmod(0o644)

    result = gate.main(
        [
            "predelivery",
            *_common(database, minimum=5),
            "--handoff",
            str(handoff),
            "--expected-owner-uid",
            str(os.geteuid()),
            "--expected-owner-gid",
            str(os.getegid()),
        ],
        now=NOW + timedelta(seconds=100),
    )

    assert result == 1
    stdout = capsys.readouterr().out
    assert "DELIVERY_GATE=FAIL:HANDOFF_MODE_INVALID" in stdout
    assert PAIRING_ID not in stdout
    assert SETUP_SECRET not in stdout


def test_pretransfer_rejects_noncurrent_pairing_hash(tmp_path: Path, capsys: object) -> None:
    database = _database(tmp_path)
    arguments = _common(database)
    arguments[arguments.index(PAIRING_SHA256)] = "0" * 64

    result = gate.main(["pretransfer", *arguments], now=NOW)

    assert result == 1
    assert "DELIVERY_GATE=FAIL:EXACT_CURRENT_PAIRING_SESSION_NOT_UNIQUE" in (
        capsys.readouterr().out
    )


def test_supported_cli_entry_point_targets_the_tested_main() -> None:
    project = Path(__file__).parents[2] / "pyproject.toml"
    document = tomllib.loads(project.read_text())

    assert document["project"]["scripts"][
        "greenhouse-manager-n3w-setup-secret-delivery-gate"
    ] == "greenhouse_manager.ops.n3w_setup_secret_handoff_delivery_gate:main"
