from __future__ import annotations

import json
import os
import socket
from pathlib import Path

import pytest

from n3w_t1_core_updater_ha_ipc import (
    REQUEST_SCHEMA,
    RESPONSE_SCHEMA,
    RESPONSE_SCHEMA_V2,
    RESPONSE_SCHEMA_V3,
    HaUsbIpcDispatcher,
    HaUsbIpcExecutor,
    HostOtaAdmission,
    UnixSocketHaOtaServer,
)
from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_usb import (
    record_media_bound,
    record_target_ready,
    start_target_preparation,
)
from n3w_t1_core_updater_ha_usb_media import (
    FormatAuthorization,
    UsbCapacityReport,
)
from n3w_t1_core_updater_ha_usb_state import (
    U1,
    U13A,
    HaUsbStateStore,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error

RELEASE = "homeassistant-2026.10.4"
ARCHIVE_SHA = "a" * 64


class Resolver:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def resolve_homeassistant_release(self, release_identity: str) -> HostOtaAdmission:
        self.calls.append(release_identity)
        return HostOtaAdmission(
            release_identity=RELEASE,
            current_image_ref="local/n3w-homeassistant:2026.10.0-0c73235a",
            current_image_identity={"digest": "old"},
            target_manifest_identity={
                "release_identity": RELEASE,
                "manifest_sha256": "b" * 64,
            },
            target_image_ref="local/n3w-homeassistant:2026.10.4-5881590f",
            target_archive_sha256=ARCHIVE_SHA,
            target_archive_size=835309535,
        )


class ControllerStub:
    def __init__(self) -> None:
        self.begin_calls = 0
        self.ensure_calls = 0
        self.refresh_calls = 0
        self.public_calls = 0
        self.confirm_calls = 0
        self.resume_calls = 0

    def begin(self, _document) -> None:
        self.begin_calls += 1

    def ensure_started(self, _document) -> None:
        self.ensure_calls += 1

    def public_status(self):
        self.public_calls += 1
        return {
            "phase": "USB_REQUIRED_CONFIRMATION",
            "progress_percent": None,
            "error_code": None,
            "usb_candidate": {
                "public_fingerprint": "c" * 64,
                "display_model": "Synthetic USB",
                "display_capacity_bytes": 16 * 1024**3,
            },
            "usb_confirmation_required": True,
            "usb_required_bytes_or_null": 5 * 1024**3,
            "usb_recommended_nominal_gb_or_null": 32,
            "usb_capacity_check_state": "CANDIDATE_READY_FOR_CONFIRMATION",
            "user_message_code_or_null": "USB_CONFIRM_ERASE",
        }

    def refresh_candidate(self):
        self.refresh_calls += 1
        return {
            "phase": "USB_REQUIRED_CONFIRMATION",
            "progress_percent": None,
            "error_code": None,
            "usb_candidate": {
                "public_fingerprint": "c" * 64,
                "display_model": "Synthetic USB",
                "display_capacity_bytes": 16 * 1024**3,
            },
            "usb_confirmation_required": True,
            "usb_required_bytes_or_null": 5 * 1024**3,
            "usb_recommended_nominal_gb_or_null": 32,
            "usb_capacity_check_state": "CANDIDATE_READY_FOR_CONFIRMATION",
            "user_message_code_or_null": "USB_CONFIRM_ERASE",
        }

    def confirm_and_prepare(self):
        self.confirm_calls += 1
        return {
            "phase": "READY_TO_INSTALL",
            "progress_percent": None,
            "error_code": None,
            "usb_candidate": None,
            "usb_confirmation_required": False,
            "usb_required_bytes_or_null": 5 * 1024**3,
            "usb_recommended_nominal_gb_or_null": 32,
            "usb_capacity_check_state": "FORMATTED_CAPACITY_PASS",
            "user_message_code_or_null": None,
        }

    def resume_prepare(self):
        self.resume_calls += 1
        return {
            "phase": "READY_TO_INSTALL",
            "progress_percent": None,
            "error_code": None,
            "usb_candidate": None,
            "usb_confirmation_required": False,
            "usb_required_bytes_or_null": 5 * 1024**3,
            "usb_recommended_nominal_gb_or_null": 32,
            "usb_capacity_check_state": "FORMATTED_CAPACITY_PASS",
            "user_message_code_or_null": None,
        }


def _executor(tmp_path: Path) -> tuple[HaUsbIpcExecutor, Resolver, HaUsbStateStore]:
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    resolver = Resolver()
    store = HaUsbStateStore(root)
    return (
        HaUsbIpcExecutor(store=store, admission_resolver=resolver),
        resolver,
        store,
    )


def test_prepare_creates_only_u1_transaction(tmp_path: Path) -> None:
    executor, resolver, store = _executor(tmp_path)
    status = executor.submit("PREPARE", RELEASE)

    document = store.read()
    assert document is not None
    assert document["phase"] == U1
    assert document["authorization_claimed"] is False
    assert status["phase"] == "PREPARE_REQUESTED"
    assert resolver.calls == [RELEASE]


def test_install_requires_exact_existing_u4_admission(tmp_path: Path) -> None:
    executor, _, store = _executor(tmp_path)
    executor.submit("PREPARE", RELEASE)
    current = store.read()
    assert current is not None

    authorization = FormatAuthorization(
        public_fingerprint="c" * 64,
        confirmation_verified=True,
        filesystem="ext4",
        label="N3W-UPDATE",
    )
    capacity = UsbCapacityReport(
        measured_usable_bytes=16 * 1024 * 1024 * 1024,
        required_bytes=15 * 1024 * 1024 * 1024,
        measured_floor_bytes=14 * 1024 * 1024 * 1024,
        measured_floor_pass=True,
        transaction_formula_pass=True,
        capacity_pass=True,
    )
    current = record_media_bound(
        current,
        format_authorization=authorization,
        filesystem_uuid="12345678-1234-1234-1234-123456789abc",
        measured_usable_bytes=capacity.measured_usable_bytes,
        capacity_report=capacity,
    )
    current = start_target_preparation(current)
    current = record_target_ready(
        current,
        target=ImageRecoveryRecord(
            kind="target",
            image_ref="local/n3w-homeassistant:2026.10.4-5881590f",
            archive_sha256=ARCHIVE_SHA,
            archive_size_bytes=835309535,
            portable_identity_sha256="d" * 64,
            platform="linux/arm64",
            verified=True,
            fsynced=True,
        ),
    )
    store.write(current)

    with pytest.raises(UpdaterV2Error, match="ha_ota_ipc_action_invalid"):
        executor.submit("INSTALL", RELEASE)
    installed = store.read()
    assert installed is not None
    assert installed["phase"] == "U4_READY_TO_INSTALL"
    assert installed["authorization_claimed"] is False


def test_dispatcher_rejects_path_injection_without_executor_call(tmp_path: Path) -> None:
    executor, resolver, _ = _executor(tmp_path)
    dispatcher = HaUsbIpcDispatcher(executor)
    response = json.loads(
        dispatcher.handle(
            json.dumps(
                {
                    "schema": REQUEST_SCHEMA,
                    "operation": "submit",
                    "action": "PREPARE",
                    "target_release_id": RELEASE,
                    "device_path": "/dev/sda",
                }
            ).encode("utf-8")
        )
    )
    assert response["schema"] == RESPONSE_SCHEMA
    assert response["accepted"] is False
    assert response["code"] == "ha_ota_ipc_request_fields_invalid"
    assert resolver.calls == []


def test_dispatcher_rejects_unknown_action(tmp_path: Path) -> None:
    executor, resolver, _ = _executor(tmp_path)
    dispatcher = HaUsbIpcDispatcher(executor)
    response = json.loads(
        dispatcher.handle(
            json.dumps(
                {
                    "schema": REQUEST_SCHEMA,
                    "operation": "submit",
                    "action": "SHELL",
                    "target_release_id": RELEASE,
                }
            ).encode("utf-8")
        )
    )
    assert response["accepted"] is False
    assert response["code"] == "ha_ota_ipc_action_invalid"
    assert resolver.calls == []


def test_unix_server_enforces_peer_uid_and_round_trip(tmp_path: Path) -> None:
    executor, _, _ = _executor(tmp_path)
    path = tmp_path / "ha-ota.sock"
    server = UnixSocketHaOtaServer(
        dispatcher=HaUsbIpcDispatcher(executor),
        path=path,
        expected_peer_uid=os.getuid(),
    )
    server.start()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(str(path))
            client.sendall(
                json.dumps(
                    {
                        "schema": REQUEST_SCHEMA,
                        "operation": "status",
                    },
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
            client.shutdown(socket.SHUT_WR)
            payload = client.recv(8192)
        response = json.loads(payload.decode("utf-8"))
        assert response["accepted"] is True
        assert response["phase"] == "DISCOVERED"
        assert response["code"] == "status"
    finally:
        server.stop()


def test_server_rejects_existing_socket_path(tmp_path: Path) -> None:
    path = tmp_path / "ha-ota.sock"
    path.write_text("not a socket", encoding="utf-8")
    other = tmp_path / "other"
    other.mkdir()
    executor, _, _ = _executor(other)
    server = UnixSocketHaOtaServer(
        dispatcher=HaUsbIpcDispatcher(executor),
        path=path,
        expected_peer_uid=os.getuid(),
    )
    with pytest.raises(UpdaterV2Error, match="ha_ota_ipc_socket_path_exists"):
        server.start()


def test_r4_executor_without_prepare_controller_stays_v1(tmp_path: Path) -> None:
    executor, _, _ = _executor(tmp_path)
    dispatcher = HaUsbIpcDispatcher(executor)

    response = json.loads(
        dispatcher.handle(
            json.dumps(
                {"schema": REQUEST_SCHEMA, "operation": "status"}
            ).encode("utf-8")
        )
    )

    assert response["schema"] == RESPONSE_SCHEMA
    assert set(response) == {
        "schema",
        "accepted",
        "code",
        "phase",
        "progress_percent",
        "error_code",
    }


def test_r7a_executor_emits_v3_capacity_projection_with_prepare_controller(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    resolver = Resolver()
    store = HaUsbStateStore(root)
    controller = ControllerStub()
    executor = HaUsbIpcExecutor(
        store=store,
        admission_resolver=resolver,
        prepare_controller=controller,
    )
    dispatcher = HaUsbIpcDispatcher(executor)

    response = json.loads(
        dispatcher.handle(
            json.dumps(
                {
                    "schema": REQUEST_SCHEMA,
                    "operation": "submit",
                    "action": "PREPARE",
                    "target_release_id": RELEASE,
                }
            ).encode("utf-8")
        )
    )

    assert response["schema"] == RESPONSE_SCHEMA_V3
    assert response["phase"] == "USB_REQUIRED_CONFIRMATION"
    assert response["usb_confirmation_required"] is True
    assert response["usb_candidate"]["display_model"] == "Synthetic USB"
    assert response["installed_version"] == "2026.10.0"
    assert response["usb_required_bytes_or_null"] == 5 * 1024**3
    assert response["usb_recommended_nominal_gb_or_null"] == 32
    assert response["usb_capacity_check_state"] == "CANDIDATE_READY_FOR_CONFIRMATION"
    assert response["user_message_code_or_null"] == "USB_CONFIRM_ERASE"
    assert controller.begin_calls == 1
    assert executor._discovery_thread is not None
    executor.stop_background_workers()


def test_r7a_status_is_read_only_for_u1_candidate_projection(
    tmp_path: Path,
) -> None:
    root = tmp_path / "readonly-state"
    root.mkdir(mode=0o700)
    resolver = Resolver()
    store = HaUsbStateStore(root)
    HaUsbIpcExecutor(
        store=store,
        admission_resolver=resolver,
    ).submit("PREPARE", RELEASE)

    controller = ControllerStub()
    executor = HaUsbIpcExecutor(
        store=store,
        admission_resolver=resolver,
        prepare_controller=controller,
    )

    status = executor.status()

    assert status["phase"] == "USB_REQUIRED_CONFIRMATION"
    assert controller.public_calls == 1
    assert controller.refresh_calls == 0
    assert controller.ensure_calls == 0
    assert executor._discovery_thread is None
    assert executor._prepare_thread is None


def test_r7a_background_recovery_not_status_starts_u3_resume(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    resolver = Resolver()
    store = HaUsbStateStore(root)
    base = HaUsbIpcExecutor(
        store=store,
        admission_resolver=resolver,
    )
    base.submit("PREPARE", RELEASE)
    current = store.read()
    assert current is not None

    authorization = FormatAuthorization(
        public_fingerprint="c" * 64,
        confirmation_verified=True,
        filesystem="ext4",
        label="N3W-UPDATE",
    )
    capacity = UsbCapacityReport(
        measured_usable_bytes=16 * 1024**3,
        required_bytes=8 * 1024**3,
        measured_floor_bytes=14 * 1024**3,
        measured_floor_pass=True,
        transaction_formula_pass=True,
        capacity_pass=True,
    )
    current = record_media_bound(
        current,
        format_authorization=authorization,
        filesystem_uuid="12345678-1234-1234-1234-123456789abc",
        measured_usable_bytes=capacity.measured_usable_bytes,
        capacity_report=capacity,
    )
    current = start_target_preparation(current)
    store.write(current)

    controller = ControllerStub()
    executor = HaUsbIpcExecutor(
        store=store,
        admission_resolver=resolver,
        prepare_controller=controller,
    )

    status = executor.status()
    assert status["phase"] == "ERROR"
    assert status["error_code"] == "ha_usb_prepare_worker_inactive"
    assert controller.resume_calls == 0
    assert executor._prepare_thread is None

    executor.start_background_recovery()
    assert executor._prepare_thread is not None
    executor._prepare_thread.join(2)
    assert controller.resume_calls == 1
    executor.stop_background_workers()


def test_committed_status_projects_target_version_without_manager_restart() -> None:
    assert (
        HaUsbIpcExecutor._installed_version(
            {
                "phase": U13A,
                "current_image_ref": "local/n3w-homeassistant:2026.10.0-aaaaaaaa",
                "target_image_ref": "local/n3w-homeassistant:2026.10.4-bbbbbbbb",
            }
        )
        == "2026.10.4"
    )


def test_wrong_bound_usb_projects_recoverable_media_wait(tmp_path: Path) -> None:
    root = tmp_path / "wrong-media-state"
    root.mkdir(mode=0o700)
    resolver = Resolver()
    store = HaUsbStateStore(root)
    base = HaUsbIpcExecutor(
        store=store,
        admission_resolver=resolver,
    )
    base.submit("PREPARE", RELEASE)
    current = store.read()
    assert current is not None
    authorization = FormatAuthorization(
        public_fingerprint="c" * 64,
        confirmation_verified=True,
        filesystem="ext4",
        label="N3W-UPDATE",
    )
    capacity = UsbCapacityReport(
        measured_usable_bytes=16 * 1024**3,
        required_bytes=8 * 1024**3,
        measured_floor_bytes=14 * 1024**3,
        measured_floor_pass=True,
        transaction_formula_pass=True,
        capacity_pass=True,
    )
    current = record_media_bound(
        current,
        format_authorization=authorization,
        filesystem_uuid="12345678-1234-1234-1234-123456789abc",
        measured_usable_bytes=capacity.measured_usable_bytes,
        capacity_report=capacity,
    )
    current = start_target_preparation(current)
    store.write(current)

    executor = HaUsbIpcExecutor(
        store=store,
        admission_resolver=resolver,
        prepare_controller=ControllerStub(),
    )
    executor._prepare_error = "usb_bound_device_identity_mismatch"

    status = executor.status()
    assert status["phase"] == "RECOVERY_MEDIA_REQUIRED"
    assert status["error_code"] is None
