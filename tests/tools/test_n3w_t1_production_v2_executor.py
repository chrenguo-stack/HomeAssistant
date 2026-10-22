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


def test_reboot_arm_waits_until_exact_operator_presence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tool = load_tool()
    run_id = "c" * 64
    expected = f"{tool.REBOOT_ARM_PREFIX} {run_id}"
    responses = iter(("NOT READY", expected))
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)

    result = tool._wait_for_reboot_arm(run_id)

    assert result == {
        "status": "PASS",
        "run_id": run_id,
        "operator_present": True,
        "post_reboot_password_expected": True,
    }
    assert prompts == ["REBOOT_ARMING> ", "REBOOT_ARMING> "]
    output = capsys.readouterr().out
    assert "REBOOT_ARMING_SUMMARY=" in output
    assert '"input_timeout_seconds":null' in output
    assert '"post_reboot_password_required":true' in output
    assert "REBOOT_ARMING_WAITING=INPUT_NOT_MATCHED" in output


def test_reboot_arm_interrupt_becomes_fail_closed_executor_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()

    def interrupted(_prompt: str) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupted)

    with pytest.raises(
        tool.ProductionExecutorError,
        match="reboot_operator_arming_input_closed",
    ):
        tool._wait_for_reboot_arm("d" * 64)


def test_reboot_arm_is_after_control_verify_and_before_reboot_claim() -> None:
    source = TOOL.read_text(encoding="utf-8")
    method = source.split("    def controlled_reboot(", 1)[1].split(
        "    def close_pre_reboot_epoch(", 1
    )[0]

    package = method.index('_stage_release_tar(')
    verified = method.index('"verify-install"')
    arm = method.index("_wait_for_reboot_arm(self.run_id)")
    claim = method.index('"claim-reboot"')
    reboot = method.index('("sudo", "-n", "systemctl", "reboot")')

    assert package < verified < arm < claim < reboot


def test_progress_surface_covers_long_and_password_wait_stages() -> None:
    source = TOOL.read_text(encoding="utf-8")
    for token in (
        'PROGRESS_SCHEMA = "gh.n3w-t1-f5-v2-production-progress/1"',
        '_emit_progress("HOST_BASELINE", "STARTED")',
        '_emit_progress("F3_DEPLOY", "STARTED")',
        '_emit_progress("PROVISION", "STARTED")',
        '_emit_progress("REBOOT_CONTROL", "WAITING_FOR_OPERATOR")',
        '_emit_progress("REBOOT_CONTROL", "ARMED")',
        '_emit_progress("REBOOT_CONTROL", "OLD_BOOT_SSH_DOWN")',
        '_emit_progress("WAIT_FOR_SSH", "STARTED")',
        '_emit_progress("SSH_EPOCH_2", "PASSWORD_REQUIRED")',
        '_emit_progress("POST_REBOOT_ACCEPTANCE", "STARTED")',
    ):
        assert token in source


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


def test_live_adapter_keeps_long_local_work_root_out_of_ssh_transport(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    release_root = tmp_path / "release"
    release_root.mkdir()
    (release_root / "release.json").write_text("{}", encoding="utf-8")
    evidence_root = tmp_path / "evidence"
    work_root = tmp_path / ("macos-default-temp-" + "x" * 120)
    captured: dict[str, object] = {}

    class Transport:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        tool,
        "verify_release_directory",
        lambda _root: {"status": "PASS"},
    )
    monkeypatch.setattr(tool, "validate_release", lambda value: value)
    monkeypatch.setattr(tool, "SSHTransport", Transport)
    monkeypatch.setattr(tool, "_tar_member_sha256", lambda *_args: "a" * 64)
    monkeypatch.setattr(
        tool.LiveProductionAdapter,
        "_artifact",
        lambda _self, _name: tmp_path / "unused",
    )

    adapter = tool.LiveProductionAdapter(
        release_root=release_root,
        target="root@192.0.2.1",
        known_hosts=tmp_path / "known_hosts",
        expected_host_key_sha256="b" * 64,
        run_id="c" * 64,
        evidence_root=evidence_root,
        work_root=work_root,
    )

    assert len(str(work_root / "n3w-f5-abcdefgh" / "ctl")) > 90
    assert adapter.work_root == work_root.resolve()
    assert captured == {
        "target": "root@192.0.2.1",
        "known_hosts": tmp_path / "known_hosts",
        "expected_host_key_sha256": "b" * 64,
    }


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


def test_pre_mutation_failure_freeze_is_private_local_only(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    adapter.evidence_root = tmp_path
    adapter.remote_root = None
    tmp_path.chmod(0o700)
    failure = {
        "schema": "gh.n3w-t1-production-v2-pre-mutation-failure/1",
        "status": "FAIL",
        "failed_stage": "SSH_EPOCH",
        "error_type": "SSHTransportError",
        "error_code": "ssh_master_unavailable",
        "error_message": "ssh_master_unavailable",
        "error_message_sha256": "a" * 64,
        "marker_state": "ABSENT",
        "operator_session_closed": True,
        "target_mutation": False,
        "reflash_required": False,
        "automatic_retry": False,
        "board_access": False,
    }

    result = adapter.freeze_pre_mutation_failure(failure)

    path = tmp_path / "failure-summary.json"
    assert path.is_file()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    frozen = json.loads(path.read_text(encoding="utf-8"))
    assert frozen["failed_stage"] == "SSH_EPOCH"
    assert frozen["target_mutation"] is False
    assert frozen["failure_frozen"] is True
    assert frozen["forensic_collector_target_mutation"] is False
    assert result["evidence_sha256"] == tool.canonical_sha256(frozen)
    assert result["target_mutation"] is False


def test_pre_mutation_failure_freeze_rejects_open_remote_workspace(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    adapter.evidence_root = tmp_path
    adapter.remote_root = "/var/tmp/n3w-f5-v2-executor.fixture"
    tmp_path.chmod(0o700)

    with pytest.raises(
        tool.ProductionExecutorError,
        match="pre_mutation_remote_workspace_invalid",
    ):
        adapter.freeze_pre_mutation_failure(
            {
                "marker_state": "ABSENT",
                "target_mutation": False,
                "reflash_required": False,
                "automatic_retry": False,
            }
        )


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



def test_runtime_snapshot_structured_insufficient_evidence_is_preserved():
    tool = load_tool()
    completed = subprocess.CompletedProcess(
        [],
        2,
        "",
        json.dumps(
            {
                "status": "FAIL",
                "failure_class": "EVIDENCE_INSUFFICIENT",
                "error_code": (
                    "broker_authenticated_connection_evidence_missing"
                ),
            }
        ),
    )
    with pytest.raises(
        tool.EvidenceInsufficientError,
        match="runtime_snapshot_evidence_insufficient",
    ):
        tool._json_output(completed, "runtime_snapshot")


def test_runtime_snapshot_explicit_failure_is_not_downgraded():
    tool = load_tool()
    completed = subprocess.CompletedProcess(
        [],
        2,
        "",
        json.dumps(
            {
                "status": "FAIL",
                "failure_class": "VERIFY_FAILED",
                "error_code": (
                    "broker_authenticated_connection_state_invalid"
                ),
            }
        ),
    )
    with pytest.raises(
        tool.ProductionExecutorError,
        match="runtime_snapshot_command_failed",
    ):
        tool._json_output(completed, "runtime_snapshot")


def _readiness_report(tool, status, reason=None):
    report = {
        "schema": tool.READINESS_SCHEMA,
        "status": status,
        "state": "READY" if status == "PASS" else "WAITING_FOR_BOOT_CONVERGENCE",
        "source_head": "3" * 40,
        "control_manifest_sha256": "a" * 64,
        "boot_id_sha256": "b" * 64,
        "board_access": False,
        "target_mutation": False,
    }
    if reason is not None:
        report["wait_reason"] = reason
    return report


def test_post_reboot_readiness_polls_inside_existing_ssh_epoch(monkeypatch):
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    adapter.release = {"source_head": "3" * 40}
    clock = [0.0]
    reports = iter(
        (
            _readiness_report(tool, "WAIT", "systemd_starting"),
            _readiness_report(tool, "PASS"),
        )
    )
    calls = []
    progress = []
    monkeypatch.setattr(tool.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        tool.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )
    monkeypatch.setattr(
        tool,
        "_emit_progress",
        lambda stage, status, **fields: progress.append((stage, status, fields)),
    )

    def remote_json(argv, stage, *, timeout):
        calls.append((argv, stage, timeout))
        return next(reports)

    adapter._remote_json = remote_json
    report = adapter.wait_for_post_reboot_readiness()
    assert report["status"] == "PASS"
    assert len(calls) == 2
    assert all(call[0] == ("sudo", "-n", tool.REBOOT_VERIFY_CLI, "--readiness") for call in calls)
    assert all(call[1] == "post_reboot_readiness" for call in calls)
    assert any(item[1] == "WAITING" for item in progress)
    assert progress[-1][1] == "PASS"


def test_post_reboot_readiness_times_out_fail_closed(monkeypatch):
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    adapter.release = {"source_head": "3" * 40}
    monkeypatch.setattr(tool, "READINESS_TIMEOUT_SECONDS", 3)
    monkeypatch.setattr(tool, "READINESS_POLL_SECONDS", 2)
    clock = [0.0]
    monkeypatch.setattr(tool.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        tool.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )
    monkeypatch.setattr(tool, "_emit_progress", lambda *_args, **_kwargs: None)
    calls = []
    adapter._remote_json = lambda *_args, **_kwargs: calls.append(1) or _readiness_report(
        tool, "WAIT", "systemd_starting"
    )
    with pytest.raises(tool.ProductionExecutorError, match="post_reboot_readiness_timeout"):
        adapter.wait_for_post_reboot_readiness()
    assert len(calls) == 2


def test_post_reboot_readiness_rejects_invalid_wait_reason(monkeypatch):
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    adapter.release = {"source_head": "3" * 40}
    monkeypatch.setattr(tool, "_emit_progress", lambda *_args, **_kwargs: None)
    adapter._remote_json = lambda *_args, **_kwargs: _readiness_report(
        tool, "WAIT", "untrusted_reason"
    )
    with pytest.raises(tool.ProductionExecutorError, match="post_reboot_readiness_report_invalid"):
        adapter.wait_for_post_reboot_readiness()


def test_target_verifier_structured_failure_code_is_preserved():
    tool = load_tool()
    report = {
        "schema": tool.TARGET_VERIFY_REPORT_SCHEMA,
        "status": "FAIL",
        "failure_class": "VERIFY_FAILED",
        "error_code": "post_reboot_unit_contract_invalid",
        "board_access": False,
    }
    completed = subprocess.CompletedProcess([], 2, "", json.dumps(report))
    with pytest.raises(tool.ProductionExecutorError) as captured:
        tool._json_output(completed, "target_local_reboot_verify")
    assert captured.value.error_code == "post_reboot_unit_contract_invalid"
    assert captured.value.target_failure_class == "VERIFY_FAILED"


def test_target_verifier_structured_insufficient_evidence_remains_distinct():
    tool = load_tool()
    report = {
        "schema": tool.TARGET_VERIFY_REPORT_SCHEMA,
        "status": "FAIL",
        "failure_class": "EVIDENCE_INSUFFICIENT",
        "error_code": "runtime_snapshot_command_evidence_unavailable",
        "board_access": False,
    }
    completed = subprocess.CompletedProcess([], 2, "", json.dumps(report))
    with pytest.raises(tool.EvidenceInsufficientError) as captured:
        tool._json_output(completed, "target_local_reboot_verify")
    assert captured.value.error_code == "runtime_snapshot_command_evidence_unavailable"
    assert captured.value.target_failure_class == "EVIDENCE_INSUFFICIENT"


def test_target_verifier_does_not_trust_arbitrary_error_code_or_nonfinal_json():
    tool = load_tool()
    report = {
        "schema": tool.TARGET_VERIFY_REPORT_SCHEMA,
        "status": "FAIL",
        "failure_class": "VERIFY_FAILED",
        "error_code": "password leaked",
        "board_access": False,
    }
    completed = subprocess.CompletedProcess([], 2, "", json.dumps(report))
    with pytest.raises(tool.ProductionExecutorError) as captured:
        tool._json_output(completed, "target_local_reboot_verify")
    assert str(captured.value) == "target_local_reboot_verify_error_code_invalid"
    assert not hasattr(captured.value, "error_code")

    completed = subprocess.CompletedProcess(
        [],
        2,
        "",
        json.dumps({**report, "error_code": "secrettoken"}),
    )
    with pytest.raises(tool.ProductionExecutorError) as captured:
        tool._json_output(completed, "target_local_reboot_verify")
    assert str(captured.value) == "target_local_reboot_verify_error_code_invalid"
    assert not hasattr(captured.value, "error_code")

    completed = subprocess.CompletedProcess(
        [],
        2,
        "",
        json.dumps({**report, "error_code": "post_reboot_unit_contract_invalid"}) + "\nnot-json",
    )
    with pytest.raises(tool.ProductionExecutorError) as captured:
        tool._json_output(completed, "target_local_reboot_verify")
    assert str(captured.value) == "target_local_reboot_verify_command_failed"
    assert not hasattr(captured.value, "error_code")

def test_reboot_disconnect_requires_tcp_22_down_after_control_master_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    adapter.host = "t1.invalid"
    adapter.target = "root@t1.invalid"
    runner_calls: list[tuple[str, ...]] = []
    reachability = iter((True, False, False))
    clock = [0.0]

    class Runner:
        def run(self, argv, *, timeout, check):
            runner_calls.append(tuple(argv))
            return subprocess.CompletedProcess(argv, 1, "", "")

    class Transport:
        runner = Runner()

    adapter.transport = Transport()
    monkeypatch.setattr(tool.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        tool.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )
    monkeypatch.setattr(tool, "_tcp_port_reachable", lambda *_args, **_kwargs: next(reachability))

    result = adapter._wait_for_old_boot_ssh_down("/tmp/control")

    assert result == {
        "control_master_disconnected": True,
        "ssh_down_observed": True,
    }
    assert len(runner_calls) == 1
    assert clock[0] == tool.REBOOT_TCP_DOWN_POLL_SECONDS * 2


def test_tcp_down_and_control_disconnect_can_be_observed_in_either_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    adapter.host = "t1.invalid"
    adapter.target = "root@t1.invalid"
    returncodes = iter((0, 1))
    events: list[str] = []
    clock = [0.0]

    class Runner:
        def run(self, argv, *, timeout, check):
            events.append("control")
            return subprocess.CompletedProcess(argv, next(returncodes), "", "")

    class Transport:
        runner = Runner()

    adapter.transport = Transport()
    monkeypatch.setattr(tool.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        tool.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )

    def reachable(*_args, **_kwargs):
        events.append("tcp")
        return False

    monkeypatch.setattr(tool, "_tcp_port_reachable", reachable)

    result = adapter._wait_for_old_boot_ssh_down("/tmp/control")

    assert result == {
        "control_master_disconnected": True,
        "ssh_down_observed": True,
    }
    assert events == ["control", "tcp", "control", "tcp"]


def test_historical_tcp_down_does_not_survive_recovery_before_control_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    adapter.host = "t1.invalid"
    adapter.target = "root@t1.invalid"
    returncodes = iter((0, 0, 0, 1, 1, 1))
    reachability = iter((False, False, True, True, False, False))
    clock = [0.0]

    class Runner:
        def run(self, argv, *, timeout, check):
            return subprocess.CompletedProcess(argv, next(returncodes), "", "")

    class Transport:
        runner = Runner()

    adapter.transport = Transport()
    monkeypatch.setattr(tool.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        tool.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )
    monkeypatch.setattr(
        tool,
        "_tcp_port_reachable",
        lambda *_args, **_kwargs: next(reachability),
    )

    result = adapter._wait_for_old_boot_ssh_down("/tmp/control")

    assert result == {
        "control_master_disconnected": True,
        "ssh_down_observed": True,
    }
    assert clock[0] == tool.REBOOT_TCP_DOWN_POLL_SECONDS * 5


def test_reboot_disconnect_fails_closed_if_old_ssh_never_goes_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    adapter = object.__new__(tool.LiveProductionAdapter)
    adapter.host = "t1.invalid"
    adapter.target = "root@t1.invalid"
    clock = [0.0]

    class Runner:
        def run(self, argv, *, timeout, check):
            return subprocess.CompletedProcess(argv, 1, "", "")

    class Transport:
        runner = Runner()

    adapter.transport = Transport()
    monkeypatch.setattr(tool, "REBOOT_DISCONNECT_SECONDS", 1.0)
    monkeypatch.setattr(tool, "REBOOT_TCP_DOWN_POLL_SECONDS", 0.5)
    monkeypatch.setattr(tool.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        tool.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )
    monkeypatch.setattr(tool, "_tcp_port_reachable", lambda *_args, **_kwargs: True)

    with pytest.raises(
        tool.ProductionExecutorError,
        match="reboot_disconnect_not_observed",
    ):
        adapter._wait_for_old_boot_ssh_down("/tmp/control")

    assert clock[0] >= 1.0


def test_controlled_reboot_requires_old_boot_ssh_down_before_reboot_pending() -> None:
    source = TOOL.read_text(encoding="utf-8")
    method = source.split("    def controlled_reboot(", 1)[1].split(
        "    def _wait_for_old_boot_ssh_down(", 1
    )[0]

    reboot = method.index('("sudo", "-n", "systemctl", "reboot")')
    down = method.index("self._wait_for_old_boot_ssh_down(control_path)")
    pending = method.index('_emit_progress("REBOOT_CONTROL", "REBOOT_PENDING")')

    assert reboot < down < pending

