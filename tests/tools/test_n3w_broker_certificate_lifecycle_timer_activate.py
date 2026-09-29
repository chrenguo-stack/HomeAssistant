from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_broker_certificate_lifecycle_timer_activate.py"


def load_tool():
    specification = importlib.util.spec_from_file_location(
        "n3w_broker_certificate_lifecycle_timer_activate",
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
    timer_path.write_text("[Timer]\nOnCalendar=daily\nPersistent=true\n", encoding="utf-8")
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

    monkeypatch.setattr(tool, "LIFECYCLE_TOOL", tool_path)
    monkeypatch.setattr(tool, "SERVICE_FILE", service_path)
    monkeypatch.setattr(tool, "TIMER_FILE", timer_path)
    monkeypatch.setattr(tool, "ENV_FILE", env_path)
    monkeypatch.setattr(tool, "STATUS_DIR", status_dir)
    monkeypatch.setattr(tool, "STATUS_FILE", status_file)
    monkeypatch.setattr(tool, "LOCK_FILE", lock_file)
    monkeypatch.setattr(tool.os, "geteuid", lambda: 0)
    monkeypatch.setattr(tool, "_require_regular_exact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(tool, "_parse_env", lambda: dict(env))
    monkeypatch.setattr(
        tool,
        "_owner_mode",
        lambda path: (0, 0, stat.S_IMODE(path.stat().st_mode)),
    )

    status_document = {
        "schema": "gh.n3w-broker-certificate-lifecycle/1",
        "action": "audit",
        "result": "ok",
        "server_state": "HEALTHY",
        "ca_state": "HEALTHY",
        "system_ca_state": "HEALTHY",
        "renewal_attempted": False,
        "rollback_attempted": False,
        "server_sha256_fingerprint": tool.EXPECTED_SERVER_FINGERPRINT,
        "ca_sha256_fingerprint": tool.EXPECTED_CA_FINGERPRINT,
        "system_ca_sha256_fingerprint": tool.EXPECTED_SYSTEM_CA_FINGERPRINT,
        "server_not_after": "2028-11-22T04:18:40Z",
        "ca_not_after": "2036-08-17T04:18:39Z",
        "system_ca_not_after": "2036-07-30T15:32:24Z",
    }

    status_hashes = ["before", "before"]

    def status():
        value = status_hashes.pop(0) if len(status_hashes) > 1 else status_hashes[0]
        return dict(status_document), "{}", value

    monkeypatch.setattr(tool, "_status_document", status)

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
        ("is-enabled", tool.LIFECYCLE_TIMER): "enabled",
        ("is-active", tool.LIFECYCLE_TIMER): "inactive",
        ("is-active", tool.LIFECYCLE_SERVICE): "inactive",
    }
    monkeypatch.setattr(tool, "_systemctl_state", lambda mode, unit: states[(mode, unit)])
    monkeypatch.setattr(tool, "_wait_service_quiescent", lambda: states[("is-active", tool.LIFECYCLE_SERVICE)])

    properties = [
        {
            "ActiveState": "active",
            "UnitFileState": "enabled",
            "NextElapseUSecRealtime": "Wed 2026-09-30 00:25:00 CST",
            "LastTriggerUSec": "n/a",
            "Result": "success",
        },
        {
            "ActiveState": "active",
            "UnitFileState": "enabled",
            "NextElapseUSecRealtime": "Wed 2026-09-30 00:25:00 CST",
            "LastTriggerUSec": "n/a",
            "Result": "success",
        },
    ]

    def timer_properties():
        return dict(properties.pop(0) if len(properties) > 1 else properties[0])

    monkeypatch.setattr(tool, "_timer_properties", timer_properties)

    calls: list[tuple[str, ...]] = []

    def run(argv, *, timeout=30, allow_failure=False):
        command = tuple(argv)
        calls.append(command)
        if command == ("systemctl", "start", tool.LIFECYCLE_TIMER):
            states[("is-active", tool.LIFECYCLE_TIMER)] = "active"
            return subprocess.CompletedProcess(argv, 0, "", "")
        if command == ("systemctl", "stop", tool.LIFECYCLE_TIMER):
            states[("is-active", tool.LIFECYCLE_TIMER)] = "inactive"
            return subprocess.CompletedProcess(argv, 0, "", "")
        if command == ("systemctl", "disable", tool.LIFECYCLE_TIMER):
            states[("is-enabled", tool.LIFECYCLE_TIMER)] = "disabled"
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(tool, "_run", run)
    return states, calls, status_hashes, properties


def test_runtime_activation_without_immediate_catchup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    _states, calls, _hashes, _properties = prepare_runtime(tmp_path, tool, monkeypatch)

    document, code = tool.activate_timer()

    assert code == 0
    assert document["result"] == "PASS"
    assert document["timer_runtime_activation"] is True
    assert document["timer_enabled"] == "enabled"
    assert document["timer_active"] == "active"
    assert document["lifecycle_service_active"] == "inactive"
    assert document["persistent_catchup_observed"] is False
    assert document["status_changed_during_activation"] is False
    assert document["renewal_attempted"] is False
    assert document["certificate_mutation"] is False
    assert ("systemctl", "start", tool.LIFECYCLE_TIMER) in calls


def test_runtime_activation_accepts_healthy_persistent_catchup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    _states, _calls, hashes, properties = prepare_runtime(tmp_path, tool, monkeypatch)
    hashes[:] = ["before", "after"]
    properties[1]["LastTriggerUSec"] = "Tue 2026-09-29 15:01:00 CST"

    document, code = tool.activate_timer()

    assert code == 0
    assert document["result"] == "PASS"
    assert document["persistent_catchup_observed"] is True
    assert document["status_changed_during_activation"] is True
    assert document["last_trigger_usec"] == "Tue 2026-09-29 15:01:00 CST"
    assert document["renewal_attempted"] is False
    assert document["broker_restart"] is False


def test_status_change_without_timer_trigger_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    states, _calls, hashes, _properties = prepare_runtime(tmp_path, tool, monkeypatch)
    hashes[:] = ["before", "after"]

    document, code = tool.activate_timer()

    assert code == 2
    assert document["result"] == "STOP"
    assert document["reason"] == "status_changed_without_timer_trigger"
    assert document["activation_rollback"] == "PASS"
    assert states[("is-enabled", tool.LIFECYCLE_TIMER)] == "disabled"
    assert states[("is-active", tool.LIFECYCLE_TIMER)] == "inactive"


def test_missing_next_elapse_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    states, _calls, _hashes, properties = prepare_runtime(tmp_path, tool, monkeypatch)
    properties[0]["NextElapseUSecRealtime"] = "n/a"

    document, code = tool.activate_timer()

    assert code == 2
    assert document["result"] == "STOP"
    assert document["reason"] == "timer_next_elapse_missing"
    assert document["activation_rollback"] == "PASS"
    assert states[("is-enabled", tool.LIFECYCLE_TIMER)] == "disabled"
    assert states[("is-active", tool.LIFECYCLE_TIMER)] == "inactive"


def test_prestate_requires_enabled_inactive_timer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    states, calls, _hashes, _properties = prepare_runtime(tmp_path, tool, monkeypatch)
    states[("is-enabled", tool.LIFECYCLE_TIMER)] = "disabled"

    with pytest.raises(tool.TimerActivationError, match="timer_not_enabled"):
        tool.activate_timer()

    assert not calls


def test_source_has_no_restart_or_auto_renew_invocation() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '"start", LIFECYCLE_TIMER' in source
    assert '"stop", LIFECYCLE_TIMER' in source
    assert '"disable", LIFECYCLE_TIMER' in source
    assert '"restart"' not in source
    assert "auto-renew" not in source
