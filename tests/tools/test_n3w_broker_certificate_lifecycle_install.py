from __future__ import annotations

import importlib.util
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_broker_certificate_lifecycle_install.py"


def load_tool():
    specification = importlib.util.spec_from_file_location(
        "n3w_broker_certificate_lifecycle_install",
        TOOL,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def fixture_source(path: Path, content: str) -> str:
    path.write_text(content, encoding="utf-8")
    data = path.read_bytes()
    import hashlib

    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def prepare_runtime(tmp_path: Path, tool, monkeypatch: pytest.MonkeyPatch):
    staging = tmp_path / "staging"
    staging.mkdir()
    lifecycle = staging / "lifecycle.py"
    service = staging / "lifecycle.service"
    timer = staging / "lifecycle.timer"
    preflight = staging / "preflight.py"

    lifecycle_blob = fixture_source(lifecycle, "#!/usr/bin/env python3\nprint('lifecycle')\n")
    service_blob = fixture_source(service, "[Service]\nType=oneshot\n")
    timer_blob = fixture_source(timer, "[Timer]\nOnCalendar=daily\n")
    preflight_blob = fixture_source(preflight, "# preflight fixture\n")

    monkeypatch.setattr(tool, "LIFECYCLE_BLOB", lifecycle_blob)
    monkeypatch.setattr(tool, "SERVICE_BLOB", service_blob)
    monkeypatch.setattr(tool, "TIMER_BLOB", timer_blob)
    monkeypatch.setattr(tool, "PREFLIGHT_BLOB", preflight_blob)

    install_root = tmp_path / "installed"
    sbin = install_root / "usr/local/sbin"
    systemd = install_root / "etc/systemd/system"
    etc_n3wfc4 = install_root / "etc/n3wfc4"
    status = install_root / "var/lib/n3wfc4-certificate-lifecycle"
    for directory in (sbin, systemd, etc_n3wfc4):
        directory.mkdir(parents=True)
    monkeypatch.setattr(tool, "LIFECYCLE_TARGET", sbin / "n3w-broker-certificate-lifecycle")
    monkeypatch.setattr(tool, "SERVICE_TARGET", systemd / "n3wfc4-broker-certificate-lifecycle.service")
    monkeypatch.setattr(tool, "TIMER_TARGET", systemd / "n3wfc4-broker-certificate-lifecycle.timer")
    monkeypatch.setattr(tool, "ENV_TARGET", etc_n3wfc4 / "broker-certificate-lifecycle.env")
    monkeypatch.setattr(tool, "STATUS_DIR", status)
    monkeypatch.setattr(tool, "STATUS_FILE", status / "status.json")

    fc4_root = tmp_path / "fc4"
    tls = fc4_root / "broker/tls"
    tls.mkdir(parents=True)
    ca_cert = tls / "ca.pem"
    server_cert = tls / "server.pem"
    server_key = tls / "server.key"
    ca_key = tls / "ca-key.pem"
    ca_cert.write_bytes(b"ca-cert")
    server_cert.write_bytes(b"server-cert")
    server_key.write_bytes(b"server-key")
    ca_key.write_bytes(b"ca-key")
    os.chmod(server_key, 0o600)
    os.chmod(ca_key, 0o600)

    system_root = tmp_path / "greenhouse-manager"
    system_root.mkdir()
    system_ca = system_root / "system-ca.pem"
    system_ca.write_bytes(b"system-ca")

    inspect = {"State": {"Running": True, "StartedAt": "2026-09-20T00:00:00Z"}}

    fake_preflight = SimpleNamespace(
        DEFAULT_MAX_FILES=5000,
        DEFAULT_MAX_DEPTH=8,
        EXPECTED_SERVER_NAME="armbian",
        EXPECTED_SERVER_FINGERPRINT="server-fingerprint",
        SYSTEM_CA_PATH=system_ca,
        preflight=lambda max_files, max_depth: {"result": "PASS"},
        _broker_container=lambda: "broker-container",
        _broker_inspect=lambda _cid: inspect,
        _mount_source=lambda _inspect, target, require_read_only: {
            "/mosquitto/tls/ca.pem": ca_cert,
            "/mosquitto/tls/server.pem": server_cert,
            "/mosquitto/tls/server.key": server_key,
        }[target],
        _persistent_root=lambda _ca: fc4_root,
        _tls_endpoint_fingerprint=lambda _ca, _name: "server-fingerprint",
    )
    monkeypatch.setattr(tool, "_load_preflight", lambda _path: fake_preflight)
    monkeypatch.setattr(tool, "_private_key_match", lambda _preflight, _ca: (ca_key, fc4_root))
    monkeypatch.setattr(tool.os, "geteuid", lambda: 0)

    states = {
        ("is-active", tool.LIFECYCLE_TIMER): "inactive",
        ("is-enabled", tool.LIFECYCLE_TIMER): "disabled",
        ("is-active", tool.LIFECYCLE_SERVICE): "inactive",
    }
    monkeypatch.setattr(tool, "_systemctl_state", lambda mode, unit: states[(mode, unit)])
    monkeypatch.setattr(tool, "_systemctl_daemon_reload", lambda: None)
    monkeypatch.setattr(tool.os, "chown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        tool,
        "_owner_mode",
        lambda path: (0, 0, stat.S_IMODE(path.stat().st_mode)),
    )

    return {
        "lifecycle": lifecycle,
        "service": service,
        "timer": timer,
        "preflight": preflight,
        "fc4_root": fc4_root,
        "ca_cert": ca_cert,
        "server_cert": server_cert,
        "server_key": server_key,
        "ca_key": ca_key,
        "system_ca": system_ca,
    }


def test_installation_only_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    runtime = prepare_runtime(tmp_path, tool, monkeypatch)

    document, code = tool.install(
        runtime["lifecycle"],
        runtime["service"],
        runtime["timer"],
        runtime["preflight"],
    )

    assert code == 0
    assert document["result"] == "PASS"
    assert document["installation_only"] is True
    assert document["certificate_mutation"] is False
    assert document["broker_restart"] is False
    assert document["timer_enablement"] is False
    assert document["timer_start"] is False
    assert document["auto_renew_start"] is False
    assert document["daemon_reload"] is True
    assert document["broker_container_continuity"] is True
    assert document["server_certificate_unchanged"] is True
    assert document["server_private_key_unchanged"] is True
    assert document["ca_certificate_unchanged"] is True

    assert tool.LIFECYCLE_TARGET.is_file()
    assert tool.SERVICE_TARGET.is_file()
    assert tool.TIMER_TARGET.is_file()
    assert tool.ENV_TARGET.is_file()
    assert tool.STATUS_DIR.is_dir()
    assert stat.S_IMODE(tool.LIFECYCLE_TARGET.stat().st_mode) == 0o755
    assert stat.S_IMODE(tool.SERVICE_TARGET.stat().st_mode) == 0o644
    assert stat.S_IMODE(tool.TIMER_TARGET.stat().st_mode) == 0o644
    assert stat.S_IMODE(tool.ENV_TARGET.stat().st_mode) == 0o600
    assert stat.S_IMODE(tool.STATUS_DIR.stat().st_mode) == 0o700

    env = tool.ENV_TARGET.read_text(encoding="utf-8")
    assert str(runtime["server_cert"]) in env
    assert str(runtime["server_key"]) in env
    assert str(runtime["ca_cert"]) in env
    assert str(runtime["ca_key"]) in env
    assert str(runtime["system_ca"]) in env
    assert 'N3WFC4_CERT_SERVER_NAME="armbian"' in env


def test_existing_status_authority_stops_before_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    runtime = prepare_runtime(tmp_path, tool, monkeypatch)
    tool.STATUS_DIR.mkdir(parents=True)

    with pytest.raises(tool.InstallError, match="status_authority_already_present"):
        tool.install(
            runtime["lifecycle"],
            runtime["service"],
            runtime["timer"],
            runtime["preflight"],
        )

    assert not tool.LIFECYCLE_TARGET.exists()
    assert not tool.SERVICE_TARGET.exists()
    assert not tool.TIMER_TARGET.exists()
    assert not tool.ENV_TARGET.exists()


def test_existing_target_stops_before_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    runtime = prepare_runtime(tmp_path, tool, monkeypatch)
    tool.SERVICE_TARGET.write_text("unexpected", encoding="utf-8")

    with pytest.raises(tool.InstallError, match="deployment_target_already_present"):
        tool.install(
            runtime["lifecycle"],
            runtime["service"],
            runtime["timer"],
            runtime["preflight"],
        )


def test_timer_enabled_stops_before_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    runtime = prepare_runtime(tmp_path, tool, monkeypatch)
    original = tool._systemctl_state

    def state(mode: str, unit: str) -> str:
        if mode == "is-enabled" and unit == tool.LIFECYCLE_TIMER:
            return "enabled"
        return original(mode, unit)

    monkeypatch.setattr(tool, "_systemctl_state", state)

    with pytest.raises(tool.InstallError, match="timer_already_enabled"):
        tool.install(
            runtime["lifecycle"],
            runtime["service"],
            runtime["timer"],
            runtime["preflight"],
        )


def test_daemon_reload_failure_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    runtime = prepare_runtime(tmp_path, tool, monkeypatch)
    calls = 0

    def reload_once_fails():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise tool.InstallError("synthetic_daemon_reload_failure")

    monkeypatch.setattr(tool, "_systemctl_daemon_reload", reload_once_fails)

    document, code = tool.install(
        runtime["lifecycle"],
        runtime["service"],
        runtime["timer"],
        runtime["preflight"],
    )

    assert code == 2
    assert document["result"] == "STOP"
    assert document["installation_rollback"] == "PASS"
    assert not tool.LIFECYCLE_TARGET.exists()
    assert not tool.SERVICE_TARGET.exists()
    assert not tool.TIMER_TARGET.exists()
    assert not tool.ENV_TARGET.exists()
    assert not tool.STATUS_DIR.exists()


def test_ca_key_must_stay_under_persistent_fc4_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    runtime = prepare_runtime(tmp_path, tool, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_key = outside / "ca-key.pem"
    outside_key.write_bytes(b"outside")
    monkeypatch.setattr(
        tool,
        "_private_key_match",
        lambda _preflight, _ca: (outside_key, outside),
    )

    with pytest.raises(tool.InstallError, match="ca_private_key_outside_persistent_root"):
        tool.install(
            runtime["lifecycle"],
            runtime["service"],
            runtime["timer"],
            runtime["preflight"],
        )


def test_source_has_no_enable_start_restart_commands() -> None:
    source = TOOL.read_text(encoding="utf-8")
    forbidden = (
        "systemctl enable",
        "systemctl start",
        "systemctl restart",
        "systemctl stop",
        "docker restart",
        "docker exec",
        "docker compose",
        "auto-renew",
    )
    for token in forbidden:
        assert token not in source
    assert "systemctl", "daemon-reload" in source


def test_atomic_write_directory_fsync_failure_removes_replaced_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    target = tmp_path / "target"
    monkeypatch.setattr(tool.os, "chown", lambda *_args, **_kwargs: None)
    calls = 0
    original_fsync = tool.os.fsync

    def fail_second_fsync(fd: int):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic directory fsync failure")
        return original_fsync(fd)

    monkeypatch.setattr(tool.os, "fsync", fail_second_fsync)

    with pytest.raises(OSError, match="synthetic directory fsync failure"):
        tool._write_atomic(target, b"payload", 0o600)

    assert not target.exists()


def test_status_directory_owner_failure_rolls_back_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    runtime = prepare_runtime(tmp_path, tool, monkeypatch)

    def fail_status_chown(path, uid, gid):
        if Path(path) == tool.STATUS_DIR:
            raise OSError("synthetic status chown failure")

    monkeypatch.setattr(tool.os, "chown", fail_status_chown)

    document, code = tool.install(
        runtime["lifecycle"],
        runtime["service"],
        runtime["timer"],
        runtime["preflight"],
    )

    assert code == 2
    assert document["result"] == "STOP"
    assert document["installation_rollback"] == "PASS"
    assert not tool.STATUS_DIR.exists()
    assert not tool.LIFECYCLE_TARGET.exists()
    assert not tool.SERVICE_TARGET.exists()
    assert not tool.TIMER_TARGET.exists()
    assert not tool.ENV_TARGET.exists()
