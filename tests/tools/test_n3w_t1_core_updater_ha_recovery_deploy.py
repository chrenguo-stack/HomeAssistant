from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import n3w_t1_core_updater_ha_recovery_deploy as deploy
from n3w_t1_core_updater_common import UpdaterError
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
    assert "--check-application-start" in stdout and "--resume-pending" in stdout
    assert deploy.install(staged, digest, root=root, systemctl=manager) == result
    assert manager.changes[2:] == [("daemon-reload",)]


@pytest.mark.parametrize("fault", ["payload", "active_transaction", "existing_file"])
def test_recovery_install_rejects_unverified_or_busy_install(package, tmp_path, fault):
    staged, digest, _ = package
    root = tmp_path / "host"
    root.mkdir()
    manager = Systemd(root)
    if fault == "payload":
        (staged / deploy.RECOVERY_TIMER).write_bytes(b"changed timer")
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
