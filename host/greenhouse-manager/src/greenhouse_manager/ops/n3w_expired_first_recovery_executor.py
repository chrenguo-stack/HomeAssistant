"""Run an expired-first recovery with exact host-source mount bindings."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sqlite3
import stat
import sys
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any, TextIO

from .registration_cli import main as registration_main


class RecoveryExecutorError(RuntimeError):
    """A fail-closed executor error with a secret-safe public code."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _absolute_regular_file(value: str, *, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise RecoveryExecutorError(f"{label}_PATH_MUST_BE_ABSOLUTE")
    if path.is_symlink() or not path.is_file():
        raise RecoveryExecutorError(f"{label}_NOT_REGULAR_FILE")
    return path


def _private_inspect_document(path: Path) -> dict[str, Any]:
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise RecoveryExecutorError("MANAGER_INSPECT_MODE_INVALID")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RecoveryExecutorError("MANAGER_INSPECT_INVALID") from error
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise RecoveryExecutorError("MANAGER_INSPECT_INVALID")
    return payload[0]


def _exact_pairing_id(
    registration: Path,
    *,
    hardware_id: str,
    pairing_id_sha256: str,
) -> str:
    connection = sqlite3.connect(f"{registration.as_uri()}?mode=ro", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute(
            "SELECT pairing_id, state, reason FROM pairing_sessions WHERE hardware_id = ?",
            (hardware_id,),
        ).fetchall()
    finally:
        connection.close()
    matches = [
        row
        for row in rows
        if _sha256_bytes(str(row["pairing_id"]).encode("utf-8")) == pairing_id_sha256
    ]
    if len(matches) != 1:
        raise RecoveryExecutorError("EXACT_PAIRING_TOMBSTONE_NOT_UNIQUE")
    if matches[0]["state"] != "expired" or matches[0]["reason"] != "expired":
        raise RecoveryExecutorError("EXACT_PAIRING_TOMBSTONE_NOT_EXPIRED")
    return str(matches[0]["pairing_id"])


def _postconditions(
    registration: Path,
    *,
    hardware_id: str,
    pairing_id_sha256: str,
) -> None:
    connection = sqlite3.connect(f"{registration.as_uri()}?mode=ro", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        current_count = connection.execute(
            "SELECT count(*) FROM registrations WHERE hardware_id = ?",
            (hardware_id,),
        ).fetchone()[0]
        sessions = connection.execute(
            "SELECT pairing_id, state, reason FROM pairing_sessions WHERE hardware_id = ?",
            (hardware_id,),
        ).fetchall()
        events = connection.execute(
            """
            SELECT event, reason FROM registration_events
            WHERE hardware_id = ? ORDER BY event_id DESC
            """,
            (hardware_id,),
        ).fetchall()
    finally:
        connection.close()
    matches = [
        row
        for row in sessions
        if _sha256_bytes(str(row["pairing_id"]).encode("utf-8")) == pairing_id_sha256
    ]
    if current_count != 0:
        raise RecoveryExecutorError("CURRENT_REGISTRATION_NOT_RELEASED")
    if len(matches) != 1 or matches[0]["state"] != "expired" or matches[0]["reason"] != "expired":
        raise RecoveryExecutorError("REPLAY_TOMBSTONE_NOT_PRESERVED")
    if not events or events[0]["event"] != "expired_first_registration_abandoned":
        raise RecoveryExecutorError("RECOVERY_EVENT_MISSING")
    if events[0]["reason"] != "expired_first_pairing_recovery":
        raise RecoveryExecutorError("RECOVERY_EVENT_REASON_INVALID")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute an exact-host-path expired-first registration recovery"
    )
    parser.add_argument("--registration-db", required=True)
    parser.add_argument("--credential-db", required=True)
    parser.add_argument("--manager-inspect-json", required=True)
    parser.add_argument("--manager-container", required=True)
    parser.add_argument("--registration-container-path", required=True)
    parser.add_argument("--credential-container-path", required=True)
    parser.add_argument("--hardware-id", required=True)
    parser.add_argument("--expected-pairing-id-sha256", required=True)
    parser.add_argument("--expected-registration-sha256", required=True)
    parser.add_argument("--expected-credential-sha256", required=True)
    parser.add_argument("--confirm-manager-stopped", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    args = _parser().parse_args(argv)
    try:
        if not args.confirm_manager_stopped:
            raise RecoveryExecutorError("MANAGER_STOP_CONFIRMATION_REQUIRED")
        for value, label in (
            (args.expected_pairing_id_sha256, "EXPECTED_PAIRING_ID_SHA256"),
            (args.expected_registration_sha256, "EXPECTED_REGISTRATION_SHA256"),
            (args.expected_credential_sha256, "EXPECTED_CREDENTIAL_SHA256"),
        ):
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise RecoveryExecutorError(f"{label}_INVALID")
        for value, label in (
            (args.registration_container_path, "REGISTRATION_CONTAINER"),
            (args.credential_container_path, "CREDENTIAL_CONTAINER"),
        ):
            if not PurePosixPath(value).is_absolute():
                raise RecoveryExecutorError(f"{label}_PATH_MUST_BE_ABSOLUTE")

        registration = _absolute_regular_file(args.registration_db, label="REGISTRATION_DATABASE")
        credential = _absolute_regular_file(args.credential_db, label="CREDENTIAL_DATABASE")
        inspect_path = _absolute_regular_file(args.manager_inspect_json, label="MANAGER_INSPECT")
        inspect_document = _private_inspect_document(inspect_path)
        registration_before = _sha256_file(registration)
        credential_before = _sha256_file(credential)
        if registration_before != args.expected_registration_sha256:
            raise RecoveryExecutorError("REGISTRATION_DATABASE_HASH_MISMATCH")
        if credential_before != args.expected_credential_sha256:
            raise RecoveryExecutorError("CREDENTIAL_DATABASE_HASH_MISMATCH")
        pairing_id = _exact_pairing_id(
            registration,
            hardware_id=args.hardware_id,
            pairing_id_sha256=args.expected_pairing_id_sha256,
        )

        raw_result = io.StringIO()
        raw_error = io.StringIO()
        code = registration_main(
            [
                "--db",
                str(registration),
                "abandon-expired-first",
                args.hardware_id,
                pairing_id,
                "--credential-db",
                str(credential),
                "--manager-container",
                args.manager_container,
                "--registration-container-path",
                args.registration_container_path,
                "--credential-container-path",
                args.credential_container_path,
                "--reason",
                "expired_first_pairing_recovery",
                "--confirm-manager-stopped",
            ],
            stdout=raw_result,
            stderr=raw_error,
            container_inspector=lambda name: inspect_document,
        )
        if code != 0:
            raise RecoveryExecutorError("RECOVERY_CLI_FAILED")
        serialized_result = raw_result.getvalue()
        if not serialized_result:
            raise RecoveryExecutorError("RECOVERY_RESULT_EMPTY")
        try:
            result = json.loads(serialized_result)
        except json.JSONDecodeError as error:
            raise RecoveryExecutorError("RECOVERY_RESULT_INVALID") from error
        required_true = (
            "current_registration_released",
            "replay_tombstone_preserved",
            "credential_history_absent",
            "manager_container_stopped",
            "registration_db_binding_verified",
            "credential_db_binding_verified",
        )
        if result.get("result") != "expired_first_registration_abandoned" or not all(
            result.get(key) is True for key in required_true
        ):
            raise RecoveryExecutorError("RECOVERY_RESULT_POSTCONDITION_INVALID")
        _postconditions(
            registration,
            hardware_id=args.hardware_id,
            pairing_id_sha256=args.expected_pairing_id_sha256,
        )
        credential_after = _sha256_file(credential)
        if credential_after != credential_before:
            raise RecoveryExecutorError("CREDENTIAL_DATABASE_UNEXPECTED_MUTATION")
        registration_after = _sha256_file(registration)
    except RecoveryExecutorError as error:
        print(f"RECOVERY_EXECUTOR=FAIL:{error}", file=error_output)
        print("PAIRING_ID_RAW_EXPOSED=false", file=error_output)
        print("SECRET_VALUE_EXPOSED=false", file=error_output)
        return 1
    except (OSError, sqlite3.Error):
        print("RECOVERY_EXECUTOR=FAIL:RECOVERY_EXECUTOR_IO_FAILED", file=error_output)
        print("PAIRING_ID_RAW_EXPOSED=false", file=error_output)
        print("SECRET_VALUE_EXPOSED=false", file=error_output)
        return 1

    document = {
        "schema": "gh.n3w.expired-first-recovery-executor/1",
        "result": "PASS",
        "hardware_id_sha256": _sha256_bytes(args.hardware_id.encode("utf-8")),
        "pairing_id_sha256": args.expected_pairing_id_sha256,
        "registration_sha256_before": registration_before,
        "registration_sha256_after": registration_after,
        "credential_sha256_before": credential_before,
        "credential_sha256_after": credential_after,
        "current_registration_released": True,
        "replay_tombstone_preserved": True,
        "recovery_event_present": True,
        "manager_stopped_inspect_verified": True,
        "host_source_database_paths_verified": True,
        "raw_recovery_result_nonempty": True,
        "pairing_id_raw_exposed": False,
        "secret_value_exposed": False,
    }
    json.dump(document, output, sort_keys=True, separators=(",", ":"))
    output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
