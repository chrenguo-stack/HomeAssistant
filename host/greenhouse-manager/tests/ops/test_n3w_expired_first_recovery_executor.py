from __future__ import annotations

import hashlib
import json
import shutil
import tomllib
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path

from greenhouse_manager.ops import n3w_expired_first_recovery_executor as executor
from greenhouse_manager.runtime.credential_lifecycle import CredentialLifecycleStore
from greenhouse_manager.runtime.registration import RegistrationRegistry

HARDWARE_ID = "ghw-c6-98a316a9f350"
PAIRING_ID = "7a7ff697-4d0b-4a62-b5c5-4903721c72f6"
PAIRING_SHA256 = hashlib.sha256(PAIRING_ID.encode()).hexdigest()
MANAGER_CONTAINER = "fc4-manager"
REGISTRATION_CONTAINER_PATH = "/var/lib/greenhouse-manager/manager/registration.sqlite3"
CREDENTIAL_CONTAINER_PATH = "/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3"


def _hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "lcd-pairing-qr"],
        "sent_at_ms": 120345,
    }


def _state_root(tmp_path: Path, name: str = "state") -> tuple[Path, Path, Path]:
    state = tmp_path / name
    registration = state / "manager" / "registration.sqlite3"
    credential = state / "n3w" / "credential-lifecycle.sqlite3"
    registration.parent.mkdir(parents=True)
    credential.parent.mkdir(parents=True)
    now = datetime(2026, 8, 21, 1, 0, tzinfo=UTC)
    with RegistrationRegistry(registration, pending_ttl_s=1) as registry:
        registry.observe_hello(_hello(), now=now)
        registry.expire_pending(now=now + timedelta(seconds=2))
    with CredentialLifecycleStore(credential):
        pass
    return state, registration, credential


def _inspect(path: Path, state: Path) -> Path:
    document = [
        {
            "Name": f"/{MANAGER_CONTAINER}",
            "State": {
                "Status": "exited",
                "Running": False,
                "Restarting": False,
                "Paused": False,
                "Pid": 0,
            },
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": str(state),
                    "Destination": "/var/lib/greenhouse-manager",
                }
            ],
        }
    ]
    path.write_text(json.dumps(document))
    path.chmod(0o600)
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _arguments(registration: Path, credential: Path, inspect: Path) -> list[str]:
    return [
        "--registration-db",
        str(registration),
        "--credential-db",
        str(credential),
        "--manager-inspect-json",
        str(inspect),
        "--manager-container",
        MANAGER_CONTAINER,
        "--registration-container-path",
        REGISTRATION_CONTAINER_PATH,
        "--credential-container-path",
        CREDENTIAL_CONTAINER_PATH,
        "--hardware-id",
        HARDWARE_ID,
        "--expected-pairing-id-sha256",
        PAIRING_SHA256,
        "--expected-registration-sha256",
        _sha256(registration),
        "--expected-credential-sha256",
        _sha256(credential),
        "--confirm-manager-stopped",
    ]


def test_real_inspect_adapter_uses_host_source_paths_and_recovers(tmp_path: Path) -> None:
    state, registration, credential = _state_root(tmp_path)
    inspect = _inspect(tmp_path / "inspect.private.json", state)
    credential_before = _sha256(credential)
    stdout = StringIO()
    stderr = StringIO()

    result = executor.main(
        _arguments(registration, credential, inspect),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert stderr.getvalue() == ""
    document = json.loads(stdout.getvalue())
    assert document["result"] == "PASS"
    assert document["host_source_database_paths_verified"] is True
    assert document["raw_recovery_result_nonempty"] is True
    assert document["pairing_id_raw_exposed"] is False
    assert document["secret_value_exposed"] is False
    assert PAIRING_ID not in stdout.getvalue()
    assert _sha256(credential) == credential_before
    with RegistrationRegistry(registration) as registry:
        assert registry.list_current() == ()
        tombstone = registry.list_events(hardware_id=HARDWARE_ID)[0]
        assert tombstone.event == "expired_first_registration_abandoned"


def test_container_destination_db_arguments_fail_before_mutation(tmp_path: Path) -> None:
    source, _source_registration, _source_credential = _state_root(tmp_path, "source-state")
    destination = tmp_path / "destination-state"
    shutil.copytree(source, destination)
    registration = destination / "manager" / "registration.sqlite3"
    credential = destination / "n3w" / "credential-lifecycle.sqlite3"
    inspect = _inspect(tmp_path / "inspect.private.json", source)
    registration_before = _sha256(registration)
    stdout = StringIO()
    stderr = StringIO()

    result = executor.main(
        _arguments(registration, credential, inspect),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 1
    assert stdout.getvalue() == ""
    assert "RECOVERY_EXECUTOR=FAIL:RECOVERY_CLI_FAILED" in stderr.getvalue()
    assert PAIRING_ID not in stderr.getvalue()
    assert _sha256(registration) == registration_before


def test_empty_nested_result_is_rejected_before_json_parse(
    tmp_path: Path, monkeypatch: object
) -> None:
    state, registration, credential = _state_root(tmp_path)
    inspect = _inspect(tmp_path / "inspect.private.json", state)
    registration_before = _sha256(registration)

    def empty_result(*args: object, **kwargs: object) -> int:
        return 0

    monkeypatch.setattr(executor, "registration_main", empty_result)
    stdout = StringIO()
    stderr = StringIO()
    result = executor.main(
        _arguments(registration, credential, inspect),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 1
    assert "RECOVERY_EXECUTOR=FAIL:RECOVERY_RESULT_EMPTY" in stderr.getvalue()
    assert _sha256(registration) == registration_before


def test_supported_cli_entry_point_targets_the_tested_main() -> None:
    project = Path(__file__).parents[2] / "pyproject.toml"
    document = tomllib.loads(project.read_text())

    assert document["project"]["scripts"][
        "greenhouse-manager-n3w-expired-first-recovery"
    ] == "greenhouse_manager.ops.n3w_expired_first_recovery_executor:main"
