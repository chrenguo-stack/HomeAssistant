from __future__ import annotations

import json
import os
import socket
from pathlib import Path

import pytest

from n3w_t1_core_updater_ha_ipc import (
    REQUEST_SCHEMA,
    RESPONSE_SCHEMA,
    HaUsbIpcDispatcher,
    HaUsbIpcExecutor,
    HostOtaAdmission,
    UnixSocketHaOtaServer,
)
from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
from n3w_t1_core_updater_ha_usb import (
    record_target_ready,
    start_target_preparation,
)
from n3w_t1_core_updater_ha_usb_media import (
    FormatAuthorization,
    UsbCapacityReport,
)
from n3w_t1_core_updater_ha_usb import record_media_bound
from n3w_t1_core_updater_ha_usb_state import (
    U1,
    U5,
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
        selected_device="/dev/test",
        public_fingerprint="c" * 64,
        confirmation_verified=True,
        filesystem="ext4",
        label="N3W-UPDATE",
    )
    capacity = UsbCapacityReport(
        measured_usable_bytes=16 * 1024 * 1024 * 1024,
        minimum_floor_bytes=14 * 1024 * 1024 * 1024,
        required_transaction_bytes=15 * 1024 * 1024 * 1024,
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
            verified=True,
        ),
    )
    store.write(current)

    status = executor.submit("INSTALL", RELEASE)
    installed = store.read()
    assert installed is not None
    assert installed["phase"] == U5
    assert status["phase"] == "INSTALL_REQUESTED_REVALIDATING"
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
    assert resolver.calls == [RELEASE]


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
    executor, _, _ = _executor(tmp_path / "other")
    server = UnixSocketHaOtaServer(
        dispatcher=HaUsbIpcDispatcher(executor),
        path=path,
        expected_peer_uid=os.getuid(),
    )
    with pytest.raises(UpdaterV2Error, match="ha_ota_ipc_socket_path_exists"):
        server.start()
