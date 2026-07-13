from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .t1_manager_runtime_secret_ownership import (
    ManagerRuntimeSecretOwnershipError,
    verify_bound_runtime_identity,
)
from .t1_migration_readiness import CommandRunner

SCHEMA = "gh.m2.t1-manager-identity-preclaim-candidate/1"
_PASSWORD_TARGET = "/run/secrets/gh_manager_mqtt_password"


class ManagerPreclaimCandidateError(RuntimeError):
    pass


def _material_values(path: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ManagerPreclaimCandidateError(
            "manager candidate environment material is missing or unsafe"
        )
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key or key in values:
            raise ManagerPreclaimCandidateError(
                "manager candidate environment material is invalid"
            )
        values[key] = value
    if set(values) != {
        "GH_MQTT_USERNAME",
        "GH_MQTT_PASSWORD_FILE",
        "GH_MQTT_CLIENT_ID",
    } or values["GH_MQTT_PASSWORD_FILE"] != _PASSWORD_TARGET:
        raise ManagerPreclaimCandidateError(
            "manager candidate authentication environment is invalid"
        )
    return values


def _candidate_secret(
    source: Path,
    workspace: Path,
    *,
    uid: int,
    gid: int,
) -> Path:
    if not source.is_file() or source.is_symlink() or source.stat().st_mode & 0o077:
        raise ManagerPreclaimCandidateError(
            "manager candidate password material is missing or unsafe"
        )
    descriptor, temporary = tempfile.mkstemp(prefix=".candidate-password.", dir=workspace)
    path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(source.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(path, 0o600)
        if os.geteuid() == 0:
            os.chown(path, uid, gid)
        stat = path.stat()
        if stat.st_mode & 0o777 != 0o600 or stat.st_uid != uid or stat.st_gid != gid:
            raise ManagerPreclaimCandidateError(
                "manager candidate password ownership does not match runtime user"
            )
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def run_preclaim_candidate_probe(
    runtime_binding: Mapping[str, Any],
    material_environment: Path,
    material_password: Path,
    workspace: Path,
    *,
    runner: CommandRunner,
) -> dict[str, object]:
    container = runtime_binding.get("container")
    if not isinstance(container, dict):
        raise ManagerPreclaimCandidateError(
            "manager candidate runtime container binding is missing"
        )
    try:
        uid, gid = verify_bound_runtime_identity(
            runtime_binding,
            image_id=container.get("image_id"),
            user_spec=container.get("user_spec"),
        )
    except ManagerRuntimeSecretOwnershipError as error:
        raise ManagerPreclaimCandidateError(
            "manager candidate runtime ownership binding is invalid"
        ) from error
    image_id = runtime_binding["manager_runtime_image_id"]
    assert isinstance(image_id, str)
    _material_values(material_environment)
    candidate = _candidate_secret(material_password, workspace, uid=uid, gid=gid)
    try:
        command = (
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "32",
            "--user",
            f"{uid}:{gid}",
            "--env-file",
            str(material_environment),
            "--mount",
            f"type=bind,src={candidate},dst={_PASSWORD_TARGET},readonly",
            "--entrypoint",
            "greenhouse-manager",
            image_id,
            "--check-config",
        )
        code, output = runner.run(command)
        if code != 0:
            raise ManagerPreclaimCandidateError(
                "manager network-isolated candidate configuration probe failed"
            )
        try:
            report = json.loads(output)
        except json.JSONDecodeError as error:
            raise ManagerPreclaimCandidateError(
                "manager candidate configuration probe returned invalid JSON"
            ) from error
        required = {
            "configuration_valid": True,
            "mqtt_authentication_configured": True,
            "password_file_used": True,
            "inline_password_used": False,
            "network_attempted": False,
            "secret_values_included": False,
        }
        if not isinstance(report, dict) or any(
            report.get(field) is not expected for field, expected in required.items()
        ):
            raise ManagerPreclaimCandidateError(
                "manager candidate configuration checks are incomplete"
            )
    finally:
        candidate.unlink(missing_ok=True)
    return {
        "schema": SCHEMA,
        "preclaim_candidate_probe_passed": True,
        "runtime_uid_bound": True,
        "runtime_gid_bound": True,
        "runtime_image_bound": True,
        "password_mode_0600": True,
        "password_owned_by_runtime_user": True,
        "password_readable_by_runtime_user": True,
        "configuration_loaded": True,
        "network_none": True,
        "read_only_rootfs": True,
        "all_capabilities_dropped": True,
        "no_new_privileges": True,
        "inline_password_absent": True,
        "candidate_removed": True,
        "authorization_created": False,
        "authorization_claimed": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "node_credentials_delivered": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }


def validate_preclaim_candidate_report(report: Mapping[str, Any]) -> None:
    required = {
        "schema": SCHEMA,
        "preclaim_candidate_probe_passed": True,
        "runtime_uid_bound": True,
        "runtime_gid_bound": True,
        "runtime_image_bound": True,
        "password_mode_0600": True,
        "password_owned_by_runtime_user": True,
        "password_readable_by_runtime_user": True,
        "configuration_loaded": True,
        "network_none": True,
        "read_only_rootfs": True,
        "all_capabilities_dropped": True,
        "no_new_privileges": True,
        "inline_password_absent": True,
        "candidate_removed": True,
        "authorization_created": False,
        "authorization_claimed": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "node_credentials_delivered": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }
    if any(report.get(field) != expected for field, expected in required.items()):
        raise ManagerPreclaimCandidateError(
            "manager preclaim candidate report is missing required safety checks"
        )
