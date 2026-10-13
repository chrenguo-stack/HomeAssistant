from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from n3w_t1_r2c_evidence_schema import REQUIREMENT_FIELDS

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = ROOT / "tools/n3w_t1_r2c_remote_executor.py"


def load_executor():
    name = "n3w_t1_r2c_remote_executor_test_module"
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


def complete_requirement(requirement_id: str) -> dict:
    return {
        "status": "OBSERVED",
        "complete": True,
        "reason_code": None,
        "method_ids": [],
        "provenance": [],
        "fields": {
            name: {"value": f"private-{name}", "status": "OBSERVED"}
            for name in REQUIREMENT_FIELDS[requirement_id]
        },
    }


def valid_report(
    *,
    execution_id: str,
    source_head: str,
    probe_sha256: str,
    contract_sha256: str,
    grant_id: str,
    binding_sha256: str,
) -> dict:
    return {
        "schema": "gh.n3w.t1-r2c-readonly-evidence/1",
        "execution_id": execution_id,
        "source_head": source_head,
        "probe_sha256": probe_sha256,
        "contract_sha256": contract_sha256,
        "authorization": {
            "grant_id": grant_id,
            "granted": True,
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
        },
        "target_binding": {
            "binding_token_sha256": binding_sha256,
            "strict_host_key_checking_required": True,
            "same_boot": True,
            "platform_expected": True,
        },
        "requirements": {
            requirement_id: complete_requirement(requirement_id)
            for requirement_id in REQUIREMENT_FIELDS
        },
        "capture_status": "COMPLETE",
        "static_review_status": "NOT_EXECUTED",
        "stop_reasons": [],
        "boundaries": {
            "t1_access": True,
            "intentional_target_write": False,
            "service_mutation": False,
            "board_access": False,
            "merge": False,
        },
        "os_identity_semantics_proven": False,
        "controlled_clone_boot_required": True,
        "disk_capture_ready": False,
        "public_projection_review": "NOT_REVIEWED",
    }


def test_local_source_authority_binds_exact_modules_and_contract() -> None:
    module = load_executor()
    authority = module.validate_local_source_authority(current_head())

    assert authority["observed_source_head"] == current_head()
    assert authority["tracked_worktree_clean"] is True
    assert authority["contract_blob"] == module.EXPECTED_CONTRACT_BLOB_SHA
    assert len(authority["module_blobs"]) == len(module.MODULE_BINDINGS)


def test_remote_program_is_deterministic_and_bound() -> None:
    module = load_executor()

    first = module.build_remote_program()
    second = module.build_remote_program()

    assert first == second
    assert b"n3w_t1_r2c_remote_probe" in first
    assert len(first) > 1000


def test_ssh_transport_requires_existing_host_key() -> None:
    module = load_executor()
    command = module._remote_command(
        execution_id="r2c-test",
        source_head="a" * 40,
        probe_sha256="b" * 64,
        contract_digest="c" * 64,
        grant_id="grant-test",
        target_binding_token_sha256="d" * 64,
    )
    argv = module.ssh_argv("root@192.0.2.10", command)

    assert "-n" not in argv
    assert "BatchMode=yes" in argv
    assert "StrictHostKeyChecking=yes" in argv
    assert "ClearAllForwardings=yes" in argv
    assert "RequestTTY=no" in argv
    assert "accept-new" not in " ".join(argv)
    assert argv[-2] == "root@192.0.2.10"
    assert "sudo -n python3 -B -" in argv[-1]


def test_wrong_confirmation_stops_before_evidence_or_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_executor()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("transport must not run")

    monkeypatch.setattr(module.subprocess, "run", forbidden)
    evidence = tmp_path / "evidence"

    with pytest.raises(module.StopExecution, match="readonly_confirmation_invalid"):
        module.execute(
            target="root@192.0.2.10",
            target_binding_id="target-1",
            evidence_root=evidence,
            confirmation="NO",
            grant_id="grant-1",
            authorization_expires_at="2099-01-01T00:00:00Z",
            execution_id="execution-1",
            expected_source_head="a" * 40,
        )

    assert not evidence.exists()


def test_execute_claims_before_single_remote_request_and_persists_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_executor()
    head = "a" * 40
    program = b"bound-remote-program"
    contract_digest = "c" * 64
    execution_id = "execution-2"
    grant_id = "grant-2"
    binding_id = "target-binding-2"
    binding_digest = module.sha256_bytes(binding_id.encode())
    probe_digest = module.sha256_bytes(program)
    evidence = tmp_path / "evidence"

    monkeypatch.setattr(
        module,
        "validate_local_source_authority",
        lambda expected: {
            "expected_source_head": expected,
            "observed_source_head": expected,
            "tracked_worktree_clean": True,
            "module_blobs": {"module": "b" * 40},
            "contract_blob": module.EXPECTED_CONTRACT_BLOB_SHA,
            "executor_blob": "e" * 40,
        },
    )
    monkeypatch.setattr(module, "build_remote_program", lambda: program)
    monkeypatch.setattr(module, "contract_sha256", lambda: contract_digest)

    response = {
        "schema": module.PROBE_SCHEMA,
        "status": "PASS",
        "report": valid_report(
            execution_id=execution_id,
            source_head=head,
            probe_sha256=probe_digest,
            contract_sha256=contract_digest,
            grant_id=grant_id,
            binding_sha256=binding_digest,
        ),
    }
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        assert (evidence / "authorization-claim.json").is_file()
        claim = json.loads(
            (evidence / "authorization-claim.json").read_text(encoding="utf-8")
        )
        assert claim["claimed"] is True
        assert claim["consumed"] is False
        assert kwargs["input"] == program
        assert kwargs["check"] is False
        assert kwargs["capture_output"] is True
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(response, sort_keys=True).encode(),
            stderr=b"",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    result = module.execute(
        target="root@192.0.2.10",
        target_binding_id=binding_id,
        evidence_root=evidence,
        confirmation=module.CONFIRMATION,
        grant_id=grant_id,
        authorization_expires_at="2099-01-01T00:00:00Z",
        execution_id=execution_id,
        expected_source_head=head,
    )

    assert len(calls) == 1
    assert result["status"] == "PASS"
    assert result["capture_status"] == "COMPLETE"
    assert result["authorization_consumed"] is True
    assert result["replay_permitted"] is False
    assert result["same_boot"] is True
    assert stat.S_IMODE(evidence.stat().st_mode) == 0o700
    expected_files = {
        "start.json",
        "authorization-claim.json",
        "command.json",
        "stdout.bin",
        "stderr.bin",
        "report.json",
        "public-candidate.json",
        "authorization-result.json",
        "result.json",
    }
    assert {path.name for path in evidence.iterdir()} == expected_files
    for path in evidence.iterdir():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    public = json.loads(
        (evidence / "public-candidate.json").read_text(encoding="utf-8")
    )
    public_text = json.dumps(public, sort_keys=True)
    assert grant_id not in public_text
    assert binding_id not in public_text
    assert binding_digest not in public_text
    assert "private-" not in public_text


def test_timeout_consumes_authorization_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_executor()
    evidence = tmp_path / "evidence"
    calls = 0

    monkeypatch.setattr(
        module,
        "validate_local_source_authority",
        lambda expected: {
            "expected_source_head": expected,
            "observed_source_head": expected,
            "tracked_worktree_clean": True,
            "module_blobs": {},
            "contract_blob": module.EXPECTED_CONTRACT_BLOB_SHA,
            "executor_blob": "e" * 40,
        },
    )
    monkeypatch.setattr(module, "build_remote_program", lambda: b"program")
    monkeypatch.setattr(module, "contract_sha256", lambda: "c" * 64)

    def timed_out(_argv, **_kwargs):
        nonlocal calls
        calls += 1
        raise subprocess.TimeoutExpired(
            cmd=["ssh"],
            timeout=150,
            output=b"partial",
            stderr=b"transport-unknown",
        )

    monkeypatch.setattr(module.subprocess, "run", timed_out)

    with pytest.raises(module.StopExecution, match="readonly_probe_timeout"):
        module.execute(
            target="root@192.0.2.10",
            target_binding_id="target-3",
            evidence_root=evidence,
            confirmation=module.CONFIRMATION,
            grant_id="grant-3",
            authorization_expires_at="2099-01-01T00:00:00Z",
            execution_id="execution-3",
            expected_source_head="a" * 40,
        )

    assert calls == 1
    result = json.loads((evidence / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "STOP"
    assert result["authorization_consumed"] is True
    assert result["replay_permitted"] is False


def test_executor_source_forbids_unsafe_transport_shortcuts() -> None:
    source = EXECUTOR.read_text(encoding="utf-8").lower()

    assert "accept-new" not in source
    assert "userknownhostsfile=/dev/null" not in source
    assert "stricthostkeychecking=no" not in source
    assert "scp " not in source
    assert "ssh-keygen -r" not in source
