from __future__ import annotations

import copy
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import n3w_t1_core_updater_ha_recovery_deploy as deploy
from n3w_t1_core_updater_common import UpdaterError, sha256_bytes
from n3w_t1_core_updater_ha_ipc import (
    APPROVED_MANIFEST, APPROVED_MANIFEST_SCHEMA, IPC_SOCKET, RELEASE_PIN, HaUsbIpcExecutor, LocalApprovedHaRelease,
)
from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
from n3w_t1_core_updater_v2_common import UpdaterV2Error
from n3w_t1_core_updater_v2_state import HA_USB_TX_SCHEMA_GUARD
from n3w_t1_portable_image_identity import PortableImageIdentityError


@pytest.fixture
def package(tmp_path):
    head = subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=REPO, text=True).strip()
    staged = tmp_path / "candidate"
    digest = deploy.build(REPO, head, staged)
    return staged, digest, head


class Systemd:
    def __init__(self, root: Path):
        self.root = root
        self.enabled: set[str] = set()
        self.changes: list[tuple[str, ...]] = []
        self.fail_reload = False

    def __call__(self, *args, check=True):
        if args[0] == "is-enabled":
            return "enabled" if args[1] in self.enabled else "disabled"
        self.changes.append(args)
        if args[:2] == ("--no-reload", "enable"):
            assert not (self.root / deploy.DESTINATIONS[deploy.GUARD]).exists()
            assert all((self.root / deploy.DESTINATIONS[unit]).is_file() for unit in args[2:])
            for unit, directory in zip(deploy.PERSISTENT_UNITS, deploy.ENABLEMENT_DIRS):
                if unit in args[2:]:
                    target = self.root / deploy.DESTINATIONS[unit]
                    wants = target.parent / directory
                    wants.mkdir(exist_ok=True)
                    (wants / unit).symlink_to(target)
            self.enabled.update(args[2:])
        elif args[:2] == ("--no-reload", "disable"):
            assert all((self.root / deploy.DESTINATIONS[unit]).is_file() for unit in args[2:])
            for unit, directory in zip(deploy.PERSISTENT_UNITS, deploy.ENABLEMENT_DIRS):
                if unit in args[2:]:
                    (self.root / deploy.DESTINATIONS[unit]).with_name(directory).joinpath(unit).unlink()
            self.enabled.difference_update(args[2:])
        else:
            assert args == ("daemon-reload",)
            if self.fail_reload:
                self.fail_reload = False
                raise UpdaterError("simulated_systemd_reload_failure")
        return ""


def test_exact_package_installs_and_executes_self_contained_recovery(package, tmp_path):
    staged, digest, head = package
    assert deploy.build(REPO, head, tmp_path / "repeated-build") == digest
    root = tmp_path / "host"
    root.mkdir()
    manager = Systemd(root)
    result = deploy.install(staged, digest, root=root, systemctl=manager)
    assert result == {
        "schema": deploy.SCHEMA, "source_head": head, "installed": True, "units_started": False,
    }
    assert manager.enabled == set(deploy.PERSISTENT_UNITS)
    assert manager.changes == [("--no-reload", "enable", *deploy.PERSISTENT_UNITS), ("daemon-reload",)]
    installed = root / deploy.DESTINATIONS[deploy.ARCHIVE]
    for name, target in deploy.DESTINATIONS.items():
        assert (root / target).read_bytes() == (staged / name).read_bytes()
        assert (root / target).stat().st_mode & 0o777 == 0o644
    stdout = subprocess.check_output((sys.executable, "-I", installed, "--help"), cwd=tmp_path, text=True)
    assert all(flag in stdout for flag in ("--check-application-start", "--resume-pending", "--install-requested", "--serve-ipc"))
    assert "--issue-prepare-authority" in stdout and "--issue-install-authority" in stdout
    check_help = subprocess.check_output(
        (sys.executable, "-I", installed, "check-candidate-activation", "--help"), cwd=tmp_path, text=True,
    )
    assert "--manifest-sha256" in check_help
    stage_help = subprocess.check_output(
        (sys.executable, "-I", installed, "materialize-candidate", "--help"), cwd=tmp_path, text=True,
    )
    assert "--approved-manifest-sha256" in stage_help
    signed_help = subprocess.check_output(
        (sys.executable, "-I", installed, "check-signed-release", "--help"), cwd=tmp_path, text=True,
    )
    assert "--trust-policy" in signed_help
    assert deploy.install(staged, digest, root=root, systemctl=manager) == result
    assert manager.changes[2:] == [("daemon-reload",)]


def test_candidate_compose_renders_only_the_manager_ota_binding(package, tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose CLI unavailable")
    staged, _, _ = package
    base = REPO / deploy.BASE_COMPOSE
    candidate = staged / deploy.CANDIDATE_COMPOSE
    environment = {
        **os.environ,
        "GH_BROKER_IMAGE": "local/n3w-mosquitto:fixture",
        "GH_MANAGER_IMAGE": "local/greenhouse-manager:fixture",
        "GH_HOMEASSISTANT_IMAGE": "local/n3w-homeassistant:fixture",
        "GH_MQTT_CLIENT_ID": "fixture-manager",
        "GH_MQTT_USERNAME": "fixture-manager",
        "GH_N3W_PAIRING_MANAGER_ID": "fixture-manager",
        "GH_N3W_PROVISIONING_CLIENT_ID": "fixture-provisioning",
        "GH_N3W_PROVISIONING_USERNAME": "fixture-provisioning",
        "GH_SYSTEM_ID": "fixture",
        "GH_N3W_T1_OTA_INSTALLED_VERSION": "2026.10.0",
    }

    def render(path):
        return json.loads(subprocess.check_output(
            ("docker", "compose", "-f", str(path), "--profile", "application", "config", "--format", "json"),
            env=environment, cwd=tmp_path,
        ))

    original = render(base)
    configured = render(candidate)
    deploy._verify_candidate_delta(original, copy.deepcopy(configured), "2026.10.0")
    manager = configured["services"]["manager"]
    expected = {
        "GH_N3W_T1_OTA_ENABLED": "true",
        "GH_N3W_T1_OTA_INSTALLED_VERSION": "2026.10.0",
        "GH_N3W_T1_OTA_MANIFEST_PATH": str(IPC_SOCKET.with_name(APPROVED_MANIFEST)),
        "GH_N3W_T1_OTA_SOCKET_PATH": str(IPC_SOCKET),
    }
    assert {key: manager["environment"].pop(key) for key in expected} == expected
    assert "create_host_path: false" in candidate.read_text()
    ota_mount = next(volume for volume in manager["volumes"] if volume["target"] == str(IPC_SOCKET.parent))
    assert ota_mount["type"] == "bind"
    assert ota_mount["source"] == str(IPC_SOCKET.parent)
    assert ota_mount["read_only"] is True
    assert ota_mount.get("bind", {}).get("create_host_path", False) is False
    manager["volumes"].remove(ota_mount)
    assert configured == original
    environment["GH_N3W_T1_OTA_INSTALLED_VERSION"] = ""
    with pytest.raises(subprocess.CalledProcessError):
        render(candidate)
    assert render(base) == original


@pytest.mark.parametrize("fault", [
    None, "empty_bind", "socket", "version", "mount", "create_path", "broker", "transaction",
])
def test_activation_preflight_is_read_only(package, tmp_path, monkeypatch, fault):
    staged, digest, head = package
    root = tmp_path / "host"
    root.mkdir()
    manager = Systemd(root)
    deploy.install(staged, digest, root=root, systemctl=manager)
    path = root / IPC_SOCKET.relative_to("/")
    path.parent.mkdir(parents=True)
    path.touch()
    original_lstat = Path.lstat

    def lstat(candidate):
        if candidate == path:
            return SimpleNamespace(
                st_mode=stat.S_IFSOCK | 0o660, st_uid=os.geteuid(), st_gid=deploy.MANAGER_PEER_UID,
            )
        return original_lstat(candidate)

    monkeypatch.setattr(Path, "lstat", lstat)

    def unit_status(*args):
        if args[0] == "is-enabled":
            return manager(*args)
        assert args == ("show", "--property=SubState", "--value", deploy.IPC_SOCKET_UNIT)
        return "dead" if fault == "socket" else "listening"

    ref = "local/n3w-homeassistant:2026.10.0-01234567"
    active = {"services": {
        "manager": {"environment": {}, "volumes": [], "image": "manager"},
        "broker": {"image": "broker"},
        "homeassistant": {"image": ref},
    }}
    proposed = copy.deepcopy(active)
    proposed["services"]["manager"]["environment"] = deploy._candidate_settings(
        "2026.10.4" if fault == "version" else "2026.10.0",
    )
    proposed["services"]["manager"]["volumes"] = [{
        "type": "bind", "source": str(IPC_SOCKET.parent), "target": str(IPC_SOCKET.parent),
        "read_only": fault != "mount", "bind": {} if fault == "empty_bind" else {
            "create_host_path": fault == "create_path",
        },
    }]
    if fault == "broker":
        proposed["services"]["broker"]["image"] = "unexpected"
    if fault == "transaction":
        store = deploy.V2StateStore(root / deploy.STATE_ROOT_V2.relative_to("/"))
        store.ha_usb_path.write_text(json.dumps({"schema": HA_USB_TX_SCHEMA_GUARD, "status": "ACTIVE"}))
        store.ha_usb_path.chmod(0o600)

    observed = {"image_ref": ref, "image_id": "sha256:" + "c" * 64}
    bound = []

    def capture_binding(document):
        bound.append(document)
        return {"images": {name: {"reference": config["image"]} for name, config in active["services"].items()}}

    runtime = SimpleNamespace(
        _runtime=lambda name: observed,
        capture_start_binding=capture_binding,
        image_binding_modes_v2=lambda: {"homeassistant": "dynamic"},
    )

    def render(candidate):
        return copy.deepcopy(active if candidate.name == "docker-compose.yml" else proposed)

    errors = {
        "socket": "candidate_socket_unavailable", "version": "manager_settings_drift",
        "mount": "manager_mount_drift", "create_path": "manager_mount_drift",
        "broker": "unexpected_compose_change", "transaction": "transaction_active",
    }
    changes = manager.changes[:]
    if fault in errors:
        with pytest.raises(UpdaterError, match=errors[fault]):
            deploy.check_candidate_activation(
                staged, digest, root=root, runtime=runtime, systemctl=unit_status, render=render,
            )
    else:
        assert deploy.check_candidate_activation(
            staged, digest, root=root, runtime=runtime, systemctl=unit_status, render=render,
        ) == {"source_head": head, "status": "CANDIDATE_ACTIVATION_PREFLIGHT_PASS", "predecessor_version": "2026.10.0"}
        assert bound == [{
            "current_image_ref": observed["image_ref"], "current_image_identity": {"runtime_image_id": observed["image_id"]},
        }]
    assert manager.changes == changes
    assert not (root / deploy.COMPOSE.relative_to("/")).exists()


@pytest.mark.parametrize("fault", [None, "manifest_digest", "archive_digest", "extra_tag", "interrupted_publication"])
def test_materialize_candidate_is_bound_and_retryable(tmp_path, monkeypatch, fault):
    target = json.loads((REPO / "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json").read_bytes())
    source = tmp_path / "incoming.tar"
    layer = b"test layer"
    config = json.dumps({
        "architecture": "arm64", "os": "linux", "config": {"Entrypoint": ["homeassistant"]},
        "rootfs": {"type": "layers", "diff_ids": ["sha256:" + sha256_bytes(layer)]},
    }).encode()
    config_name = sha256_bytes(config) + ".json"
    tags = [target["target_image_ref"]]
    if fault == "extra_tag":
        tags.append("local/unrelated:fixture")
    saved = [{"Config": config_name, "RepoTags": tags, "Layers": ["layer.tar"]}]
    with tarfile.open(source, "w") as archive:
        for name, value in ((config_name, config), ("manifest.json", json.dumps(saved).encode()), ("layer.tar", layer)):
            member = tarfile.TarInfo(name)
            member.size = len(value)
            archive.addfile(member, io.BytesIO(value))
    target["target_archive_sha256"] = "0" * 64 if fault == "archive_digest" else sha256_bytes(source.read_bytes())
    manifest = tmp_path / "approval.json"
    release = "homeassistant-2026.10.4"
    manifest.write_text(json.dumps({
        "schema": APPROVED_MANIFEST_SCHEMA, "release_identity": release, "version": "2026.10.4",
        "approval_status": "APPROVED", "signature_status": "VERIFIED", "validity_status": "VALID",
        "verification_status": "PASS", "target_archive_size_bytes": source.stat().st_size, "target": target,
    }))
    approved_digest = "0" * 64 if fault == "manifest_digest" else sha256_bytes(manifest.read_bytes())
    current = {"image_ref": target["expected_predecessor_image_ref"], "image_id": "sha256:" + "d" * 64,
               "platform": "linux/arm64"}
    root = tmp_path / "host"
    outbound = root / IPC_SOCKET.parent.relative_to("/")
    outbound.mkdir(parents=True)
    store = HaUsbStateStore(root / deploy.STATE_ROOT_V2.relative_to("/"))
    public_manifest, pin = outbound / APPROVED_MANIFEST, store.root / RELEASE_PIN
    runtime = SimpleNamespace(
        _runtime=lambda service: current, _open_target_source=deploy.LocalHaPredecessorRuntime._open_target_source,
        capture_start_binding=lambda transaction: transaction,
    )
    resolver = LocalApprovedHaRelease(pin, public_manifest, lambda: current)

    def materialize():
        return deploy.materialize_candidate(manifest, approved_digest, source, 0x7FFFFFFF, root=root, runtime=runtime)

    if fault in {"manifest_digest", "archive_digest", "extra_tag"}:
        reason = {"manifest_digest": "approval_digest_mismatch", "archive_digest": "archive_digest_mismatch",
                  "extra_tag": "image_load_requires_exact_single_tag"}
        with pytest.raises((UpdaterError, PortableImageIdentityError), match=reason[fault]):
            materialize()
        assert not pin.exists() and not public_manifest.exists() and not list(store.root.glob("*.tar"))
        return

    if fault == "interrupted_publication":
        publish = deploy._write_candidate_record
        public_manifest.write_bytes(b"previous manifest")

        def interrupt(path, content, mode):
            if path == public_manifest:
                raise OSError("simulated public manifest interruption")
            publish(path, content, mode)

        with monkeypatch.context() as patch:
            patch.setattr(deploy, "_write_candidate_record", interrupt)
            with pytest.raises(OSError, match="simulated public manifest interruption"):
                materialize()
        with pytest.raises(UpdaterV2Error, match="release_digest_mismatch"):
            resolver.resolve_homeassistant_release(release)

    result = materialize()
    staged = Path(result["target_source"])
    assert result["status"] == "CANDIDATE_MATERIALIZED" and staged.parent == store.root
    assert staged.read_bytes() == source.read_bytes() and staged.stat().st_mode & 0o777 == 0o600
    assert public_manifest.read_bytes() == manifest.read_bytes() and public_manifest.stat().st_mode & 0o777 == 0o644
    assert pin.stat().st_mode & 0o777 == 0o600
    source.unlink()
    assert materialize() == result
    assert store.read() is None
    executor = HaUsbIpcExecutor(store=store, admission_resolver=resolver)
    assert executor.submit("PREPARE", release)["phase"] == "PREPARE_REQUESTED"
    assert store.read()["target_archive_sha256"] == target["target_archive_sha256"]
    assert store.read()["authorization_consumed"] is False
    with pytest.raises(UpdaterError, match="transaction_active"):
        materialize()


@pytest.mark.parametrize("fault", ["payload", "candidate_compose", "active_transaction", "existing_file"])
def test_recovery_install_rejects_unverified_or_busy_install(package, tmp_path, fault):
    staged, digest, _ = package
    root = tmp_path / "host"
    root.mkdir()
    manager = Systemd(root)
    if fault == "payload":
        (staged / deploy.RECOVERY_TIMER).write_bytes(b"changed timer")
        reason = "payload_digest_mismatch"
    elif fault == "candidate_compose":
        (staged / deploy.CANDIDATE_COMPOSE).write_bytes(b"changed compose")
        reason = "payload_digest_mismatch"
    elif fault == "active_transaction":
        store = deploy.V2StateStore(root / "var/lib/n3w-t1-core-updater")
        store._ensure_root()
        store.ha_usb_path.write_text(json.dumps({
            "schema": HA_USB_TX_SCHEMA_GUARD,
            "status": "ACTIVE",
        }))
        store.ha_usb_path.chmod(0o600)
        reason = "transaction_active"
    else:
        existing = root / deploy.DESTINATIONS[deploy.RECOVERY_TIMER]
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"administrator file")
        reason = "existing_file_drift"
    with pytest.raises(UpdaterError, match=reason):
        deploy.install(staged, digest, root=root, systemctl=manager)
    assert not manager.changes
    assert not (root / deploy.DESTINATIONS[deploy.GUARD]).exists()
    if fault == "existing_file":
        assert existing.read_bytes() == b"administrator file"


def test_recovery_install_can_retry_after_reload_failure(package, tmp_path):
    staged, digest, _ = package
    root = tmp_path / "host"
    root.mkdir()
    manager = Systemd(root)
    manager.fail_reload = True
    with pytest.raises(UpdaterError, match="simulated_systemd_reload_failure"):
        deploy.install(staged, digest, root=root, systemctl=manager)
    assert not manager.enabled
    assert all(not (root / dest).exists() for dest in deploy.DESTINATIONS.values())
    assert deploy.install(staged, digest, root=root, systemctl=manager)["installed"]
