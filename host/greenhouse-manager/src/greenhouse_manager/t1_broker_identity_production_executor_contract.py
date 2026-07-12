from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from .dynsec_api import LEGACY_ANONYMOUS_GROUP
from .t1_broker_identity_activation_checks import (
    BrokerIdentityActivationCheckError,
    Verifier,
    read_json,
    validated_handoff,
)
from .t1_broker_identity_activation_handoff import (
    BrokerIdentityActivationHandoffError,
    verify_broker_identity_activation_handoff,
)
from .t1_migration_stage import MigrationStageError, verify_migration_stage
from .t1_shadow import (
    PLUGIN_CONFIG_LINE,
    PLUGIN_LINE,
    PLUGIN_PASSWORD_INIT_LINE,
)

SCHEMA = "gh.m2.t1-broker-identity-production-executor-contract/1"
StageVerifier = Callable[[str | Path], dict[str, Any]]

_REQUIRED_MATERIAL = (
    ("material/broker/dynsec-request.json", True),
    ("material/broker/mosquitto-plugin.conf", False),
    ("material/bootstrap/dynsec-password-init", True),
    ("material/bootstrap/admin-client.conf", True),
    ("material/provisioning/mosquitto-client.conf", True),
    ("material/homeassistant/mqtt-update.json", True),
)
_ALLOWED_REQUEST_COMMANDS = {
    "setDefaultACLAccess",
    "createRole",
    "createGroup",
    "setAnonymousGroup",
    "createClient",
}
_REQUIRED_REQUEST_COMMANDS = frozenset(_ALLOWED_REQUEST_COMMANDS)
_REQUIRED_DEFAULTS = {
    "publishClientSend": False,
    "publishClientReceive": False,
    "subscribe": False,
    "unsubscribe": True,
}
_REQUIRED_SEQUENCE = (
    "revalidate_handoff_stage_and_fresh_rollback",
    "revalidate_live_runtime_and_mount_bindings",
    "create_same_filesystem_private_staging_files",
    "fsync_staged_broker_configuration_and_bootstrap_secret",
    "atomically_replace_only_broker_configuration_targets",
    "restart_only_mosquitto",
    "wait_for_dynamic_security_state",
    "apply_exact_bound_dynamic_security_request",
    "verify_provisioning_identity",
    "delete_bootstrap_admin",
    "run_read_only_postactivation_audit",
    "handoff_homeassistant_to_official_mqtt_ui_config_flow",
    "retain_fresh_rollback_until_authenticated_stability_gate",
)
_ALLOWED_TARGETS = (
    "/mosquitto/config/mosquitto.conf",
    "/mosquitto/config/dynsec-password-init",
    "/mosquitto/data/dynamic-security.json",
)
_FORBIDDEN_TARGETS = (
    "/config/.storage",
    "/opt/HomeAssistant/infra/compose/t1/docker-compose.yml",
    "/opt/HomeAssistant/infra/compose/t1/.env",
    "/opt/greenhouse-secrets/mqtt/node",
    "/opt/greenhouse-secrets/mqtt/homeassistant",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class BrokerIdentityProductionExecutorContractError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_document(document: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(document).encode("utf-8")).hexdigest()


def _safe_relative(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise BrokerIdentityProductionExecutorContractError(f"{label} path is missing")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise BrokerIdentityProductionExecutorContractError(f"{label} path is unsafe")
    return path


def _private_file(path: Path, label: str) -> None:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityProductionExecutorContractError(
            f"{label} is missing, unsafe, or not mode 0600"
        )


def _active_lines(path: Path) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _validate_plugin_contract(path: Path) -> None:
    if _active_lines(path) != (
        PLUGIN_LINE,
        PLUGIN_CONFIG_LINE,
        PLUGIN_PASSWORD_INIT_LINE,
    ):
        raise BrokerIdentityProductionExecutorContractError(
            "Broker plugin material does not match the canonical Dynamic Security contract"
        )


def _validate_default_acl(command: dict[str, Any]) -> None:
    raw = command.get("acls")
    if not isinstance(raw, list):
        raise BrokerIdentityProductionExecutorContractError(
            "Dynamic Security default ACL command is incomplete"
        )
    actual: dict[str, bool] = {}
    for item in raw:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("acltype"), str)
            or not isinstance(item.get("allow"), bool)
        ):
            raise BrokerIdentityProductionExecutorContractError(
                "Dynamic Security default ACL entry is invalid"
            )
        acl_type = str(item["acltype"])
        if acl_type in actual:
            raise BrokerIdentityProductionExecutorContractError(
                "Dynamic Security default ACL entry is duplicated"
            )
        actual[acl_type] = bool(item["allow"])
    if actual != _REQUIRED_DEFAULTS:
        raise BrokerIdentityProductionExecutorContractError(
            "Dynamic Security default ACL baseline has drifted"
        )


def _validate_request(path: Path) -> dict[str, object]:
    request = read_json(path, "Dynamic Security request")
    raw_commands = request.get("commands")
    if not isinstance(raw_commands, list) or not raw_commands:
        raise BrokerIdentityProductionExecutorContractError(
            "Dynamic Security request is empty or invalid"
        )

    commands: list[dict[str, Any]] = []
    names: list[str] = []
    for item in raw_commands:
        if not isinstance(item, dict) or not isinstance(item.get("command"), str):
            raise BrokerIdentityProductionExecutorContractError(
                "Dynamic Security request contains an invalid command"
            )
        name = str(item["command"])
        if name not in _ALLOWED_REQUEST_COMMANDS:
            raise BrokerIdentityProductionExecutorContractError(
                f"Dynamic Security request contains a forbidden command: {name}"
            )
        commands.append(item)
        names.append(name)

    if not _REQUIRED_REQUEST_COMMANDS.issubset(names):
        raise BrokerIdentityProductionExecutorContractError(
            "Dynamic Security request is missing required migration commands"
        )

    defaults = [item for item in commands if item["command"] == "setDefaultACLAccess"]
    if len(defaults) != 1:
        raise BrokerIdentityProductionExecutorContractError(
            "Dynamic Security request must contain one default ACL baseline"
        )
    _validate_default_acl(defaults[0])

    anonymous = [item for item in commands if item["command"] == "setAnonymousGroup"]
    if (
        len(anonymous) != 1
        or anonymous[0].get("groupname") != LEGACY_ANONYMOUS_GROUP
    ):
        raise BrokerIdentityProductionExecutorContractError(
            "Dynamic Security request does not preserve the canonical anonymous group"
        )

    clients = [item for item in commands if item["command"] == "createClient"]
    if len(clients) < 4:
        raise BrokerIdentityProductionExecutorContractError(
            "Dynamic Security request is missing required service or node clients"
        )
    usernames: set[str] = set()
    client_ids: set[str] = set()
    for item in clients:
        username = item.get("username")
        password = item.get("password")
        client_id = item.get("clientid")
        roles = item.get("roles")
        if not all(isinstance(value, str) and value for value in (username, password, client_id)):
            raise BrokerIdentityProductionExecutorContractError(
                "Dynamic Security client command is incomplete"
            )
        if username in usernames or client_id in client_ids:
            raise BrokerIdentityProductionExecutorContractError(
                "Dynamic Security client identity is duplicated"
            )
        if not isinstance(roles, list) or not roles:
            raise BrokerIdentityProductionExecutorContractError(
                "Dynamic Security client role binding is missing"
            )
        usernames.add(username)
        client_ids.add(client_id)

    return {
        "sha256": _sha256_path(path),
        "command_count": len(commands),
        "command_types": sorted(set(names)),
        "client_count": len(clients),
        "default_acl_deny_by_default": True,
        "anonymous_group_preserved": True,
    }


def build_production_executor_contract(
    handoff_directory: str | Path,
    stage_directory: str | Path,
    *,
    handoff_verifier: Verifier = verify_broker_identity_activation_handoff,
    stage_verifier: StageVerifier = verify_migration_stage,
) -> dict[str, object]:
    root = Path(handoff_directory).expanduser().resolve()
    stage = Path(stage_directory).expanduser().resolve()
    if (
        not root.is_dir()
        or root.is_symlink()
        or not stage.is_dir()
        or stage.is_symlink()
    ):
        raise BrokerIdentityProductionExecutorContractError(
            "production executor contract source directory is unsafe"
        )

    manifest, _plan = validated_handoff(root, handoff_verifier)
    stage_manifest = stage_verifier(stage)
    if (
        stage_manifest.get("activation_enabled") is not False
        or stage_manifest.get("current_services_modified") is not False
        or stage_manifest.get("active_paths_modified") is not False
    ):
        raise BrokerIdentityProductionExecutorContractError(
            "migration stage is not an inactive source"
        )

    stage_record = manifest.get("stage")
    if not isinstance(stage_record, dict):
        raise BrokerIdentityProductionExecutorContractError(
            "activation handoff stage binding is missing"
        )
    stage_manifest_path = stage / "stage-manifest.json"
    _private_file(stage_manifest_path, "stage manifest")
    stage_sha = _sha256_path(stage_manifest_path)
    broker_sha = stage_record.get("broker_config_sha256")
    if (
        stage_record.get("name") != stage.name
        or stage_record.get("manifest_sha256") != stage_sha
        or not isinstance(broker_sha, str)
        or _SHA256.fullmatch(broker_sha) is None
    ):
        raise BrokerIdentityProductionExecutorContractError(
            "activation handoff stage or Broker binding has drifted"
        )

    fresh = manifest.get("fresh_rollback")
    if not isinstance(fresh, dict):
        raise BrokerIdentityProductionExecutorContractError(
            "fresh rollback record is missing"
        )
    rollback_relative = _safe_relative(fresh.get("path"), "fresh rollback")
    rollback = root.joinpath(*rollback_relative.parts)
    _private_file(rollback, "fresh rollback archive")
    rollback_sha = _sha256_path(rollback)
    if fresh.get("sha256") != rollback_sha:
        raise BrokerIdentityProductionExecutorContractError(
            "fresh rollback fingerprint has drifted"
        )

    material_bindings: list[dict[str, object]] = []
    for relative, secret in _REQUIRED_MATERIAL:
        path = root / relative
        _private_file(path, f"activation handoff material {relative}")
        material_bindings.append(
            {
                "path": relative,
                "sha256": _sha256_path(path),
                "contains_secret": secret,
            }
        )

    _validate_plugin_contract(root / "material/broker/mosquitto-plugin.conf")
    request = _validate_request(root / "material/broker/dynsec-request.json")

    contract: dict[str, object] = {
        "schema": SCHEMA,
        "handoff": root.name,
        "stage": stage.name,
        "source_binding": {
            "stage_manifest_sha256": stage_sha,
            "baseline_broker_config_sha256": broker_sha,
        },
        "fresh_rollback": {
            "archive": rollback.name,
            "sha256": rollback_sha,
            "verified": True,
            "must_remain_available_until_stability_gate": True,
        },
        "material_bindings": material_bindings,
        "dynamic_security_request": request,
        "mutation_scope": {
            "container": "mosquitto",
            "restart_services": ["mosquitto"],
            "allowed_container_targets": list(_ALLOWED_TARGETS),
            "forbidden_targets": list(_FORBIDDEN_TARGETS),
            "same_filesystem_atomic_replace_required": True,
            "file_and_directory_fsync_required": True,
            "fresh_rollback_required_before_mutation": True,
            "compose_recreate_forbidden": True,
            "homeassistant_restart_forbidden": True,
            "manager_restart_forbidden": True,
        },
        "required_sequence": list(_REQUIRED_SEQUENCE),
        "rollback_contract": {
            "mandatory_after_mutation_entry_failure": True,
            "restore_complete_snapshot_inventory": True,
            "remove_dynamic_security_state": True,
            "restart_only_mosquitto": True,
            "verify_anonymous_retained_state": True,
            "rollback_failure_is_terminal": True,
        },
        "homeassistant_contract": {
            "mode": "official_mqtt_ui_config_flow",
            "automatic_storage_write_forbidden": True,
            "automatic_reconfigure_forbidden": True,
        },
        "node_credential_delivery_contract": {
            "real_device_path_verified": False,
            "automatic_write_forbidden": True,
            "blocks_anonymous_closure": True,
        },
        "contract_review_complete": True,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    contract["contract_sha256"] = _sha256_document(contract)
    return contract


def verify_production_executor_contract(
    contract: dict[str, object],
) -> dict[str, object]:
    if contract.get("schema") != SCHEMA:
        raise BrokerIdentityProductionExecutorContractError(
            "production executor contract schema is invalid"
        )
    digest = contract.get("contract_sha256")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise BrokerIdentityProductionExecutorContractError(
            "production executor contract fingerprint is invalid"
        )
    unsigned = dict(contract)
    unsigned.pop("contract_sha256", None)
    if _sha256_document(unsigned) != digest:
        raise BrokerIdentityProductionExecutorContractError(
            "production executor contract fingerprint does not match"
        )

    required = {
        "contract_review_complete": True,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if contract.get(field) != expected:
            raise BrokerIdentityProductionExecutorContractError(
                f"production executor contract safety flag failed: {field}"
            )

    scope = contract.get("mutation_scope")
    if not isinstance(scope, dict):
        raise BrokerIdentityProductionExecutorContractError(
            "production executor mutation scope is missing"
        )
    if (
        scope.get("container") != "mosquitto"
        or scope.get("restart_services") != ["mosquitto"]
        or scope.get("allowed_container_targets") != list(_ALLOWED_TARGETS)
        or scope.get("forbidden_targets") != list(_FORBIDDEN_TARGETS)
        or scope.get("compose_recreate_forbidden") is not True
        or scope.get("homeassistant_restart_forbidden") is not True
        or scope.get("manager_restart_forbidden") is not True
    ):
        raise BrokerIdentityProductionExecutorContractError(
            "production executor mutation scope has drifted"
        )
    if contract.get("required_sequence") != list(_REQUIRED_SEQUENCE):
        raise BrokerIdentityProductionExecutorContractError(
            "production executor sequence has drifted"
        )
    return {
        "schema": SCHEMA,
        "contract_sha256": digest,
        "verified": True,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "current_services_modified": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only production executor contract from a verified "
            "Broker activation handoff and inactive migration stage."
        )
    )
    parser.add_argument("handoff_directory")
    parser.add_argument("stage_directory")
    args = parser.parse_args(argv)
    try:
        result = build_production_executor_contract(
            args.handoff_directory,
            args.stage_directory,
        )
        verify_production_executor_contract(result)
    except (
        BrokerIdentityActivationCheckError,
        BrokerIdentityActivationHandoffError,
        BrokerIdentityProductionExecutorContractError,
        MigrationStageError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(
            f"T1 Broker production executor contract failed: {error}",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
