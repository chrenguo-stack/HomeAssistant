from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
TOOL = TOOLS / "n3w_t1_production_v2_executor.py"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def load_tool():
    name = "n3w_t1_production_v2_executor_test"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def plan(run_id: str) -> dict[str, object]:
    return {
        "schema": "gh.n3w-t1-production-v2-plan/1",
        "run_id": run_id,
        "release_id": "1" * 64,
        "release_sha256": "2" * 64,
        "source_head": "3" * 40,
        "target_binding_sha256": "4" * 64,
        "ssh_host_key_sha256": "5" * 64,
        "actions": ["HOST_BASELINE"],
    }


def test_target_binding_is_deterministic_host_key_identity() -> None:
    tool = load_tool()
    host_key = "a" * 64
    expected = hashlib.sha256(
        ("ssh-ed25519:" + host_key).encode("ascii")
    ).hexdigest()
    assert tool.target_binding_sha256(host_key) == expected


def test_target_binding_rejects_invalid_host_key_digest() -> None:
    tool = load_tool()
    with pytest.raises(
        tool.ProductionExecutorError,
        match="host_key_sha256_invalid",
    ):
        tool.target_binding_sha256("not-a-digest")


def test_one_operator_approval_is_exact_and_privately_recorded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    run_id = "a" * 64
    expected = f"{tool.APPROVAL_PREFIX} {run_id}"
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return expected

    monkeypatch.setattr("builtins.input", fake_input)
    callback = tool.approval_callback(run_id, tmp_path)

    assert callback(plan(run_id)) is True
    assert prompts == ["PRODUCTION_APPROVAL> "]
    stored = json.loads(
        (tmp_path / "production-plan.json").read_text(encoding="utf-8")
    )
    assert stored == plan(run_id)
    assert stat.S_IMODE(
        (tmp_path / "production-plan.json").stat().st_mode
    ) == 0o600


def test_wrong_operator_approval_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    run_id = "a" * 64
    monkeypatch.setattr("builtins.input", lambda _prompt: "NO")
    assert tool.approval_callback(run_id, tmp_path)(plan(run_id)) is False


def test_remote_sha256_uses_target_sha256sum_exact_bytes() -> None:
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    calls: list[tuple[str, ...]] = []

    def remote(argv, *, timeout=300, check=True):
        calls.append(tuple(argv))
        return subprocess.CompletedProcess(
            argv,
            0,
            "b" * 64 + "  /target/file\n",
            "",
        )

    adapter._remote = remote
    assert adapter._remote_sha256("/target/file") == "b" * 64
    assert calls == [
        ("sudo", "-n", "sha256sum", "/target/file"),
    ]


def test_start_ssh_epoch_has_zero_target_workspace_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    host_key = "a" * 64
    events: list[str] = []

    class Transport:
        def start_epoch(self):
            events.append("start_epoch")
            return {
                "status": "PASS",
                "epoch": 1,
                "host_key_sha256": host_key,
            }

    adapter.transport = Transport()
    adapter.expected_host_key_sha256 = host_key

    def forbidden_workspace_open():
        pytest.fail("remote workspace opened before approval")

    monkeypatch.setattr(adapter, "_open_remote_root", forbidden_workspace_open)

    result = adapter.start_ssh_epoch()

    assert result["status"] == "PASS"
    assert events == ["start_epoch"]


def test_fresh_qualification_has_zero_target_workspace_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    adapter.transport = object()

    def forbidden_workspace_open():
        pytest.fail("remote workspace opened during qualification")

    monkeypatch.setattr(adapter, "_open_remote_root", forbidden_workspace_open)
    monkeypatch.setattr(
        tool,
        "collect_qualification",
        lambda transport, release: {
            "status": "PASS",
            "read_only": True,
            "mutation_performed": False,
        },
    )

    result = adapter.qualify({"release": "fixture"})

    assert result["status"] == "PASS"
    assert result["read_only"] is True
    assert result["mutation_performed"] is False


def test_start_marker_is_first_adapter_path_that_opens_remote_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    events: list[str] = []
    adapter.remote_root = None

    def open_workspace():
        events.append("open_remote_workspace")
        adapter.remote_root = "/var/tmp/n3w-f5-v2-executor.fixture"

    def marker_command(command, binding, *extra):
        events.append("build_marker_command")
        assert command == "start"
        return ("marker", "start")

    def remote_json(argv, stage, *, timeout=300):
        events.append("execute_marker_start")
        assert argv == ("marker", "start")
        assert stage == "marker_start"
        return {"status": "PASS", "state": "STARTED"}

    monkeypatch.setattr(adapter, "_open_remote_root", open_workspace)
    monkeypatch.setattr(adapter, "_marker_command", marker_command)
    monkeypatch.setattr(adapter, "_remote_json", remote_json)

    result = adapter.start_marker({"run_id": "fixture"})

    assert result["state"] == "STARTED"
    assert events == [
        "open_remote_workspace",
        "build_marker_command",
        "execute_marker_start",
    ]


def test_post_reboot_epoch_has_zero_target_workspace_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    host_key = "a" * 64
    adapter.reboot_actuated = True
    events: list[str] = []

    class Transport:
        def start_post_reboot_epoch(self):
            events.append("start_post_reboot_epoch")
            return {
                "status": "PASS",
                "epoch": 2,
                "host_key_sha256": host_key,
            }

    adapter.transport = Transport()
    adapter.expected_host_key_sha256 = host_key

    def forbidden_workspace_open():
        pytest.fail("remote workspace opened before post-reboot acceptance")

    monkeypatch.setattr(adapter, "_open_remote_root", forbidden_workspace_open)

    result = adapter.start_post_reboot_epoch()

    assert result["status"] == "PASS"
    assert adapter.reboot_actuated is False
    assert events == ["start_post_reboot_epoch"]


def test_post_reboot_acceptance_has_zero_target_workspace_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    events: list[str] = []

    def forbidden_workspace_open():
        pytest.fail("remote workspace opened during post-reboot acceptance")

    def fake_acceptance(current_adapter, release, binding):
        assert current_adapter is adapter
        events.append("acceptance")
        return {
            "status": "PASS",
            "acceptance_sha256": "b" * 64,
        }

    monkeypatch.setattr(adapter, "_open_remote_root", forbidden_workspace_open)
    monkeypatch.setattr(tool, "run_acceptance", fake_acceptance)

    result = adapter.post_reboot_acceptance(
        {"release": "fixture"},
        {"binding": "fixture"},
    )

    assert result["status"] == "PASS"
    assert events == ["acceptance"]


def test_accept_marker_opens_workspace_only_after_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    adapter.remote_root = None
    events: list[str] = []

    def open_workspace():
        events.append("open_remote_workspace")
        adapter.remote_root = "/var/tmp/n3w-f5-v2-executor.fixture"

    def marker_command(command, binding, *extra):
        events.append("build_marker_command")
        assert command == "accept"
        assert "--acceptance-sha256" in extra
        return ("marker", "accept")

    def remote_json(argv, stage, *, timeout=300):
        events.append("execute_marker_accept")
        assert argv == ("marker", "accept")
        assert stage == "marker_accept"
        return {
            "status": "PASS",
            "state": "ACCEPTED",
            "T1_PRODUCTION_READY": True,
        }

    monkeypatch.setattr(adapter, "_open_remote_root", open_workspace)
    monkeypatch.setattr(adapter, "_marker_command", marker_command)
    monkeypatch.setattr(adapter, "_remote_json", remote_json)

    result = adapter.accept_marker(
        {"run_id": "fixture"},
        "b" * 64,
    )

    assert result["state"] == "ACCEPTED"
    assert result["T1_PRODUCTION_READY"] is True
    assert events == [
        "open_remote_workspace",
        "build_marker_command",
        "execute_marker_accept",
    ]


def test_executor_uses_release_bound_f3_and_distinct_f4_authorities() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '"--release-f3-payload"' in source
    assert '"--release-f3-images"' in source
    assert '"F4_PERSISTENCE"' in source
    assert '"F4_CERT_AUDIT"' in source
    assert '"F4_CERT_TIMER"' in source
    assert '"REBOOT_CONTROL_INSTALL"' in (
        ROOT / "tools/n3w_t1_production_v2.py"
    ).read_text(encoding="utf-8")
    assert "resume-if-needed" not in source
    assert "repair-" not in source


def test_executor_cli_has_no_noninteractive_approval_bypass() -> None:
    tool = load_tool()
    parser = tool.parser()
    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert "--approved" not in option_strings
    assert "--approval" not in option_strings
    assert "--release-root" in option_strings
    assert "--target" in option_strings
    assert "--known-hosts" in option_strings
    assert "--expected-host-key-sha256" in option_strings


def test_external_acceptance_contract_is_fully_implemented() -> None:
    source = TOOL.read_text(encoding="utf-8")
    for token in (
        "TCP_8883",
        "TLS_CA",
        "TLS_HOSTNAME_SNI",
        "INVALID_CREDENTIAL_REJECTED",
        "HOMEASSISTANT_HTTP_READY",
    ):
        assert token in source
    assert "observe_runtime" in source
    assert "_service_material" not in source
    assert "_mqtt_authenticate" not in source
    assert "system-ca.pem" not in source
    assert "T1_PRODUCTION_READY" in source


@pytest.mark.parametrize("packet", [
    b"\x20\x03\x00\x00\x00", b"\x20\x03\x00\x89\x00",
    b"\x20\x03\x01\x87\x00", b"\x20\x03\x00\x87\x01",
    b"\x20\x02\x00\x87", b"\x20\x03\x00", b"\xe0\x00",
    b"\x20\x83\x00\x00\x87\x00",
])
def test_negative_probe_never_treats_non_auth_refusal_as_pass(monkeypatch, packet):
    tool = load_tool()
    stream = mqtt_stream(packet)
    monkeypatch.setattr(tool.socket, "create_connection", lambda *a, **k: stream)
    monkeypatch.setattr(tool.ssl, "SSLContext", lambda *a: tls_context(stream))
    with pytest.raises((tool.ProductionExecutorError, OSError)):
        tool._mqtt_rejection_reason("test", ca_pem="test", username="denied", password="fake", client_id="unique")


def mqtt_stream(packet):
    from io import BytesIO
    class Stream(BytesIO):
        def recv(self, size):
            return self.read(size)
        def settimeout(self, value):
            pass
        def sendall(self, data):
            self.sent = data
    return Stream(packet)


def tls_context(stream):
    class Context:
        def load_verify_locations(self, **kwargs):
            pass
        def wrap_socket(self, raw, **kwargs):
            assert kwargs["server_hostname"] == "armbian"
            return stream
    return Context()


@pytest.mark.parametrize("reason", [0x86, 0x87])
def test_negative_probe_requires_exact_mqtt5_authentication_refusal(monkeypatch, reason):
    tool = load_tool()
    stream = mqtt_stream(bytes([0x20, 3, 0, reason, 0]))
    monkeypatch.setattr(tool.socket, "create_connection", lambda *a, **k: stream)
    monkeypatch.setattr(tool.ssl, "SSLContext", lambda *a: tls_context(stream))
    assert tool._mqtt_rejection_reason("test", ca_pem="test", username="denied", password="fake", client_id="unique") == reason


def test_external_negative_probe_does_not_read_service_credentials(monkeypatch):
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    adapter.host = "isolated.invalid"
    adapter._ca_pem = None
    paths, attempts = [], []
    adapter._remote_secret_text = lambda path: paths.append(path) or "broker-ca"
    def probe(host, **kwargs):
        attempts.append(kwargs)
        assert kwargs["ca_pem"] == "broker-ca"
        assert kwargs["username"].startswith("n3w-acceptance-denied-")
        assert kwargs["client_id"].startswith("n3w-acceptance-denied-")
        return 0x87
    monkeypatch.setattr(tool, "_mqtt_rejection_reason", probe)
    for _ in range(2):
        assert adapter.external_probe("INVALID_CREDENTIAL_REJECTED")["accepted"]
    assert paths == ["/etc/n3wfc4/tls/ca.pem"]
    assert attempts[0]["client_id"] != attempts[1]["client_id"]
    with pytest.raises(tool.ProductionExecutorError, match="unknown"):
        adapter.external_probe("MANAGER_MQTT_AUTH")


def test_runtime_snapshot_uses_only_installed_readonly_entrypoint():
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    calls = []
    adapter._remote_json = lambda *a, **k: calls.append((a, k)) or {"status": "PASS"}
    assert adapter.runtime_snapshot()["status"] == "PASS"
    assert calls[0][0][0] == ("sudo", "-n", tool.REBOOT_VERIFY_CLI, "--snapshot")
    assert calls[0][1]["timeout"] == 15


def test_observation_samples_and_stops_immediately_on_failure(monkeypatch):
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    clock = [0.0]
    monkeypatch.setattr(tool.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(tool.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(tool, "require_continuity", lambda baseline, value: value if value == baseline else (_ for _ in ()).throw(ValueError("changed")))
    calls = []
    def sample():
        calls.append(clock[0])
        return {"stable": clock[0] < 4}
    adapter.runtime_snapshot = sample
    with pytest.raises(ValueError, match="changed"):
        adapter.observe_runtime(90, {"stable": True})
    assert calls == [0, 2, 4]
    adapter.runtime_snapshot = lambda: {"stable": True}
    clock[0] = 0
    result = adapter.observe_runtime(90, {"stable": True})
    assert len(result["samples"]) == 46
    assert result["samples"][-1]["elapsed_seconds"] == 90
