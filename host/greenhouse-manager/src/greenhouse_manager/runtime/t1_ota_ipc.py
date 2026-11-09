from __future__ import annotations

import json
import re
import socket
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .t1_ota_manager import (
    OtaControlError,
    OtaControlIntent,
    OtaRuntimeSnapshot,
)

REQUEST_SCHEMA = "gh.n3w-t1-ha-ota-ipc-request/1"
RESPONSE_SCHEMA = "gh.n3w-t1-ha-ota-ipc-response/1"
RESPONSE_SCHEMA_V2 = "gh.n3w-t1-ha-ota-ipc-response/2"
RESPONSE_SCHEMA_V3 = "gh.n3w-t1-ha-ota-ipc-response/3"
MAX_FRAME_BYTES = 8192
MAX_MANIFEST_BYTES = 65536
DEFAULT_TIMEOUT_S = 2.0

_CODE_RE = re.compile(r"^[a-z0-9_]{3,96}$")
_RELEASE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OtaControlError("ota_ipc_duplicate_field")
        result[key] = value
    return result


def _path_contains_symlink(path: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        if current == current.parent:
            return False
        current = current.parent


def _read_frame(connection: socket.socket) -> bytes:
    payload = bytearray()
    frame_end: int | None = None
    while len(payload) <= MAX_FRAME_BYTES:
        block = connection.recv(min(1024, MAX_FRAME_BYTES + 1 - len(payload)))
        if not block:
            break
        payload.extend(block)
        if len(payload) > MAX_FRAME_BYTES:
            raise OtaControlError("ota_ipc_response_too_large")
        if frame_end is None:
            newline = payload.find(b"\n")
            if newline >= 0:
                frame_end = newline
        if frame_end is not None and bytes(payload[frame_end + 1 :]).strip():
            raise OtaControlError("ota_ipc_response_invalid")
    if not payload:
        raise OtaControlError("ota_ipc_response_invalid")
    if frame_end is not None:
        del payload[frame_end:]
    if not payload:
        raise OtaControlError("ota_ipc_response_invalid")
    return bytes(payload)


class ApprovedManifestFileProvider:
    """Read one host-published, read-only approved manifest envelope."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        if not self.path.is_absolute():
            raise OtaControlError("approved_manifest_path_invalid")

    def get_approved_homeassistant_manifest(self) -> Mapping[str, Any] | None:
        path = self.path
        if _path_contains_symlink(path):
            raise OtaControlError("approved_manifest_path_invalid")
        try:
            metadata = path.stat()
        except OSError as error:
            raise OtaControlError("approved_manifest_unavailable") from error
        if not path.is_file() or metadata.st_size <= 0 or metadata.st_size > MAX_MANIFEST_BYTES:
            raise OtaControlError("approved_manifest_file_invalid")
        try:
            raw = path.read_bytes()
            document = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_no_duplicate_object,
            )
        except OtaControlError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OtaControlError("approved_manifest_file_invalid") from error
        if not isinstance(document, dict):
            raise OtaControlError("approved_manifest_file_invalid")
        return document


class UnixSocketOtaBridge:
    """Narrow Manager-side IPC client; no host path is accepted from MQTT."""

    def __init__(
        self,
        path: str | Path,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.path = Path(path).expanduser()
        self.timeout_s = timeout_s
        if not self.path.is_absolute() or "\x00" in str(self.path):
            raise OtaControlError("ota_ipc_socket_path_invalid")
        if timeout_s <= 0 or timeout_s > 10:
            raise OtaControlError("ota_ipc_timeout_invalid")

    def _request(self, document: dict[str, object]) -> OtaRuntimeSnapshot:
        request = (
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
        if len(request) > MAX_FRAME_BYTES:
            raise OtaControlError("ota_ipc_request_too_large")
        if self.path.is_symlink():
            raise OtaControlError("ota_ipc_socket_path_invalid")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(self.timeout_s)
            try:
                client.connect(str(self.path))
                client.sendall(request)
                client.shutdown(socket.SHUT_WR)
                payload = _read_frame(client)
            except OtaControlError:
                raise
            except (OSError, TimeoutError) as error:
                raise OtaControlError("ota_ipc_unavailable") from error
        try:
            response = json.loads(
                payload.decode("utf-8"),
                object_pairs_hook=_no_duplicate_object,
            )
        except OtaControlError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OtaControlError("ota_ipc_response_invalid") from error
        if not isinstance(response, dict):
            raise OtaControlError("ota_ipc_response_invalid")
        schema = response.get("schema")
        expected_v1 = {
            "schema",
            "accepted",
            "code",
            "phase",
            "progress_percent",
            "error_code",
        }
        expected_v2 = expected_v1 | {
            "installed_version",
            "usb_candidate",
            "usb_confirmation_required",
        }
        expected_v3 = expected_v2 | {
            "usb_required_bytes_or_null",
            "usb_recommended_nominal_gb_or_null",
            "usb_capacity_check_state",
            "user_message_code_or_null",
        }

        installed_version = None
        candidate_model = None
        candidate_capacity = None
        confirmation_required = False
        usb_required_bytes = None
        usb_recommended_nominal_gb = None
        usb_capacity_check_state = "NOT_CALCULATED"
        user_message_code = None

        if schema == RESPONSE_SCHEMA:
            if set(response) != expected_v1:
                raise OtaControlError("ota_ipc_response_invalid")
        elif schema in {RESPONSE_SCHEMA_V2, RESPONSE_SCHEMA_V3}:
            expected = expected_v3 if schema == RESPONSE_SCHEMA_V3 else expected_v2
            if set(response) != expected:
                raise OtaControlError("ota_ipc_response_invalid")
            installed_version = response["installed_version"]
            if installed_version is not None and not isinstance(
                installed_version,
                str,
            ):
                raise OtaControlError("ota_ipc_response_invalid")
            candidate = response["usb_candidate"]
            if candidate is not None:
                if (
                    not isinstance(candidate, dict)
                    or set(candidate)
                    != {
                        "public_fingerprint",
                        "display_model",
                        "display_capacity_bytes",
                    }
                    or not isinstance(candidate["public_fingerprint"], str)
                    or _SHA256_RE.fullmatch(candidate["public_fingerprint"]) is None
                    or not isinstance(candidate["display_model"], str)
                    or type(candidate["display_capacity_bytes"]) is not int
                    or candidate["display_capacity_bytes"] <= 0
                ):
                    raise OtaControlError("ota_ipc_response_invalid")
                candidate_model = candidate["display_model"]
                candidate_capacity = candidate["display_capacity_bytes"]
            confirmation_required = response["usb_confirmation_required"]
            if type(confirmation_required) is not bool:
                raise OtaControlError("ota_ipc_response_invalid")

            if schema == RESPONSE_SCHEMA_V3:
                usb_required_bytes = response["usb_required_bytes_or_null"]
                if usb_required_bytes is not None and (
                    type(usb_required_bytes) is not int
                    or usb_required_bytes <= 0
                ):
                    raise OtaControlError("ota_ipc_response_invalid")
                usb_recommended_nominal_gb = response[
                    "usb_recommended_nominal_gb_or_null"
                ]
                if usb_recommended_nominal_gb is not None and (
                    type(usb_recommended_nominal_gb) is not int
                    or usb_recommended_nominal_gb
                    not in {32, 64, 128, 256, 512, 1024}
                ):
                    raise OtaControlError("ota_ipc_response_invalid")
                usb_capacity_check_state = response["usb_capacity_check_state"]
                if usb_capacity_check_state not in {
                    "NOT_CALCULATED",
                    "RECOMMENDATION_READY",
                    "CANDIDATE_PENDING",
                    "CANDIDATE_CAPACITY_INSUFFICIENT",
                    "CANDIDATE_READY_FOR_CONFIRMATION",
                    "FORMATTED_CAPACITY_PASS",
                    "CAPACITY_REQUIREMENT_CHANGED",
                }:
                    raise OtaControlError("ota_ipc_response_invalid")
                user_message_code = response["user_message_code_or_null"]
                if user_message_code is not None and user_message_code not in {
                    "USB_INSERT_RECOMMENDED",
                    "USB_CAPACITY_INSUFFICIENT",
                    "USB_CONFIRM_ERASE",
                }:
                    raise OtaControlError("ota_ipc_response_invalid")
        else:
            raise OtaControlError("ota_ipc_response_invalid")
        if type(response["accepted"]) is not bool:
            raise OtaControlError("ota_ipc_response_invalid")
        code = response["code"]
        if not isinstance(code, str) or _CODE_RE.fullmatch(code) is None:
            raise OtaControlError("ota_ipc_response_invalid")
        snapshot = OtaRuntimeSnapshot(
            phase=response["phase"],
            progress_percent=response["progress_percent"],
            error_code=response["error_code"],
            installed_version=installed_version,
            usb_candidate_model=candidate_model,
            usb_candidate_capacity_bytes=candidate_capacity,
            usb_confirmation_required=confirmation_required,
            usb_required_bytes=usb_required_bytes,
            usb_recommended_nominal_gb=usb_recommended_nominal_gb,
            usb_capacity_check_state=usb_capacity_check_state,
            user_message_code=user_message_code,
        ).validate()
        if response["accepted"] is not True:
            raise OtaControlError(code)
        return snapshot

    def submit_homeassistant_ota_intent(self, intent: OtaControlIntent) -> None:
        if intent.action not in {"PREPARE", "CONFIRM_USB_ERASE"}:
            raise OtaControlError("ota_ipc_action_invalid")
        if _RELEASE_RE.fullmatch(intent.target_release_id) is None:
            raise OtaControlError("ota_ipc_release_invalid")
        self._request(
            {
                "schema": REQUEST_SCHEMA,
                "operation": "submit",
                "action": intent.action,
                "target_release_id": intent.target_release_id,
            }
        )

    def get_homeassistant_ota_runtime_state(self) -> OtaRuntimeSnapshot:
        return self._request(
            {
                "schema": REQUEST_SCHEMA,
                "operation": "status",
            }
        )
