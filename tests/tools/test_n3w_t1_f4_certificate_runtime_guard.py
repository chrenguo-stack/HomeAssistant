from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_f4_certificate_runtime_guard.py"


def load_tool():
    name = "n3w_t1_f4_certificate_runtime_guard"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, document: dict[str, object], mode: int = 0o600) -> None:
    path.write_text(json.dumps(document) + "\n", encoding="utf-8")
    path.chmod(mode)


def fake_fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    monkeypatch.setattr(tool, "_certificate_fingerprint", lambda path, _mode: fake_fingerprint(path))

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
    monkeypatch.setattr(tool, "_certificate_fingerprint", lambda path, _mode: fake_fingerprint(path))

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
