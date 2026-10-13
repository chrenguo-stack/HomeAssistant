from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
PACKAGE = (
    ROOT
    / "tools/execution_packages/n3w/p2b/t1_os_identity_readonly_evidence"
)
EXECUTOR = PACKAGE / "executor.py"


def load_executor():
    name = "n3w_p2b_t1_os_identity_readonly_evidence_executor"
    specification = importlib.util.spec_from_file_location(name, EXECUTOR)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def current_head() -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def test_probe_source_binding_is_exact() -> None:
    module = load_executor()
    data = module.PROBE_SOURCE.read_bytes()
    assert module.git_blob_sha(data) == module.EXPECTED_PROBE_BLOB_SHA
    assert module.PROBE_SOURCE_COMMIT == (
        "a43c5750a8051946a9f08e3b3b2af3c5d7b9de69"
    )


def test_local_source_authority_accepts_exact_current_head() -> None:
    module = load_executor()
    report = module.validate_local_source_authority(current_head())

    assert report["observed_source_head"] == current_head()
    assert report["tracked_worktree_clean"] is True
    assert report["authorized_probe_blob_sha"] == module.EXPECTED_PROBE_BLOB_SHA


def test_local_source_authority_rejects_invalid_expected_head() -> None:
    module = load_executor()
    with pytest.raises(module.StopExecution, match="expected_source_head_invalid"):
        module.validate_local_source_authority("not-a-head")


def test_ssh_streaming_owns_stdin_and_disables_bytecode_writes() -> None:
    module = load_executor()
    argv = module.ssh_argv("root@192.0.2.10")

    assert argv[0] == "ssh"
    assert "-n" not in argv
    assert "BatchMode=yes" in argv
    assert argv[-2] == "root@192.0.2.10"
    assert argv[-1] == "sudo -n python3 -B - --root /"


@pytest.mark.parametrize(
    "target",
    (
        "",
        " root@host",
        "root@host ",
        "root@host extra",
        "-oProxyCommand=bad",
        "placeholder",
        "<t1>",
    ),
)
def test_invalid_target_is_rejected(target: str) -> None:
    module = load_executor()
    with pytest.raises(module.StopExecution):
        module.validate_target(target)


@pytest.mark.parametrize("value", (0, -1, 601, True))
def test_invalid_timeout_is_rejected(value: int) -> None:
    module = load_executor()
    with pytest.raises(module.StopExecution, match="timeout_seconds_invalid"):
        module.validate_timeout(value)


def test_wrong_confirmation_stops_before_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_executor()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("subprocess must not run")

    expected_head = "a" * 40
    monkeypatch.setattr(module.subprocess, "run", forbidden)
    evidence = tmp_path / "evidence"

    with pytest.raises(module.StopExecution, match="readonly_confirmation_invalid"):
        module.execute(
            target="root@192.0.2.10",
            evidence_root=evidence,
            confirmation="NO",
            expected_source_head=expected_head,
        )

    assert not evidence.exists()


def test_execute_streams_probe_and_persists_private_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_executor()
    probe = module.PROBE_SOURCE.read_bytes()
    report = {
        "schema": "gh.n3w.t1-os-identity-readonly-probe/1",
        "status": "PASS",
        "secret_values_included": False,
        "mutation": False,
        "production_service_start": False,
        "os_identity_semantics_proven": False,
        "controlled_clone_boot_evidence_required": True,
        "machine_identity": {},
        "ssh_host_keys": [],
        "networkmanager_profiles": [],
        "identity_related_units": [],
    }
    output = json.dumps(report, sort_keys=True).encode()

    monkeypatch.setattr(
        module,
        "validate_local_source_authority",
        lambda expected: {
            "expected_source_head": expected,
            "observed_source_head": expected,
            "tracked_worktree_clean": True,
            "authorized_probe_blob_sha": module.EXPECTED_PROBE_BLOB_SHA,
        },
    )

    def fake_run(argv, **kwargs):
        assert argv == module.ssh_argv("root@192.0.2.10")
        assert kwargs["input"] == probe
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=output,
            stderr=b"",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    evidence = tmp_path / "evidence"
    head = "a" * 40
    result = module.execute(
        target="root@192.0.2.10",
        evidence_root=evidence,
        confirmation=module.CONFIRMATION,
        expected_source_head=head,
    )

    assert result["status"] == "PASS"
    assert result["expected_source_head"] == head
    assert result["python_bytecode_write_disabled"] is True
    assert result["read_only"] is True
    assert result["t1_file_write"] is False
    assert result["production_service_start"] is False
    assert "root@192.0.2.10" not in json.dumps(result)
    assert stat.S_IMODE(evidence.stat().st_mode) == 0o700
    assert evidence.stat().st_uid == module.os.geteuid()
    for name in (
        "command.json",
        "stdout.bin",
        "stderr.bin",
        "report.json",
        "result.json",
    ):
        path = evidence / name
        metadata = path.stat()
        assert path.is_file()
        assert stat.S_IMODE(metadata.st_mode) == 0o600
        assert metadata.st_uid == module.os.geteuid()
        assert metadata.st_nlink == 1


def test_timeout_persists_structured_stop_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_executor()
    monkeypatch.setattr(
        module,
        "validate_local_source_authority",
        lambda expected: {
            "expected_source_head": expected,
            "observed_source_head": expected,
            "tracked_worktree_clean": True,
            "authorized_probe_blob_sha": module.EXPECTED_PROBE_BLOB_SHA,
        },
    )

    def timed_out(_argv, **_kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["ssh"],
            timeout=60,
            output=b"partial",
            stderr=b"timeout-detail",
        )

    monkeypatch.setattr(module.subprocess, "run", timed_out)
    evidence = tmp_path / "evidence"

    with pytest.raises(module.StopExecution, match="readonly_probe_timeout"):
        module.execute(
            target="root@192.0.2.10",
            evidence_root=evidence,
            confirmation=module.CONFIRMATION,
            expected_source_head="b" * 40,
        )

    result = json.loads((evidence / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "STOP"
    assert result["error_code"] == "readonly_probe_timeout"
    assert result["timed_out"] is True
    assert result["stdout_bytes"] == len(b"partial")
    assert (evidence / "stdout.bin").read_bytes() == b"partial"


def test_nonzero_remote_exit_persists_stop_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_executor()
    monkeypatch.setattr(
        module,
        "validate_local_source_authority",
        lambda expected: {
            "expected_source_head": expected,
            "observed_source_head": expected,
            "tracked_worktree_clean": True,
            "authorized_probe_blob_sha": module.EXPECTED_PROBE_BLOB_SHA,
        },
    )

    def failed(argv, **_kwargs):
        return subprocess.CompletedProcess(
            argv,
            2,
            stdout=b"",
            stderr=b"remote-failure",
        )

    monkeypatch.setattr(module.subprocess, "run", failed)
    evidence = tmp_path / "evidence"

    with pytest.raises(module.StopExecution, match="readonly_probe_failed:2"):
        module.execute(
            target="root@192.0.2.10",
            evidence_root=evidence,
            confirmation=module.CONFIRMATION,
            expected_source_head="c" * 40,
        )

    result = json.loads((evidence / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "STOP"
    assert result["returncode"] == 2
    assert result["timed_out"] is False


def test_report_contract_fails_closed() -> None:
    module = load_executor()
    with pytest.raises(
        module.StopExecution,
        match="probe_report_binding_invalid:mutation",
    ):
        module.validate_report(
            {
                "schema": "gh.n3w.t1-os-identity-readonly-probe/1",
                "status": "PASS",
                "secret_values_included": False,
                "mutation": True,
                "production_service_start": False,
                "os_identity_semantics_proven": False,
                "controlled_clone_boot_evidence_required": True,
            }
        )


def test_executor_source_has_no_t1_write_or_service_mutation_commands() -> None:
    source = EXECUTOR.read_text(encoding="utf-8").lower()

    assert "scp" not in source
    assert "systemctl " not in source
    assert "docker " not in source
    assert "reboot" not in source
    assert "shutdown" not in source
    assert "sudo -n python3 -b - --root /" in source
