from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from n3w_t1_core_updater_ha_ipc import (
    APPROVED_MANIFEST,
    APPROVED_MANIFEST_SCHEMA,
    RELEASE_PIN,
    RELEASE_PIN_SCHEMA,
    REQUEST_SCHEMA,
    RESPONSE_SCHEMA,
    HaUsbIpcDispatcher,
    HaUsbIpcExecutor,
    HostOtaAdmission,
    LocalApprovedHaRelease,
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
    U5,
    HaUsbStateStore,
)
from n3w_t1_core_updater_v2_common import UpdaterV2Error, sha256_bytes

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


def _approved_release(directory: Path, store: HaUsbStateStore):
    target_path = Path(__file__).resolve().parents[2] / "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json"
    target = json.loads(target_path.read_bytes())
    manifest = directory / APPROVED_MANIFEST
    manifest.write_text(json.dumps({
        "schema": APPROVED_MANIFEST_SCHEMA, "release_identity": RELEASE, "version": "2026.10.4",
        "approval_status": "APPROVED", "signature_status": "VERIFIED", "validity_status": "VALID",
        "verification_status": "PASS", "target_archive_size_bytes": 835309535, "target": target,
    }))
    manifest.chmod(0o644)
    current = {
        "image_ref": target["expected_predecessor_image_ref"], "image_id": "sha256:" + "3" * 64,
        "platform": "linux/arm64",
    }
    pin = store.root / RELEASE_PIN
    pin.write_text(json.dumps({
        "schema": RELEASE_PIN_SCHEMA, "manifest_sha256": sha256_bytes(manifest.read_bytes()),
        "predecessor_image_id": current["image_id"], "expires_at_unix": 0x7FFFFFFF,
    }))
    pin.chmod(0o600)
    return manifest, pin, current


@pytest.mark.parametrize("fault", ["digest", "predecessor", "expired", "pin_mode"])
def test_local_release_admission_rejects_drift(tmp_path, fault):
    _, _, store = _executor(tmp_path)
    manifest, pin, current = _approved_release(tmp_path, store)
    resolver = LocalApprovedHaRelease(pin, manifest, lambda: current)
    admission = resolver.resolve_homeassistant_release(RELEASE)
    assert admission.target_manifest_identity["manifest_sha256"] == sha256_bytes(manifest.read_bytes())
    assert admission.current_image_identity["runtime_image_id"] == current["image_id"]
    if fault == "digest":
        manifest.write_bytes(manifest.read_bytes() + b"\n")
        expected = "ha_ota_ipc_release_digest_mismatch"
    elif fault == "predecessor":
        current["image_id"] = "sha256:" + "4" * 64
        expected = "ha_ota_ipc_predecessor_identity_drift"
    elif fault == "expired":
        pin.write_text(json.dumps({**json.loads(pin.read_bytes()), "expires_at_unix": 1}))
        expected = "ha_ota_ipc_release_pin_invalid"
    else:
        pin.chmod(0o644)
        expected = "ha_ota_ipc_release_input_unavailable"
    with pytest.raises(UpdaterV2Error, match=expected):
        resolver.resolve_homeassistant_release(RELEASE)
    assert store.read() is None


@pytest.mark.parametrize("wrong_uid", [False, True])
def test_activated_ipc_uses_manager_client_and_pinned_release(tmp_path, monkeypatch, wrong_uid):
    repo = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(repo / "host/greenhouse-manager/src"))
    from greenhouse_manager.runtime.t1_ota_ipc import UnixSocketOtaBridge
    from greenhouse_manager.runtime.t1_ota_manager import OtaControlError, OtaControlIntent

    _, _, store = _executor(tmp_path)
    # Keep the Unix socket path below the OS limit even with a long pytest work directory.
    with tempfile.TemporaryDirectory(prefix="n3w-ipc-") as work:
        directory = Path(work).resolve()
        manifest, _, current = _approved_release(directory, store)
        path = directory / "ha-ota.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(path))
            listener.listen()
            descriptor = listener.fileno()
            process = subprocess.Popen(
                (sys.executable, "-c", """
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import n3w_t1_core_updater_ha_ipc as ipc
import n3w_t1_core_updater_ha_recovery_startup as startup

descriptor = int(sys.argv[1])
if descriptor != 3:
    os.dup2(descriptor, 3)
    os.close(descriptor)
os.environ["LISTEN_PID"] = str(os.getpid())
os.environ["LISTEN_FDS"] = "1"
ipc.IPC_SOCKET = Path(sys.argv[2])
ipc.MANAGER_PEER_UID = int(sys.argv[3])
startup.HaUsbStateStore = lambda: ipc.HaUsbStateStore(Path(sys.argv[4]))
startup.LocalHaPredecessorRuntime = lambda: SimpleNamespace(_runtime=lambda _: json.loads(sys.argv[5]))
raise SystemExit(startup.cli(["--serve-ipc"]))
""", str(descriptor), str(path), str(os.getuid() + int(wrong_uid)), str(store.root), json.dumps(current)),
                env={**os.environ, "PYTHONPATH": str(repo / "tools")}, pass_fds=(descriptor,),
            )
            try:
                client = UnixSocketOtaBridge(path)
                if wrong_uid:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as rejected:
                        rejected.settimeout(2)
                        rejected.connect(str(path))
                        reply = json.loads(rejected.recv(8192))
                    assert reply["code"] == "ha_ota_ipc_peer_uid_rejected"
                    assert reply["phase"] == "ERROR" and reply["accepted"] is False
                    assert store.read() is None
                    return
                assert client.get_homeassistant_ota_runtime_state().phase == "DISCOVERED"
                original = manifest.read_bytes()
                manifest.write_bytes(original + b"\n")
                with pytest.raises(OtaControlError, match="ha_ota_ipc_release_digest_mismatch"):
                    client.submit_homeassistant_ota_intent(OtaControlIntent("PREPARE", RELEASE))
                assert store.read() is None
                manifest.write_bytes(original)
                client.submit_homeassistant_ota_intent(OtaControlIntent("PREPARE", RELEASE))
                assert client.get_homeassistant_ota_runtime_state().phase == "PREPARE_REQUESTED"
                queued = store.read()
                assert queued["phase"] == U1 and queued["authorization_consumed"] is False
                assert not (store.root / "ha-install-authority.json").exists()
            finally:
                process.terminate()
                process.wait(timeout=5)

def test_ipc_cli_requires_passed_listener(monkeypatch, capsys):
    import n3w_t1_core_updater_ha_recovery_startup as startup

    monkeypatch.delenv("LISTEN_PID", raising=False)
    monkeypatch.delenv("LISTEN_FDS", raising=False)
    assert startup.cli(["--serve-ipc"]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "IPC_STARTUP_NEEDS_REVIEW"}
