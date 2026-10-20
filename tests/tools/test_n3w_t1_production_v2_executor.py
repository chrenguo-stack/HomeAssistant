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
        "MANAGER_MQTT_AUTH",
        "HOMEASSISTANT_MQTT_AUTH",
        "INVALID_CREDENTIAL_REJECTED",
        "HOMEASSISTANT_HTTP_READY",
    ):
        assert token in source
    assert "observe_critical_restarts" in source
    assert "time.sleep(seconds)" in source
    assert "T1_PRODUCTION_READY" in source
