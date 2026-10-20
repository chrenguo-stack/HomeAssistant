from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_f4_reboot_verify.py"


def load_tool():
    name = "n3w_t1_f4_reboot_verify"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_requires_new_boot_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    claim = {
        "schema": tool.CLAIM_SCHEMA,
        "stage": "REBOOT_PENDING",
        "reboot_authorization_claimed": True,
        "reboot_authorization_consumed": True,
        "reboot_authorization_replay_allowed": False,
        "reboot_acceptance_passed": False,
        "pre_boot_id_sha256": "a" * 64,
        "f4_transaction_sha256": "b" * 64,
        "board_access": False,
    }
    monkeypatch.setattr(tool, "_json", lambda _path, _mode: claim)
    monkeypatch.setattr(tool, "_installed_control_binding", lambda _claim: None)
    monkeypatch.setattr(tool, "_boot_id_sha256", lambda: "a" * 64)

    with pytest.raises(tool.VerifyError, match="reboot_not_observed"):
        tool.verify()


def test_verify_rejects_changed_f4_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    claim = {
        "schema": tool.CLAIM_SCHEMA,
        "stage": "REBOOT_PENDING",
        "reboot_authorization_claimed": True,
        "reboot_authorization_consumed": True,
        "reboot_authorization_replay_allowed": False,
        "reboot_acceptance_passed": False,
        "pre_boot_id_sha256": "a" * 64,
        "f4_transaction_sha256": "b" * 64,
        "board_access": False,
    }
    monkeypatch.setattr(tool, "_json", lambda _path, _mode: claim)
    monkeypatch.setattr(tool, "_installed_control_binding", lambda _claim: None)
    monkeypatch.setattr(tool, "_boot_id_sha256", lambda: "c" * 64)
    monkeypatch.setattr(tool, "_sha256", lambda _path: "d" * 64)

    with pytest.raises(
        tool.VerifyError,
        match="f4_transaction_changed_across_reboot",
    ):
        tool.verify()


def test_verifier_is_read_only_for_reboot_control() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '("systemctl", "reboot")' not in source
    assert '("systemctl", "poweroff")' not in source
    assert '("shutdown"' not in source
    assert "write_text(" not in source
    assert "os.replace(" not in source



def test_inactive_certificate_oneshot_must_have_success_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    monkeypatch.setattr(
        tool,
        "_run",
        lambda *_args, **_kwargs: (
            "ActiveState=inactive\n"
            "Result=exit-code\n"
            "ExecMainStatus=2\n"
        ),
    )
    with pytest.raises(tool.VerifyError, match="oneshot_not_successful"):
        tool._inactive_oneshot_success("certificate.service")


def test_inactive_certificate_oneshot_success_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    monkeypatch.setattr(
        tool,
        "_run",
        lambda *_args, **_kwargs: (
            "ActiveState=inactive\n"
            "Result=success\n"
            "ExecMainStatus=0\n"
        ),
    )
    tool._inactive_oneshot_success("certificate.service")



def test_control_binding_rejects_tampered_installed_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    manifest = tmp_path / "manifest.json"
    target = tmp_path / "guard.py"
    target.write_text("exact", encoding="utf-8")
    target.chmod(0o755)

    monkeypatch.setattr(tool, "CONTROL_MANIFEST", manifest)
    monkeypatch.setattr(
        tool,
        "CONTROL_TARGETS",
        {"guard.py": (target, 0o755)},
    )

    document = {
        "schema": tool.PACKAGE_SCHEMA,
        "source_head": "a" * 40,
        "files": [
            {
                "path": "guard.py",
                "sha256": "0" * 64,
                "size": target.stat().st_size,
            }
        ],
    }
    manifest.write_text(
        __import__("json").dumps(document) + "\n",
        encoding="utf-8",
    )
    manifest.chmod(0o644)

    monkeypatch.setattr(
        tool,
        "_json",
        lambda path, _mode: __import__("json").loads(
            path.read_text(encoding="utf-8")
        ),
    )

    claim = {
        "source_head": "a" * 40,
        "control_manifest_sha256": tool._sha256(manifest),
    }
    with pytest.raises(tool.VerifyError, match="control_target_binding_invalid"):
        tool._installed_control_binding(claim)


def test_broker_auth_evidence_requires_current_exact_identity_and_catches_reconnect():
    tool = load_tool()
    identity = {"client_id": "test-service", "username": "test-user"}
    connected = "123: New client connected from 172.18.0.1:4000 as test-service (p5, c1, k60, u'test-user')."
    before = tool._broker_auth_evidence(connected, identity)
    for suffix in ("Client test-service disconnected.", "Client test-service closed its connection.",
                   "Client test-service already connected, closing old connection.",
                   connected.replace("test-user", "other")):
        with pytest.raises(tool.VerifyError, match="unproven"):
            tool._broker_auth_evidence(connected + "\n" + suffix, identity)
    after = tool._broker_auth_evidence(connected + "\nClient test-service disconnected.\n" + connected, identity)
    assert before != after
    with pytest.raises(tool.VerifyError, match="unproven"):
        tool._broker_auth_evidence("", identity)
    with pytest.raises(tool.VerifyError, match="coverage"):
        tool._broker_auth_evidence("x\n" * tool.LOG_LIMIT + connected, identity)


def test_socket_script_observes_real_owned_endpoint_without_network_mutation():
    import json
    import socket
    import subprocess
    import sys
    tool = load_tool()
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port)) as client:
            peer, _ = server.accept()
            with peer:
                args = [sys.executable, "-c", tool.SOCKET_SCRIPT, "127.0.0.1", str(port)]
                first = json.loads(subprocess.check_output(args, text=True))
                second = json.loads(subprocess.check_output(args, text=True))
                assert first == second and len(first["owned_socket_sha256"]) == 64
                client.shutdown(socket.SHUT_RDWR)
                failed = subprocess.run(args, check=False, capture_output=True)
                assert failed.returncode != 0


def test_snapshot_cli_dispatches_without_running_full_f4(monkeypatch, capsys):
    import json
    tool = load_tool()
    monkeypatch.setattr(tool.sys, "argv", ["n3w-t1-f4-reboot-verify", "--snapshot"])
    monkeypatch.setattr(tool, "verify", lambda: pytest.fail("full verifier must not run on each sample"))
    monkeypatch.setattr(tool, "runtime_snapshot", lambda: {"schema": tool.SNAPSHOT_SCHEMA, "status": "PASS"})
    assert tool.main() == 0
    assert json.loads(capsys.readouterr().out)["schema"] == tool.SNAPSHOT_SCHEMA


def test_systemd_snapshot_allows_healthy_certificate_oneshot_and_detects_errors(monkeypatch):
    from types import SimpleNamespace
    tool = load_tool()
    module = SimpleNamespace(**{name: name for name in (
        "PROVISION_UNIT", "GUARD_UNIT", "BROKER_UNIT", "SERVICES_UNIT", "CERT_TIMER", "CERT_SERVICE",
    )})
    active = ["inactive"]
    errors = [""]
    def run(argv):
        if argv[0] == "journalctl":
            return errors[0]
        state = active[0] if argv[2] == "CERT_SERVICE" else "active"
        return "ActiveState=" + state + "\nResult=success\nExecMainStatus=0\nNRestarts=0\nExecMainStartTimestampMonotonic=10\n"
    monkeypatch.setattr(tool, "_snapshot_run", run)
    before = tool._systemd_snapshot(module)
    active[0] = "activating"
    assert tool._systemd_snapshot(module) == before
    errors[0] = '{"__CURSOR":"new-error-event"}'
    assert tool._systemd_snapshot(module) != before
    active[0] = "failed"
    with pytest.raises(tool.VerifyError, match="state_invalid"):
        tool._systemd_snapshot(module)


def test_snapshot_entrypoint_collects_bound_public_evidence(monkeypatch, capsys):
    import json
    from types import SimpleNamespace
    tool = load_tool()
    claim = {"source_head": "a" * 40, "control_manifest_sha256": "b" * 64,
             "f4_transaction_sha256": "c" * 64}
    monkeypatch.setattr(tool, "_json", lambda *args: claim)
    monkeypatch.setattr(tool, "_sha256", lambda path: "c" * 64)
    monkeypatch.setattr(tool, "_installed_control_binding", lambda doc: None)
    monkeypatch.setattr(tool, "_boot_id_sha256", lambda: "d" * 64)
    def identity(path, *, uid, gid):
        name = path.parent.name
        assert uid == gid == (999 if name == "manager" else 0)
        return {"username": "user-" + name, "client_id": name}
    module = SimpleNamespace(
        _private_service_json=identity,
        _compose_service_inspect=lambda name: {
            "Id": name, "RestartCount": 0,
            "State": {"Running": True, "Paused": False, "Restarting": False, "StartedAt": "2026-10-20T00:00:00Z"},
        },
    )
    monkeypatch.setattr(tool, "_load_f4", lambda: module)
    monkeypatch.setattr(tool, "_systemd_snapshot", lambda mod: ("e" * 64, "f" * 64))
    calls = []
    def run(argv):
        calls.append(argv)
        if argv[1] == "logs":
            return "\n".join(f"123: New client connected from 172.18.0.1:4000 as {name} (p5, c1, k60, u'user-{name}')."
                             for name in ("manager", "homeassistant"))
        assert argv[:2] == ("docker", "exec")
        return json.dumps({"owned_socket_sha256": "1" * 64})
    monkeypatch.setattr(tool, "_snapshot_run", run)
    class HTTP:
        def __init__(self, host, port, timeout):
            assert (host, port) == ("127.0.0.1", 8123)
        def request(self, method, path):
            assert (method, path) == ("GET", "/api/")
        def getresponse(self):
            return SimpleNamespace(status=401, read=lambda size: b"")
        def close(self):
            pass
    monkeypatch.setattr(tool.http.client, "HTTPConnection", HTTP)
    monkeypatch.setattr(tool.sys, "argv", ["verifier", "--snapshot"])
    assert tool.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["source_head"] == claim["source_head"]
    assert report["runtime_service_auth"]["manager"]["endpoint_port"] == 8883
    assert report["runtime_service_auth"]["homeassistant"]["endpoint_port"] == 1883
    assert len(calls) == 3
    public = json.dumps(report)
    assert "user-manager" not in public and "172.18" not in public
    assert "password" not in public
