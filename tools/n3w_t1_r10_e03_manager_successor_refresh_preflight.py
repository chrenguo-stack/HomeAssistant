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
EXPECTED_SERVICES_EXECSTART = (
    "ExecStart=/usr/bin/docker compose "
    "--project-name ${N3WFC4_COMPOSE_PROJECT_NAME} "
    "--env-file ${N3WFC4_COMPOSE_ENV_FILE} "
    "-f ${N3WFC4_COMPOSE_FILE} --profile application up --no-deps "
    "--no-log-prefix --abort-on-container-exit manager homeassistant"
)
EXPECTED_SERVICES_EXECSTOP = (
    "ExecStop=/usr/bin/docker compose "
    "--project-name ${N3WFC4_COMPOSE_PROJECT_NAME} "
    "--env-file ${N3WFC4_COMPOSE_ENV_FILE} "
    "-f ${N3WFC4_COMPOSE_FILE} stop homeassistant manager"
)
MANAGER_DB = "/var/lib/greenhouse-manager/manager/manager-state.sqlite3"
CREDENTIAL_DB = "/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3"
EXPECTED_CURRENT_MANAGER_IMAGE = "local/greenhouse-manager:fresh-ff750b3801a2"
EXPECTED_FAILED_PAIRING_ID_SHA256 = (
    "9931c366d483abd3af6e1e3d903b82645542346dbd258975acd788998f0404dc"
)
EXPECTED_FAILED_HARDWARE_ID_SHA256 = (
    "3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55"
)
EXPECTED_TARGET_SOURCE_HEAD = "f8876fd87165df731d792690a8288867c3eeef55"
EXPECTED_TARGET_MANAGER_IMAGE = "local/greenhouse-manager:fresh-f8876fd87165"
EXPECTED_TARGET_MANAGER_IMAGE_ID = (
    "sha256:089153fa4bbc823a1357427083f23ef96933a119c6ae150c143b62d7b40859e4"
)
EXPECTED_TARGET_MANAGER_TAR_SHA256 = (
    "d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5"
)
EXPECTED_TARGET_ARTIFACT_ID = 12900601779
EXPECTED_TARGET_ARTIFACT_DIGEST_SHA256 = (
    "c94568f740b911eee0f4238207249b1e98f84748c17a902938ccc35293e4b183"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
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


def _require_git_sha(value: str, label: str) -> str:
    normalized = value.lower()
    if _GIT_SHA.fullmatch(normalized) is None:
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


def _services_supervision_contract(runner: Runner) -> dict[str, Any]:
    content = _require_success(
        runner.run(("systemctl", "cat", SERVICES_UNIT)),
        "services_unit_cat",
    )
    execstart = [
        line.strip()
        for line in content.splitlines()
        if line.strip().startswith("ExecStart=")
    ]
    execstop = [
        line.strip()
        for line in content.splitlines()
        if line.strip().startswith("ExecStop=")
    ]
    if len(execstart) != 1 or len(execstop) != 1:
        raise PreflightError("services_supervision_command_count_invalid")
    if "--force-recreate" in content:
        raise PreflightError("services_supervision_force_recreate_forbidden")
    if execstart[0] != EXPECTED_SERVICES_EXECSTART:
        raise PreflightError("services_supervision_execstart_drift")
    if execstop[0] != EXPECTED_SERVICES_EXECSTOP:
        raise PreflightError("services_supervision_execstop_drift")
    return {
        "unit": SERVICES_UNIT,
        "execstart_sha256": _sha256_text(execstart[0]),
        "execstop_sha256": _sha256_text(execstop[0]),
        "manager_homeassistant_joint_owner": True,
        "manager_only_recreate_forbidden": True,
    }


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
        or _IMAGE_ID.fullmatch(image_id.lower()) is None
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
required = {"first_registration_attempts", "registrations", "pairing_sessions"}
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

credential_path = "/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3"
credentials = sqlite3.connect(
    "file:" + credential_path + "?mode=ro",
    uri=True,
)
credentials.row_factory = sqlite3.Row
credentials.execute("PRAGMA query_only=ON")
credential_tables = {
    item[0]
    for item in credentials.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
}
if "credential_assignments" not in credential_tables:
    raise RuntimeError("credential_assignments_table_missing")

attempts = []
for row in rows:
    pairing_id = str(row["pairing_id"])
    session = connection.execute(
        """
        SELECT hardware_id, state, reason
        FROM pairing_sessions
        WHERE pairing_id = ?
        """,
        (pairing_id,),
    ).fetchone()
    if session is None:
        session_hardware_sha256 = None
        session_state = None
        current_pairing_matches = False
        registration_node_id_present = False
        pairing_credential_count = 0
        hardware_credential_history_count = 0
    else:
        hardware_id = str(session["hardware_id"])
        session_hardware_sha256 = hashlib.sha256(
            hardware_id.encode("utf-8")
        ).hexdigest()
        session_state = str(session["state"])
        registration = connection.execute(
            """
            SELECT current_pairing_id, node_id
            FROM registrations
            WHERE hardware_id = ?
            """,
            (hardware_id,),
        ).fetchone()
        current_pairing_matches = bool(
            registration is not None
            and registration["current_pairing_id"] == pairing_id
        )
        registration_node_id_present = bool(
            registration is not None and registration["node_id"] is not None
        )
        pairing_credential_count = int(
            credentials.execute(
                """
                SELECT COUNT(*)
                FROM credential_assignments
                WHERE pairing_id = ?
                """,
                (pairing_id,),
            ).fetchone()[0]
        )
        hardware_credential_history_count = int(
            credentials.execute(
                """
                SELECT COUNT(*)
                FROM credential_assignments
                WHERE hardware_id = ?
                """,
                (hardware_id,),
            ).fetchone()[0]
        )

    attempts.append(
        {
            "pairing_id_sha256": hashlib.sha256(
                pairing_id.encode("utf-8")
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
            "session_hardware_sha256": session_hardware_sha256,
            "session_state": session_state,
            "current_pairing_matches": current_pairing_matches,
            "registration_node_id_present": registration_node_id_present,
            "pairing_credential_count": pairing_credential_count,
            "hardware_credential_history_count": hardware_credential_history_count,
        }
    )
credentials.close()

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
registration_rows = connection.execute(
    """
    SELECT
        hardware_id,
        current_pairing_id,
        pairing_epoch,
        node_id,
        logical_location_id,
        repair_authorized,
        retired_at,
        retirement_reason
    FROM registrations
    ORDER BY hardware_id
    """
).fetchall()
registration_inventory = [
    [
        row["hardware_id"],
        row["current_pairing_id"],
        row["pairing_epoch"],
        row["node_id"],
        row["logical_location_id"],
        row["repair_authorized"],
        row["retired_at"],
        row["retirement_reason"],
    ]
    for row in registration_rows
]
registration_inventory_sha256 = hashlib.sha256(
    json.dumps(
        registration_inventory,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()
registration_count = len(registration_rows)
connection.close()

print(
    json.dumps(
        {
            "attempt_count": len(attempts),
            "unresolved_count": int(unresolved),
            "registration_count": int(registration_count),
            "registration_inventory_sha256": registration_inventory_sha256,
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
        or attempt.get("registration_match_count") != 1
    ):
        raise PreflightError("failed_attempt_state_drift")
    if (
        attempt.get("session_state") != "pending"
        or attempt.get("current_pairing_matches") is not True
        or attempt.get("registration_node_id_present") is not False
        or attempt.get("pairing_credential_count") != 0
        or attempt.get("hardware_credential_history_count") != 0
    ):
        raise PreflightError("failed_attempt_commit_classification_drift")
    pairing_hash = attempt.get("pairing_id_sha256")
    hardware_hash = attempt.get("hardware_id_sha256")
    if (
        not isinstance(pairing_hash, str)
        or _SHA256.fullmatch(pairing_hash) is None
        or not isinstance(hardware_hash, str)
        or _SHA256.fullmatch(hardware_hash) is None
    ):
        raise PreflightError("failed_attempt_hash_binding_invalid")
    if pairing_hash != EXPECTED_FAILED_PAIRING_ID_SHA256:
        raise PreflightError("failed_attempt_pairing_identity_drift")
    if hardware_hash != EXPECTED_FAILED_HARDWARE_ID_SHA256:
        raise PreflightError("failed_attempt_hardware_identity_drift")
    if attempt.get("session_hardware_sha256") != hardware_hash:
        raise PreflightError("failed_attempt_session_hardware_drift")
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
    supervision = _services_supervision_contract(runner)

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
    registration_inventory_sha256 = ledger.get(
        "registration_inventory_sha256"
    )
    if (
        not isinstance(registration_inventory_sha256, str)
        or _SHA256.fullmatch(registration_inventory_sha256) is None
    ):
        raise PreflightError("registration_inventory_hash_invalid")
    attempt = _validate_expected_failed_attempt(
        ledger,
        expected_registration_count=args.expected_registration_count,
        expected_attempt_count=args.expected_attempt_count,
        expected_unresolved_count=args.expected_unresolved_count,
    )

    target = {
        "source_head": _require_git_sha(
            args.target_source_head,
            "target_source_head",
        ),
        "manager_image": EXPECTED_TARGET_MANAGER_IMAGE,
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
    if target["source_head"] != EXPECTED_TARGET_SOURCE_HEAD:
        raise PreflightError("target_source_head_drift")
    if target["manager_image_id"] != EXPECTED_TARGET_MANAGER_IMAGE_ID:
        raise PreflightError("target_manager_image_id_drift")
    if target["manager_tar_sha256"] != EXPECTED_TARGET_MANAGER_TAR_SHA256:
        raise PreflightError("target_manager_tar_sha256_drift")
    if target["artifact_id"] != EXPECTED_TARGET_ARTIFACT_ID:
        raise PreflightError("target_artifact_id_drift")
    if (
        target["artifact_digest_sha256"]
        != EXPECTED_TARGET_ARTIFACT_DIGEST_SHA256
    ):
        raise PreflightError("target_artifact_digest_drift")

    return {
        "schema": "gh.n3w-r10-e03-manager-successor-refresh-preflight/1",
        "status": "PASS",
        "operation": "preflight",
        "mutation": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "current_manager_image_ref": manager["image_ref"],
        "services_supervision": supervision,
        "runtime": runtime,
        "listeners": listeners,
        "ledger": {
            "registration_count": ledger["registration_count"],
            "registration_inventory_sha256": registration_inventory_sha256,
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
                "session_hardware_sha256": attempt["session_hardware_sha256"],
                "session_state": attempt["session_state"],
                "current_pairing_matches": attempt["current_pairing_matches"],
                "registration_node_id_present": attempt[
                    "registration_node_id_present"
                ],
                "pairing_credential_count": attempt[
                    "pairing_credential_count"
                ],
                "hardware_credential_history_count": attempt[
                    "hardware_credential_history_count"
                ],
                "commit_classification": "DEFINITELY_NOT_COMMITTED",
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
