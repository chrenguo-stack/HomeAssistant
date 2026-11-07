from __future__ import annotations

import json
import socket
import threading
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.runtime.t1_ota_ipc import (
    REQUEST_SCHEMA,
    RESPONSE_SCHEMA,
    RESPONSE_SCHEMA_V2,
    ApprovedManifestFileProvider,
    UnixSocketOtaBridge,
)
from greenhouse_manager.runtime.t1_ota_manager import (
    OtaControlError,
    OtaControlIntent,
)


def _serve_once(
    path: Path,
    response: dict[str, Any],
    captured: list[dict[str, Any]],
) -> threading.Thread:
    ready = threading.Event()

    def run() -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(path))
            listener.listen(1)
            ready.set()
            connection, _ = listener.accept()
            with connection:
                payload = bytearray()
                while b"\n" not in payload:
                    block = connection.recv(1024)
                    if not block:
                        break
                    payload.extend(block)
                captured.append(json.loads(bytes(payload).decode("utf-8")))
                connection.sendall(
                    json.dumps(
                        response,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    + b"\n"
                )

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert ready.wait(2)
    return thread


def _response(*, phase: str, accepted: bool = True, code: str = "status") -> dict[str, Any]:
    return {
        "schema": RESPONSE_SCHEMA,
        "accepted": accepted,
        "code": code,
        "phase": phase,
        "progress_percent": None,
        "error_code": None,
    }


def test_bridge_status_uses_exact_narrow_schema(tmp_path: Path) -> None:
    path = tmp_path / "ota.sock"
    captured: list[dict[str, Any]] = []
    thread = _serve_once(path, _response(phase="DISCOVERED"), captured)

    snapshot = UnixSocketOtaBridge(path).get_homeassistant_ota_runtime_state()
    thread.join(2)

    assert snapshot.phase == "DISCOVERED"
    assert captured == [{"schema": REQUEST_SCHEMA, "operation": "status"}]


def test_bridge_submit_cannot_carry_host_paths_or_commands(tmp_path: Path) -> None:
    path = tmp_path / "ota.sock"
    captured: list[dict[str, Any]] = []
    thread = _serve_once(path, _response(phase="PREPARE_REQUESTED", code="accepted"), captured)

    UnixSocketOtaBridge(path).submit_homeassistant_ota_intent(
        OtaControlIntent(
            action="PREPARE",
            target_release_id="homeassistant-2026.10.4",
        )
    )
    thread.join(2)

    assert captured == [
        {
            "schema": REQUEST_SCHEMA,
            "operation": "submit",
            "action": "PREPARE",
            "target_release_id": "homeassistant-2026.10.4",
        }
    ]
    serialized = json.dumps(captured[0])
    for forbidden in ("/dev/", "docker", "shell", "path", "authorization"):
        assert forbidden not in serialized.lower()


def test_bridge_rejects_install_locally_in_r7a(tmp_path: Path) -> None:
    path = tmp_path / "ota.sock"

    with pytest.raises(OtaControlError, match="ota_ipc_action_invalid"):
        UnixSocketOtaBridge(path).submit_homeassistant_ota_intent(
            OtaControlIntent(
                action="INSTALL",
                target_release_id="homeassistant-2026.10.4",
            )
        )


def test_manifest_file_provider_rejects_duplicate_fields(tmp_path: Path) -> None:
    path = tmp_path / "approved.json"
    path.write_text('{"schema":"a","schema":"b"}', encoding="utf-8")
    with pytest.raises(OtaControlError, match="ota_ipc_duplicate_field"):
        ApprovedManifestFileProvider(path).get_approved_homeassistant_manifest()


def test_manifest_file_provider_rejects_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real.json"
    real.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(OtaControlError, match="approved_manifest_path_invalid"):
        ApprovedManifestFileProvider(link).get_approved_homeassistant_manifest()


def test_bridge_accepts_v2_public_usb_confirmation_projection(tmp_path: Path) -> None:
    path = tmp_path / "ota.sock"
    captured: list[dict[str, Any]] = []
    response = {
        "schema": RESPONSE_SCHEMA_V2,
        "accepted": True,
        "code": "status",
        "phase": "USB_REQUIRED_CONFIRMATION",
        "progress_percent": None,
        "error_code": None,
        "installed_version": "2026.10.0",
        "usb_candidate": {
            "public_fingerprint": "a" * 64,
            "display_model": "Synthetic USB",
            "display_capacity_bytes": 16 * 1024**3,
        },
        "usb_confirmation_required": True,
    }
    thread = _serve_once(path, response, captured)

    snapshot = UnixSocketOtaBridge(path).get_homeassistant_ota_runtime_state()
    thread.join(2)

    assert snapshot.phase == "USB_REQUIRED_CONFIRMATION"
    assert snapshot.installed_version == "2026.10.0"
    assert snapshot.usb_candidate_model == "Synthetic USB"
    assert snapshot.usb_candidate_capacity_bytes == 16 * 1024**3
    assert snapshot.usb_confirmation_required is True
    assert captured == [{"schema": REQUEST_SCHEMA, "operation": "status"}]


def test_bridge_confirmation_intent_cannot_carry_device_path(tmp_path: Path) -> None:
    path = tmp_path / "ota.sock"
    captured: list[dict[str, Any]] = []
    response = {
        "schema": RESPONSE_SCHEMA_V2,
        "accepted": True,
        "code": "accepted",
        "phase": "TARGET_DOWNLOADING_VERIFYING",
        "progress_percent": None,
        "error_code": None,
        "installed_version": "2026.10.0",
        "usb_candidate": None,
        "usb_confirmation_required": False,
    }
    thread = _serve_once(path, response, captured)

    UnixSocketOtaBridge(path).submit_homeassistant_ota_intent(
        OtaControlIntent(
            action="CONFIRM_USB_ERASE",
            target_release_id="homeassistant-2026.10.4",
        )
    )
    thread.join(2)

    assert captured == [
        {
            "schema": REQUEST_SCHEMA,
            "operation": "submit",
            "action": "CONFIRM_USB_ERASE",
            "target_release_id": "homeassistant-2026.10.4",
        }
    ]
    encoded = json.dumps(captured[0]).lower()
    for forbidden in ("/dev/", "mount", "docker", "shell", "authorization"):
        assert forbidden not in encoded
