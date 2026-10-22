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


def test_broker_auth_evidence_requires_latest_explicit_lifecycle_to_be_authenticated():
    tool = load_tool()
    identity = {"client_id": "test-service", "username": "test-user"}
    connected = "123: New client connected from 192.0.2.1:4000 as test-service (p5, c1, k60, u'test-user')."
    before = tool._broker_auth_evidence(connected, identity)

    for suffix in (
        "Client test-service benign event.",
        "Client test-service-f4-invalid disconnected.",
    ):
        assert tool._broker_auth_evidence(connected + "\n" + suffix, identity) == before

    for terminal in (
        "Client test-service [192.0.2.1:4000] disconnected.",
        "Client test-service [192.0.2.1:4000] disconnected: connection closed by client.",
        "Client test-service [192.0.2.1:4000] disconnected: exceeded timeout.",
        "Client test-service [192.0.2.1:4000] disconnected: session taken over.",
        "Client test-service [192.0.2.1:4000] disconnected: malformed packet.",
        "Client test-service [192.0.2.1:4000] disconnected: bad socket read/write: protocol error",
        "Client test-service disconnected.",
        "Client test-service closed its connection.",
        "Client test-service already connected, closing old connection.",
        "Client test-service has exceeded timeout, disconnecting.",
    ):
        with pytest.raises(
            tool.EvidenceInsufficientError,
            match="current_session_authentication_evidence_missing",
        ):
            tool._broker_auth_evidence(connected + "\n" + terminal, identity)

    after = tool._broker_auth_evidence(
        connected
        + "\nClient test-service [192.0.2.1:4000] disconnected: session taken over.\n"
        + connected,
        identity,
    )
    assert before != after

    with pytest.raises(
        tool.VerifyError,
        match="broker_authenticated_connection_identity_mismatch",
    ):
        tool._broker_auth_evidence(connected.replace("test-user", "other"), identity)

    with pytest.raises(
        tool.EvidenceInsufficientError,
        match="evidence_missing",
    ):
        tool._broker_auth_evidence("Client test-service disconnected.", identity)

    with pytest.raises(
        tool.EvidenceInsufficientError,
        match="coverage",
    ):
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
                assert first == second
                assert first["owned_socket_count"] == 1
                assert len(first["owned_socket_sha256"]) == 64
                client.shutdown(socket.SHUT_RDWR)
                after = json.loads(subprocess.check_output(args, text=True))
                assert after["owned_socket_count"] == 0
                assert len(after["owned_socket_sha256"]) == 64


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
            return (
                "123: New client connected from 192.0.2.1:4000 as manager "
                "(p5, c1, k60, u'user-manager').\n"
                "Client manager benign event.\n"
                "123: New client connected from 192.0.2.1:4001 as homeassistant "
                "(p5, c1, k60, u'user-homeassistant').\n"
                "Client homeassistant benign event."
            )
        assert argv[:2] == ("docker", "exec")
        return json.dumps({"owned_socket_count": 1, "owned_socket_sha256": "1" * 64})
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
    assert len(calls) == 6
    public = json.dumps(report)
    assert "user-manager" not in public and "192.0.2" not in public
    assert "password" not in public



def test_runtime_snapshot_rejects_terminal_session_even_with_stable_current_socket(monkeypatch):
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
        return {"username": "user-" + name, "client_id": name}

    module = SimpleNamespace(
        _private_service_json=identity,
        _compose_service_inspect=lambda name: {
            "Id": name, "RestartCount": 0,
            "State": {"Running": True, "Paused": False, "Restarting": False,
                      "StartedAt": "2026-10-20T00:00:00Z"},
        },
    )
    monkeypatch.setattr(tool, "_load_f4", lambda: module)
    monkeypatch.setattr(tool, "_systemd_snapshot", lambda mod: ("e" * 64, "f" * 64))

    def run(argv):
        if argv[1] == "logs":
            return (
                "123: New client connected from 192.0.2.1:4000 as manager "
                "(p5, c1, k60, u'user-manager').\n"
                "Client manager [192.0.2.1:4000] disconnected: connection closed by client."
            )
        return json.dumps({"owned_socket_count": 1, "owned_socket_sha256": "1" * 64})

    monkeypatch.setattr(tool, "_snapshot_run", run)
    with pytest.raises(
        tool.EvidenceInsufficientError,
        match="current_session_authentication_evidence_missing",
    ):
        tool.runtime_snapshot()


def test_runtime_snapshot_rejects_socket_change_across_auth_evidence(monkeypatch):
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
        return {"username": "user-" + name, "client_id": name}

    module = SimpleNamespace(
        _private_service_json=identity,
        _compose_service_inspect=lambda name: {
            "Id": name, "RestartCount": 0,
            "State": {"Running": True, "Paused": False, "Restarting": False,
                      "StartedAt": "2026-10-20T00:00:00Z"},
        },
    )
    monkeypatch.setattr(tool, "_load_f4", lambda: module)
    monkeypatch.setattr(tool, "_systemd_snapshot", lambda mod: ("e" * 64, "f" * 64))
    socket_hashes = iter(("1" * 64, "2" * 64))

    def run(argv):
        if argv[1] == "logs":
            return "123: New client connected from 192.0.2.1:4000 as manager (p5, c1, k60, u'user-manager')."
        return json.dumps({
            "owned_socket_count": 1,
            "owned_socket_sha256": next(socket_hashes),
        })

    monkeypatch.setattr(tool, "_snapshot_run", run)
    with pytest.raises(
        tool.EvidenceInsufficientError,
        match="runtime_socket_auth_evidence_unstable",
    ):
        tool.runtime_snapshot()


def test_snapshot_run_classifies_unavailable_readonly_evidence(monkeypatch):
    tool = load_tool()

    def failed_run(_argv, timeout=8):
        assert timeout == 8
        raise tool.VerifyError(
            "command_failed:docker:1:permission denied"
        )

    monkeypatch.setattr(tool, "_run", failed_run)
    with pytest.raises(
        tool.EvidenceInsufficientError,
        match="evidence_unavailable",
    ):
        tool._snapshot_run(("docker", "logs", "broker"))


def test_runtime_socket_evidence_enforces_service_contract():
    tool = load_tool()
    digest = "1" * 64

    assert tool._runtime_socket_evidence(
        "manager",
        {"owned_socket_count": 1, "owned_socket_sha256": digest},
    ) == (1, digest)
    assert tool._runtime_socket_evidence(
        "homeassistant",
        {"owned_socket_count": 2, "owned_socket_sha256": digest},
    ) == (2, digest)

    for count in (0, 2):
        with pytest.raises(
            tool.VerifyError,
            match="manager_mqtt_socket_count_invalid",
        ):
            tool._runtime_socket_evidence(
                "manager",
                {"owned_socket_count": count, "owned_socket_sha256": digest},
            )

    with pytest.raises(
        tool.VerifyError,
        match="homeassistant_mqtt_socket_missing",
    ):
        tool._runtime_socket_evidence(
            "homeassistant",
            {"owned_socket_count": 0, "owned_socket_sha256": digest},
        )

    with pytest.raises(
        tool.EvidenceInsufficientError,
        match="runtime_socket_evidence_invalid",
    ):
        tool._runtime_socket_evidence(
            "manager",
            {"owned_socket_count": 1, "owned_socket_sha256": "invalid"},
        )


def test_valid_current_socket_does_not_replace_historical_authentication_proof():
    tool = load_tool()
    digest = "1" * 64
    identity = {"client_id": "test-service", "username": "test-user"}

    assert tool._runtime_socket_evidence(
        "manager",
        {"owned_socket_count": 1, "owned_socket_sha256": digest},
    ) == (1, digest)
    with pytest.raises(
        tool.EvidenceInsufficientError,
        match="broker_authenticated_connection_evidence_missing",
    ):
        tool._broker_auth_evidence("Client test-service disconnected.", identity)


def test_snapshot_cli_emits_structured_evidence_insufficient(monkeypatch, capsys):
    import json

    tool = load_tool()
    monkeypatch.setattr(
        tool.sys,
        "argv",
        ["n3w-t1-f4-reboot-verify", "--snapshot"],
    )

    def insufficient():
        raise tool.EvidenceInsufficientError(
            "broker_authenticated_connection_evidence_missing"
        )

    monkeypatch.setattr(tool, "runtime_snapshot", insufficient)
    assert tool.main() == 2
    report = json.loads(capsys.readouterr().err)
    assert report["status"] == "FAIL"
    assert report["failure_class"] == "EVIDENCE_INSUFFICIENT"
    assert report["error_code"] == (
        "broker_authenticated_connection_evidence_missing"
    )


def test_snapshot_cli_keeps_explicit_runtime_failure_distinct(monkeypatch, capsys):
    import json

    tool = load_tool()
    monkeypatch.setattr(
        tool.sys,
        "argv",
        ["n3w-t1-f4-reboot-verify", "--snapshot"],
    )

    def failed():
        raise tool.VerifyError(
            "broker_authenticated_connection_identity_mismatch"
        )

    monkeypatch.setattr(tool, "runtime_snapshot", failed)
    assert tool.main() == 2
    report = json.loads(capsys.readouterr().err)
    assert report["status"] == "FAIL"
    assert report["failure_class"] == "VERIFY_FAILED"
    assert report["error_code"] == "broker_authenticated_connection_identity_mismatch"


def _configure_readiness(
    tool,
    monkeypatch,
    *,
    systemd_state="running",
    running_services=frozenset({"broker", "manager", "homeassistant"}),
    unit_overrides=None,
    timer_enabled="enabled",
):
    from types import SimpleNamespace

    claim = {
        "schema": tool.CLAIM_SCHEMA,
        "stage": "REBOOT_PENDING",
        "reboot_authorization_claimed": True,
        "reboot_authorization_consumed": True,
        "reboot_authorization_replay_allowed": False,
        "reboot_acceptance_passed": False,
        "board_access": False,
        "pre_boot_id_sha256": "a" * 64,
        "f4_transaction_sha256": "b" * 64,
        "source_head": "c" * 40,
        "control_manifest_sha256": "d" * 64,
    }
    transaction = {
        "stage": "PERSISTENCE_ENABLED",
        "runtime_acceptance_passed": True,
        "persistence_enabled": True,
        "certificate_first_audit_passed": True,
        "certificate_timer_enabled": True,
        "pre_reboot_ready": True,
    }
    module = SimpleNamespace(
        PROVISION_UNIT="provision.service",
        GUARD_UNIT="guard.service",
        BROKER_UNIT="broker.service",
        SERVICES_UNIT="services.service",
        CERT_TIMER="certificate.timer",
        CERT_SERVICE="certificate.service",
        BROKER_PROJECT="n3wfc4",
        COMPOSE_ENV="/etc/n3wfc4/docker-compose.env",
        COMPOSE_TARGET="/etc/n3wfc4/docker-compose.yml",
    )
    monkeypatch.setattr(
        tool,
        "_json",
        lambda path, _mode: claim if path == tool.CLAIM_PATH else transaction,
    )
    monkeypatch.setattr(tool, "_installed_control_binding", lambda _claim: None)
    monkeypatch.setattr(tool, "_boot_id_sha256", lambda: "e" * 64)
    monkeypatch.setattr(tool, "_sha256", lambda _path: "b" * 64)
    monkeypatch.setattr(tool, "_load_f4", lambda: module)
    monkeypatch.setattr(tool, "_readiness_systemd_state", lambda: systemd_state)
    default = {
        "LoadState": "loaded",
        "ActiveState": "active",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    states = {
        unit: dict(default)
        for unit in (
            module.PROVISION_UNIT,
            module.GUARD_UNIT,
            module.BROKER_UNIT,
            module.SERVICES_UNIT,
            module.CERT_TIMER,
        )
    }
    states[module.CERT_SERVICE] = {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "Result": "success",
        "ExecMainStatus": "0",
    }
    states.update(unit_overrides or {})
    monkeypatch.setattr(tool, "_readiness_unit_state", lambda unit: states.get(unit))
    monkeypatch.setattr(tool, "_readiness_timer_enabled", lambda _unit: timer_enabled)
    monkeypatch.setattr(
        tool,
        "_readiness_running_services",
        lambda _module: running_services,
    )
    return module, claim, transaction, states


def test_readiness_waits_when_systemd_is_still_starting(monkeypatch):
    tool = load_tool()
    _configure_readiness(tool, monkeypatch, systemd_state="starting")
    report = tool.readiness()
    assert report["schema"] == tool.READINESS_SCHEMA
    assert report["status"] == "WAIT"
    assert report["state"] == "WAITING_FOR_BOOT_CONVERGENCE"
    assert report["wait_reason"] == "systemd_starting"
    assert report["board_access"] is False
    assert report["target_mutation"] is False


def test_readiness_waits_for_incomplete_runtime_service_set(monkeypatch):
    tool = load_tool()
    _configure_readiness(
        tool,
        monkeypatch,
        running_services=frozenset({"broker"}),
    )
    report = tool.readiness()
    assert report["status"] == "WAIT"
    assert report["wait_reason"] == "runtime_service_set_incomplete"


def test_readiness_passes_only_when_required_units_and_runtime_set_are_ready(monkeypatch):
    tool = load_tool()
    _configure_readiness(tool, monkeypatch, systemd_state="degraded")
    report = tool.readiness()
    assert report["status"] == "PASS"
    assert report["state"] == "READY"
    assert report["boot_id_sha256"] == "e" * 64
    assert report["source_head"] == "c" * 40
    assert report["board_access"] is False
    assert report["target_mutation"] is False


def test_readiness_fails_immediately_for_failed_required_unit(monkeypatch):
    tool = load_tool()
    _configure_readiness(
        tool,
        monkeypatch,
        unit_overrides={
            "broker.service": {
                "LoadState": "loaded",
                "ActiveState": "failed",
                "Result": "exit-code",
                "ExecMainStatus": "1",
            }
        },
    )
    with pytest.raises(tool.VerifyError, match="readiness_required_unit_failed"):
        tool.readiness()


def test_readiness_starting_state_does_not_hide_failed_unit(monkeypatch):
    tool = load_tool()
    _configure_readiness(
        tool,
        monkeypatch,
        systemd_state="starting",
        unit_overrides={
            "broker.service": {
                "LoadState": "loaded",
                "ActiveState": "failed",
                "Result": "exit-code",
                "ExecMainStatus": "1",
            }
        },
    )
    with pytest.raises(tool.VerifyError, match="readiness_required_unit_failed"):
        tool.readiness()


def test_readiness_fails_immediately_for_unexpected_runtime_service(monkeypatch):
    tool = load_tool()
    _configure_readiness(
        tool,
        monkeypatch,
        running_services=frozenset({"broker", "manager", "homeassistant", "unexpected"}),
    )
    with pytest.raises(tool.VerifyError, match="runtime_service_set_unexpected"):
        tool.readiness()


def test_readiness_fails_when_certificate_timer_is_not_enabled(monkeypatch):
    tool = load_tool()
    _configure_readiness(tool, monkeypatch, timer_enabled="disabled")
    with pytest.raises(tool.VerifyError, match="readiness_certificate_timer_not_enabled"):
        tool.readiness()


def test_readiness_cli_dispatches_without_running_full_verifier(monkeypatch, capsys):
    import json

    tool = load_tool()
    report = {
        "schema": tool.READINESS_SCHEMA,
        "status": "WAIT",
        "state": "WAITING_FOR_BOOT_CONVERGENCE",
        "wait_reason": "systemd_starting",
        "source_head": "a" * 40,
        "control_manifest_sha256": "b" * 64,
        "boot_id_sha256": "c" * 64,
        "board_access": False,
        "target_mutation": False,
    }
    monkeypatch.setattr(tool.sys, "argv", ["n3w-t1-f4-reboot-verify", "--readiness"])
    monkeypatch.setattr(tool, "readiness", lambda: report)
    monkeypatch.setattr(tool, "verify", lambda: pytest.fail("full verify must not run during readiness"))
    assert tool.main() == 0
    assert json.loads(capsys.readouterr().out) == report


def test_target_verifier_error_codes_are_sanitized():
    tool = load_tool()
    assert tool._safe_error_code(tool.VerifyError("post_reboot_unit_contract_invalid")) == (
        "post_reboot_unit_contract_invalid"
    )
    assert tool._safe_error_code(
        tool.VerifyError("command_failed:/usr/local/sbin/n3w-t1-f4-activation:2:secret value")
    ) == "command_failed:n3w-t1-f4-activation:2"
    assert tool._safe_error_code(
        tool.VerifyError("command_failed:systemctl:1:secrettoken")
    ) == "command_failed:systemctl:1"
    assert tool._safe_error_code(RuntimeError("secrettoken")) == "verification_error"
    assert tool._safe_error_code(tool.VerifyError("secrettoken")) == "verify_failed"
