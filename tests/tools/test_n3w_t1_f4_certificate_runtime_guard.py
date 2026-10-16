from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_f4_certificate_runtime_guard.py"
LIFECYCLE_TEST = ROOT / "tests/tools/test_n3w_broker_certificate_lifecycle.py"


def load_tool():
    name = "n3w_t1_f4_certificate_runtime_guard"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module





def load_lifecycle_helpers():
    name = "n3w_broker_certificate_lifecycle_test_helpers"
    spec = importlib.util.spec_from_file_location(name, LIFECYCLE_TEST)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, document: dict[str, object], mode: int = 0o600) -> None:
    path.write_text(json.dumps(document) + "\n", encoding="utf-8")
    path.chmod(mode)


def fake_fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json_test_fixture(
    path: Path,
    mode: int,
) -> dict[str, object]:
    assert path.is_file()
    assert not path.is_symlink()
    assert path.stat().st_mode & 0o777 == mode
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_runtime_guard_accepts_legitimate_status_evolution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    transaction = tmp_path / "transaction.json"
    status = tmp_path / "status.json"
    server = tmp_path / "server.pem"
    ca = tmp_path / "ca.pem"
    system_ca = tmp_path / "system-ca.pem"

    for path, mode in ((server, 0o644), (ca, 0o644), (system_ca, 0o600)):
        path.write_text(path.name + "\n", encoding="ascii")
        path.chmod(mode)

    first_audit_sha = "a" * 64
    write_json(
        transaction,
        {
            "stage": "PERSISTENCE_ENABLED",
            "broker_services_persistence_enabled": True,
            "persistence_enabled": True,
            "certificate_first_audit_passed": True,
            "certificate_timer_enabled": True,
            "pre_reboot_ready": True,
            "certificate_status_sha256": first_audit_sha,
        },
    )

    monkeypatch.setattr(tool, "TRANSACTION_PATH", transaction)
    monkeypatch.setattr(tool, "CERT_STATUS_FILE", status)
    monkeypatch.setattr(tool, "SERVER_CERT", server)
    monkeypatch.setattr(tool, "CA_CERT", ca)
    monkeypatch.setattr(tool, "SYSTEM_CA", system_ca)
    monkeypatch.setattr(tool, "_json", read_json_test_fixture)
    monkeypatch.setattr(tool, "_f4_control_contract", lambda _transaction: None)
    monkeypatch.setattr(
        tool,
        "_certificate_fingerprint",
        lambda path, _mode: fake_fingerprint(path),
    )

    def status_document(checked_at: str) -> dict[str, object]:
        return {
            "schema": tool.STATUS_SCHEMA,
            "checked_at": checked_at,
            "action": "audit",
            "result": "ok",
            "server_state": "HEALTHY",
            "ca_state": "HEALTHY",
            "system_ca_state": "HEALTHY",
            "server_sha256_fingerprint": fake_fingerprint(server),
            "ca_sha256_fingerprint": fake_fingerprint(ca),
            "system_ca_sha256_fingerprint": fake_fingerprint(system_ca),
            "renewal_attempted": False,
            "rollback_attempted": False,
        }

    write_json(status, status_document("2026-10-16T01:00:00Z"))
    first_runtime_sha = hashlib.sha256(status.read_bytes()).hexdigest()
    assert first_runtime_sha != first_audit_sha
    assert tool.check()["status"] == "PASS"

    write_json(status, status_document("2026-10-17T01:00:00Z"))
    second_runtime_sha = hashlib.sha256(status.read_bytes()).hexdigest()
    assert second_runtime_sha != first_runtime_sha
    result = tool.check()
    assert result["status"] == "PASS"
    assert result["runtime_status_sha256"] == second_runtime_sha


def test_runtime_guard_rejects_status_certificate_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    transaction = tmp_path / "transaction.json"
    status = tmp_path / "status.json"
    server = tmp_path / "server.pem"
    ca = tmp_path / "ca.pem"
    system_ca = tmp_path / "system-ca.pem"

    for path, mode in ((server, 0o644), (ca, 0o644), (system_ca, 0o600)):
        path.write_text(path.name + "\n", encoding="ascii")
        path.chmod(mode)

    write_json(
        transaction,
        {
            "stage": "PERSISTENCE_ENABLED",
            "broker_services_persistence_enabled": True,
            "persistence_enabled": True,
            "certificate_first_audit_passed": True,
            "certificate_timer_enabled": True,
            "pre_reboot_ready": True,
            "certificate_status_sha256": "b" * 64,
        },
    )
    write_json(
        status,
        {
            "schema": tool.STATUS_SCHEMA,
            "checked_at": "2026-10-16T01:00:00Z",
            "action": "audit",
            "result": "ok",
            "server_state": "HEALTHY",
            "ca_state": "HEALTHY",
            "system_ca_state": "HEALTHY",
            "server_sha256_fingerprint": "0" * 64,
            "ca_sha256_fingerprint": fake_fingerprint(ca),
            "system_ca_sha256_fingerprint": fake_fingerprint(system_ca),
            "renewal_attempted": False,
            "rollback_attempted": False,
        },
    )

    monkeypatch.setattr(tool, "TRANSACTION_PATH", transaction)
    monkeypatch.setattr(tool, "CERT_STATUS_FILE", status)
    monkeypatch.setattr(tool, "SERVER_CERT", server)
    monkeypatch.setattr(tool, "CA_CERT", ca)
    monkeypatch.setattr(tool, "SYSTEM_CA", system_ca)
    monkeypatch.setattr(tool, "_json", read_json_test_fixture)
    monkeypatch.setattr(tool, "_f4_control_contract", lambda _transaction: None)
    monkeypatch.setattr(
        tool,
        "_certificate_fingerprint",
        lambda path, _mode: fake_fingerprint(path),
    )

    with pytest.raises(tool.GuardError, match="server_sha256_fingerprint"):
        tool.check()


def test_dropin_replaces_old_exact_status_gate() -> None:
    dropin = (
        ROOT
        / "infra/n3w-t1/f4/reboot-successor/"
        "n3wfc4-broker-certificate-lifecycle.service.d/"
        "10-runtime-status-evolution.conf"
    ).read_text(encoding="utf-8")

    assert "ExecStartPre=" in dropin
    assert (
        "ExecStartPre=/usr/local/sbin/"
        "n3w-t1-f4-certificate-runtime-guard check"
    ) in dropin
    assert "eligibility --phase certificate" not in dropin


def test_production_guard_keeps_root_owned_record_contract() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert "metadata.st_uid != 0" in source
    assert "metadata.st_gid != 0" in source
    assert "metadata.st_nlink != 1" in source
    assert "stat.S_IMODE(metadata.st_mode) != mode" in source



def test_two_real_lifecycle_checks_remain_runtime_guard_eligible(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    guard = load_tool()
    helpers = load_lifecycle_helpers()
    lifecycle = helpers.load_tool()
    material = helpers.make_material(tmp_path, server_days=120, ca_days=3650)
    status_dir = tmp_path / "status"
    status_dir.mkdir(mode=0o700)
    status = status_dir / "status.json"
    transaction = tmp_path / "transaction.json"

    config = lifecycle.LifecycleConfig(
        server_cert=material["server_cert"],
        server_key=material["server_key"],
        ca_cert=material["ca_cert"],
        ca_key=material["ca_key"],
        system_ca=material["ca_cert"],
        server_name="broker.test",
        status_file=status,
        allowed_roots=(tmp_path,),
    )
    base_now = lifecycle._certificate_info(
        material["server_cert"]
    ).not_before + timedelta(days=1)
    initial_document, initial_code = lifecycle.audit(config, now=base_now)
    assert initial_code == 0
    lifecycle._atomic_write_status(status, initial_document)
    first_audit_sha = hashlib.sha256(status.read_bytes()).hexdigest()

    write_json(
        transaction,
        {
            "stage": "PERSISTENCE_ENABLED",
            "broker_services_persistence_enabled": True,
            "persistence_enabled": True,
            "certificate_first_audit_passed": True,
            "certificate_timer_enabled": True,
            "pre_reboot_ready": True,
            "certificate_status_sha256": first_audit_sha,
        },
    )

    monkeypatch.setattr(guard, "TRANSACTION_PATH", transaction)
    monkeypatch.setattr(guard, "CERT_STATUS_FILE", status)
    monkeypatch.setattr(guard, "SERVER_CERT", material["server_cert"])
    monkeypatch.setattr(guard, "CA_CERT", material["ca_cert"])
    monkeypatch.setattr(guard, "SYSTEM_CA", material["ca_cert"])
    monkeypatch.setattr(guard, "_json", read_json_test_fixture)
    monkeypatch.setattr(guard, "_f4_control_contract", lambda _transaction: None)
    monkeypatch.setattr(
        guard,
        "_certificate_fingerprint",
        lambda path, _mode: lifecycle._certificate_info(path).fingerprint,
    )

    first_precheck = guard.check()
    assert first_precheck["status"] == "PASS"
    runtime_hashes = [first_precheck["runtime_status_sha256"]]

    for current in (
        base_now + timedelta(days=1),
        base_now + timedelta(days=2),
    ):
        document, code = lifecycle.auto_renew(config, now=current)
        assert code == 0
        lifecycle._atomic_write_status(status, document)
        report = guard.check()
        assert report["status"] == "PASS"
        runtime_hashes.append(report["runtime_status_sha256"])

    assert runtime_hashes[0] == first_audit_sha
    assert runtime_hashes[1] != first_audit_sha
    assert runtime_hashes[2] != runtime_hashes[1]


def test_runtime_guard_accepts_ca_rollover_required_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    guard = load_tool()
    helpers = load_lifecycle_helpers()
    lifecycle = helpers.load_tool()
    material = helpers.make_material(tmp_path, server_days=45, ca_days=850)
    status_dir = tmp_path / "status"
    status_dir.mkdir(mode=0o700)
    status = status_dir / "status.json"
    transaction = tmp_path / "transaction.json"
    config = lifecycle.LifecycleConfig(
        server_cert=material["server_cert"],
        server_key=material["server_key"],
        ca_cert=material["ca_cert"],
        ca_key=material["ca_key"],
        system_ca=material["ca_cert"],
        server_name="broker.test",
        status_file=status,
        allowed_roots=(tmp_path,),
    )
    current = lifecycle._certificate_info(
        material["server_cert"]
    ).not_before + timedelta(days=1)
    document, code = lifecycle.auto_renew(config, now=current)
    assert code == 2
    assert document["result"] == "ca_rollover_required"
    assert document["server_state"] == "RENEW_DUE"
    assert document["ca_state"] == "CA_ROLLOVER_REQUIRED"
    lifecycle._atomic_write_status(status, document)

    write_json(
        transaction,
        {
            "stage": "PERSISTENCE_ENABLED",
            "broker_services_persistence_enabled": True,
            "persistence_enabled": True,
            "certificate_first_audit_passed": True,
            "certificate_timer_enabled": True,
            "pre_reboot_ready": True,
            "certificate_status_sha256": "a" * 64,
        },
    )
    monkeypatch.setattr(guard, "TRANSACTION_PATH", transaction)
    monkeypatch.setattr(guard, "CERT_STATUS_FILE", status)
    monkeypatch.setattr(guard, "SERVER_CERT", material["server_cert"])
    monkeypatch.setattr(guard, "CA_CERT", material["ca_cert"])
    monkeypatch.setattr(guard, "SYSTEM_CA", material["ca_cert"])
    monkeypatch.setattr(guard, "_json", read_json_test_fixture)
    monkeypatch.setattr(guard, "_f4_control_contract", lambda _transaction: None)
    monkeypatch.setattr(
        guard,
        "_certificate_fingerprint",
        lambda path, _mode: lifecycle._certificate_info(path).fingerprint,
    )

    report = guard.check()
    assert report["status"] == "PASS"
    assert report["server_state"] == "RENEW_DUE"
    assert report["ca_state"] == "CA_ROLLOVER_REQUIRED"

def test_production_guard_preserves_full_f4_control_contract() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert "module._provision_verify()" in source
    assert "module._validate_transaction_binding(verified)" in source
    assert "module._validate_factory_binding(verified)" in source
    assert "module._verify_installed_material(verified_transaction)" in source
    assert "module._runtime_activity()" in source
