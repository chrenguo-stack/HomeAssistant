from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

SCHEMA = "gh.m2.t1-homeassistant-mqtt-migration-material-evidence/1"
_EXPECTED_UPDATE_SCHEMA = "gh.m2.homeassistant-mqtt-update/1"
_EXPECTED_RECONFIGURE_SCHEMA = "gh.m2.homeassistant-mqtt-reconfigure-values/1"
_EXPECTED_STATE_SCHEMA = "gh.m2.t1-broker-partial-activation-baseline/79"
_ALLOWED_BASENAMES = frozenset({"mqtt-update.json", "reconfigure-values.json"})
_PROTECTED_SERVICES = ("greenhouse-manager", "mosquitto", "homeassistant")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_MAX_FILES_VISITED = 50_000
_MAX_CANDIDATE_BYTES = 1024 * 1024
_MAX_CANDIDATES = 256


class HomeAssistantMigrationMaterialEvidenceError(RuntimeError):
    pass


class CommandRunner(Protocol):
    def run(
        self,
        command: Sequence[str],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]: ...


class SubprocessRunner:
    def run(
        self,
        command: Sequence[str],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        completed = subprocess.run(
            tuple(command),
            check=False,
            capture_output=True,
            text=True,
            input=input_text,
        )
        output = completed.stdout if completed.stdout else completed.stderr
        return completed.returncode, output


@dataclass(frozen=True, slots=True, repr=False)
class CandidateMaterial:
    username: str
    password: str
    client_id: str
    port: int
    schema: str
    broker: str | None

    def __repr__(self) -> str:
        return (
            "CandidateMaterial("
            f"username=<redacted>, password=<redacted>, client_id=<redacted>, "
            f"port={self.port!r}, schema={self.schema!r}, broker=<redacted>)"
        )

    @property
    def binding_fingerprint(self) -> str:
        return _fingerprint(
            "\0".join(
                (
                    self.username,
                    self.password,
                    self.client_id,
                    str(self.port),
                    self.broker or "",
                )
            )
        )


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_success(
    runner: CommandRunner,
    command: Sequence[str],
    message: str,
    *,
    input_text: str | None = None,
) -> str:
    code, output = runner.run(tuple(command), input_text=input_text)
    if code != 0:
        raise HomeAssistantMigrationMaterialEvidenceError(message)
    return output


def _inspect(runner: CommandRunner, name: str) -> dict[str, Any]:
    output = _require_success(
        runner,
        ("docker", "inspect", name),
        f"container metadata could not be read: {name}",
    )
    try:
        documents = json.loads(output)
    except json.JSONDecodeError as error:
        raise HomeAssistantMigrationMaterialEvidenceError(
            f"container metadata is invalid: {name}"
        ) from error
    if (
        not isinstance(documents, list)
        or len(documents) != 1
        or not isinstance(documents[0], dict)
    ):
        raise HomeAssistantMigrationMaterialEvidenceError(
            f"container metadata is incomplete: {name}"
        )
    return documents[0]


def _snapshot(runner: CommandRunner) -> dict[str, tuple[str, str, str, int, str]]:
    snapshot: dict[str, tuple[str, str, str, int, str]] = {}
    for name in _PROTECTED_SERVICES:
        document = _inspect(runner, name)
        state = document.get("State")
        if not isinstance(state, Mapping):
            raise HomeAssistantMigrationMaterialEvidenceError(
                f"container state is missing: {name}"
            )
        status = str(state.get("Status", ""))
        restart_count = int(document.get("RestartCount", 0))
        if status != "running" or restart_count != 0:
            raise HomeAssistantMigrationMaterialEvidenceError(
                f"protected service is not running with zero restarts: {name}"
            )
        snapshot[name] = (
            str(document.get("Id", "")),
            str(document.get("Image", "")),
            str(state.get("StartedAt", "")),
            restart_count,
            status,
        )
    return snapshot


def _active_lines(text: str) -> list[str]:
    return [
        raw.split("#", 1)[0].strip()
        for raw in text.splitlines()
        if raw.split("#", 1)[0].strip()
    ]


def _broker_config_and_state(
    runner: CommandRunner,
) -> tuple[dict[str, object], dict[str, Any], str, str]:
    config = _require_success(
        runner,
        (
            "docker",
            "exec",
            "mosquitto",
            "sh",
            "-c",
            "test -r /mosquitto/config/mosquitto.conf && "
            "cat /mosquitto/config/mosquitto.conf",
        ),
        "live Broker configuration could not be read",
    )
    state_raw = _require_success(
        runner,
        (
            "docker",
            "exec",
            "mosquitto",
            "sh",
            "-c",
            "test -r /mosquitto/data/dynamic-security.json && "
            "cat /mosquitto/data/dynamic-security.json",
        ),
        "Dynamic Security state could not be read",
    )
    mode_owner = _require_success(
        runner,
        (
            "docker",
            "exec",
            "mosquitto",
            "sh",
            "-c",
            "stat -c '%a:%u:%g:%h:%s' /mosquitto/data/dynamic-security.json && "
            "awk '/^Uid:|^Gid:/{print $2}' /proc/1/status | paste -sd ':' -",
        ),
        "Dynamic Security state metadata could not be read",
    ).splitlines()
    if len(mode_owner) != 2:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "Dynamic Security state metadata is incomplete"
        )
    file_parts = mode_owner[0].split(":")
    process_parts = mode_owner[1].split(":")
    if len(file_parts) != 5 or len(process_parts) != 2:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "Dynamic Security state metadata is invalid"
        )
    try:
        mode, uid, gid, links, size = (int(item) for item in file_parts)
        process_uid, process_gid = (int(item) for item in process_parts)
    except ValueError as error:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "Dynamic Security state metadata is invalid"
        ) from error
    try:
        state = json.loads(state_raw)
    except json.JSONDecodeError as error:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "Dynamic Security state is invalid JSON"
        ) from error
    if not isinstance(state, dict):
        raise HomeAssistantMigrationMaterialEvidenceError(
            "Dynamic Security state must be an object"
        )
    lines = _active_lines(config)
    anonymous = any(
        line.casefold() in {
            "allow_anonymous true",
            "allow_anonymous yes",
            "allow_anonymous 1",
            "allow_anonymous on",
        }
        for line in lines
    )
    plugin = [
        line
        for line in lines
        if line.startswith(("plugin ", "global_plugin "))
        and "dynamic_security" in line
    ]
    state_refs = [
        line
        for line in lines
        if line.startswith("plugin_opt_config_file ")
        and "dynamic-security.json" in line
    ]
    if not anonymous or len(plugin) != 1 or len(state_refs) != 1:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "Broker is not in the verified partial-activation compatibility state"
        )
    if (
        mode != 600
        or links != 1
        or size <= 0
        or uid != process_uid
        or gid != process_gid
    ):
        raise HomeAssistantMigrationMaterialEvidenceError(
            "Dynamic Security state ownership or privacy is invalid"
        )
    report = {
        "anonymous_enabled": True,
        "dynamic_security_configured": True,
        "plugin_directive_count": 1,
        "state_reference_count": 1,
        "state_private": True,
        "state_single_hardlink": True,
        "state_runtime_owner_bound": True,
        "config_sha256": _sha256_text(config),
        "state_sha256": _sha256_text(state_raw),
    }
    return report, state, report["config_sha256"], report["state_sha256"]


def _state_clients(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    clients = state.get("clients")
    if not isinstance(clients, list):
        raise HomeAssistantMigrationMaterialEvidenceError(
            "Dynamic Security client inventory is missing"
        )
    return [dict(item) for item in clients if isinstance(item, Mapping)]


def _role_names(client: Mapping[str, Any]) -> set[str]:
    roles = client.get("roles")
    if not isinstance(roles, list):
        return set()
    names: set[str] = set()
    for item in roles:
        if isinstance(item, Mapping) and isinstance(item.get("rolename"), str):
            names.add(str(item["rolename"]))
        elif isinstance(item, str):
            names.add(item)
    return names


def _validate_state_binding(
    state: Mapping[str, Any],
    *,
    system_id: str,
) -> dict[str, object]:
    expected_username = f"ghs_{system_id}_homeassistant"
    expected_client_id = f"gh-homeassistant-{system_id}"
    expected_role = f"gh-service-{system_id}-homeassistant"
    matches = [
        item
        for item in _state_clients(state)
        if item.get("username") == expected_username
    ]
    if len(matches) != 1:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "exactly one provisioned Home Assistant identity is required"
        )
    client = matches[0]
    if (
        client.get("clientid") != expected_client_id
        or client.get("disabled") is True
        or _role_names(client) != {expected_role}
    ):
        raise HomeAssistantMigrationMaterialEvidenceError(
            "provisioned Home Assistant identity binding has drifted"
        )
    return {
        "identity_provisioned": True,
        "identity_disabled": False,
        "username_fingerprint": _fingerprint(expected_username),
        "client_id_fingerprint": _fingerprint(expected_client_id),
        "role_fingerprint": _fingerprint(expected_role),
    }


def _private_candidate(path: Path) -> bool:
    try:
        metadata = path.lstat()
        parent = path.parent.lstat()
    except OSError:
        return False
    return bool(
        stat.S_ISREG(metadata.st_mode)
        and not path.is_symlink()
        and metadata.st_nlink == 1
        and stat.S_IMODE(metadata.st_mode) == 0o600
        and 0 < metadata.st_size <= _MAX_CANDIDATE_BYTES
        and stat.S_ISDIR(parent.st_mode)
        and not path.parent.is_symlink()
        and stat.S_IMODE(parent.st_mode) & 0o077 == 0
    )


def _normalize_material(document: Mapping[str, Any]) -> CandidateMaterial | None:
    schema = document.get("schema")
    if schema == _EXPECTED_UPDATE_SCHEMA:
        valid = (
            document.get("automatic_apply") is False
            and document.get("operation") == "update_existing_mqtt_config_entry"
            and document.get("preserve_discovery") is True
        )
        username = document.get("username")
        password = document.get("password")
        client_id = document.get("required_client_id")
        broker = None
    elif schema == _EXPECTED_RECONFIGURE_SCHEMA:
        valid = (
            document.get("official_config_flow_only") is True
            and document.get("preserve_discovery") is True
        )
        username = document.get("username")
        password = document.get("password")
        client_id = document.get("client_id")
        broker = document.get("broker")
    else:
        return None
    port = document.get("port")
    if (
        not valid
        or not isinstance(username, str)
        or not username
        or not isinstance(password, str)
        or not password
        or len(password) > 1024
        or not isinstance(client_id, str)
        or not client_id
        or not isinstance(port, int)
        or not 1 <= port <= 65535
        or (broker is not None and (not isinstance(broker, str) or not broker))
    ):
        return None
    return CandidateMaterial(
        username=username,
        password=password,
        client_id=client_id,
        port=port,
        schema=str(schema),
        broker=str(broker) if broker is not None else None,
    )


def _candidate_files(search_roots: Sequence[Path]) -> list[Path]:
    candidates: list[Path] = []
    visited = 0
    for raw_root in search_roots:
        root = raw_root.expanduser()
        if not root.is_absolute() or root.is_symlink() or not root.is_dir():
            continue
        for current, directory_names, file_names in os.walk(root, followlinks=False):
            directory_names[:] = sorted(
                name
                for name in directory_names
                if not (Path(current) / name).is_symlink()
            )
            visited += len(directory_names) + len(file_names)
            if visited > _MAX_FILES_VISITED:
                raise HomeAssistantMigrationMaterialEvidenceError(
                    "migration material search exceeded the bounded inventory"
                )
            for name in sorted(set(file_names) & _ALLOWED_BASENAMES):
                path = Path(current) / name
                if _private_candidate(path):
                    candidates.append(path)
                if len(candidates) > _MAX_CANDIDATES:
                    raise HomeAssistantMigrationMaterialEvidenceError(
                        "migration material candidate count exceeded the bound"
                    )
    return candidates


def _load_materials(paths: Sequence[Path]) -> tuple[list[CandidateMaterial], int]:
    materials: dict[str, CandidateMaterial] = {}
    valid_file_count = 0
    for path in paths:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(document, Mapping):
            continue
        material = _normalize_material(document)
        if material is None:
            continue
        valid_file_count += 1
        materials.setdefault(material.binding_fingerprint, material)
    return list(materials.values()), valid_file_count


def _temporary_client(
    runner: CommandRunner,
    material: CandidateMaterial,
    *,
    client_id: str,
    topic: str,
) -> tuple[int, str]:
    config = (
        "-h 127.0.0.1\n"
        f"-u {material.username}\n"
        f"-P {material.password}\n"
        f"-i {client_id}\n"
        "-V 5\n"
    )
    script = (
        "umask 077; f=/tmp/gh-m2-ha-material-$$.conf; "
        "trap 'rm -f \"$f\"' EXIT; cat > \"$f\"; "
        "mosquitto_sub -o \"$f\" -C 1 -W 5 -F '%p' -t \"$1\""
    )
    return runner.run(
        (
            "docker",
            "exec",
            "-i",
            "mosquitto",
            "sh",
            "-c",
            script,
            "sh",
            topic,
        ),
        input_text=config,
    )


def _validate_credentials(
    runner: CommandRunner,
    material: CandidateMaterial,
    *,
    expected_username: str,
    expected_client_id: str,
    expected_retained_topic: str,
    node_id: str,
) -> dict[str, object]:
    if material.username != expected_username or material.client_id != expected_client_id:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "candidate identity does not match the provisioned Home Assistant binding"
        )
    code, output = _temporary_client(
        runner,
        material,
        client_id=material.client_id,
        topic=expected_retained_topic,
    )
    if code != 0 or not output.strip():
        raise HomeAssistantMigrationMaterialEvidenceError(
            "candidate Home Assistant credentials could not read retained state"
        )
    try:
        retained = json.loads(output)
    except json.JSONDecodeError as error:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "candidate Home Assistant retained read returned invalid JSON"
        ) from error
    if not isinstance(retained, Mapping) or retained.get("node_id") != node_id:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "candidate Home Assistant retained identity validation failed"
        )
    wrong_id = f"{material.client_id}-wrong"
    wrong_code, wrong_output = _temporary_client(
        runner,
        material,
        client_id=wrong_id,
        topic=expected_retained_topic,
    )
    if wrong_code == 0 and bool(wrong_output.strip()):
        raise HomeAssistantMigrationMaterialEvidenceError(
            "Home Assistant client ID binding is not enforced"
        )
    return {
        "correct_identity_retained_readable": True,
        "wrong_client_id_rejected": True,
        "password_verified_without_output": True,
        "credential_binding_fingerprint": material.binding_fingerprint,
    }


def _networks(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    settings = document.get("NetworkSettings")
    raw = settings.get("Networks") if isinstance(settings, Mapping) else None
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(name): dict(value)
        for name, value in raw.items()
        if isinstance(value, Mapping)
    }


def _network_mode(document: Mapping[str, Any]) -> str:
    host = document.get("HostConfig")
    return str(host.get("NetworkMode", "")) if isinstance(host, Mapping) else ""


def _probe_from_homeassistant(
    runner: CommandRunner,
    host: str,
    port: int,
) -> bool:
    script = (
        "import socket,sys; "
        "s=socket.create_connection((sys.argv[1],int(sys.argv[2])),2); "
        "s.close(); print('ok')"
    )
    code, output = runner.run(
        (
            "docker",
            "exec",
            "homeassistant",
            "python3",
            "-c",
            script,
            host,
            str(port),
        )
    )
    return code == 0 and output.strip() == "ok"


def _target_topology(
    runner: CommandRunner,
    *,
    port: int,
) -> dict[str, object]:
    homeassistant = _inspect(runner, "homeassistant")
    broker = _inspect(runner, "mosquitto")
    ha_networks = _networks(homeassistant)
    broker_networks = _networks(broker)
    shared = set(ha_networks) & set(broker_networks)
    aliases: set[str] = set()
    for network in shared:
        raw = broker_networks[network].get("Aliases")
        if isinstance(raw, list):
            aliases.update(str(item) for item in raw if item)
    candidates = [
        (
            "docker_service_alias",
            "mosquitto",
            bool(shared and "mosquitto" in aliases),
        ),
        ("loopback", "127.0.0.1", _network_mode(homeassistant) == "host"),
    ]
    eligible: list[tuple[str, str]] = []
    results: list[dict[str, object]] = []
    for kind, host, topology_eligible in candidates:
        reachable = _probe_from_homeassistant(runner, host, port)
        accepted = topology_eligible and reachable
        results.append(
            {
                "kind": kind,
                "host_fingerprint": _fingerprint(host),
                "topology_eligible": topology_eligible,
                "tcp_connectable": reachable,
                "eligible": accepted,
            }
        )
        if accepted:
            eligible.append((kind, host))
    priority = {"docker_service_alias": 0, "loopback": 1}
    eligible.sort(key=lambda item: priority[item[0]])
    if not eligible:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "Home Assistant Broker target topology is unresolved"
        )
    kind, host = eligible[0]
    return {
        "candidate_count": len(results),
        "candidates": results,
        "selected_target_kind": kind,
        "selected_target_fingerprint": _fingerprint(host),
        "official_config_flow_only": True,
        "direct_storage_edit_forbidden": True,
    }


def build_homeassistant_mqtt_migration_material_evidence(
    *,
    system_id: str,
    node_id: str,
    expected_retained_topic: str,
    search_roots: Sequence[str | Path] = (
        "/tmp",
        "/opt/HomeAssistant",
        "/opt/greenhouse-secrets",
    ),
    runner: CommandRunner | None = None,
    repository_sha: str | None = None,
    manager_source_version: str | None = None,
) -> dict[str, object]:
    expected_topic = f"gh/v1/{system_id}/state/{node_id}/telemetry"
    if (
        not system_id
        or not node_id
        or expected_retained_topic != expected_topic
        or not search_roots
    ):
        raise ValueError("Home Assistant migration material evidence inputs are invalid")
    if repository_sha is not None and _GIT_SHA.fullmatch(repository_sha) is None:
        raise ValueError(
            "repository SHA must be a 40-character lowercase Git SHA"
        )

    command_runner = runner or SubprocessRunner()
    before_runtime = _snapshot(command_runner)
    broker, state, before_config_sha, before_state_sha = _broker_config_and_state(
        command_runner
    )
    state_binding = _validate_state_binding(state, system_id=system_id)
    paths = _candidate_files(tuple(Path(item) for item in search_roots))
    materials, valid_file_count = _load_materials(paths)
    expected_username = f"ghs_{system_id}_homeassistant"
    expected_client_id = f"gh-homeassistant-{system_id}"
    exact = [
        item
        for item in materials
        if item.username == expected_username
        and item.client_id == expected_client_id
        and item.port == 1883
    ]
    if len(exact) != 1:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "exactly one unique Home Assistant credential binding is required"
        )
    selected = exact[0]
    credentials = _validate_credentials(
        command_runner,
        selected,
        expected_username=expected_username,
        expected_client_id=expected_client_id,
        expected_retained_topic=expected_retained_topic,
        node_id=node_id,
    )
    topology = _target_topology(command_runner, port=selected.port)

    after_runtime = _snapshot(command_runner)
    _broker_after, _state_after, after_config_sha, after_state_sha = (
        _broker_config_and_state(command_runner)
    )
    if before_runtime != after_runtime:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "a protected service changed during material evidence collection"
        )
    if before_config_sha != after_config_sha or before_state_sha != after_state_sha:
        raise HomeAssistantMigrationMaterialEvidenceError(
            "Broker configuration or Dynamic Security state changed during evidence collection"
        )

    blockers = [
        "explicit_operator_decision_required",
        "homeassistant_official_mqtt_ui_config_flow_pending",
        "homeassistant_postchange_runtime_verification_pending",
        "real_node_credential_delivery_unverified",
        "authenticated_observation_window_pending",
        "anonymous_closure_not_authorized",
    ]
    report: dict[str, object] = {
        "schema": SCHEMA,
        "status": "homeassistant_mqtt_migration_material_evidence_verified",
        "read_only": True,
        "material_evidence_verified": True,
        "broker": broker,
        "state_binding": state_binding,
        "material": {
            "private_candidate_file_count": len(paths),
            "valid_candidate_file_count": valid_file_count,
            "unique_credential_binding_count": len(materials),
            "exact_binding_count": len(exact),
            "selected_schema": selected.schema,
            "selected_binding_fingerprint": selected.binding_fingerprint,
            "secret_values_included": False,
            "source_paths_included": False,
        },
        "credential_probe": credentials,
        "target_topology": topology,
        "protected_services_stable": True,
        "broker_config_and_state_stable": True,
        "homeassistant_identity_provisioned": True,
        "homeassistant_identity_runtime_verified": False,
        "homeassistant_storage_read": False,
        "homeassistant_storage_written": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "activation_blockers": blockers,
        "operator_action_required": True,
        "operator_action_authorized": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "authorization_reused": False,
        "production_execution_invoked": False,
        "apply_enabled": False,
        "execution_enabled": False,
        "current_services_modified": False,
        "ready_for_homeassistant_official_reconfigure_handoff": True,
        "ready_for_live_apply": False,
        "ready_for_anonymous_closure": False,
        "repository_sha": repository_sha,
        "manager_source_version": manager_source_version,
        "secret_values_included": False,
        "source_paths_included": False,
        "path_values_redacted": True,
        "container_ids_included": False,
        "image_ids_included": False,
    }
    serialized = _canonical_json(report)
    forbidden = (
        selected.username,
        selected.password,
        selected.client_id,
        selected.broker or "",
    )
    if any(value and value in serialized for value in forbidden):
        raise HomeAssistantMigrationMaterialEvidenceError(
            "sanitized report contains credential or target material"
        )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify existing Home Assistant MQTT migration material against the "
            "live partially activated Broker without reading Home Assistant storage."
        )
    )
    parser.add_argument("--system-id", default="greenhouse")
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument("--search-root", action="append", default=None)
    parser.add_argument("--repository-sha")
    parser.add_argument("--manager-source-version")
    args = parser.parse_args(argv)
    roots = tuple(args.search_root or ("/tmp", "/opt/HomeAssistant", "/opt/greenhouse-secrets"))
    try:
        report = build_homeassistant_mqtt_migration_material_evidence(
            system_id=args.system_id,
            node_id=args.node_id,
            expected_retained_topic=args.expected_retained_topic,
            search_roots=roots,
            repository_sha=args.repository_sha,
            manager_source_version=args.manager_source_version,
        )
    except (
        HomeAssistantMigrationMaterialEvidenceError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(
            f"T1 Home Assistant MQTT migration material evidence failed: {error}",
            file=sys.stderr,
        )
        return 2
    print(_canonical_json(report))
    return 0 if report["material_evidence_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
