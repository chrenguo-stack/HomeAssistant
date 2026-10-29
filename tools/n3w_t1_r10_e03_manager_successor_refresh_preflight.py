#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Sequence

PROJECT = "n3wfc4"
BROKER_UNIT = "n3wfc4-broker-activation.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
REGISTRATION_GUARD_UNIT = "n3wfc4-registration-ingress-guard.service"
MANAGER_DB = "/var/lib/greenhouse-manager/manager/manager-state.sqlite3"
EXPECTED_CURRENT_MANAGER_IMAGE = "local/greenhouse-manager:fresh-ff750b3801a2"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


class PreflightError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


class Runner:
    def run(self, argv: Sequence[str], *, timeout: int = 30) -> CommandResult:
        completed = subprocess.run(
            tuple(argv),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )


def _require_success(result: CommandResult, label: str) -> str:
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise PreflightError(f"{label}_failed:{detail[:400]}")
    return result.stdout.strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_sha256(value: str, label: str) -> str:
    normalized = value.lower()
    if _SHA256.fullmatch(normalized) is None:
        raise PreflightError(f"{label}_invalid")
    return normalized


def _require_image_id(value: str, label: str) -> str:
    normalized = value.lower()
    if _IMAGE_ID.fullmatch(normalized) is None:
        raise PreflightError(f"{label}_invalid")
    return normalized


def _systemctl(runner: Runner, action: str, unit: str) -> str:
    return _require_success(
        runner.run(("systemctl", action, unit)),
        f"systemctl_{action}_{unit}",
    )


def _service_container_id(runner: Runner, service: str) -> str:
    output = _require_success(
        runner.run(
            (
                "docker",
                "ps",
                "-q",
                "--filter",
                f"label=com.docker.compose.project={PROJECT}",
                "--filter",
                f"label=com.docker.compose.service={service}",
            )
        ),
        f"{service}_container_lookup",
    )
    values = [line.strip() for line in output.splitlines() if line.strip()]
    if len(values) != 1:
        raise PreflightError(
            f"{service}_container_count_invalid:{len(values)}"
        )
    return values[0]


def _inspect_container(runner: Runner, container_id: str) -> dict[str, Any]:
    output = _require_success(
        runner.run(("docker", "inspect", container_id)),
        "container_inspect",
    )
    try:
        document = json.loads(output)
    except json.JSONDecodeError as error:
        raise PreflightError("container_inspect_json_invalid") from error
    if (
        not isinstance(document, list)
        or len(document) != 1
        or not isinstance(document[0], dict)
    ):
        raise PreflightError("container_inspect_shape_invalid")
    return document[0]


def _runtime_record(document: dict[str, Any], service: str) -> dict[str, Any]:
    state = document.get("State")
    config = document.get("Config")
    host = document.get("HostConfig")
    labels = config.get("Labels") if isinstance(config, dict) else None
    if (
        not isinstance(state, dict)
        or state.get("Running") is not True
        or not isinstance(config, dict)
        or not isinstance(host, dict)
        or not isinstance(labels, dict)
        or labels.get("com.docker.compose.project") != PROJECT
        or labels.get("com.docker.compose.service") != service
    ):
        raise PreflightError(f"{service}_runtime_contract_invalid")
    container_id = document.get("Id")
    image_id = document.get("Image")
    image_ref = config.get("Image")
    started_at = state.get("StartedAt")
    restart_count = document.get("RestartCount")
    if (
        not isinstance(container_id, str)
        or not container_id
        or not isinstance(image_id, str)
        or not image_id.startswith("sha256:")
        or not isinstance(image_ref, str)
        or not image_ref
        or not isinstance(started_at, str)
        or not isinstance(restart_count, int)
    ):
        raise PreflightError(f"{service}_runtime_identity_invalid")
    return {
        "container_id_sha256": _sha256_text(container_id),
        "image_id": image_id,
        "image_ref": image_ref,
        "started_at": started_at,
        "restart_count": restart_count,
        "network_mode": host.get("NetworkMode"),
    }


def _listener_count(runner: Runner, protocol: str, port: int) -> int:
    flag = "-ltn" if protocol == "tcp" else "-lun"
    output = _require_success(
        runner.run(
            ("ss", "-H", flag, "sport", "=", f":{port}")
        ),
        f"{protocol}_{port}_listener_probe",
    )
    return len([line for line in output.splitlines() if line.strip()])


_LEDGER_PROBE = r'''
import hashlib
import json
import sqlite3

path = "/var/lib/greenhouse-manager/manager/manager-state.sqlite3"
connection = sqlite3.connect("file:" + path + "?mode=ro", uri=True)
connection.row_factory = sqlite3.Row
connection.execute("PRAGMA query_only=ON")

tables = {
    row[0]
    for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
}
required = {"first_registration_attempts", "registrations"}
if not required.issubset(tables):
    raise RuntimeError("required_first_registration_tables_missing")

rows = connection.execute(
    """
    SELECT
        a.pairing_id,
        a.hardware_id_sha256,
        a.opened_at,
        a.expires_at,
        a.state,
        a.phase,
        a.cleanup_state,
        a.node_id,
        a.terminal_at,
        a.terminal_reason,
        CASE
            WHEN julianday(a.expires_at) <= julianday('now') THEN 1
            ELSE 0
        END AS expired_by_clock,
        (
            SELECT COUNT(*)
            FROM registrations AS r
            WHERE r.current_pairing_id = a.pairing_id
        ) AS registration_match_count
    FROM first_registration_attempts AS a
    ORDER BY a.opened_at, a.pairing_id
    """
).fetchall()

attempts = []
for row in rows:
    attempts.append(
        {
            "pairing_id_sha256": hashlib.sha256(
                str(row["pairing_id"]).encode("utf-8")
            ).hexdigest(),
            "hardware_id_sha256": str(row["hardware_id_sha256"]),
            "opened_at": str(row["opened_at"]),
            "expires_at": str(row["expires_at"]),
            "state": str(row["state"]),
            "phase": str(row["phase"]),
            "cleanup_state": str(row["cleanup_state"]),
            "node_id_present": row["node_id"] is not None,
            "terminal_at_present": row["terminal_at"] is not None,
            "terminal_reason": row["terminal_reason"],
            "expired_by_clock": bool(row["expired_by_clock"]),
            "registration_match_count": int(row["registration_match_count"]),
        }
    )

unresolved = connection.execute(
    """
    SELECT COUNT(*)
    FROM first_registration_attempts
    WHERE state = 'ACTIVE'
       OR (
            state IN ('EXPIRED', 'RESTART_INVALIDATED')
            AND cleanup_state != 'COMPLETE'
       )
    """
).fetchone()[0]
registration_count = connection.execute(
    "SELECT COUNT(*) FROM registrations"
).fetchone()[0]
connection.close()

print(
    json.dumps(
        {
            "attempt_count": len(attempts),
            "unresolved_count": int(unresolved),
            "registration_count": int(registration_count),
            "attempts": attempts,
        },
        sort_keys=True,
    )
)
'''


def _ledger_snapshot(runner: Runner, manager_id: str) -> dict[str, Any]:
    output = _require_success(
        runner.run(
            (
                "docker",
                "exec",
                manager_id,
                "python",
                "-c",
                _LEDGER_PROBE,
            ),
            timeout=30,
        ),
        "first_registration_ledger_probe",
    )
    try:
        document = json.loads(output)
    except json.JSONDecodeError as error:
        raise PreflightError("ledger_probe_json_invalid") from error
    if not isinstance(document, dict):
        raise PreflightError("ledger_probe_shape_invalid")
    return document


def _validate_expected_failed_attempt(
    ledger: dict[str, Any],
    *,
    expected_registration_count: int,
    expected_attempt_count: int,
    expected_unresolved_count: int,
) -> dict[str, Any]:
    if ledger.get("registration_count") != expected_registration_count:
        raise PreflightError("registration_count_drift")
    if ledger.get("attempt_count") != expected_attempt_count:
        raise PreflightError("attempt_count_drift")
    if ledger.get("unresolved_count") != expected_unresolved_count:
        raise PreflightError("unresolved_count_drift")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list) or len(attempts) != 1:
        raise PreflightError("failed_attempt_cardinality_invalid")
    attempt = attempts[0]
    if not isinstance(attempt, dict):
        raise PreflightError("failed_attempt_shape_invalid")
    if (
        attempt.get("state") != "ACTIVE"
        or attempt.get("phase") != "BOOTSTRAP_ACCEPTED"
        or attempt.get("cleanup_state") != "NONE"
        or attempt.get("expired_by_clock") is not True
        or attempt.get("node_id_present") is not False
        or attempt.get("terminal_at_present") is not False
        or attempt.get("terminal_reason") is not None
        or attempt.get("registration_match_count") != 0
    ):
        raise PreflightError("failed_attempt_state_drift")
    pairing_hash = attempt.get("pairing_id_sha256")
    hardware_hash = attempt.get("hardware_id_sha256")
    if (
        not isinstance(pairing_hash, str)
        or _SHA256.fullmatch(pairing_hash) is None
        or not isinstance(hardware_hash, str)
        or _SHA256.fullmatch(hardware_hash) is None
    ):
        raise PreflightError("failed_attempt_hash_binding_invalid")
    return attempt


def preflight(args: argparse.Namespace, runner: Runner | None = None) -> dict[str, Any]:
    runner = runner or Runner()

    if _systemctl(runner, "is-active", BROKER_UNIT) != "active":
        raise PreflightError("broker_unit_not_active")
    if _systemctl(runner, "is-active", SERVICES_UNIT) != "active":
        raise PreflightError("services_unit_not_active")
    if _systemctl(runner, "is-active", REGISTRATION_GUARD_UNIT) != "active":
        raise PreflightError("registration_guard_not_active")
    if _systemctl(runner, "is-enabled", BROKER_UNIT) != "enabled":
        raise PreflightError("broker_unit_not_enabled")
    if _systemctl(runner, "is-enabled", SERVICES_UNIT) != "enabled":
        raise PreflightError("services_unit_not_enabled")

    runtime: dict[str, dict[str, Any]] = {}
    ids: dict[str, str] = {}
    for service in ("broker", "manager", "homeassistant"):
        container_id = _service_container_id(runner, service)
        ids[service] = container_id
        runtime[service] = _runtime_record(
            _inspect_container(runner, container_id),
            service,
        )

    manager = runtime["manager"]
    if manager["image_ref"] != args.expected_current_manager_image:
        raise PreflightError("current_manager_image_ref_drift")
    if manager["network_mode"] != "host":
        raise PreflightError("manager_network_mode_drift")
    if runtime["homeassistant"]["network_mode"] != "host":
        raise PreflightError("homeassistant_network_mode_drift")
    for service in ("broker", "manager", "homeassistant"):
        if runtime[service]["restart_count"] != 0:
            raise PreflightError(f"{service}_restart_count_drift")

    listeners = {
        "tcp_8883": _listener_count(runner, "tcp", 8883),
        "tcp_47110": _listener_count(runner, "tcp", 47110),
        "udp_47111": _listener_count(runner, "udp", 47111),
        "tcp_47112": _listener_count(runner, "tcp", 47112),
    }
    if listeners["tcp_8883"] != 1:
        raise PreflightError("broker_8883_listener_count_invalid")
    if listeners["tcp_47110"] != 1:
        raise PreflightError("registration_47110_listener_count_invalid")
    if listeners["udp_47111"] != 1:
        raise PreflightError("discovery_47111_listener_count_invalid")
    if listeners["tcp_47112"] != 0:
        raise PreflightError("pairing_47112_must_be_closed")

    ledger = _ledger_snapshot(runner, ids["manager"])
    attempt = _validate_expected_failed_attempt(
        ledger,
        expected_registration_count=args.expected_registration_count,
        expected_attempt_count=args.expected_attempt_count,
        expected_unresolved_count=args.expected_unresolved_count,
    )

    target = {
        "source_head": _require_sha256(
            args.target_source_head,
            "target_source_head",
        ),
        "manager_image_id": _require_image_id(
            args.target_manager_image_id,
            "target_manager_image_id",
        ),
        "manager_tar_sha256": _require_sha256(
            args.target_manager_tar_sha256,
            "target_manager_tar_sha256",
        ),
        "artifact_id": args.artifact_id,
        "artifact_digest_sha256": _require_sha256(
            args.artifact_digest_sha256,
            "artifact_digest_sha256",
        ),
    }
    if not isinstance(target["artifact_id"], int) or target["artifact_id"] <= 0:
        raise PreflightError("artifact_id_invalid")

    return {
        "schema": "gh.n3w-r10-e03-manager-successor-refresh-preflight/1",
        "status": "PASS",
        "operation": "preflight",
        "mutation": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "current_manager_image_ref": manager["image_ref"],
        "runtime": runtime,
        "listeners": listeners,
        "ledger": {
            "registration_count": ledger["registration_count"],
            "attempt_count": ledger["attempt_count"],
            "unresolved_count": ledger["unresolved_count"],
            "failed_attempt": {
                "pairing_id_sha256": attempt["pairing_id_sha256"],
                "hardware_id_sha256": attempt["hardware_id_sha256"],
                "opened_at": attempt["opened_at"],
                "expires_at": attempt["expires_at"],
                "state": attempt["state"],
                "phase": attempt["phase"],
                "cleanup_state": attempt["cleanup_state"],
                "expired_by_clock": attempt["expired_by_clock"],
                "registration_match_count": attempt["registration_match_count"],
            },
        },
        "target": target,
        "refresh_contract": {
            "supervision_owner": SERVICES_UNIT,
            "manager_only_compose_recreate_forbidden": True,
            "broker_must_remain_running": True,
            "manager_and_homeassistant_restart_together": True,
            "manual_database_edit_forbidden": True,
            "startup_reconciliation_expected": True,
        },
        "t1_mutation": False,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-current-manager-image", default=EXPECTED_CURRENT_MANAGER_IMAGE)
    parser.add_argument("--expected-registration-count", type=int, default=1)
    parser.add_argument("--expected-attempt-count", type=int, default=1)
    parser.add_argument("--expected-unresolved-count", type=int, default=1)
    parser.add_argument("--target-source-head", required=True)
    parser.add_argument("--target-manager-image-id", required=True)
    parser.add_argument("--target-manager-tar-sha256", required=True)
    parser.add_argument("--artifact-id", required=True, type=int)
    parser.add_argument("--artifact-digest-sha256", required=True)
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    try:
        report = preflight(args)
    except (PreflightError, subprocess.SubprocessError, OSError) as error:
        print(
            json.dumps(
                {
                    "schema": "gh.n3w-r10-e03-manager-successor-refresh-preflight/1",
                    "status": "STOP",
                    "operation": "preflight",
                    "mutation": False,
                    "authorization_claimed": False,
                    "authorization_consumed": False,
                    "reason": f"{type(error).__name__}:{error}",
                    "t1_mutation": False,
                    "board_access": False,
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
