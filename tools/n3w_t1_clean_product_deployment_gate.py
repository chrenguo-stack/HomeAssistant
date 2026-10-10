#!/usr/bin/env python3
"""Validate the clean-product T1 Manager/Broker/Home Assistant Compose contract."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

SCHEMA = "gh.n3w-t1-clean-product-deployment-gate/1"
EXPECTED_COMPOSE_PROJECT_NAME = "n3wfc4"
EXPECTED_BROKER_NETWORKS = frozenset(
    {
        "n3wfc4-private",
        "n3wfc4-services",
    }
)
TLS_PORT = 8883
HA_MQTT_PORT = 1883
TLS_HOST_IP = "0.0.0.0"
HA_MQTT_HOST_IP = "127.0.0.1"
MANAGER_PASSWORD_TARGET = "/run/secrets/gh_manager_mqtt_password"
PROVISIONING_PASSWORD_TARGET = (
    "/run/secrets/gh_n3w_provisioning_mqtt_password"
)
HA_PASSWORD_TARGET = "/run/secrets/gh_homeassistant_mqtt_password"
HA_BOOTSTRAP_TARGET = "/run/n3w/ha-mqtt-bootstrap.json"


class DeploymentContractError(ValueError):
    """Rendered deployment does not match the clean-product security contract."""


def _port(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 65535 else None
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        return parsed if 1 <= parsed <= 65535 else None
    return None


def _services(document: Mapping[object, object]) -> Mapping[object, object]:
    services = document.get("services")
    if not isinstance(services, Mapping):
        raise DeploymentContractError("compose_services_invalid")
    return services


def _service(
    services: Mapping[object, object],
    name: str,
) -> Mapping[object, object]:
    value = services.get(name)
    if not isinstance(value, Mapping):
        raise DeploymentContractError(f"{name}_service_missing")
    return value


def _environment(
    service: Mapping[object, object],
) -> dict[str, str]:
    raw = service.get("environment", {})
    if isinstance(raw, Mapping):
        result: dict[str, str] = {}
        for key, value in raw.items():
            if not isinstance(key, str):
                raise DeploymentContractError("service_environment_invalid")
            if value is None:
                result[key] = ""
            elif isinstance(value, (str, int, float, bool)):
                result[key] = str(value)
            else:
                raise DeploymentContractError("service_environment_invalid")
        return result
    if isinstance(raw, list):
        result = {}
        for item in raw:
            if not isinstance(item, str):
                raise DeploymentContractError("service_environment_invalid")
            key, separator, value = item.partition("=")
            if not key:
                raise DeploymentContractError("service_environment_invalid")
            result[key] = value if separator else ""
        return result
    raise DeploymentContractError("service_environment_invalid")


def _mounts(service: Mapping[object, object]) -> list[Mapping[object, object]]:
    raw = service.get("volumes", [])
    if not isinstance(raw, list):
        raise DeploymentContractError("service_mounts_invalid")
    mounts: list[Mapping[object, object]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise DeploymentContractError("service_mount_entry_invalid")
        mounts.append(item)
    return mounts


def _require_readonly_bind(
    service: Mapping[object, object],
    target: str,
) -> None:
    matches = [
        item
        for item in _mounts(service)
        if item.get("target") == target
    ]
    if len(matches) != 1:
        raise DeploymentContractError("secret_mount_target_count_invalid")
    mount = matches[0]
    source = mount.get("source")
    if (
        mount.get("type") != "bind"
        or not isinstance(source, str)
        or not source
        or mount.get("read_only") is not True
    ):
        raise DeploymentContractError("secret_mount_contract_invalid")


def _require_host_network_no_ports(
    service: Mapping[object, object],
    label: str,
) -> None:
    if service.get("network_mode") != "host":
        raise DeploymentContractError(f"{label}_network_mode_invalid")
    ports = service.get("ports", [])
    if not isinstance(ports, list):
        raise DeploymentContractError(f"{label}_ports_invalid")
    if ports:
        raise DeploymentContractError(f"{label}_host_network_ports_must_be_absent")


def _broker_networks(
    document: Mapping[object, object],
    broker: Mapping[object, object],
) -> frozenset[str]:
    raw = broker.get("networks")
    if isinstance(raw, Mapping):
        keys = list(raw)
    elif isinstance(raw, list):
        keys = list(raw)
    else:
        raise DeploymentContractError("broker_networks_invalid")
    if any(not isinstance(item, str) or not item for item in keys):
        raise DeploymentContractError("broker_networks_invalid")
    network_keys = frozenset(keys)
    if network_keys != EXPECTED_BROKER_NETWORKS:
        raise DeploymentContractError("broker_network_attachment_set_invalid")

    definitions = document.get("networks")
    if not isinstance(definitions, Mapping):
        raise DeploymentContractError("compose_networks_invalid")
    for key in EXPECTED_BROKER_NETWORKS:
        definition = definitions.get(key)
        if (
            not isinstance(definition, Mapping)
            or definition.get("name") != key
        ):
            raise DeploymentContractError("broker_effective_network_name_invalid")
    return network_keys


def _port_publications(
    services: Mapping[object, object],
    port: int,
) -> list[tuple[str, Mapping[object, object]]]:
    matches: list[tuple[str, Mapping[object, object]]] = []
    for raw_name, raw_service in services.items():
        if not isinstance(raw_name, str) or not raw_name:
            raise DeploymentContractError("compose_service_name_invalid")
        if not isinstance(raw_service, Mapping):
            raise DeploymentContractError("compose_service_invalid")
        raw_ports = raw_service.get("ports", [])
        if not isinstance(raw_ports, list):
            raise DeploymentContractError("compose_service_ports_invalid")
        for item in raw_ports:
            if not isinstance(item, Mapping):
                raise DeploymentContractError("compose_port_entry_invalid")
            protocol = item.get("protocol", "tcp")
            if not isinstance(protocol, str):
                raise DeploymentContractError("compose_port_protocol_invalid")
            target = _port(item.get("target"))
            published = _port(item.get("published"))
            if target is None or published is None:
                raise DeploymentContractError("compose_port_spec_invalid")
            if protocol == "tcp" and (target == port or published == port):
                matches.append((raw_name, item))
    return matches


def _require_publication(
    services: Mapping[object, object],
    *,
    broker_name: str,
    port: int,
    host_ip: str,
) -> None:
    matches = _port_publications(services, port)
    if len(matches) != 1:
        raise DeploymentContractError(f"broker_{port}_publication_count_invalid")
    owner, publication = matches[0]
    if owner != broker_name:
        raise DeploymentContractError(f"broker_{port}_publication_owner_invalid")
    if (
        _port(publication.get("target")) != port
        or _port(publication.get("published")) != port
        or publication.get("protocol", "tcp") != "tcp"
        or publication.get("host_ip") != host_ip
    ):
        raise DeploymentContractError(f"broker_{port}_publication_invalid")


def validate_compose_document(
    document: object,
    *,
    manager_service_name: str = "manager",
    broker_service_name: str = "broker",
    homeassistant_service_name: str = "homeassistant",
) -> dict[str, object]:
    if not isinstance(document, Mapping):
        raise DeploymentContractError("compose_document_invalid")
    if document.get("name") != EXPECTED_COMPOSE_PROJECT_NAME:
        raise DeploymentContractError("compose_project_identity_invalid")

    services = _services(document)
    manager = _service(services, manager_service_name)
    broker = _service(services, broker_service_name)
    homeassistant = _service(services, homeassistant_service_name)

    _require_host_network_no_ports(manager, "manager")
    manager_environment = _environment(manager)
    if (
        manager_environment.get("GH_MQTT_PASSWORD_FILE")
        != MANAGER_PASSWORD_TARGET
        or manager_environment.get("GH_N3W_PROVISIONING_PASSWORD_FILE")
        != PROVISIONING_PASSWORD_TARGET
        or manager_environment.get("GH_MQTT_PASSWORD", "") != ""
    ):
        raise DeploymentContractError("manager_secret_environment_invalid")
    if MANAGER_PASSWORD_TARGET == PROVISIONING_PASSWORD_TARGET:
        raise DeploymentContractError("manager_secret_targets_not_distinct")
    _require_readonly_bind(manager, MANAGER_PASSWORD_TARGET)
    _require_readonly_bind(manager, PROVISIONING_PASSWORD_TARGET)

    _require_host_network_no_ports(homeassistant, "homeassistant")
    _require_readonly_bind(homeassistant, HA_PASSWORD_TARGET)
    _require_readonly_bind(homeassistant, HA_BOOTSTRAP_TARGET)

    if broker.get("restart") != "no":
        raise DeploymentContractError("broker_restart_policy_invalid")
    broker_networks = _broker_networks(document, broker)
    _require_publication(
        services,
        broker_name=broker_service_name,
        port=TLS_PORT,
        host_ip=TLS_HOST_IP,
    )
    _require_publication(
        services,
        broker_name=broker_service_name,
        port=HA_MQTT_PORT,
        host_ip=HA_MQTT_HOST_IP,
    )

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "compose_project_name": EXPECTED_COMPOSE_PROJECT_NAME,
        "manager_host_network": True,
        "manager_ports_absent": True,
        "manager_secret_file_count": 2,
        "manager_secret_targets_distinct": True,
        "homeassistant_host_network": True,
        "homeassistant_ports_absent": True,
        "homeassistant_password_mount_readonly": True,
        "homeassistant_bootstrap_mount_readonly": True,
        "broker_restart_policy": "no",
        "broker_networks": sorted(broker_networks),
        "broker_tls_publication": "ipv4_wildcard_8883",
        "broker_homeassistant_publication": "ipv4_loopback_1883",
        "host_8883_owner": broker_service_name,
        "host_1883_owner": broker_service_name,
        "host_1883_non_loopback_publication_count": 0,
        "secret_values_included": False,
    }


def _load_document(path: str) -> object:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(
        Path(path).read_text(encoding="utf-8")
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the rendered clean-product T1 Compose contract."
        )
    )
    parser.add_argument(
        "--compose-json",
        default="-",
        help="rendered Compose JSON path, or '-' for stdin",
    )
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
        document = _load_document(args.compose_json)
        report = validate_compose_document(document)
    except (DeploymentContractError, OSError, json.JSONDecodeError) as error:
        print(
            f"T1 clean-product deployment gate failed: {error}",
            file=error_output,
        )
        return 2
    json.dump(
        report,
        output,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
