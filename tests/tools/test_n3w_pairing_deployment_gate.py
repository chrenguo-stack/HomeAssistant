from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_pairing_deployment_gate.py"
EXPECTED_COMPOSE_PROJECT_NAME = "n3wfc4"
EXPECTED_BROKER_NETWORKS = (
    "n3wfc4-private",
    "n3wfc4-services",
)


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
    broker_host_ip: str | None = "0.0.0.0",
    broker_published_port: str = "8883",
    broker_networks: tuple[str, ...] = EXPECTED_BROKER_NETWORKS,
    broker_restart: str | None = "no",
    compose_project_name: str | None = EXPECTED_COMPOSE_PROJECT_NAME,
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

    broker_port = {
        "mode": "ingress",
        "target": 8883,
        "published": broker_published_port,
        "protocol": "tcp",
    }
    if broker_host_ip is not None:
        broker_port["host_ip"] = broker_host_ip

    broker: dict = {
        "ports": [broker_port],
        "networks": {
            network: None
            for network in broker_networks
        },
    }
    if broker_restart is not None:
        broker["restart"] = broker_restart

    return {
        "name": compose_project_name,
        "services": {
            "manager": manager,
            "broker": broker,
        },
        "networks": {
            network: {"name": network}
            for network in broker_networks
        },
    }


def test_accepts_host_network_ipv4_wildcard_and_exact_networks() -> None:
    tool = load_tool()

    result = tool.validate_compose_document(
        rendered_compose(),
        service_name="manager",
        broker_service_name="broker",
        broker_loopback_ip="127.0.1.1",
    )

    assert result["status"] == "PASS"
    assert result["compose_project_name"] == "n3wfc4"
    assert result["compose_project_identity_verified"] is True
    assert result["network_mode"] == "host"
    assert result["docker_udp_publication"] is False
    assert result["broker_ipv4_wildcard_publication"] is True
    assert result["broker_restart_policy"] == "no"
    assert result["broker_host_tls_publication_exclusive"] is True
    assert result["broker_concrete_lan_ip_dependency"] is False
    assert result["broker_network_keys"] == [
        "n3wfc4-private",
        "n3wfc4-services",
    ]
    assert result["broker_networks"] == [
        "n3wfc4-private",
        "n3wfc4-services",
    ]
    assert result["broker_network_attachment_set_verified"] is True
    assert result["broker_effective_network_names_verified"] is True
    assert result["broker_manager_loopback_ip"] == "127.0.1.1"
    assert result["broker_manager_loopback_runtime_probe_required"] is True
    assert result["broker_ingress_runtime_probe_required"] is True
    assert result["secret_values_included"] is False


@pytest.mark.parametrize("project_name", [None, "", "recipes", "other-project"])
def test_rejects_compose_project_identity_drift(
    project_name: str | None,
) -> None:
    tool = load_tool()

    with pytest.raises(
        tool.DeploymentContractError,
        match="compose_project_identity_invalid",
    ):
        tool.validate_compose_document(
            rendered_compose(compose_project_name=project_name),
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


@pytest.mark.parametrize(
    "restart_policy",
    [None, "always", "unless-stopped", "on-failure"],
)
def test_rejects_broker_restart_policy_that_can_bypass_guard(
    restart_policy: str | None,
) -> None:
    tool = load_tool()

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_restart_policy_not_no",
    ):
        tool.validate_compose_document(
            rendered_compose(broker_restart=restart_policy),
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_implicit_broker_host_binding() -> None:
    tool = load_tool()

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_wildcard_tls_publication_missing",
    ):
        tool.validate_compose_document(
            rendered_compose(broker_host_ip=None),
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.0.1",
        )


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


@pytest.mark.parametrize(
    "broker_host_ip",
    [
        "127.0.0.1",
        "127.0.1.1",
        "192.0.2.10",
        "198.51.100.10",
        "203.0.113.10",
        "::",
    ],
)
def test_rejects_non_ipv4_wildcard_broker_host_binding(
    broker_host_ip: str,
) -> None:
    tool = load_tool()

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_wildcard_tls_publication_missing",
    ):
        tool.validate_compose_document(
            rendered_compose(broker_host_ip=broker_host_ip),
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_empty_broker_host_binding() -> None:
    tool = load_tool()

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_wildcard_tls_publication_missing",
    ):
        tool.validate_compose_document(
            rendered_compose(broker_host_ip=""),
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_broker_publication_with_wrong_published_port() -> None:
    tool = load_tool()

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_tls_publication_port_mismatch",
    ):
        tool.validate_compose_document(
            rendered_compose(broker_published_port="1883"),
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_extra_misdirected_tls_publication() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["broker"]["ports"].append(
        {
            "host_ip": "0.0.0.0",
            "mode": "ingress",
            "target": 8883,
            "published": "18883",
            "protocol": "tcp",
        }
    )

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_tls_publication_count_invalid",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_duplicate_tls_publications() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["broker"]["ports"].append(
        {
            "host_ip": "192.0.2.10",
            "mode": "ingress",
            "target": 8883,
            "published": "8883",
            "protocol": "tcp",
        }
    )

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_tls_publication_count_invalid",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_published_range_overlapping_8883() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["broker"]["ports"].append(
        {
            "host_ip": "192.0.2.10",
            "mode": "ingress",
            "target": 1883,
            "published": "8880-8890",
            "protocol": "tcp",
        }
    )

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_tls_publication_count_invalid",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_target_range_overlapping_8883() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["broker"]["ports"].append(
        {
            "host_ip": "192.0.2.10",
            "mode": "ingress",
            "target": "8880-8890",
            "published": "18880-18890",
            "protocol": "tcp",
        }
    )

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_tls_publication_count_invalid",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_unparseable_tcp_port_spec() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["broker"]["ports"].append(
        {
            "host_ip": "192.0.2.10",
            "mode": "ingress",
            "target": 1883,
            "published": "dynamic",
            "protocol": "tcp",
        }
    )

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_port_spec_invalid",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


@pytest.mark.parametrize(
    "broker_networks",
    [
        ("n3wfc4-private",),
        ("n3wfc4-services",),
        ("n3wfc4-private", "replacement-network"),
        ("n3wfc4-private", "n3wfc4-services", "unexpected-network"),
    ],
)
def test_rejects_incorrect_broker_network_attachment_set(
    broker_networks: tuple[str, ...],
) -> None:
    tool = load_tool()

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_network_attachment_set_invalid",
    ):
        tool.validate_compose_document(
            rendered_compose(broker_networks=broker_networks),
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_missing_broker_networks() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["broker"].pop("networks")

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_networks_invalid",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_broker_effective_network_name_drift() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["networks"]["n3wfc4-services"]["name"] = "replacement-network"

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_effective_network_set_invalid",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_swapped_broker_effective_network_names() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["networks"]["n3wfc4-private"]["name"] = "n3wfc4-services"
    document["networks"]["n3wfc4-services"]["name"] = "n3wfc4-private"

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_effective_network_set_invalid",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_missing_top_level_broker_network_definition() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["networks"].pop("n3wfc4-services")

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_network_definition_missing",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_missing_effective_network_name() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["networks"]["n3wfc4-services"].pop("name")

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_effective_network_name_invalid",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_non_loopback_manager_broker_address() -> None:
    tool = load_tool()

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_loopback_ip_not_loopback",
    ):
        tool.validate_compose_document(
            rendered_compose(),
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
        "schema": "gh.n3w-pairing-deployment-gate/2",
        "status": "FAIL",
        "reason": "discovery_udp_requires_host_network",
        "secret_values_included": False,
    }


def test_rejects_other_service_publishing_tcp_8883() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["other"] = {
        "ports": [
            {
                "host_ip": "0.0.0.0",
                "target": 9443,
                "published": "8883",
                "protocol": "tcp",
            }
        ]
    }

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_host_tls_publication_owner_invalid",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_rejects_other_service_tcp_range_covering_8883() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["other"] = {
        "ports": [
            {
                "host_ip": "0.0.0.0",
                "target": "9000-9010",
                "published": "8880-8890",
                "protocol": "tcp",
            }
        ]
    }

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_host_tls_publication_owner_invalid",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )


def test_allows_other_service_udp_8883() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["other"] = {
        "ports": [
            {
                "host_ip": "0.0.0.0",
                "target": 8883,
                "published": "8883",
                "protocol": "udp",
            }
        ]
    }

    result = tool.validate_compose_document(
        document,
        service_name="manager",
        broker_service_name="broker",
        broker_loopback_ip="127.0.1.1",
    )

    assert result["broker_host_tls_publication_exclusive"] is True


def test_allows_other_service_target_8883_on_different_host_port() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["other"] = {
        "ports": [
            {
                "host_ip": "0.0.0.0",
                "target": 8883,
                "published": "18883",
                "protocol": "tcp",
            }
        ]
    }

    result = tool.validate_compose_document(
        document,
        service_name="manager",
        broker_service_name="broker",
        broker_loopback_ip="127.0.1.1",
    )

    assert result["broker_host_tls_publication_exclusive"] is True


def test_rejects_unparseable_other_service_tcp_publication() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["other"] = {
        "ports": [
            {
                "host_ip": "0.0.0.0",
                "target": 9443,
                "published": "dynamic",
                "protocol": "tcp",
            }
        ]
    }

    with pytest.raises(
        tool.DeploymentContractError,
        match="compose_tcp_port_spec_invalid",
    ):
        tool.validate_compose_document(
            document,
            service_name="manager",
            broker_service_name="broker",
            broker_loopback_ip="127.0.1.1",
        )
