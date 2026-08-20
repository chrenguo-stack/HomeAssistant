#!/usr/bin/env python3
"""Validate the rendered Compose UDP publication used by N3-W discovery."""

from __future__ import annotations

import argparse
import ipaddress
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

SCHEMA = "gh.n3w-pairing-deployment-gate/1"
DISCOVERY_PORT = 47111
BROKER_TLS_PORT = 8883


class DeploymentContractError(ValueError):
    """Rendered deployment does not preserve limited-broadcast discovery."""


def _published_port(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


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
    if not loopback.is_loopback:
        raise DeploymentContractError("broker_loopback_ip_not_loopback")

    broker = services.get(broker_service_name)
    if not isinstance(broker, Mapping):
        raise DeploymentContractError("broker_service_missing")
    broker_ports = broker.get("ports", [])
    if not isinstance(broker_ports, list):
        raise DeploymentContractError("broker_ports_invalid")
    broker_loopback_matches = [
        item
        for item in broker_ports
        if isinstance(item, Mapping)
        and item.get("protocol") == "tcp"
        and _published_port(item.get("target")) == BROKER_TLS_PORT
        and _published_port(item.get("published")) == BROKER_TLS_PORT
        and item.get("host_ip") == broker_loopback_ip
    ]
    if len(broker_loopback_matches) != 1:
        raise DeploymentContractError("broker_resolved_loopback_publication_missing")

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "service": service_name,
        "network_mode": "host",
        "discovery_udp_port": DISCOVERY_PORT,
        "docker_udp_publication": False,
        "broker_service": broker_service_name,
        "broker_tls_port": BROKER_TLS_PORT,
        "broker_loopback_ip": broker_loopback_ip,
        "broker_resolved_loopback_publication": True,
        "secret_values_included": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a `docker compose config --format json` document "
            "for N3-W UDP discovery."
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
            "Loopback IPv4/IPv6 address resolved for the broker hostname from "
            "the host-network Manager runtime"
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
