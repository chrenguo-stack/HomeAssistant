from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import n3w_t1_core_updater_broker_support as support


class FakeSystemd:
    def __init__(self) -> None:
        self.enabled = False
        self.active = False
        self.calls: list[tuple[str, str | None]] = []
        self.fail_enable = False

    def __call__(self, action: str, unit: str | None = None) -> str:
        self.calls.append((action, unit))
        if action == "is-active":
            return "active" if self.active else "inactive"
        if action == "is-enabled":
            return "enabled" if self.enabled else "disabled"
        if action == "daemon-reload":
            return ""
        if action == "enable":
            self.enabled = True
            if self.fail_enable:
                raise support.BrokerSupportError("synthetic_enable_failure")
            return ""
        if action == "disable":
            self.enabled = False
            return ""
        raise AssertionError((action, unit))


@pytest.fixture
def exact_package(tmp_path: Path):
    head = subprocess.check_output(
        ("git", "rev-parse", "HEAD"),
        cwd=ROOT,
        text=True,
    ).strip()
    first = tmp_path / "first"
    result = support.build(ROOT, head, first)
    return first, result, head


def _prepare_install_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "host"
    (root / "opt").mkdir(parents=True)
    (root / "etc/systemd/system").mkdir(parents=True)
    monkeypatch.setattr(support.os, "geteuid", lambda: 0)
    monkeypatch.setattr(support.os, "chown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(support, "_owner_uid", lambda _path: 0)
    return root


def test_package_build_is_deterministic_and_self_contained(
    exact_package,
    tmp_path: Path,
):
    package, first, head = exact_package
    second_dir = tmp_path / "second"
    second = support.build(ROOT, head, second_dir)

    assert first == second
    assert (package / support.UPDATER).read_bytes() == (
        second_dir / support.UPDATER
    ).read_bytes()
    assert (package / support.MANIFEST).read_bytes() == (
        second_dir / support.MANIFEST
    ).read_bytes()

    with zipfile.ZipFile(package / support.UPDATER, "r") as archive:
        names = set(archive.namelist())
    assert "n3w_t1_core_updater_broker_recovery.py" in names
    assert "n3w_t1_core_updater_v2.py" in names
    assert "__main__.py" in names

    help_text = subprocess.check_output(
        (sys.executable, "-I", package / support.UPDATER, "--help"),
        cwd=tmp_path,
        text=True,
    )
    assert "recover-broker-pending" in help_text


def test_package_manifest_binds_exact_source_and_fixed_install_paths(
    exact_package,
):
    package, result, head = exact_package
    manifest = json.loads(
        (package / support.MANIFEST).read_text(encoding="utf-8")
    )

    assert manifest["source_head"] == head
    assert result["manifest_sha256"] == hashlib.sha256(
        (package / support.MANIFEST).read_bytes()
    ).hexdigest()
    assert manifest["files"][support.UPDATER]["install_path"] == str(
        support.UPDATER_INSTALL
    )
    assert manifest["files"][support.UNIT]["install_path"] == str(
        support.UNIT_INSTALL
    )
    assert manifest["files"][support.UPDATER]["install_mode"] == 0o755
    assert manifest["files"][support.UNIT]["install_mode"] == 0o644
    assert manifest["t1_access"] is False
    assert manifest["production_service_start"] is False


def test_package_tamper_is_rejected(exact_package):
    package, result, _head = exact_package
    (package / support.UPDATER).write_bytes(b"tampered")

    with pytest.raises(
        support.BrokerSupportError,
        match="broker_support_payload_digest_mismatch",
    ):
        support.verify(
            package,
            expected_manifest_sha256=result["manifest_sha256"],
        )


def test_install_enables_without_starting_runtime(
    exact_package,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    package, result, _head = exact_package
    root = _prepare_install_root(tmp_path, monkeypatch)
    systemd = FakeSystemd()

    document = support.install(
        package,
        result["manifest_sha256"],
        root=root,
        systemctl=systemd,
    )

    updater = root / support.UPDATER_INSTALL.relative_to("/")
    unit = root / support.UNIT_INSTALL.relative_to("/")
    assert document["installed"] is True
    assert document["reinstall"] is False
    assert document["unit_enabled"] is True
    assert document["unit_started"] is False
    assert document["product_service_mutation"] is False
    assert updater.read_bytes() == (package / support.UPDATER).read_bytes()
    assert unit.read_bytes() == (package / support.UNIT).read_bytes()
    assert stat.S_IMODE(updater.stat().st_mode) == 0o755
    assert stat.S_IMODE(unit.stat().st_mode) == 0o644
    assert ("enable", support.UNIT) in systemd.calls
    assert not any(
        action in {"start", "stop", "restart"}
        for action, _unit in systemd.calls
    )


def test_exact_reinstall_is_idempotent(
    exact_package,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    package, result, _head = exact_package
    root = _prepare_install_root(tmp_path, monkeypatch)
    systemd = FakeSystemd()

    support.install(
        package,
        result["manifest_sha256"],
        root=root,
        systemctl=systemd,
    )
    calls_before = len(systemd.calls)
    document = support.install(
        package,
        result["manifest_sha256"],
        root=root,
        systemctl=systemd,
    )

    assert document["reinstall"] is True
    assert systemd.enabled is True
    assert not any(
        action in {"start", "stop", "restart"}
        for action, _unit in systemd.calls[calls_before:]
    )


def test_install_drift_stops_before_daemon_reload(
    exact_package,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    package, result, _head = exact_package
    root = _prepare_install_root(tmp_path, monkeypatch)
    systemd = FakeSystemd()
    updater_dir = root / support.UPDATER_INSTALL.parent.relative_to("/")
    updater_dir.mkdir()
    target = root / support.UPDATER_INSTALL.relative_to("/")
    target.write_bytes(b"drift")
    target.chmod(0o755)

    with pytest.raises(
        support.BrokerSupportError,
        match="broker_support_install_target_drift",
    ):
        support.install(
            package,
            result["manifest_sha256"],
            root=root,
            systemctl=systemd,
        )

    assert systemd.calls == []


def test_enable_failure_rolls_back_new_payload(
    exact_package,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    package, result, _head = exact_package
    root = _prepare_install_root(tmp_path, monkeypatch)
    systemd = FakeSystemd()
    systemd.fail_enable = True

    with pytest.raises(
        support.BrokerSupportError,
        match="synthetic_enable_failure",
    ):
        support.install(
            package,
            result["manifest_sha256"],
            root=root,
            systemctl=systemd,
        )

    assert not (root / support.UPDATER_INSTALL.relative_to("/")).exists()
    assert not (root / support.UNIT_INSTALL.relative_to("/")).exists()
    assert not (
        root / support.UPDATER_INSTALL.parent.relative_to("/")
    ).exists()
    assert systemd.enabled is False
    assert not any(
        action in {"start", "stop", "restart"}
        for action, _unit in systemd.calls
    )


def test_install_refuses_active_recovery_unit(
    exact_package,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    package, result, _head = exact_package
    root = _prepare_install_root(tmp_path, monkeypatch)
    systemd = FakeSystemd()
    systemd.active = True

    with pytest.raises(
        support.BrokerSupportError,
        match="broker_support_recovery_unit_active",
    ):
        support.install(
            package,
            result["manifest_sha256"],
            root=root,
            systemctl=systemd,
        )


def test_unit_source_never_orders_before_product_owners():
    text = (
        ROOT
        / "infra/n3w-t1/systemd/n3wfc4-core-updater-broker-recovery.service"
    ).read_text(encoding="utf-8")

    assert "Before=n3wfc4-broker-activation.service" not in text
    assert "Before=n3wfc4-services-activation.service" not in text
    assert (
        "ExecStart=/opt/n3w-t1-core-updater/t1-core-updater.pyz "
        "recover-broker-pending"
    ) in text


def test_manifest_install_metadata_tamper_is_rejected(
    exact_package,
):
    package, _result, _head = exact_package
    manifest_path = package / support.MANIFEST
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["files"][support.UPDATER]["install_path"] = "/tmp/not-authority"
    manifest_path.write_text(
        json.dumps(document, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        support.BrokerSupportError,
        match="broker_support_payload_digest_mismatch",
    ):
        support.verify(package)


def test_active_unit_precheck_leaves_no_updater_directory(
    exact_package,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    package, result, _head = exact_package
    root = _prepare_install_root(tmp_path, monkeypatch)
    systemd = FakeSystemd()
    systemd.active = True

    with pytest.raises(
        support.BrokerSupportError,
        match="broker_support_recovery_unit_active",
    ):
        support.install(
            package,
            result["manifest_sha256"],
            root=root,
            systemctl=systemd,
        )

    assert not (
        root / support.UPDATER_INSTALL.parent.relative_to("/")
    ).exists()
