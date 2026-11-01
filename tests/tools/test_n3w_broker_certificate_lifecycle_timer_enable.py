from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_broker_certificate_lifecycle_timer_enable.py"


def load_tool():
    specification = importlib.util.spec_from_file_location(
        "n3w_broker_certificate_lifecycle_timer_enable",
        TOOL,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def prepare_runtime(tmp_path: Path, tool, monkeypatch: pytest.MonkeyPatch):
    installed = tmp_path / "installed"
    tool_path = installed / "usr/local/sbin/n3w-broker-certificate-lifecycle"
    service_path = installed / "etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service"
    timer_path = installed / "etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer"
    env_path = installed / "etc/n3wfc4/broker-certificate-lifecycle.env"
    status_dir = installed / "var/lib/n3wfc4-certificate-lifecycle"
    for path in (tool_path.parent, service_path.parent, env_path.parent, status_dir):
        path.mkdir(parents=True, exist_ok=True)

    tool_path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    service_path.write_text("[Service]\nType=oneshot\n", encoding="utf-8")
    timer_path.write_text("[Timer]\nOnCalendar=daily\n", encoding="utf-8")
    os.chmod(tool_path, 0o755)
    os.chmod(service_path, 0o644)
    os.chmod(timer_path, 0o644)
    os.chmod(status_dir, 0o700)

    status_file = status_dir / "status.json"
    lock_file = status_dir / ".certificate-lifecycle.lock"
    status_file.write_text("status", encoding="utf-8")
    lock_file.write_text("", encoding="utf-8")
    os.chmod(status_file, 0o600)
    os.chmod(lock_file, 0o600)

    env_path.write_text(
        '\n'.join(
            (
                'N3WFC4_CERT_SERVER_CERT_FILE="/fc4/server.pem"',
                'N3WFC4_CERT_SERVER_KEY_FILE="/fc4/server.key"',
                'N3WFC4_CERT_CA_CERT_FILE="/fc4/ca.pem"',
                'N3WFC4_CERT_CA_KEY_FILE="/fc4/ca-key.pem"',
                'N3WFC4_CERT_SYSTEM_CA_FILE="/system/system-ca.pem"',
                'N3WFC4_CERT_SERVER_NAME="armbian"',
                f'N3WFC4_CERT_STATUS_FILE="{status_file}"',
                'N3WFC4_CERT_ALLOWED_ROOT_FC4="/fc4"',
                'N3WFC4_CERT_ALLOWED_ROOT_SYSTEM="/system"',
                "",
            )
        ),
        encoding="utf-8",
    )
    os.chmod(env_path, 0o600)

    monkeypatch.setattr(tool, "LIFECYCLE_TOOL", tool_path)
    monkeypatch.setattr(tool, "SERVICE_FILE", service_path)
    monkeypatch.setattr(tool, "TIMER_FILE", timer_path)
    monkeypatch.setattr(tool, "ENV_FILE", env_path)
    monkeypatch.setattr(tool, "STATUS_DIR", status_dir)
    monkeypatch.setattr(tool, "STATUS_FILE", status_file)
    monkeypatch.setattr(tool, "LOCK_FILE", lock_file)
    monkeypatch.setattr(tool.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        tool,
        "_owner_mode",
        lambda path: (0, 0, stat.S_IMODE(path.stat().st_mode)),
    )
    monkeypatch.setattr(tool, "_require_regular_exact", lambda *_args, **_kwargs: None)

    env = {
        "N3WFC4_CERT_SERVER_CERT_FILE": "/fc4/server.pem",
        "N3WFC4_CERT_SERVER_KEY_FILE": "/fc4/server.key",
        "N3WFC4_CERT_CA_CERT_FILE": "/fc4/ca.pem",
        "N3WFC4_CERT_CA_KEY_FILE": "/fc4/ca-key.pem",
        "N3WFC4_CERT_SYSTEM_CA_FILE": "/system/system-ca.pem",
        "N3WFC4_CERT_SERVER_NAME": "armbian",
        "N3WFC4_CERT_STATUS_FILE": str(status_file),
        "N3WFC4_CERT_ALLOWED_ROOT_FC4": "/fc4",
        "N3WFC4_CERT_ALLOWED_ROOT_SYSTEM": "/system",
    }
    monkeypatch.setattr(tool, "_parse_env", lambda: env)
    monkeypatch.setattr(
        tool,
        "_read_status",
        lambda: ({"result": "ok"}, "status-sha"),
    )
    runtime = {
        "container": "broker-container",
        "started": "2026-09-20T00:00:00Z",
        "server_cert_sha256": "server-cert-sha",
        "server_key_sha256": "server-key-sha",
        "ca_cert_sha256": "ca-cert-sha",
        "ca_cert": Path("/fc4/ca.pem"),
    }
    monkeypatch.setattr(tool, "_capture_runtime", lambda _env: dict(runtime))

    states = {
        ("is-active", tool.LIFECYCLE_TIMER): "inactive",
        ("is-enabled", tool.LIFECYCLE_TIMER): "disabled",
        ("is-active", tool.LIFECYCLE_SERVICE): "inactive",
    }
    calls: list[tuple[str, ...]] = []

    def run(argv, *, timeout=30, allow_failure=False):
        command = tuple(argv)
        calls.append(command)
        if command == ("systemctl", "enable", tool.LIFECYCLE_TIMER):
            states[("is-enabled", tool.LIFECYCLE_TIMER)] = "enabled"
            return subprocess.CompletedProcess(argv, 0, "", "")
        if command == ("systemctl", "disable", tool.LIFECYCLE_TIMER):
            states[("is-enabled", tool.LIFECYCLE_TIMER)] = "disabled"
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(tool, "_run", run)
    monkeypatch.setattr(tool, "_systemctl_state", lambda mode, unit: states[(mode, unit)])
    return states, calls


def test_timer_enablement_success_uses_enable_without_now(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    states, calls = prepare_runtime(tmp_path, tool, monkeypatch)

    document, code = tool.enable_timer()

    assert code == 0
    assert document["result"] == "PASS"
    assert document["timer_enablement"] is True
    assert document["timer_enabled"] == "enabled"
    assert document["timer_active"] == "inactive"
    assert document["lifecycle_service_active"] == "inactive"
    assert document["timer_start"] is False
    assert document["enable_now_used"] is False
    assert document["auto_renew_invocation"] is False
    assert document["status_unchanged"] is True
    assert document["broker_restart"] is False
    assert document["certificate_mutation"] is False
    assert ("systemctl", "enable", tool.LIFECYCLE_TIMER) in calls
    assert all("--now" not in command for command in calls)
    assert states[("is-enabled", tool.LIFECYCLE_TIMER)] == "enabled"


def test_prestate_requires_disabled_timer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    states, calls = prepare_runtime(tmp_path, tool, monkeypatch)
    states[("is-enabled", tool.LIFECYCLE_TIMER)] = "enabled"

    with pytest.raises(tool.TimerEnableError, match="timer_prestate_not_disabled"):
        tool.enable_timer()

    assert not calls


def test_enable_failure_rolls_back_to_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    states, calls = prepare_runtime(tmp_path, tool, monkeypatch)

    def run(argv, *, timeout=30, allow_failure=False):
        command = tuple(argv)
        calls.append(command)
        if command == ("systemctl", "enable", tool.LIFECYCLE_TIMER):
            states[("is-enabled", tool.LIFECYCLE_TIMER)] = "enabled"
            return subprocess.CompletedProcess(argv, 1, "", "synthetic")
        if command == ("systemctl", "disable", tool.LIFECYCLE_TIMER):
            states[("is-enabled", tool.LIFECYCLE_TIMER)] = "disabled"
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(tool, "_run", run)

    document, code = tool.enable_timer()

    assert code == 2
    assert document["result"] == "STOP"
    assert document["reason"] == "systemctl_enable_failed"
    assert document["enablement_rollback"] == "PASS"
    assert states[("is-enabled", tool.LIFECYCLE_TIMER)] == "disabled"


def test_poststate_active_timer_rolls_back_enablement_but_stays_unproven(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    states, calls = prepare_runtime(tmp_path, tool, monkeypatch)

    def run(argv, *, timeout=30, allow_failure=False):
        command = tuple(argv)
        calls.append(command)
        if command == ("systemctl", "enable", tool.LIFECYCLE_TIMER):
            states[("is-enabled", tool.LIFECYCLE_TIMER)] = "enabled"
            states[("is-active", tool.LIFECYCLE_TIMER)] = "active"
            return subprocess.CompletedProcess(argv, 0, "", "")
        if command == ("systemctl", "disable", tool.LIFECYCLE_TIMER):
            states[("is-enabled", tool.LIFECYCLE_TIMER)] = "disabled"
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(tool, "_run", run)

    document, code = tool.enable_timer()

    assert code == 3
    assert document["result"] == "STOP"
    assert document["reason"] == "timer_became_active"
    assert document["enablement_rollback"] == "UNPROVEN"
    assert states[("is-enabled", tool.LIFECYCLE_TIMER)] == "disabled"
    assert states[("is-active", tool.LIFECYCLE_TIMER)] == "active"


def test_status_change_after_enablement_triggers_disable_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    states, _calls = prepare_runtime(tmp_path, tool, monkeypatch)
    read_count = 0

    def read_status():
        nonlocal read_count
        read_count += 1
        return ({"result": "ok"}, "before" if read_count == 1 else "after")

    monkeypatch.setattr(tool, "_read_status", read_status)

    document, code = tool.enable_timer()

    assert code == 2
    assert document["result"] == "STOP"
    assert document["reason"] == "status_changed_during_enablement"
    assert document["enablement_rollback"] == "PASS"
    assert states[("is-enabled", tool.LIFECYCLE_TIMER)] == "disabled"


def test_source_never_uses_enable_now_or_start_restart() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '"enable", LIFECYCLE_TIMER' in source
    assert "--now" not in source
    forbidden = (
        '"start"',
        '"restart"',
        "auto-renew",
        "docker restart",
        "docker exec",
    )
    for token in forbidden:
        assert token not in source
