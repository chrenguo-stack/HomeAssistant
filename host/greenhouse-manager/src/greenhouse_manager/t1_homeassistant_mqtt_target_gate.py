from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .t1_client_migration_audit import (
    ClientMigrationAuditError,
    build_client_migration_audit,
)
from .t1_migration_readiness import CommandRunner, SubprocessRunner

GATE_SCHEMA = "gh.m2.t1-homeassistant-mqtt-target-gate/1"
_ALLOWED_KINDS = frozenset(
    {"docker_service_alias", "loopback", "host_address"}
)
_LABEL_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_PROBE_SCRIPT = """\
import json
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
result = {"dns_resolved": False, "tcp_connectable": False, "address_count": 0}
try:
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
except OSError:
    addresses = []
result["dns_resolved"] = bool(addresses)
result["address_count"] = len(addresses)
for family, socktype, proto, _canonname, sockaddr in addresses:
    connection = socket.socket(family, socktype, proto)
    connection.settimeout(2.0)
    try:
        connection.connect(sockaddr)
    except OSError:
        pass
    else:
        result["tcp_connectable"] = True
        connection.close()
        break
    connection.close()
print(json.dumps(result, separators=(",", ":")))
"""


class HomeAssistantMqttTargetGateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BrokerCandidate:
    label: str
    kind: str
    host: str

    def __post_init__(self) -> None:
        if not _LABEL_RE.fullmatch(self.label):
            raise ValueError("candidate label is invalid")
        if self.kind not in _ALLOWED_KINDS:
            raise ValueError("candidate kind is invalid")
        if not self.host or any(character.isspace() for character in self.host):
            raise ValueError("candidate host is invalid")


DEFAULT_CANDIDATES = (
    BrokerCandidate("docker_alias", "docker_service_alias", "mosquitto"),
    BrokerCandidate("loopback", "loopback", "127.0.0.1"),
)


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _require_success(
    runner: CommandRunner,
    command: Sequence[str],
    message: str,
) -> str:
    return_code, output = runner.run(tuple(command))
    if return_code != 0:
        raise HomeAssistantMqttTargetGateError(message)
    return output


def _docker_rows(runner: CommandRunner) -> list[dict[str, Any]]:
    output = _require_success(
        runner,
        ("docker", "ps", "-a", "--format", "{{json .}}"),
        "Docker container inventory could not be read",
    )
    rows: list[dict[str, Any]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise HomeAssistantMqttTargetGateError(
                "Docker container inventory contains invalid JSON"
            ) from error
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _discover_container(
    rows: Sequence[dict[str, Any]],
    *,
    exact_name: str,
    token: str,
) -> str:
    exact = [str(row.get("Names", "")) for row in rows if row.get("Names") == exact_name]
    if len(exact) == 1:
        return exact[0]
    candidates: list[str] = []
    normalized_token = token.lower().replace("-", "")
    for row in rows:
        name = str(row.get("Names", ""))
        image = str(row.get("Image", ""))
        normalized = f"{name} {image}".lower().replace("-", "")
        if normalized_token in normalized and name:
            candidates.append(name)
    unique = sorted(set(candidates))
    if len(unique) != 1:
        raise HomeAssistantMqttTargetGateError(
            f"exactly one {token} container must be discoverable"
        )
    return unique[0]


def _inspect_container(runner: CommandRunner, name: str) -> dict[str, Any]:
    output = _require_success(
        runner,
        ("docker", "inspect", name),
        "container metadata could not be read",
    )
    try:
        documents = json.loads(output)
    except json.JSONDecodeError as error:
        raise HomeAssistantMqttTargetGateError(
            "Docker inspect returned invalid JSON"
        ) from error
    if not isinstance(documents, list) or len(documents) != 1:
        raise HomeAssistantMqttTargetGateError(
            "Docker inspect returned an unexpected document"
        )
    document = documents[0]
    if not isinstance(document, dict):
        raise HomeAssistantMqttTargetGateError("Docker inspect document is invalid")
    return document


def _network_mode(document: dict[str, Any]) -> str:
    host_config = document.get("HostConfig")
    if not isinstance(host_config, dict):
        return ""
    return str(host_config.get("NetworkMode", ""))


def _networks(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    network_settings = document.get("NetworkSettings")
    raw_networks = (
        network_settings.get("Networks")
        if isinstance(network_settings, dict)
        else None
    )
    if not isinstance(raw_networks, dict):
        return {}
    return {
        str(name): value
        for name, value in raw_networks.items()
        if isinstance(value, dict)
    }


def _shared_network_aliases(
    homeassistant: dict[str, Any],
    broker: dict[str, Any],
) -> tuple[set[str], set[str]]:
    ha_networks = _networks(homeassistant)
    broker_networks = _networks(broker)
    shared = set(ha_networks) & set(broker_networks)
    aliases: set[str] = set()
    for network_name in shared:
        raw_aliases = broker_networks[network_name].get("Aliases")
        if isinstance(raw_aliases, list):
            aliases.update(str(alias) for alias in raw_aliases if alias)
    return shared, aliases


def _storage_sha256(runner: CommandRunner, homeassistant_name: str) -> str:
    output = _require_success(
        runner,
        (
            "docker",
            "exec",
            homeassistant_name,
            "sha256sum",
            "/config/.storage/core.config_entries",
        ),
        "Home Assistant config entry fingerprint could not be read",
    )
    digest = output.strip().split(maxsplit=1)[0]
    if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise HomeAssistantMqttTargetGateError(
            "Home Assistant config entry fingerprint is invalid"
        )
    return digest.lower()


def _probe_candidate(
    runner: CommandRunner,
    homeassistant_name: str,
    candidate: BrokerCandidate,
    port: int,
) -> dict[str, object]:
    output = _require_success(
        runner,
        (
            "docker",
            "exec",
            homeassistant_name,
            "python3",
            "-c",
            _PROBE_SCRIPT,
            candidate.host,
            str(port),
        ),
        "Home Assistant candidate reachability probe failed",
    )
    try:
        result = json.loads(output)
    except json.JSONDecodeError as error:
        raise HomeAssistantMqttTargetGateError(
            "Home Assistant candidate reachability probe returned invalid JSON"
        ) from error
    if not isinstance(result, dict):
        raise HomeAssistantMqttTargetGateError(
            "Home Assistant candidate reachability probe returned invalid data"
        )
    dns_resolved = result.get("dns_resolved") is True
    tcp_connectable = result.get("tcp_connectable") is True
    address_count = result.get("address_count")
    if not isinstance(address_count, int) or address_count < 0:
        raise HomeAssistantMqttTargetGateError(
            "Home Assistant candidate reachability count is invalid"
        )
    return {
        "label": candidate.label,
        "kind": candidate.kind,
        "host_fingerprint": _fingerprint(candidate.host),
        "dns_resolved": dns_resolved,
        "tcp_connectable": tcp_connectable,
        "address_count": address_count,
    }


def _validate_prior_audit(report: dict[str, object]) -> None:
    if (
        report.get("schema") != "gh.m2.t1-auth-client-migration-audit/1"
        or report.get("read_only") is not True
        or report.get("apply_enabled") is not False
        or report.get("current_services_modified") is not False
        or report.get("audit_complete") is not True
        or report.get("ready_for_live_apply") is not False
    ):
        raise HomeAssistantMqttTargetGateError(
            "M2.4f client migration audit is not a safe completed baseline"
        )


def build_homeassistant_mqtt_target_gate(
    stage_directory: str | Path,
    *,
    expected_retained_topic: str,
    candidates: Sequence[BrokerCandidate] = DEFAULT_CANDIDATES,
    port: int = 1883,
    allow_host_address_fallback: bool = False,
    compose_directory: str | Path = "/opt/HomeAssistant/infra/compose/t1",
    secret_root: str | Path = "/opt/greenhouse-secrets/mqtt",
    runner: CommandRunner | None = None,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")
    if not 1 <= port <= 65535:
        raise ValueError("candidate port is invalid")
    if not candidates:
        raise ValueError("at least one Broker candidate is required")
    labels = [candidate.label for candidate in candidates]
    kinds = [candidate.kind for candidate in candidates]
    if len(labels) != len(set(labels)) or len(kinds) != len(set(kinds)):
        raise ValueError("candidate labels and kinds must be unique")

    command_runner = runner or SubprocessRunner()
    prior_audit = build_client_migration_audit(
        stage_directory,
        expected_retained_topic=expected_retained_topic,
        expected_broker="__m2_target_not_selected__",
        compose_directory=compose_directory,
        secret_root=secret_root,
        runner=command_runner,
    )
    _validate_prior_audit(prior_audit)

    rows = _docker_rows(command_runner)
    homeassistant_name = _discover_container(
        rows,
        exact_name="homeassistant",
        token="homeassistant",
    )
    broker_name = _discover_container(
        rows,
        exact_name="mosquitto",
        token="mosquitto",
    )
    homeassistant = _inspect_container(command_runner, homeassistant_name)
    broker = _inspect_container(command_runner, broker_name)
    ha_host_network = _network_mode(homeassistant) == "host"
    broker_host_network = _network_mode(broker) == "host"
    shared_networks, broker_aliases = _shared_network_aliases(homeassistant, broker)

    results: list[dict[str, object]] = []
    eligible: list[dict[str, object]] = []
    for candidate in candidates:
        result = _probe_candidate(
            command_runner,
            homeassistant_name,
            candidate,
            port,
        )
        alias_declared = (
            candidate.kind == "docker_service_alias"
            and candidate.host in broker_aliases
            and bool(shared_networks)
        )
        topology_eligible = False
        if candidate.kind == "docker_service_alias":
            topology_eligible = alias_declared
        elif candidate.kind == "loopback":
            topology_eligible = ha_host_network
        elif candidate.kind == "host_address":
            topology_eligible = allow_host_address_fallback
        candidate_eligible = bool(
            topology_eligible
            and result["dns_resolved"] is True
            and result["tcp_connectable"] is True
        )
        result.update(
            {
                "declared_on_shared_network": alias_declared,
                "topology_eligible": topology_eligible,
                "eligible": candidate_eligible,
            }
        )
        results.append(result)
        if candidate_eligible:
            eligible.append(result)

    priority = {"docker_service_alias": 0, "loopback": 1, "host_address": 2}
    eligible.sort(key=lambda item: priority[str(item["kind"])])
    selected = eligible[0] if eligible else None
    target_model_ready = selected is not None

    homeassistant_report = prior_audit.get("homeassistant")
    if not isinstance(homeassistant_report, dict):
        raise HomeAssistantMqttTargetGateError(
            "M2.4f Home Assistant audit section is missing"
        )
    mqtt_entry = homeassistant_report.get("mqtt_config_entry")
    staged_material = homeassistant_report.get("staged_material")
    if not isinstance(mqtt_entry, dict) or not isinstance(staged_material, dict):
        raise HomeAssistantMqttTargetGateError(
            "M2.4f Home Assistant audit details are incomplete"
        )
    live_readiness = prior_audit.get("live_readiness")
    retained_readable = bool(
        isinstance(live_readiness, dict)
        and live_readiness.get("retained_topic_readable") is True
    )
    discovery_preserved = mqtt_entry.get("discovery_disabled") is False
    staged_complete = staged_material.get("staged_material_complete") is True
    storage_sha256 = _storage_sha256(command_runner, homeassistant_name)

    blockers = [
        "broker_identity_not_activated",
        "homeassistant_operator_reconfigure_required",
        "node_credential_delivery_path_unverified",
    ]
    if not target_model_ready:
        blockers.append("homeassistant_broker_target_unresolved")
    if not discovery_preserved:
        blockers.append("homeassistant_discovery_not_preserved")
    if not staged_complete:
        blockers.append("homeassistant_staged_material_incomplete")
    if not retained_readable:
        blockers.append("retained_baseline_unreadable")

    report: dict[str, object] = {
        "schema": GATE_SCHEMA,
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "prior_audit_complete": True,
        "network_topology": {
            "homeassistant_host_network": ha_host_network,
            "broker_host_network": broker_host_network,
            "shared_network_count": len(shared_networks),
            "broker_alias_count_on_shared_networks": len(broker_aliases),
        },
        "candidate_count": len(results),
        "candidates": results,
        "target_model_ready": target_model_ready,
        "selected_target_kind": selected.get("kind") if selected else None,
        "selected_target_fingerprint": (
            selected.get("host_fingerprint") if selected else None
        ),
        "homeassistant_official_reconfigure": {
            "official_config_flow_only": True,
            "direct_storage_edit_forbidden": True,
            "automatic_apply": False,
            "operator_action_required": True,
            "operator_action_authorized": False,
            "pre_change_entry_fingerprint": mqtt_entry.get(
                "entry_id_fingerprint"
            ),
            "pre_change_storage_sha256": storage_sha256,
            "staged_material_complete": staged_complete,
            "discovery_preserved": discovery_preserved,
            "retained_baseline_readable": retained_readable,
            "post_change_reaudit_required": True,
            "rollback_via_official_reconfigure_or_fresh_backup": True,
        },
        "activation_blockers": sorted(set(blockers)),
        "ready_for_operator_reconfigure": False,
        "ready_for_live_apply": False,
    }
    serialized = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    for candidate in candidates:
        if candidate.host in serialized:
            raise HomeAssistantMqttTargetGateError(
                "target gate report contains a raw Broker candidate"
            )
    return report


def _parse_candidate(value: str) -> BrokerCandidate:
    label, separator, remainder = value.partition("=")
    kind, separator_kind, host = remainder.partition(":")
    if not separator or not separator_kind:
        raise argparse.ArgumentTypeError(
            "candidate must use LABEL=KIND:HOST"
        )
    try:
        return BrokerCandidate(label=label, kind=kind, host=host)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit Home Assistant-to-Broker reachability and generate a disabled "
            "official MQTT reconfigure gate without modifying live services."
        )
    )
    parser.add_argument("stage_directory")
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument(
        "--candidate",
        action="append",
        type=_parse_candidate,
        default=None,
        help="repeatable LABEL=KIND:HOST candidate",
    )
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--allow-host-address-fallback", action="store_true")
    parser.add_argument(
        "--compose-directory",
        default="/opt/HomeAssistant/infra/compose/t1",
    )
    parser.add_argument(
        "--secret-root",
        default="/opt/greenhouse-secrets/mqtt",
    )
    args = parser.parse_args(argv)
    try:
        report = build_homeassistant_mqtt_target_gate(
            args.stage_directory,
            expected_retained_topic=args.expected_retained_topic,
            candidates=tuple(args.candidate or DEFAULT_CANDIDATES),
            port=args.port,
            allow_host_address_fallback=args.allow_host_address_fallback,
            compose_directory=args.compose_directory,
            secret_root=args.secret_root,
        )
    except (
        ClientMigrationAuditError,
        HomeAssistantMqttTargetGateError,
        OSError,
        ValueError,
    ) as error:
        print(f"T1 Home Assistant MQTT target gate failed: {error}", file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
