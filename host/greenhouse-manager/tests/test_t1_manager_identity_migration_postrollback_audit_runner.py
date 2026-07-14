from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any, Sequence

import pytest

from greenhouse_manager.t1_manager_identity_migration_postrollback_audit import (
    AUTHENTICATION_ENVIRONMENT_KEYS,
    ManagerPostrollbackAuditError,
    build_manager_postrollback_audit,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeRunner:
    def __init__(self, documents: dict[str, dict[str, Any]]) -> None:
        self.documents = documents
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: Sequence[str]) -> tuple[int, str]:
        normalized = tuple(command)
        self.commands.append(normalized)
        if normalized[:2] == ("docker", "inspect"):
            document = self.documents.get(normalized[2])
            return (0, json.dumps([document])) if document else (1, "missing")
        if normalized[:4] == ("docker", "exec", "mosquitto", "mosquitto_sub"):
            return 0, '{"temperature":25}\n'
        return 1, "unexpected command"


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)


def _archive(path: Path, rollback: dict[str, Any]) -> None:
    payload = json.dumps(rollback, sort_keys=True).encode("utf-8")
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo("rollback-manifest.json")
        info.size = len(payload)
        info.mode = 0o600
        archive.addfile(info, io.BytesIO(payload))
    path.chmod(0o600)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _baseline() -> dict[str, object]:
    return {
        key: {
            "present": key != "GH_MQTT_PASSWORD_FILE",
            "nonempty": False,
        }
        for key in AUTHENTICATION_ENVIRONMENT_KEYS
    }


def _container(
    *,
    image: str,
    started_at: str = "2026-07-14T10:00:00Z",
    restart_count: int = 0,
    pid: int = 321,
    environment: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "Image": image,
        "RestartCount": restart_count,
        "State": {
            "Status": "running",
            "StartedAt": started_at,
            "Pid": pid,
        },
        "Config": {"Env": environment or []},
        "Mounts": [],
    }


def _fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, FakeRunner, FakeClock, dict[str, Any]]:
    transaction = tmp_path / "transaction-test"
    execution = tmp_path / "greenhouse-manager-execution-preparation-test"
    working = tmp_path / "compose"
    secret_root = tmp_path / "secrets"
    for directory in (transaction, execution, working, secret_root):
        directory.mkdir(mode=0o700)

    rollback: dict[str, Any] = {
        "schema": "gh.m2.t1-manager-identity-fresh-rollback/1",
        "manager_only": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "compose_working_directory": str(working),
        "manager_secret_root": str(secret_root),
        "manager_password_target": str(secret_root / "manager/password"),
        "manager_runtime_image_id": "sha256:manager-image",
        "preclaim_authentication_environment_baseline": _baseline(),
        "created_directory_targets": [],
    }
    rollback_path = execution / "fresh-rollback-manifest.json"
    archive_path = execution / "fresh-manager-rollback.tar.gz"
    _write_json(rollback_path, rollback)
    _archive(archive_path, rollback)
    journal = {
        "schema": "gh.m2.t1-manager-identity-production-journal/1",
        "target": "greenhouse-manager",
        "phase": "rollback_completed",
        "created_at": "2026-07-14T12:00:00Z",
        "fresh_rollback_archive_sha256": _sha(archive_path),
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    _write_json(transaction / "journal.json", journal)

    proc_root = tmp_path / "proc"
    net = proc_root / "321/net"
    net.mkdir(parents=True)
    header = "sl local_address rem_address st tx tr retr uid timeout inode\n"
    socket = (
        "0: 0100007F:C350 0100007F:075B 01 00000000:00000000 "
        "00:00000000 00000000 1000 0 424242\n"
    )
    (net / "tcp").write_text(header + socket, encoding="ascii")
    (net / "tcp6").write_text(header, encoding="ascii")

    documents = {
        "greenhouse-manager": _container(
            image="sha256:manager-image",
            environment=[
                "GH_MQTT_USERNAME=",
                "GH_MQTT_PASSWORD=",
                "GH_MQTT_CLIENT_ID=greenhouse-manager",
                "UNRELATED_SECRET=must-not-leak",
            ],
        ),
        "mosquitto": _container(image="sha256:mosquitto"),
        "homeassistant": _container(image="sha256:homeassistant"),
    }
    runner = FakeRunner(documents)
    return transaction, execution, proc_root, runner, FakeClock(), rollback


def _audit(
    transaction: Path,
    execution: Path,
    proc_root: Path,
    runner: FakeRunner,
    clock: FakeClock,
) -> dict[str, object]:
    return build_manager_postrollback_audit(
        transaction,
        execution,
        expected_retained_topic="gh/greenhouse/node-01/telemetry",
        timeout_s=0.04,
        poll_interval_s=0.01,
        proc_root=proc_root,
        runner=runner,
        sleeper=clock.sleep,
        monotonic=clock.monotonic,
    )


def test_live_read_only_postrollback_audit_passes_and_is_redacted(
    tmp_path: Path,
) -> None:
    transaction, execution, proc_root, runner, clock, _rollback = _fixture(tmp_path)

    report = _audit(transaction, execution, proc_root, runner, clock)

    assert report["rollback_audit_passed"] is True
    assert report["manual_recovery_required"] is False
    assert report["manual_review_required"] is False
    assert len(runner.commands) == 4
    serialized = json.dumps(report)
    assert str(tmp_path) not in serialized
    assert "must-not-leak" not in serialized
    assert "greenhouse-manager" not in serialized


def test_legacy_missing_baselines_requires_review_not_recovery(tmp_path: Path) -> None:
    transaction, execution, proc_root, runner, clock, rollback = _fixture(tmp_path)
    rollback.pop("preclaim_authentication_environment_baseline")
    rollback.pop("created_directory_targets")
    _write_json(execution / "fresh-rollback-manifest.json", rollback)
    _archive(execution / "fresh-manager-rollback.tar.gz", rollback)
    journal = json.loads((transaction / "journal.json").read_text())
    journal["fresh_rollback_archive_sha256"] = _sha(
        execution / "fresh-manager-rollback.tar.gz"
    )
    _write_json(transaction / "journal.json", journal)

    report = _audit(transaction, execution, proc_root, runner, clock)

    assert report["rollback_audit_passed"] is False
    assert report["baseline_unavailable"] is True
    assert report["manual_recovery_required"] is False
    assert report["manual_review_required"] is True


@pytest.mark.parametrize("service", ("mosquitto", "homeassistant"))
def test_protected_service_restart_requires_recovery(
    tmp_path: Path,
    service: str,
) -> None:
    transaction, execution, proc_root, runner, clock, _rollback = _fixture(tmp_path)
    runner.documents[service]["RestartCount"] = 1

    report = _audit(transaction, execution, proc_root, runner, clock)

    assert report["rollback_audit_passed"] is False
    assert report["manual_recovery_required"] is True


def test_archived_manifest_drift_is_rejected(tmp_path: Path) -> None:
    transaction, execution, proc_root, runner, clock, _rollback = _fixture(tmp_path)
    manifest = json.loads(
        (execution / "fresh-rollback-manifest.json").read_text()
    )
    manifest["created_directory_targets"] = [str(tmp_path / "unexpected")]
    _write_json(execution / "fresh-rollback-manifest.json", manifest)

    with pytest.raises(ManagerPostrollbackAuditError, match="archive binding"):
        _audit(transaction, execution, proc_root, runner, clock)
