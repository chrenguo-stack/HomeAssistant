from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from .dynsec_plan import NodeProvisioningPlan, build_node_provisioning_plan
from .t1_homeassistant_mqtt_migration_material_evidence import (
    CommandRunner,
    HomeAssistantMigrationMaterialEvidenceError,
    SubprocessRunner,
    _broker_config_and_state,
    _canonical_json,
    _snapshot,
)

SCHEMA = "gh.m2.t1-node-mqtt-migration-readiness-evidence/1"
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class NodeMigrationReadinessEvidenceError(RuntimeError):
    pass


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _role_names(client: Mapping[str, Any]) -> set[str]:
    roles = client.get("roles")
    if not isinstance(roles, list):
        return set()
    return {
        str(item["rolename"] if isinstance(item, Mapping) else item)
        for item in roles
        if (isinstance(item, Mapping) and isinstance(item.get("rolename"), str))
        or isinstance(item, str)
    }


def _acls(raw: object) -> tuple[tuple[str, str, bool, int], ...]:
    if not isinstance(raw, list):
        raise NodeMigrationReadinessEvidenceError("node role ACL list is missing")
    values: list[tuple[str, str, bool, int]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise NodeMigrationReadinessEvidenceError("node role ACL entry is invalid")
        value = (
            item.get("acltype"),
            item.get("topic"),
            item.get("allow"),
            item.get("priority"),
        )
        if not (
            isinstance(value[0], str)
            and isinstance(value[1], str)
            and isinstance(value[2], bool)
            and isinstance(value[3], int)
        ):
            raise NodeMigrationReadinessEvidenceError("node role ACL entry is invalid")
        values.append(value)  # type: ignore[arg-type]
    if len(values) != len(set(values)):
        raise NodeMigrationReadinessEvidenceError("node role ACL list contains duplicates")
    return tuple(sorted(values))


def _node_binding(
    state: Mapping[str, Any],
    *,
    system_id: str,
    node_id: str,
    generation: int,
) -> tuple[dict[str, object], NodeProvisioningPlan]:
    plan = build_node_provisioning_plan(
        system_id=system_id,
        node_id=node_id,
        generation=generation,
    )
    clients = state.get("clients")
    roles = state.get("roles")
    if not isinstance(clients, list) or not isinstance(roles, list):
        raise NodeMigrationReadinessEvidenceError("Dynamic Security inventory is incomplete")
    matched_clients = [
        item
        for item in clients
        if isinstance(item, Mapping) and item.get("username") == plan.username
    ]
    matched_roles = [
        item
        for item in roles
        if isinstance(item, Mapping) and item.get("rolename") == plan.role_name
    ]
    if len(matched_clients) != 1 or len(matched_roles) != 1:
        raise NodeMigrationReadinessEvidenceError("node identity or role is not unique")
    client = matched_clients[0]
    if (
        client.get("clientid") != plan.client_id
        or client.get("disabled") is True
        or _role_names(client) != {plan.role_name}
    ):
        raise NodeMigrationReadinessEvidenceError("node client binding has drifted")
    credential_fields = [
        key
        for key in ("encoded_password", "password")
        if key in client and client.get(key) not in (None, "", [], {})
    ]
    if len(credential_fields) != 1:
        raise NodeMigrationReadinessEvidenceError("node credential state is ambiguous")
    expected_acls = tuple(
        sorted((acl.acl_type, acl.topic, acl.allow, acl.priority) for acl in plan.acls)
    )
    if _acls(matched_roles[0].get("acls")) != expected_acls:
        raise NodeMigrationReadinessEvidenceError("node role ACLs have drifted")
    defaults = state.get("defaultACLAccess")
    expected_defaults = {
        "publishClientSend": plan.defaults.publish_client_send,
        "publishClientReceive": plan.defaults.publish_client_receive,
        "subscribe": plan.defaults.subscribe,
        "unsubscribe": plan.defaults.unsubscribe,
    }
    if not isinstance(defaults, Mapping) or any(
        defaults.get(key) is not value for key, value in expected_defaults.items()
    ):
        raise NodeMigrationReadinessEvidenceError("default ACL access has drifted")
    return (
        {
            "identity_preconfigured": True,
            "identity_disabled": False,
            "identity_exact": True,
            "role_exact": True,
            "acl_exact": True,
            "default_access_exact": True,
            "credential_material_present": True,
            "credential_state_field": credential_fields[0],
            "username_fingerprint": _fingerprint(plan.username),
            "client_id_fingerprint": _fingerprint(plan.client_id),
            "role_fingerprint": _fingerprint(plan.role_name),
            "acl_fingerprint": _fingerprint(_canonical_json(expected_acls)),
        },
        plan,
    )


def _message(runner: CommandRunner, topic: str, timeout_s: int) -> dict[str, Any]:
    if (
        not (topic.startswith("gh/") or topic.startswith("homeassistant/"))
        or "+" in topic
        or "#" in topic
    ):
        raise ValueError("MQTT evidence topic is not exact or is outside allowed namespaces")
    command = (
        "docker",
        "exec",
        "mosquitto",
        "mosquitto_sub",
        "-h",
        "127.0.0.1",
        "-V",
        "5",
        "-C",
        "1",
        "-W",
        str(timeout_s),
        "-F",
        "%p",
        "-t",
        topic,
    )
    code, output = runner.run(command)
    if code != 0:
        raise NodeMigrationReadinessEvidenceError("anonymous MQTT evidence read failed")
    try:
        result = json.loads(output)
    except json.JSONDecodeError as error:
        raise NodeMigrationReadinessEvidenceError("MQTT evidence is invalid JSON") from error
    if not isinstance(result, dict):
        raise NodeMigrationReadinessEvidenceError("MQTT evidence must be an object")
    return result


def _continuity(
    runner: CommandRunner,
    *,
    system_id: str,
    node_id: str,
    discovery_topic: str,
    timeout_s: int,
) -> dict[str, object]:
    state_topic = f"gh/v1/{system_id}/state/{node_id}/telemetry"
    availability_topic = f"gh/v1/{system_id}/state/{node_id}/availability"
    ingress_topic = f"gh/v1/{system_id}/ingress/node/{node_id}/telemetry"
    telemetry = _message(runner, state_topic, timeout_s)
    availability = _message(runner, availability_topic, timeout_s)
    discovery = _message(runner, discovery_topic, timeout_s)
    ingress = _message(runner, ingress_topic, timeout_s)
    if telemetry.get("node_id") != node_id or ingress.get("node_id") != node_id:
        raise NodeMigrationReadinessEvidenceError("telemetry identity continuity failed")
    if (
        availability.get("node_id") != node_id
        or availability.get("state") not in {"online", "unavailable"}
    ):
        raise NodeMigrationReadinessEvidenceError("availability continuity failed")
    device = discovery.get("device")
    identifiers = device.get("identifiers") if isinstance(device, Mapping) else None
    components = discovery.get("components")
    availability_entries = discovery.get("availability")
    if (
        discovery.get("state_topic") != state_topic
        or not isinstance(identifiers, list)
        or not any(isinstance(item, str) and node_id in item for item in identifiers)
        or not isinstance(components, Mapping)
        or not components
        or not isinstance(availability_entries, list)
        or not any(
            isinstance(item, Mapping) and item.get("topic") == availability_topic
            for item in availability_entries
        )
    ):
        raise NodeMigrationReadinessEvidenceError("Discovery binding has drifted")
    unique_ids = [
        item.get("unique_id") for item in components.values() if isinstance(item, Mapping)
    ]
    if len(unique_ids) != len(components) or any(
        not isinstance(item, str) or node_id not in item for item in unique_ids
    ):
        raise NodeMigrationReadinessEvidenceError("entity identity continuity failed")
    return {
        "canonical_retained_continuous": True,
        "availability_retained_continuous": True,
        "discovery_retained_continuous": True,
        "fresh_ingress_observed": True,
        "anonymous_observer_connection_used": True,
        "existing_entity_identity_continuous": True,
        "component_count": len(components),
        "availability_state": availability.get("state"),
    }


def _runtime(runner: CommandRunner, plan: NodeProvisioningPlan, tail: int) -> dict[str, object]:
    code, output = runner.run(("docker", "logs", "--tail", str(tail), "mosquitto"))
    if code != 0:
        raise NodeMigrationReadinessEvidenceError("Broker connection log could not be read")
    marker = f" as {plan.client_id} "
    matches = [
        line
        for line in output.splitlines()
        if "New client connected" in line and marker in line
    ]
    if not matches:
        raise NodeMigrationReadinessEvidenceError("node connection attribution is unavailable")
    username_match = re.search(r"\bu'([^']*)'", matches[-1])
    username = username_match.group(1) if username_match else None
    if username == plan.username:
        raise NodeMigrationReadinessEvidenceError(
            "node authenticated runtime was observed before authorization"
        )
    if username not in {None, "", "<unknown>", "unknown"}:
        raise NodeMigrationReadinessEvidenceError("node uses an unexpected MQTT username")
    return {
        "exact_client_id_connection_observed": True,
        "runtime_connection_anonymous": True,
        "authenticated_node_connection_observed": False,
        "connection_attribution_source": "broker_connection_log",
        "raw_log_included": False,
    }


def build_node_mqtt_migration_readiness_evidence(
    *,
    system_id: str,
    node_id: str,
    discovery_topic: str,
    generation: int = 1,
    mqtt_timeout_s: int = 35,
    broker_log_tail: int = 20_000,
    runner: CommandRunner | None = None,
    repository_sha: str | None = None,
    manager_source_version: str | None = None,
    expected_broker_config_sha256: str | None = None,
    expected_dynamic_security_state_sha256: str | None = None,
) -> dict[str, object]:
    if (
        not system_id
        or not node_id
        or discovery_topic != f"homeassistant/device/{node_id}/config"
        or not 1 <= generation <= 4_294_967_295
        or not 1 <= mqtt_timeout_s <= 120
        or not 100 <= broker_log_tail <= 100_000
    ):
        raise ValueError("node migration readiness evidence inputs are invalid")
    if repository_sha is not None and _GIT_SHA.fullmatch(repository_sha) is None:
        raise ValueError("repository SHA must be a 40-character lowercase Git SHA")
    expected_hashes = (
        expected_broker_config_sha256,
        expected_dynamic_security_state_sha256,
    )
    if any(value is not None for value in expected_hashes) and any(
        value is None or _SHA256.fullmatch(value) is None for value in expected_hashes
    ):
        raise ValueError("expected Broker baseline hashes must be paired SHA-256 values")
    command_runner = runner or SubprocessRunner()
    before = _snapshot(command_runner)
    broker, state, config_sha, state_sha = _broker_config_and_state(command_runner)
    if expected_broker_config_sha256 is not None and (
        config_sha != expected_broker_config_sha256
        or state_sha != expected_dynamic_security_state_sha256
    ):
        raise NodeMigrationReadinessEvidenceError("bound Broker baseline has drifted")
    identity, plan = _node_binding(
        state,
        system_id=system_id,
        node_id=node_id,
        generation=generation,
    )
    continuity = _continuity(
        command_runner,
        system_id=system_id,
        node_id=node_id,
        discovery_topic=discovery_topic,
        timeout_s=mqtt_timeout_s,
    )
    runtime = _runtime(command_runner, plan, broker_log_tail)
    after = _snapshot(command_runner)
    _broker_after, _state_after, after_config_sha, after_state_sha = (
        _broker_config_and_state(command_runner)
    )
    if before != after:
        raise NodeMigrationReadinessEvidenceError("a protected service changed")
    if config_sha != after_config_sha or state_sha != after_state_sha:
        raise NodeMigrationReadinessEvidenceError("Broker state changed during evidence")
    return {
        "schema": SCHEMA,
        "status": "node_mqtt_migration_readiness_evidence_verified",
        "read_only": True,
        "evidence_verified": True,
        "system_id": system_id,
        "node_id": node_id,
        "generation": generation,
        "broker": broker,
        "node_identity": identity,
        "continuity": continuity,
        "node_runtime": runtime,
        "protected_services_stable": True,
        "broker_config_and_state_stable": True,
        "baseline_binding": {
            "expected_hashes_supplied": expected_broker_config_sha256 is not None,
            "exact": True,
        },
        "node_runtime_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "homeassistant_storage_read": False,
        "homeassistant_storage_written": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "authorization_reused": False,
        "production_execution_invoked": False,
        "production_manager_upgraded": False,
        "current_services_modified": False,
        "activation_blockers": [
            "node_firmware_authenticated_mqtt_capability_unverified",
            "node_private_credential_delivery_path_unverified",
            "node_anonymous_fallback_rollback_unverified",
            "fresh_node_migration_authorization_not_created",
            "authenticated_node_observation_window_pending",
            "anonymous_closure_not_authorized",
        ],
        "ready_for_node_migration_design": True,
        "ready_for_node_credential_generation": False,
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect read-only node migration evidence")
    parser.add_argument("--system-id", default="greenhouse")
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--discovery-topic", required=True)
    parser.add_argument("--generation", type=int, default=1)
    parser.add_argument("--mqtt-timeout-seconds", type=int, default=35)
    parser.add_argument("--broker-log-tail", type=int, default=20_000)
    parser.add_argument("--repository-sha")
    parser.add_argument("--manager-source-version")
    parser.add_argument("--expected-broker-config-sha256")
    parser.add_argument("--expected-dynamic-security-state-sha256")
    args = parser.parse_args(argv)
    try:
        report = build_node_mqtt_migration_readiness_evidence(
            system_id=args.system_id,
            node_id=args.node_id,
            discovery_topic=args.discovery_topic,
            generation=args.generation,
            mqtt_timeout_s=args.mqtt_timeout_seconds,
            broker_log_tail=args.broker_log_tail,
            repository_sha=args.repository_sha,
            manager_source_version=args.manager_source_version,
            expected_broker_config_sha256=args.expected_broker_config_sha256,
            expected_dynamic_security_state_sha256=(
                args.expected_dynamic_security_state_sha256
            ),
        )
    except (
        HomeAssistantMigrationMaterialEvidenceError,
        NodeMigrationReadinessEvidenceError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"T1 node MQTT migration readiness evidence failed: {error}", file=sys.stderr)
        return 2
    print(_canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
