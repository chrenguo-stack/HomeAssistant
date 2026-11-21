from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import n3w_t1_core_updater_ha_recovery_deploy as deploy
from n3w_t1_core_updater_common import UpdaterError
from n3w_t1_core_updater_ha_ipc import APPROVED_MANIFEST, IPC_SOCKET
from n3w_t1_core_updater_v2_state import HA_USB_TX_SCHEMA_GUARD


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
