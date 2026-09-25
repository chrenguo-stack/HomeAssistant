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


class DeploymentContractError(ValueError):
    """Rendered deployment does not preserve N3-W network portability."""


def _published_port(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _ipv4_wildcard(value: object) -> bool:
    return value is None or value == BROKER_IPV4_WILDCARD


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

    broker_ports = broker.get("ports", [])
    if not isinstance(broker_ports, list):
        raise DeploymentContractError("broker_ports_invalid")

    broker_tls_publications = [
        item
        for item in broker_ports
        if isinstance(item, Mapping)
        and item.get("protocol") == "tcp"
        and (
            _published_port(item.get("target")) == BROKER_TLS_PORT
            or _published_port(item.get("published")) == BROKER_TLS_PORT
        )
    ]
    if len(broker_tls_publications) != 1:
        raise DeploymentContractError("broker_tls_publication_count_invalid")

    publication = broker_tls_publications[0]
    if (
        _published_port(publication.get("target")) != BROKER_TLS_PORT
        or _published_port(publication.get("published")) != BROKER_TLS_PORT
    ):
        raise DeploymentContractError("broker_tls_publication_port_mismatch")
    if not _ipv4_wildcard(publication.get("host_ip")):
        raise DeploymentContractError("broker_wildcard_tls_publication_missing")

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "service": service_name,
        "network_mode": "host",
        "discovery_udp_port": DISCOVERY_PORT,
        "docker_udp_publication": False,
        "broker_service": broker_service_name,
        "broker_tls_port": BROKER_TLS_PORT,
        "broker_ipv4_wildcard_publication": True,
        "broker_concrete_lan_ip_dependency": False,
        "broker_manager_loopback_ip": broker_loopback_ip,
        "broker_manager_loopback_runtime_probe_required": True,
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
