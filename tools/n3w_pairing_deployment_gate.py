#!/usr/bin/env python3
"""Validate the rendered N3-W Manager/Broker deployment contract."""

from __future__ import annotations

import argparse
import ipaddress
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

SCHEMA = "gh.n3w-pairing-deployment-gate/2"
DISCOVERY_PORT = 47111
BROKER_TLS_PORT = 8883
BROKER_IPV4_WILDCARD = "0.0.0.0"
EXPECTED_BROKER_NETWORKS = frozenset(
    {
        "n3wfc4-private",
        "n3wfc4-services",
    }
)


class DeploymentContractError(ValueError):
    """Rendered deployment does not preserve N3-W network portability."""


def _port_span(value: object) -> tuple[int, int] | None:
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, int):
        if 1 <= value <= 65535:
            return value, value
        return None

    if not isinstance(value, str):
        return None

    token = value.strip()
    if token.isdigit():
        port = int(token)
        if 1 <= port <= 65535:
            return port, port
        return None

    if token.count("-") != 1:
        return None

    start_text, end_text = token.split("-", 1)
    if not start_text.isdigit() or not end_text.isdigit():
        return None

    start = int(start_text)
    end = int(end_text)
    if not (1 <= start <= end <= 65535):
        return None
    return start, end


def _port_spec_includes(value: object, port: int) -> bool:
    span = _port_span(value)
    return span is not None and span[0] <= port <= span[1]


def _exact_port(value: object, port: int) -> bool:
    return _port_span(value) == (port, port)


def _broker_network_names(value: object) -> frozenset[str]:
    if isinstance(value, Mapping):
        raw_names = list(value.keys())
    elif isinstance(value, list):
        raw_names = list(value)
    else:
        raise DeploymentContractError("broker_networks_invalid")

    if (
        not raw_names
        or any(not isinstance(name, str) or not name for name in raw_names)
    ):
        raise DeploymentContractError("broker_networks_invalid")

    return frozenset(raw_names)


def _effective_broker_network_names(
    document: Mapping[object, object],
    network_keys: frozenset[str],
) -> dict[str, str]:
    networks = document.get("networks")
    if not isinstance(networks, Mapping):
        raise DeploymentContractError("compose_networks_invalid")

    effective_names: dict[str, str] = {}
    for key in network_keys:
        network = networks.get(key)
        if not isinstance(network, Mapping):
            raise DeploymentContractError(
                "broker_network_definition_missing"
            )
        name = network.get("name")
        if not isinstance(name, str) or not name:
            raise DeploymentContractError(
                "broker_effective_network_name_invalid"
            )
        effective_names[key] = name

    return effective_names


def validate_compose_document(
    document: object,
    *,
    service_name: str,
    broker_service_name: str,
    broker_loopback_ip: str,
) -> dict[str, object]:
    if not isinstance(document, Mapping):
        raise DeploymentContractError("compose_document_invalid")

    services = document.get("services")
    if not isinstance(services, Mapping):
        raise DeploymentContractError("compose_services_invalid")

    service = services.get(service_name)
    if not isinstance(service, Mapping):
        raise DeploymentContractError("pairing_service_missing")

    ports = service.get("ports", [])
    if not isinstance(ports, list):
        raise DeploymentContractError("pairing_ports_invalid")

    if service.get("network_mode") != "host":
        raise DeploymentContractError("discovery_udp_requires_host_network")
    if ports:
        raise DeploymentContractError("host_network_manager_ports_must_be_absent")

    try:
        loopback = ipaddress.ip_address(broker_loopback_ip)
    except ValueError as error:
        raise DeploymentContractError("broker_loopback_ip_invalid") from error
    if loopback.version != 4 or not loopback.is_loopback:
        raise DeploymentContractError("broker_loopback_ip_not_loopback")

    broker = services.get(broker_service_name)
    if not isinstance(broker, Mapping):
        raise DeploymentContractError("broker_service_missing")
    if broker.get("restart") != "no":
        raise DeploymentContractError("broker_restart_policy_not_no")

    broker_network_keys = _broker_network_names(broker.get("networks"))
    if broker_network_keys != EXPECTED_BROKER_NETWORKS:
        raise DeploymentContractError("broker_network_attachment_set_invalid")

    broker_networks = _effective_broker_network_names(
        document,
        broker_network_keys,
    )
    if any(
        broker_networks.get(key) != key
        for key in EXPECTED_BROKER_NETWORKS
    ):
        raise DeploymentContractError("broker_effective_network_set_invalid")

    broker_ports = broker.get("ports", [])
    if not isinstance(broker_ports, list):
        raise DeploymentContractError("broker_ports_invalid")

    broker_tls_publications: list[Mapping[object, object]] = []
    for item in broker_ports:
        if not isinstance(item, Mapping):
            raise DeploymentContractError("broker_port_entry_invalid")

        protocol = item.get("protocol", "tcp")
        if not isinstance(protocol, str):
            raise DeploymentContractError("broker_port_protocol_invalid")
        if protocol != "tcp":
            continue

        target = item.get("target")
        published = item.get("published")
        if _port_span(target) is None or _port_span(published) is None:
            raise DeploymentContractError("broker_port_spec_invalid")

        if (
            _port_spec_includes(target, BROKER_TLS_PORT)
            or _port_spec_includes(published, BROKER_TLS_PORT)
        ):
            broker_tls_publications.append(item)

    if len(broker_tls_publications) != 1:
        raise DeploymentContractError("broker_tls_publication_count_invalid")

    publication = broker_tls_publications[0]
    if (
        not _exact_port(publication.get("target"), BROKER_TLS_PORT)
        or not _exact_port(publication.get("published"), BROKER_TLS_PORT)
    ):
        raise DeploymentContractError("broker_tls_publication_port_mismatch")
    if publication.get("host_ip") != BROKER_IPV4_WILDCARD:
        raise DeploymentContractError("broker_wildcard_tls_publication_missing")

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "service": service_name,
        "network_mode": "host",
        "discovery_udp_port": DISCOVERY_PORT,
        "docker_udp_publication": False,
        "broker_service": broker_service_name,
        "broker_restart_policy": "no",
        "broker_tls_port": BROKER_TLS_PORT,
        "broker_ipv4_wildcard_publication": True,
        "broker_concrete_lan_ip_dependency": False,
        "broker_network_keys": sorted(broker_network_keys),
        "broker_networks": sorted(broker_networks.values()),
        "broker_network_attachment_set_verified": True,
        "broker_effective_network_names_verified": True,
        "broker_manager_loopback_ip": broker_loopback_ip,
        "broker_manager_loopback_runtime_probe_required": True,
        "broker_ingress_runtime_probe_required": True,
        "secret_values_included": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a docker compose config --format json document "
            "for host-network N3-W discovery and LAN-IP-independent Broker TLS."
        )
    )
    parser.add_argument(
        "--compose-json",
        default="-",
        help="rendered Compose JSON path, or '-' for stdin",
    )
    parser.add_argument(
        "--service",
        default="manager",
        help="Compose service that owns the N3-W pairing listener",
    )
    parser.add_argument(
        "--broker-service",
        default="broker",
        help="Compose service that owns the N3-W TLS broker listener",
    )
    parser.add_argument(
        "--broker-loopback-ip",
        required=True,
        help=(
            "IPv4 loopback endpoint reserved for the host-network Manager "
            "runtime connectivity probe"
        ),
    )
    return parser


def _read_document(source: str, *, stdin: TextIO) -> object:
    try:
        payload = (
            stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
        )
        return json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeploymentContractError("compose_json_invalid") from error


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    args = _parser().parse_args(argv)
    input_stream = stdin or sys.stdin
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr

    try:
        document = _read_document(args.compose_json, stdin=input_stream)
        result = validate_compose_document(
            document,
            service_name=args.service,
            broker_service_name=args.broker_service,
            broker_loopback_ip=args.broker_loopback_ip,
        )
    except DeploymentContractError as error:
        json.dump(
            {
                "schema": SCHEMA,
                "status": "FAIL",
                "reason": str(error),
                "secret_values_included": False,
            },
            error_output,
            separators=(",", ":"),
        )
        error_output.write("\n")
        return 3

    json.dump(result, output, separators=(",", ":"))
    output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
