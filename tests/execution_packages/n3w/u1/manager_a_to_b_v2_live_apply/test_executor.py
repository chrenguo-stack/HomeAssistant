from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
EXECUTOR = ROOT / "tools/execution_packages/n3w/u1/manager_a_to_b_v2_live_apply/executor.py"

spec = importlib.util.spec_from_file_location("u1_v2_live_executor", EXECUTOR)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def completed(doc: dict, rc: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["remote"],
        returncode=rc,
        stdout=json.dumps(doc),
        stderr="",
    )


def status(manager: str, *, terminal: str = "COMMITTED") -> dict:
    return {
        "schema": mod.STATUS_SCHEMA,
        "status": "PASS",
        "operation": "status",
        "component": "manager",
        "mutation": False,
        "recovery_required": False,
        "transaction": {
            "schema": mod.TX_SCHEMA,
            "status": terminal,
            "phase": terminal,
            "component": "manager",
            "target": {"target_image_ref": manager},
        },
        "legacy_manager_transaction": None,
    }


def legacy_status(manager: str, *, terminal: str = "COMMITTED") -> dict:
    return {
        "schema": mod.LEGACY_STATUS_SCHEMA,
        "status": "PASS",
        "operation": "status",
        "component": "manager",
        "mutation": False,
        "recovery_required": False,
        "transaction": {
            "schema": mod.LEGACY_TX_SCHEMA,
            "status": terminal,
            "phase": terminal,
            "component": "manager",
            "predecessor_image": "local/greenhouse-manager:fresh-3539c8f871e2",
            "target": {"image": manager},
        },
    }


def inspect(manager: str, baseline: dict) -> dict:
    return {
        "schema": mod.INSPECT_SCHEMA,
        "status": "PASS",
        "operation": "inspect",
        "component": "manager",
        "mutation": False,
        "snapshot": {
            "image_bindings": {
                "manager": manager,
                "homeassistant": baseline["stack_images"]["homeassistant"],
                "broker": baseline["stack_images"]["broker"],
            },
            "image_binding_modes": {
                "manager": "dynamic",
                "homeassistant": "dynamic",
                "broker": "dynamic",
            },
            "mqtt_authenticated": {"manager": True, "homeassistant": True},
            "listeners": {
                "tcp_8883": 1,
                "tcp_47110": 1,
                "udp_47111": 1,
                "tcp_47112": 0,
            },
        },
    }


def plan() -> dict:
    return {
        "schema": mod.PLAN_SCHEMA,
        "status": "PASS",
        "operation": "plan",
        "component": "manager",
        "mutation": False,
        "current": {"image": mod.EXPECTED_PREDECESSOR},
        "target": {"target_image_ref": mod.TARGET_MANAGER},
        "target_image_prestate": "ABSENT",
        "target_archive_verified": True,
        "rollback_available": True,
    }


def package_info() -> dict:
    baseline = json.loads(
        (ROOT / mod.BASELINE_RELATIVE).read_text(encoding="utf-8")
    )
    return {
        "metadata": {"id": mod.ARTIFACT_ID},
        "target": {"schema": mod.TARGET_SCHEMA},
        "baseline": baseline,
        "binding": {"transaction_schema": mod.TX_SCHEMA},
    }


def args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        expected_package_commit="0" * 40,
        authorization_id=mod.AUTHORIZATION,
        execution_id="test-execution",
        evidence_root=tmp_path / "evidence",
        t1_ssh_target="root@192.0.2.1",
        control_path="/tmp/n3w-test.sock",
        confirm=mod.CONFIRMATION,
    )


def test_success_path_invokes_exactly_one_apply_and_no_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = package_info()
    package = tmp_path / "package"
    package.mkdir()
    calls: list[list[str]] = []

    monkeypatch.setattr(mod, "validate_local_source", lambda _: None)
    monkeypatch.setattr(mod, "verify_github_artifact", lambda _: (package, info))
    monkeypatch.setattr(mod, "stage_package", lambda *a: {"x": "y"})

    responses = [
        completed(status(mod.EXPECTED_PREDECESSOR)),
        completed(inspect(mod.EXPECTED_PREDECESSOR, info["baseline"])),
        completed(plan()),
        completed({
            "schema": mod.STATUS_SCHEMA,
            "status": "PASS",
            "operation": "apply",
            "component": "manager",
            "transaction_status": "COMMITTED",
            "authorization_consumed": True,
            "t1_mutation": True,
        }),
        completed(status(mod.TARGET_MANAGER)),
        completed(inspect(mod.TARGET_MANAGER, info["baseline"])),
    ]

    def remote(*_a, **kw):
        calls.append(list(_a[2]))
        return responses.pop(0)

    monkeypatch.setattr(mod, "remote_updater_command", remote)
    result = mod.execute(args(tmp_path))

    assert result["status"] == "PASS"
    assert sum(1 for call in calls if call and call[0] == "apply") == 1
    assert all(not call or call[0] != "rollback" for call in calls)
    assert result["second_apply_invoked"] is False
    assert result["automatic_rollback"] is False


def test_failed_apply_is_not_retried_or_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = package_info()
    package = tmp_path / "package"
    package.mkdir()
    calls: list[list[str]] = []

    monkeypatch.setattr(mod, "validate_local_source", lambda _: None)
    monkeypatch.setattr(mod, "verify_github_artifact", lambda _: (package, info))
    monkeypatch.setattr(mod, "stage_package", lambda *a: {"x": "y"})

    responses = [
        completed(status(mod.EXPECTED_PREDECESSOR)),
        completed(inspect(mod.EXPECTED_PREDECESSOR, info["baseline"])),
        completed(plan()),
        completed({
            "schema": mod.STATUS_SCHEMA,
            "status": "STOP",
            "operation": "apply",
            "reason": "injected",
            "t1_mutation": "UNKNOWN",
        }, rc=2),
        completed(status(mod.EXPECTED_PREDECESSOR)),
        completed(inspect(mod.EXPECTED_PREDECESSOR, info["baseline"])),
    ]

    def remote(*_a, **kw):
        calls.append(list(_a[2]))
        return responses.pop(0)

    monkeypatch.setattr(mod, "remote_updater_command", remote)
    result = mod.execute(args(tmp_path))

    assert result["status"] == "STOP"
    assert result["first_failed_operation"] == "apply_not_committed"
    assert sum(1 for call in calls if call and call[0] == "apply") == 1
    assert all(not call or call[0] != "rollback" for call in calls)
    assert result["authorization_claimed"] is True
    assert result["authorization_consumed_by_executor"] is True


def test_nonterminal_prestate_stops_before_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = package_info()
    package = tmp_path / "package"
    package.mkdir()
    calls: list[list[str]] = []

    monkeypatch.setattr(mod, "validate_local_source", lambda _: None)
    monkeypatch.setattr(mod, "verify_github_artifact", lambda _: (package, info))
    monkeypatch.setattr(mod, "stage_package", lambda *a: {"x": "y"})

    def remote(*_a, **kw):
        calls.append(list(_a[2]))
        return completed(status(mod.EXPECTED_PREDECESSOR, terminal="APPLYING"))

    monkeypatch.setattr(mod, "remote_updater_command", remote)
    result = mod.execute(args(tmp_path))

    assert result["status"] == "STOP"
    assert result["apply_invoked"] is False
    assert result["authorization_claimed"] is False
    assert all(not call or call[0] != "apply" for call in calls)


def test_terminal_legacy_committed_status_is_accepted() -> None:
    mod.require_terminal_status(legacy_status(mod.EXPECTED_PREDECESSOR))


def test_nonterminal_legacy_status_stops() -> None:
    with pytest.raises(mod.StopExecution, match="fresh_status_invalid|fresh_legacy"):
        document = legacy_status(mod.EXPECTED_PREDECESSOR, terminal="APPLYING")
        document["recovery_required"] = True
        mod.require_terminal_status(document)


def test_existing_exact_remote_staging_is_reused_without_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    local_hashes = {}
    for name in sorted(mod.EXPECTED_PACKAGE_FILES):
        path = package / name
        path.write_bytes(("payload-" + name).encode())
        local_hashes[name] = mod.sha256_file(path)

    ssh_calls = []

    def fake_ssh(target, control_path, command, *, timeout=180, check=True):
        ssh_calls.append(command)
        if len(ssh_calls) == 1:
            listing = "\n".join(
                ["root:root:700:directory", *sorted(mod.EXPECTED_PACKAGE_FILES)]
            ) + "\n"
            return subprocess.CompletedProcess(
                args=["ssh"], returncode=0, stdout=listing, stderr=""
            )
        hashes = "\n".join(
            f"{local_hashes[name]}  {mod.REMOTE_DIR}/{name}"
            for name in sorted(mod.EXPECTED_PACKAGE_FILES)
        ) + "\n"
        return subprocess.CompletedProcess(
            args=["ssh"], returncode=0, stdout=hashes, stderr=""
        )

    def fail_run(*args, **kwargs):
        raise AssertionError("scp or local copy must not run for exact staging reuse")

    monkeypatch.setattr(mod, "ssh_command", fake_ssh)
    monkeypatch.setattr(mod, "run", fail_run)

    observed = mod.stage_package(
        package,
        "root@192.0.2.1",
        "/tmp/n3w-test.sock",
    )

    assert observed == local_hashes
    assert len(ssh_calls) == 2
