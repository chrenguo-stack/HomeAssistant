from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_pairing_deployment_gate.py"


def load_tool():
    specification = importlib.util.spec_from_file_location(
        "n3w_pairing_deployment_gate",
        TOOL,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def rendered_compose(
    *,
    network_mode: str | None = "host",
    udp_host_ip: str | None = None,
    broker_loopback_ip: str = "127.0.1.1",
    broker_published_port: str = "8883",
) -> dict:
    manager: dict = {}
    if network_mode is not None:
        manager["network_mode"] = network_mode
    if udp_host_ip is not None:
        manager["ports"] = [
            {
                "host_ip": udp_host_ip,
                "mode": "ingress",
                "target": 47111,
                "published": "47111",
                "protocol": "udp",
            }
        ]
    return {
        "services": {
            "manager": manager,
            "broker": {
                "ports": [
                    {
                        "host_ip": broker_loopback_ip,
                        "mode": "ingress",
                        "target": 8883,
                        "published": broker_published_port,
                        "protocol": "tcp",
                    }
                ]
            },
        }
    }


def test_accepts_host_network_without_docker_udp_publication() -> None:
    tool = load_tool()

    result = tool.validate_compose_document(
        rendered_compose(),
        service_name="manager",
        broker_service_name="broker",
        broker_loopback_ip="127.0.1.1",
    )

    assert result["status"] == "PASS"
    assert result["network_mode"] == "host"
    assert result["docker_udp_publication"] is False
    assert result["broker_resolved_loopback_publication"] is True
    assert result["broker_loopback_ip"] == "127.0.1.1"
    assert result["secret_values_included"] is False


@pytest.mark.parametrize(
    "host_ip",
    ["192.0.2.10", "0.0.0.0", "127.0.0.1"],
)
def test_rejects_every_docker_udp_publication(host_ip: str) -> None:
    tool = load_tool()

    with pytest.raises(
        tool.DeploymentContractError,
        match="host_network_manager_ports_must_be_absent",
    ):
        tool.validate_compose_document(
            rendered_compose(
                network_mode="host",
                udp_host_ip=host_ip,
            ),
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_unrelated_tcp_publication_on_host_network_manager() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["manager"]["ports"] = [
        {
            "host_ip": "127.0.0.1",
            "target": 9090,
            "published": "9090",
            "protocol": "tcp",
        }
    ]

    with pytest.raises(
        tool.DeploymentContractError,
        match="host_network_manager_ports_must_be_absent",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


@pytest.mark.parametrize("network_mode", [None, "bridge"])
def test_rejects_non_host_network_without_udp_publication(
    network_mode: str | None,
) -> None:
    tool = load_tool()

    with pytest.raises(
        tool.DeploymentContractError,
        match="requires_host_network",
    ):
        tool.validate_compose_document(
            rendered_compose(network_mode=network_mode),
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_broker_publication_on_different_loopback_address() -> None:
    tool = load_tool()

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_resolved_loopback_publication_missing",
    ):
        tool.validate_compose_document(
            rendered_compose(broker_loopback_ip="127.0.0.1"),
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_broker_publication_with_wrong_published_port() -> None:
    tool = load_tool()

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_resolved_loopback_publication_missing",
    ):
        tool.validate_compose_document(
            rendered_compose(broker_published_port="1883"),
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_non_loopback_broker_address() -> None:
    tool = load_tool()

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_loopback_ip_not_loopback",
    ):
        tool.validate_compose_document(
            rendered_compose(broker_loopback_ip="192.0.2.10"),
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="192.0.2.10",
        )


def test_cli_failure_is_structured_and_secret_free() -> None:
    tool = load_tool()
    output = io.StringIO()

    status = tool.main(
        [
            "--service",
            "manager",
            "--broker-service",
            "broker",
            "--broker-loopback-ip",
            "127.0.1.1",
        ],
        stdin=io.StringIO(
            json.dumps(
                rendered_compose(
                    network_mode=None,
                    udp_host_ip="0.0.0.0",
                )
            )
        ),
        stderr=output,
    )

    report = json.loads(output.getvalue())
    assert status == 3
    assert report == {
        "schema": "gh.n3w-pairing-deployment-gate/1",
        "status": "FAIL",
        "reason": "discovery_udp_requires_host_network",
        "secret_values_included": False,
    }
