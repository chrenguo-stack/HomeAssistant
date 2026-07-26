from __future__ import annotations

import json
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from greenhouse_manager.ops.node_retirement_cli import main
from greenhouse_manager.runtime.credential_lifecycle import CredentialLifecycleStore
from greenhouse_manager.runtime.registration import RegistrationRegistry

HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
NODE_ID = "gh-n1-a9f2f8"


class FakeRevoker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def revoke(self, job: object, generation: int) -> None:
        self.calls.append((job.node_id, generation))


def hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 3,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "simulator-M2.1c",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "lcd-pairing-qr"],
        "sent_at_ms": 120345,
    }


def database(tmp_path: Path) -> Path:
    path = tmp_path / "registration.sqlite3"
    now = datetime.now(UTC)
    with RegistrationRegistry(path) as registry:
        registry.observe_hello(hello(), now=now)
        registry.approve(HARDWARE_ID, PAIRING_ID, node_id=NODE_ID, now=now)
    with CredentialLifecycleStore(path) as lifecycle:
        lifecycle.activate(
            hardware_id=HARDWARE_ID,
            node_id=NODE_ID,
            generation=2,
            now=now,
        )
    return path


def run(
    path: Path,
    *args: str,
    revoker: FakeRevoker | None = None,
) -> tuple[int, object, str]:
    stdout = StringIO()
    stderr = StringIO()
    code = main(
        ["--db", str(path), *args],
        stdout=stdout,
        stderr=stderr,
        credential_revoker=revoker,
    )
    document = json.loads(stdout.getvalue()) if stdout.getvalue() else None
    return code, document, stderr.getvalue()


def test_retire_command_queues_durable_cleanup(tmp_path: Path) -> None:
    path = database(tmp_path)
    code, document, error = run(
        path,
        "retire",
        HARDWARE_ID,
        "--system-id",
        "greenhouse",
        "--defer-credential-revocation",
    )

    assert code == 0
    assert error == ""
    assert document["node_id"] == NODE_ID
    assert document["runtime_cleanup_complete"] is False
    assert document["credentials_revoked"] is False


def test_retire_command_can_revoke_credentials_without_secrets_in_output(
    tmp_path: Path,
) -> None:
    path = database(tmp_path)
    revoker = FakeRevoker()

    code, document, error = run(
        path,
        "retire",
        HARDWARE_ID,
        "--system-id",
        "greenhouse",
        revoker=revoker,
    )

    assert code == 0
    assert error == ""
    assert revoker.calls == [(NODE_ID, 2)]
    assert document["credentials_revoked"] is True
    assert "password" not in json.dumps(document)
    with CredentialLifecycleStore(path) as lifecycle:
        record = lifecycle.get(HARDWARE_ID)
    assert record.node_id is None
    assert record.last_node_id == NODE_ID


class FailingRevoker:
    def revoke(self, job: object, generation: int) -> None:
        raise RuntimeError("injected revocation failure")


def test_credential_revocation_failure_is_recorded_in_outbox(tmp_path: Path) -> None:
    path = database(tmp_path)

    code, document, error = run(
        path,
        "retire",
        HARDWARE_ID,
        "--system-id",
        "greenhouse",
        revoker=FailingRevoker(),
    )

    assert code == 3
    assert document is None
    assert "injected revocation failure" in error
    with RegistrationRegistry(path) as registry:
        job = registry.list_retirement_jobs()[0]
    assert job.attempts == 1
    assert job.last_error == "credential_revocation_failed:RuntimeError"
    assert job.credentials_revoked is False
