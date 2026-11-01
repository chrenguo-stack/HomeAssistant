from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_broker_certificate_lifecycle_first_audit.py"


def load_tool():
    specification = importlib.util.spec_from_file_location(
        "n3w_broker_certificate_lifecycle_first_audit",
        TOOL,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


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

    fc4_root = tmp_path / "fc4"
    tls = fc4_root / "broker/tls"
    tls.mkdir(parents=True)
    server_cert = tls / "server.pem"
    server_key = tls / "server.key"
    ca_cert = tls / "ca.pem"
    ca_key = tls / "ca-key.pem"
    server_cert.write_bytes(b"server-cert")
    server_key.write_bytes(b"server-key")
    ca_cert.write_bytes(b"ca-cert")
    ca_key.write_bytes(b"ca-key")

    system_root = tmp_path / "system"
    system_root.mkdir()
    system_ca = system_root / "system-ca.pem"
    system_ca.write_bytes(b"system-ca")

    env = {
        "N3WFC4_CERT_SERVER_CERT_FILE": str(server_cert),
        "N3WFC4_CERT_SERVER_KEY_FILE": str(server_key),
        "N3WFC4_CERT_CA_CERT_FILE": str(ca_cert),
        "N3WFC4_CERT_CA_KEY_FILE": str(ca_key),
        "N3WFC4_CERT_SYSTEM_CA_FILE": str(system_ca),
        "N3WFC4_CERT_SERVER_NAME": "armbian",
        "N3WFC4_CERT_STATUS_FILE": str(status_dir / "status.json"),
        "N3WFC4_CERT_ALLOWED_ROOT_FC4": str(fc4_root),
        "N3WFC4_CERT_ALLOWED_ROOT_SYSTEM": str(system_root),
    }
    env_path.write_text(
        "".join(f'{key}="{value}"\n' for key, value in env.items()),
        encoding="utf-8",
    )
    os.chmod(env_path, 0o600)

    monkeypatch.setattr(tool, "LIFECYCLE_TOOL", tool_path)
    monkeypatch.setattr(tool, "SERVICE_FILE", service_path)
    monkeypatch.setattr(tool, "TIMER_FILE", timer_path)
    monkeypatch.setattr(tool, "ENV_FILE", env_path)
    monkeypatch.setattr(tool, "STATUS_DIR", status_dir)
    monkeypatch.setattr(tool, "STATUS_FILE", status_dir / "status.json")
    monkeypatch.setattr(tool, "LOCK_FILE", status_dir / ".certificate-lifecycle.lock")
    monkeypatch.setattr(tool, "LIFECYCLE_TOOL_BLOB", blob(tool_path))
    monkeypatch.setattr(tool, "SERVICE_BLOB", blob(service_path))
    monkeypatch.setattr(tool, "TIMER_BLOB", blob(timer_path))
    monkeypatch.setattr(tool.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        tool,
        "_owner_mode",
        lambda path: (0, 0, stat.S_IMODE(path.stat().st_mode)),
    )

    states = {
        ("is-active", tool.LIFECYCLE_SERVICE): "inactive",
        ("is-active", tool.LIFECYCLE_TIMER): "inactive",
        ("is-enabled", tool.LIFECYCLE_TIMER): "disabled",
    }
    monkeypatch.setattr(tool, "_systemctl_state", lambda mode, unit: states[(mode, unit)])

    inspect = {
        "State": {"Running": True, "StartedAt": "2026-09-20T00:00:00Z"},
        "Mounts": [
            {
                "Destination": "/mosquitto/tls/ca.pem",
                "Source": str(ca_cert),
                "Type": "bind",
                "RW": False,
            },
            {
                "Destination": "/mosquitto/tls/server.pem",
                "Source": str(server_cert),
                "Type": "bind",
                "RW": False,
            },
            {
                "Destination": "/mosquitto/tls/server.key",
                "Source": str(server_key),
                "Type": "bind",
                "RW": False,
            },
        ],
    }
    monkeypatch.setattr(
        tool,
        "_broker_container",
        lambda: ("broker-container", "2026-09-20T00:00:00Z", inspect),
    )
    monkeypatch.setattr(
        tool,
        "_fingerprint",
        lambda path: {
            server_cert: tool.EXPECTED_SERVER_FINGERPRINT,
            ca_cert: tool.EXPECTED_CA_FINGERPRINT,
            system_ca: tool.EXPECTED_SYSTEM_CA_FINGERPRINT,
        }[path],
    )
    monkeypatch.setattr(
        tool,
        "_live_tls_fingerprint",
        lambda _ca, _name: tool.EXPECTED_SERVER_FINGERPRINT,
    )

    document = {
        "schema": "gh.n3w-broker-certificate-lifecycle/1",
        "checked_at": "2026-09-29T06:00:00Z",
        "server_not_after": "2028-11-22T04:18:40Z",
        "server_remaining_seconds": 1,
        "server_state": "HEALTHY",
        "server_sha256_fingerprint": tool.EXPECTED_SERVER_FINGERPRINT,
        "ca_not_after": "2036-08-17T04:18:39Z",
        "ca_remaining_seconds": 1,
        "ca_state": "HEALTHY",
        "ca_sha256_fingerprint": tool.EXPECTED_CA_FINGERPRINT,
        "system_ca_not_after": "2036-07-30T15:32:24Z",
        "system_ca_remaining_seconds": 1,
        "system_ca_state": "HEALTHY",
        "system_ca_sha256_fingerprint": tool.EXPECTED_SYSTEM_CA_FINGERPRINT,
        "action": "audit",
        "result": "ok",
        "renewal_attempted": False,
        "rollback_attempted": False,
    }

    def run(argv, *, timeout=30, allow_failure=False):
        if tuple(argv)[1:2] == ("audit",):
            tool.STATUS_FILE.write_text(
                json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            tool.LOCK_FILE.write_text("", encoding="utf-8")
            os.chmod(tool.STATUS_FILE, 0o600)
            os.chmod(tool.LOCK_FILE, 0o600)
            return subprocess.CompletedProcess(argv, 0, json.dumps(document), "")
        raise AssertionError(f"unexpected command: {argv}")

    monkeypatch.setattr(tool, "_run", run)
    return env, document


def test_audit_argv_omits_private_keys_and_auto_renew(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    env, _ = prepare_runtime(tmp_path, tool, monkeypatch)
    argv = tool._audit_argv(env)

    assert argv[1] == "audit"
    assert "--server-key" not in argv
    assert "--ca-key" not in argv
    assert "auto-renew" not in argv


def test_first_audit_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    prepare_runtime(tmp_path, tool, monkeypatch)

    result, code = tool.first_audit()

    assert code == 0
    assert result["result"] == "PASS"
    assert result["first_audit"] is True
    assert result["audit_action"] == "audit"
    assert result["audit_result"] == "ok"
    assert result["server_state"] == "HEALTHY"
    assert result["ca_state"] == "HEALTHY"
    assert result["system_ca_state"] == "HEALTHY"
    assert result["renewal_attempted"] is False
    assert result["rollback_attempted"] is False
    assert result["certificate_mutation"] is False
    assert result["broker_restart"] is False
    assert result["timer_enablement"] is False
    assert result["auto_renew_invocation"] is False
    assert result["private_key_arguments_used"] is False
    assert tool.STATUS_FILE.is_file()
    assert tool.LOCK_FILE.is_file()


def test_existing_status_stops_first_audit_before_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    prepare_runtime(tmp_path, tool, monkeypatch)
    tool.STATUS_FILE.write_text("existing", encoding="utf-8")

    called = False

    def forbidden(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("audit must not run")

    monkeypatch.setattr(tool, "_run", forbidden)

    with pytest.raises(tool.AuditGateError, match="first_audit_status_already_present"):
        tool.first_audit()

    assert called is False


def test_unexpected_audit_document_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    _env, document = prepare_runtime(tmp_path, tool, monkeypatch)
    bad = dict(document)
    bad["renewal_attempted"] = True

    def run(argv, *, timeout=30, allow_failure=False):
        tool.STATUS_FILE.write_text(
            json.dumps(bad, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        tool.LOCK_FILE.write_text("", encoding="utf-8")
        os.chmod(tool.STATUS_FILE, 0o600)
        os.chmod(tool.LOCK_FILE, 0o600)
        return subprocess.CompletedProcess(argv, 0, json.dumps(bad), "")

    monkeypatch.setattr(tool, "_run", run)

    with pytest.raises(tool.AuditGateError, match="audit_document_unexpected"):
        tool.first_audit()


def test_environment_requires_exact_key_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    prepare_runtime(tmp_path, tool, monkeypatch)
    raw = tool.ENV_FILE.read_text(encoding="utf-8")
    tool.ENV_FILE.write_text(
        raw + 'UNKNOWN_KEY="value"\n',
        encoding="utf-8",
    )

    with pytest.raises(tool.AuditGateError, match="environment_key_invalid"):
        tool._parse_environment(tool.ENV_FILE)


def test_source_contains_no_service_or_timer_activation() -> None:
    source = TOOL.read_text(encoding="utf-8")
    forbidden = (
        "systemctl enable",
        "systemctl start",
        "systemctl restart",
        "systemctl stop",
        "docker restart",
        "docker exec",
    )
    for token in forbidden:
        assert token not in source


def test_unknown_status_directory_entry_stops_first_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    prepare_runtime(tmp_path, tool, monkeypatch)
    (tool.STATUS_DIR / "unexpected").write_text("x", encoding="utf-8")

    with pytest.raises(tool.AuditGateError, match="first_audit_status_directory_not_empty"):
        tool.first_audit()
