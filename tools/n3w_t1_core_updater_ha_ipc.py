from __future__ import annotations

import json
import os
import re
import socket
import stat
import struct
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from n3w_t1_core_updater_ha_usb import request_install, request_prepare
from n3w_t1_core_updater_ha_usb_state import (
    PRE_CUTOVER_RECOVERY_PHASES,
    U0,
    U1,
    U2,
    U3,
    U4,
    U5,
    U6,
    U7,
    U8,
    U9,
    U10,
    U11,
    U12,
    U13A,
    U13B,
    HaUsbStateStore,
    new_transaction,
)
from n3w_t1_core_updater_v2_common import ComponentTarget, UpdaterV2Error, sha256_bytes

REQUEST_SCHEMA = "gh.n3w-t1-ha-ota-ipc-request/1"
RESPONSE_SCHEMA = "gh.n3w-t1-ha-ota-ipc-response/1"
VERSIONED_STATUS_SCHEMA = "gh.n3w-t1-ha-ota-ipc-response/2"
VERSIONED_STATUS_OPERATION = "status_with_version"
MAX_FRAME_BYTES = 8192
DEFAULT_SOCKET_MODE = 0o660
IPC_SOCKET = Path("/run/n3w/t1-ota/ha-ota.sock")
IPC_SOCKET_UNIT = "n3w-t1-ha-ota-ipc.socket"
IPC_SERVICE_UNIT = "n3w-t1-ha-ota-ipc.service"
MANAGER_PEER_UID = 999
APPROVED_MANIFEST = "approved-homeassistant.json"
RELEASE_PIN = "ha-release-pin.json"
RELEASE_PIN_SCHEMA = "gh.n3w-t1-ha-release-pin/1"
APPROVED_MANIFEST_SCHEMA = "gh.n3w-t1-ota-approved-manifest/1"

_RELEASE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PUBLIC_CODE_RE = re.compile(r"^[a-z0-9_]{3,96}$")
_HA_IMAGE_VERSION = re.compile(r"local/n3w-homeassistant:([0-9]{4}\.[0-9]{1,2}\.[0-9]{1,3})-[0-9a-f]{8,64}")


def ha_image_version(reference: object) -> str | None:
    match = _HA_IMAGE_VERSION.fullmatch(reference) if isinstance(reference, str) else None
    return match[1] if match else None

_PHASE_MAP = {
    U0: "DISCOVERED",
    U1: "PREPARE_REQUESTED",
    U2: "USB_QUALIFIED_FORMATTED_BOUND",
    U3: "TARGET_DOWNLOADING_VERIFYING",
    U4: "READY_TO_INSTALL",
    U5: "INSTALL_REQUESTED_REVALIDATING",
    U6: "PREDECESSOR_RECOVERY_PREPARING",
    U7: "HA_QUIESCED_DATA_BACKUP_PREPARING",
    U8: "RECOVERY_ADMISSION_COMPLETE",
    U9: "LIVE_AUTHORIZATION_CLAIMED",
    U10: "INTERNAL_PREDECESSOR_CAPACITY_RELEASED",
    U11: "TARGET_INSTALLED_STARTED",
    U12: "TARGET_ACCEPTANCE",
    U13A: "COMMITTED",
    U13B: "ROLLED_BACK",
}


@dataclass(frozen=True, slots=True)
class HostOtaAdmission:
    release_identity: str
    current_image_ref: str
    current_image_identity: dict[str, Any]
    target_manifest_identity: dict[str, Any]
    target_image_ref: str
    target_archive_sha256: str
    target_archive_size: int

    def validate(self) -> HostOtaAdmission:
        if _RELEASE_RE.fullmatch(self.release_identity) is None:
            raise UpdaterV2Error("ha_ota_ipc_release_invalid")
        if (
            not self.current_image_ref.startswith("local/n3w-homeassistant:")
            or not self.target_image_ref.startswith("local/n3w-homeassistant:")
            or self.current_image_ref == self.target_image_ref
        ):
            raise UpdaterV2Error("ha_ota_ipc_image_identity_invalid")
        if not self.current_image_identity or not self.target_manifest_identity:
            raise UpdaterV2Error("ha_ota_ipc_admission_identity_invalid")
        if (
            self.target_manifest_identity.get("release_identity")
            != self.release_identity
        ):
            raise UpdaterV2Error("ha_ota_ipc_release_binding_invalid")
        if _SHA256_RE.fullmatch(self.target_archive_sha256) is None:
            raise UpdaterV2Error("ha_ota_ipc_archive_sha256_invalid")
        if (
            type(self.target_archive_size) is not int
            or self.target_archive_size <= 0
            or self.target_archive_size > 8 * 1024 * 1024 * 1024
        ):
            raise UpdaterV2Error("ha_ota_ipc_archive_size_invalid")
        return self


class HostOtaAdmissionResolver(Protocol):
    def resolve_homeassistant_release(
        self,
        release_identity: str,
    ) -> HostOtaAdmission:
        """Independently resolve approved target and current runtime authority."""


def read_local_release_input(path: Path, *, limit: int, private: bool) -> bytes:
    reason = "ha_ota_ipc_release_input_unavailable"
    try:
        if path.resolve(strict=True) != path:
            raise UpdaterV2Error(reason)
        parent = path.parent.stat()
        if parent.st_uid != os.geteuid() or parent.st_mode & 0o022:
            raise UpdaterV2Error(reason)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            entry = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(entry.st_mode) or entry.st_uid != os.geteuid() or entry.st_mode & 0o022
                or (private and stat.S_IMODE(entry.st_mode) != 0o600) or entry.st_size > limit
            ):
                raise UpdaterV2Error(reason)
            value = stream.read(limit + 1)
    except OSError as error:
        raise UpdaterV2Error(reason) from error
    if not value or len(value) > limit:
        raise UpdaterV2Error(reason)
    return value


def candidate_admission(raw: bytes, current: dict[str, Any]) -> HostOtaAdmission:
    try:
        envelope = json.loads(raw, object_pairs_hook=reject_duplicate_fields)
    except ValueError as error:
        raise UpdaterV2Error("ha_ota_ipc_release_input_invalid") from error
    if (
        not isinstance(envelope, dict) or envelope.get("schema") != APPROVED_MANIFEST_SCHEMA
        or envelope.get("approval_status") != "APPROVED" or envelope.get("signature_status") != "VERIFIED"
        or envelope.get("validity_status") != "VALID" or envelope.get("verification_status") != "PASS"
    ):
        raise UpdaterV2Error("ha_ota_ipc_release_not_approved")
    release_identity = envelope.get("release_identity")
    if not isinstance(release_identity, str) or _RELEASE_RE.fullmatch(release_identity) is None:
        raise UpdaterV2Error("ha_ota_ipc_release_invalid")
    target = ComponentTarget.from_document(envelope.get("target"))
    if target.component != "homeassistant":
        raise UpdaterV2Error("ha_ota_ipc_release_component_invalid")
    version = ha_image_version(target.target_image_ref)
    if version is None or envelope.get("version") != version:
        raise UpdaterV2Error("ha_ota_ipc_release_version_invalid")
    image_id = current.get("image_id")
    if (
        current.get("image_ref") != target.expected_predecessor_image_ref
        or current.get("platform") != target.target_platform
        or not isinstance(image_id, str) or not image_id.startswith("sha256:")
        or _SHA256_RE.fullmatch(image_id[7:]) is None
    ):
        raise UpdaterV2Error("ha_ota_ipc_predecessor_identity_drift")
    return HostOtaAdmission(
        release_identity=release_identity,
        current_image_ref=target.expected_predecessor_image_ref,
        current_image_identity={"runtime_image_id": image_id, "platform": target.target_platform},
        target_manifest_identity={"release_identity": release_identity, "manifest_sha256": sha256_bytes(raw)},
        target_image_ref=target.target_image_ref,
        target_archive_sha256=target.target_archive_sha256,
        target_archive_size=envelope.get("target_archive_size_bytes"),
    ).validate()


class LocalApprovedHaRelease:
    """Resolve a host-pinned engineering candidate and independently inspect its predecessor."""

    def __init__(
        self, pin: Path, manifest: Path, read_current: Callable[[], dict[str, Any]],
    ) -> None:
        self.pin = pin
        self.manifest = manifest
        self.read_current = read_current

    def resolve_homeassistant_release(self, release_identity: str) -> HostOtaAdmission:
        try:
            pin = json.loads(read_local_release_input(self.pin, limit=4096, private=True),
                             object_pairs_hook=reject_duplicate_fields)
            if (
                not isinstance(pin, dict)
                or set(pin) != {"schema", "manifest_sha256", "predecessor_image_id", "expires_at_unix"}
                or pin["schema"] != RELEASE_PIN_SCHEMA
                or type(pin["expires_at_unix"]) is not int or time.time() >= pin["expires_at_unix"]
                or not isinstance(pin["predecessor_image_id"], str)
                or not pin["predecessor_image_id"].startswith("sha256:")
                or _SHA256_RE.fullmatch(pin["predecessor_image_id"][7:]) is None
            ):
                raise UpdaterV2Error("ha_ota_ipc_release_pin_invalid")
            raw = read_local_release_input(self.manifest, limit=32768, private=False)
            if pin["manifest_sha256"] != sha256_bytes(raw):
                raise UpdaterV2Error("ha_ota_ipc_release_digest_mismatch")
        except ValueError as error:
            raise UpdaterV2Error("ha_ota_ipc_release_input_invalid") from error
        admission = candidate_admission(raw, self.read_current())
        if admission.release_identity != release_identity:
            raise UpdaterV2Error("ha_ota_ipc_release_not_approved")
        if admission.current_image_identity["runtime_image_id"] != pin["predecessor_image_id"]:
            raise UpdaterV2Error("ha_ota_ipc_predecessor_identity_drift")
        return admission


class HaUsbIpcExecutor:
    """Bind narrow IPC intent to the durable HA-USB transaction boundary only."""

    def __init__(
        self,
        *,
        store: HaUsbStateStore,
        admission_resolver: HostOtaAdmissionResolver,
        install_ready: threading.Event | None = None,
    ) -> None:
        self.store = store
        self.admission_resolver = admission_resolver
        self.install_ready = install_ready

    def _resolve(self, release_identity: str) -> HostOtaAdmission:
        if _RELEASE_RE.fullmatch(release_identity) is None:
            raise UpdaterV2Error("ha_ota_ipc_release_invalid")
        admission = self.admission_resolver.resolve_homeassistant_release(
            release_identity
        )
        if not isinstance(admission, HostOtaAdmission):
            raise UpdaterV2Error("ha_ota_ipc_admission_invalid")
        admission.validate()
        if admission.release_identity != release_identity:
            raise UpdaterV2Error("ha_ota_ipc_release_binding_invalid")
        return admission

    def status(self, *, include_version: bool = False) -> dict[str, object]:
        document = self.store.read()
        status = self._project_status(document)
        if include_version:
            version = None
            if document is not None:
                key = "target_image_ref" if document["phase"] == U13A else "current_image_ref"
                version = ha_image_version(document[key])
            status["installed_version"] = version
        return status

    @staticmethod
    def _project_status(document: dict[str, Any] | None) -> dict[str, object]:
        if document is None:
            return {
                "phase": "DISCOVERED",
                "progress_percent": None,
                "error_code": None,
            }
        if document.get("pre_cutover_predecessor_restored") is True:
            return {"phase": "ROLLED_BACK", "progress_percent": None, "error_code": None}
        if document["recovery_required"] and (
            "ha_data_restore" in document
            or "predecessor_release_intent" in document
            or (
                document["phase"] in PRE_CUTOVER_RECOVERY_PHASES
                and "predecessor_start" in document
            )
        ):
            return {"phase": "RECOVERING", "progress_percent": None, "error_code": None}
        if document["status"] == "FAILED_EMERGENCY":
            failure = document.get("failure_code")
            code = (
                failure
                if isinstance(failure, str)
                and _PUBLIC_CODE_RE.fullmatch(failure) is not None
                else "ota_host_failure"
            )
            return {
                "phase": "ERROR",
                "progress_percent": None,
                "error_code": code,
            }
        phase = _PHASE_MAP.get(document["phase"])
        if document["phase"] == U2 and document.get("usb_binding_mode") == "existing_filesystem":
            phase = "USB_QUALIFIED_BOUND"
        if phase is None:
            raise UpdaterV2Error("ha_ota_ipc_phase_invalid")
        failure = document.get("failure_code")
        public_failures = {
            U4: ("ha_usb_install_revalidation_failed", "ha_usb_predecessor_acceptance_baseline_unavailable"),
            U13B: ("ha_usb_target_acceptance_proven_failure", "ha_usb_target_acceptance_evidence_unavailable"),
        }
        return {
            "phase": phase,
            "progress_percent": None,
            "error_code": failure if failure in public_failures.get(document["phase"], ()) else None,
        }

    @staticmethod
    def require_same_admission(
        document: dict[str, Any],
        admission: HostOtaAdmission,
    ) -> None:
        expected = {
            "current_image_ref": admission.current_image_ref,
            "current_image_identity": admission.current_image_identity,
            "target_manifest_identity": admission.target_manifest_identity,
            "target_image_ref": admission.target_image_ref,
            "target_archive_sha256": admission.target_archive_sha256,
            "target_archive_size": admission.target_archive_size,
        }
        for key, value in expected.items():
            if document.get(key) != value:
                raise UpdaterV2Error("ha_ota_ipc_admission_drift")

    def submit(self, action: str, release_identity: str) -> dict[str, object]:
        if action not in {"PREPARE", "INSTALL"}:
            raise UpdaterV2Error("ha_ota_ipc_action_invalid")
        with self.store.lock():
            admission = self._resolve(release_identity)
            if action == "PREPARE":
                document = new_transaction(
                    current_image_ref=admission.current_image_ref,
                    current_image_identity=dict(admission.current_image_identity),
                    target_manifest_identity=dict(admission.target_manifest_identity),
                    target_image_ref=admission.target_image_ref,
                    target_archive_sha256=admission.target_archive_sha256,
                    target_archive_size=admission.target_archive_size,
                )
                self.store.prepare_new(replacement=request_prepare(document))
            else:
                document = self.store.read()
                if document is None:
                    raise UpdaterV2Error("ha_ota_ipc_transaction_missing")
                self.require_same_admission(document, admission)
                self.store.write(request_install(document))
        if action == "INSTALL" and self.install_ready is not None:
            self.install_ready.set()
        return self.status()


def reject_duplicate_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise UpdaterV2Error("ha_ota_ipc_duplicate_field")
        result[key] = value
    return result


def _read_frame(connection: socket.socket) -> bytes:
    payload = bytearray()
    frame_end: int | None = None
    deadline = time.monotonic() + 2.0
    while len(payload) <= MAX_FRAME_BYTES:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise UpdaterV2Error("ha_ota_ipc_request_timeout")
        connection.settimeout(remaining)
        block = connection.recv(min(1024, MAX_FRAME_BYTES + 1 - len(payload)))
        if not block:
            break
        payload.extend(block)
        if len(payload) > MAX_FRAME_BYTES:
            raise UpdaterV2Error("ha_ota_ipc_request_too_large")
        if frame_end is None:
            newline = payload.find(b"\n")
            if newline >= 0:
                frame_end = newline
        if frame_end is not None and bytes(payload[frame_end + 1 :]).strip():
            raise UpdaterV2Error("ha_ota_ipc_request_invalid")
    if not payload:
        raise UpdaterV2Error("ha_ota_ipc_request_invalid")
    if frame_end is not None:
        del payload[frame_end:]
    if not payload:
        raise UpdaterV2Error("ha_ota_ipc_request_invalid")
    return bytes(payload)


def _public_code(error: Exception) -> str:
    code = str(error)
    if _PUBLIC_CODE_RE.fullmatch(code) is None:
        return "ota_host_rejected"
    return code


class HaUsbIpcDispatcher:
    def __init__(self, executor: HaUsbIpcExecutor) -> None:
        self.executor = executor

    def _response(
        self,
        *,
        accepted: bool,
        code: str,
        status: dict[str, object] | None = None,
    ) -> bytes:
        if status is None:
            try:
                status = self.executor.status()
            except Exception:
                status = {
                    "phase": "ERROR",
                    "progress_percent": None,
                    "error_code": "ota_host_status_unavailable",
                }
        document = {
            "schema": RESPONSE_SCHEMA,
            "accepted": accepted,
            "code": code,
            "phase": status["phase"],
            "progress_percent": status["progress_percent"],
            "error_code": status["error_code"],
        }
        if "installed_version" in status:
            document["schema"] = VERSIONED_STATUS_SCHEMA
            document["installed_version"] = status["installed_version"]
        return (
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
            + b"\n"
        )

    def handle(self, payload: bytes) -> bytes:
        try:
            try:
                document = json.loads(
                    payload.decode("utf-8"),
                    object_pairs_hook=reject_duplicate_fields,
                )
            except UpdaterV2Error:
                raise
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise UpdaterV2Error("ha_ota_ipc_request_invalid") from error
            if not isinstance(document, dict) or document.get("schema") != REQUEST_SCHEMA:
                raise UpdaterV2Error("ha_ota_ipc_request_invalid")
            operation = document.get("operation")
            if operation in ("status", VERSIONED_STATUS_OPERATION):
                if set(document) != {"schema", "operation"}:
                    raise UpdaterV2Error("ha_ota_ipc_request_fields_invalid")
                return self._response(
                    accepted=True,
                    code="status",
                    status=self.executor.status(include_version=operation == VERSIONED_STATUS_OPERATION),
                )
            if operation == "submit":
                if set(document) != {
                    "schema",
                    "operation",
                    "action",
                    "target_release_id",
                }:
                    raise UpdaterV2Error("ha_ota_ipc_request_fields_invalid")
                action = document.get("action")
                release = document.get("target_release_id")
                if not isinstance(action, str) or not isinstance(release, str):
                    raise UpdaterV2Error("ha_ota_ipc_request_invalid")
                return self._response(
                    accepted=True,
                    code="accepted",
                    status=self.executor.submit(action, release),
                )
            raise UpdaterV2Error("ha_ota_ipc_operation_invalid")
        except UpdaterV2Error as error:
            return self._response(
                accepted=False,
                code=_public_code(error),
            )
        except Exception:
            return self._response(
                accepted=False,
                code="ota_host_rejected",
            )


class UnixSocketHaOtaServer:
    """Host-side local-only server with explicit Linux peer-UID admission."""

    def __init__(
        self,
        *,
        dispatcher: HaUsbIpcDispatcher,
        path: str | Path,
        expected_peer_uid: int,
        mode: int = DEFAULT_SOCKET_MODE,
    ) -> None:
        self.dispatcher = dispatcher
        self.path = Path(path).expanduser()
        self.expected_peer_uid = expected_peer_uid
        self.mode = mode
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        if not self.path.is_absolute() or expected_peer_uid < 0:
            raise UpdaterV2Error("ha_ota_ipc_server_config_invalid")
        if mode not in {0o600, 0o660}:
            raise UpdaterV2Error("ha_ota_ipc_socket_mode_invalid")

    def _validate_parent(self) -> None:
        parent = self.path.parent
        if parent.is_symlink() or not parent.is_dir():
            raise UpdaterV2Error("ha_ota_ipc_socket_parent_invalid")
        metadata = parent.stat()
        if metadata.st_uid != os.getuid():
            raise UpdaterV2Error("ha_ota_ipc_socket_parent_owner_invalid")
        if stat.S_IMODE(metadata.st_mode) & 0o002:
            raise UpdaterV2Error("ha_ota_ipc_socket_parent_world_writable")
        if self.path.exists() or self.path.is_symlink():
            raise UpdaterV2Error("ha_ota_ipc_socket_path_exists")

    @property
    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.is_alive:
            return
        self._validate_parent()
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(self.path))
            os.chmod(self.path, self.mode)
            listener.listen(4)
            listener.settimeout(0.25)
        except Exception:
            listener.close()
            self.path.unlink(missing_ok=True)
            raise
        self._socket = listener
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._serve,
            name="n3w-t1-ha-ota-ipc",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        self._stop.set()
        listener = self._socket
        if listener is not None:
            listener.close()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout_s)
        if thread is not None and thread.is_alive():
            raise UpdaterV2Error("ha_ota_ipc_server_stop_timeout")
        self._socket = None
        self.path.unlink(missing_ok=True)

    def serve_activated(self, listener: socket.socket) -> None:
        if (
            listener.family != socket.AF_UNIX or listener.type != socket.SOCK_STREAM
            or listener.getsockname() != str(self.path)
            or listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) != 1
        ):
            raise UpdaterV2Error("ha_ota_ipc_activated_socket_invalid")
        listener.settimeout(0.25)
        self._socket = listener
        try:
            self._serve()
        finally:
            self._socket = None

    def _peer_uid(self, connection: socket.socket) -> int:
        if not hasattr(socket, "SO_PEERCRED"):
            raise UpdaterV2Error("ha_ota_ipc_peer_credentials_unavailable")
        raw = connection.getsockopt(
            socket.SOL_SOCKET,
            socket.SO_PEERCRED,
            struct.calcsize("3i"),
        )
        _pid, uid, _gid = struct.unpack("3i", raw)
        return uid

    def _serve(self) -> None:
        while not self._stop.is_set():
            listener = self._socket
            if listener is None:
                return
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                if self._stop.is_set():
                    return
                raise
            with connection:
                connection.settimeout(2.0)
                try:
                    if self._peer_uid(connection) != self.expected_peer_uid:
                        response = self.dispatcher._response(
                            accepted=False,
                            code="ha_ota_ipc_peer_uid_rejected",
                            status={"phase": "ERROR", "progress_percent": None, "error_code": None},
                        )
                    else:
                        response = self.dispatcher.handle(_read_frame(connection))
                except (UpdaterV2Error, OSError, TimeoutError) as error:
                    response = self.dispatcher._response(
                        accepted=False,
                        code=_public_code(error),
                    )
                with suppress(OSError):
                    connection.sendall(response)

def serve_activated_ha_ipc(store: HaUsbStateStore, read_current: Callable[[], dict[str, Any]]) -> None:
    if os.environ.get("LISTEN_PID") != str(os.getpid()) or os.environ.get("LISTEN_FDS") != "1":
        raise UpdaterV2Error("ha_ota_ipc_socket_activation_required")
    resolver = LocalApprovedHaRelease(store.root / RELEASE_PIN, IPC_SOCKET.with_name(APPROVED_MANIFEST), read_current)
    server = UnixSocketHaOtaServer(
        dispatcher=HaUsbIpcDispatcher(HaUsbIpcExecutor(store=store, admission_resolver=resolver)),
        path=IPC_SOCKET, expected_peer_uid=MANAGER_PEER_UID,
    )
    with socket.socket(fileno=3) as listener:
        server.serve_activated(listener)
