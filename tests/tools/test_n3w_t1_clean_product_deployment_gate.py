from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_clean_product_deployment_gate.py"


def load_tool():
    name = "n3w_t1_clean_product_deployment_gate"
    specification = importlib.util.spec_from_file_location(
        name,
        TOOL,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _bind(source: str, target: str, *, read_only: bool = True) -> dict:
    return {
        "type": "bind",
        "source": source,
        "target": target,
        "read_only": read_only,
    }


def _publication(host_ip: str, port: int) -> dict:
    return {
        "mode": "ingress",
        "host_ip": host_ip,
        "target": port,
        "published": str(port),
        "protocol": "tcp",
    }


def rendered_compose() -> dict:
    return {
        "name": "n3wfc4",
        "services": {
            "manager": {
                "network_mode": "host",
                "environment": {
                    "GH_MQTT_USERNAME": "ghs_greenhouse_manager",
                    "GH_MQTT_PASSWORD_FILE": (
                        "/run/secrets/gh_manager_mqtt_password"
                    ),
                    "GH_MQTT_CLIENT_ID": "gh-manager-greenhouse",
                    "GH_N3W_PROVISIONING_USERNAME": (
                        "ghs_greenhouse_provisioning"
                    ),
                    "GH_N3W_PROVISIONING_PASSWORD_FILE": (
                        "/run/secrets/"
                        "gh_n3w_provisioning_mqtt_password"
                    ),
                    "GH_N3W_PROVISIONING_CLIENT_ID": (
                        "gh-provisioning-greenhouse"
                    ),
                },
                "volumes": [
                    _bind(
                        "/opt/greenhouse-secrets/mqtt/manager/password",
                        "/run/secrets/gh_manager_mqtt_password",
                    ),
                    _bind(
                        "/opt/greenhouse-secrets/mqtt/provisioning/password",
                        (
                            "/run/secrets/"
                            "gh_n3w_provisioning_mqtt_password"
                        ),
                    ),
                ],
            },
            "homeassistant": {
                "network_mode": "host",
                "volumes": [
                    _bind(
                        "/opt/greenhouse-secrets/mqtt/homeassistant/password",
                        "/run/secrets/gh_homeassistant_mqtt_password",
                    ),
                    _bind(
                        (
                            "/opt/greenhouse-secrets/mqtt/homeassistant/"
                            "mqtt-bootstrap.json"
                        ),
                        "/run/n3w/ha-mqtt-bootstrap.json",
                    ),
                ],
            },
            "broker": {
                "restart": "no",
                "ports": [
                    _publication("0.0.0.0", 8883),
                    _publication("127.0.0.1", 1883),
                ],
                "networks": {
                    "n3wfc4-private": None,
                    "n3wfc4-services": None,
                },
            },
        },
        "networks": {
            "n3wfc4-private": {
                "name": "n3wfc4-private",
            },
            "n3wfc4-services": {
                "name": "n3wfc4-services",
            },
        },
    }


def test_accepts_clean_product_contract() -> None:
    tool = load_tool()

    report = tool.validate_compose_document(
        rendered_compose()
    )

    assert report["status"] == "PASS"
    assert report["compose_project_name"] == "n3wfc4"
    assert report["manager_secret_file_count"] == 2
    assert report["manager_secret_targets_distinct"] is True
    assert report["homeassistant_password_mount_readonly"] is True
    assert report["homeassistant_bootstrap_mount_readonly"] is True
    assert report["broker_tls_publication"] == "ipv4_wildcard_8883"
    assert report["broker_homeassistant_publication"] == (
        "ipv4_loopback_1883"
    )
    assert report["host_1883_non_loopback_publication_count"] == 0
    assert report["secret_values_included"] is False


@pytest.mark.parametrize(
    "host_ip",
    [
        "0.0.0.0",
        "192.0.2.10",
        "127.0.1.1",
    ],
)
def test_rejects_nonexact_homeassistant_loopback_publication(
    host_ip: str,
) -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["broker"]["ports"][1]["host_ip"] = host_ip

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_1883_publication_invalid",
    ):
        tool.validate_compose_document(document)


def test_rejects_extra_1883_owner() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["other"] = {
        "ports": [
            _publication("127.0.0.1", 1883),
        ]
    }

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_1883_publication_count_invalid",
    ):
        tool.validate_compose_document(document)


@pytest.mark.parametrize(
    "target",
    [
        "/run/secrets/gh_homeassistant_mqtt_password",
        "/run/n3w/ha-mqtt-bootstrap.json",
    ],
)
def test_rejects_writable_homeassistant_secret_mount(
    target: str,
) -> None:
    tool = load_tool()
    document = rendered_compose()
    for mount in document["services"]["homeassistant"]["volumes"]:
        if mount["target"] == target:
            mount["read_only"] = False

    with pytest.raises(
        tool.DeploymentContractError,
        match="secret_mount_contract_invalid",
    ):
        tool.validate_compose_document(document)


def test_rejects_missing_homeassistant_password_mount() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["homeassistant"]["volumes"] = [
        document["services"]["homeassistant"]["volumes"][1]
    ]

    with pytest.raises(
        tool.DeploymentContractError,
        match="secret_mount_target_count_invalid",
    ):
        tool.validate_compose_document(document)


def test_rejects_manager_password_file_target_drift() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["manager"]["environment"][
        "GH_N3W_PROVISIONING_PASSWORD_FILE"
    ] = "/run/secrets/gh_manager_mqtt_password"

    with pytest.raises(
        tool.DeploymentContractError,
        match="manager_secret_environment_invalid",
    ):
        tool.validate_compose_document(document)


def test_rejects_inline_manager_password() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["manager"]["environment"][
        "GH_MQTT_PASSWORD"
    ] = "forbidden"

    with pytest.raises(
        tool.DeploymentContractError,
        match="manager_secret_environment_invalid",
    ):
        tool.validate_compose_document(document)


def test_rejects_manager_or_homeassistant_ports() -> None:
    tool = load_tool()
    for service in ("manager", "homeassistant"):
        document = rendered_compose()
        document["services"][service]["ports"] = [
            _publication("127.0.0.1", 47112)
        ]

        with pytest.raises(
            tool.DeploymentContractError,
            match=f"{service}_host_network_ports_must_be_absent",
        ):
            tool.validate_compose_document(document)


def test_rejects_broker_network_drift() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["broker"]["networks"] = {
        "n3wfc4-private": None,
    }

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_network_attachment_set_invalid",
    ):
        tool.validate_compose_document(document)


def test_rejects_broker_restart_drift() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["broker"]["restart"] = "unless-stopped"

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_restart_policy_invalid",
    ):
        tool.validate_compose_document(document)


@pytest.mark.parametrize(
    "host_ip",
    [
        "127.0.0.1",
        "192.0.2.10",
    ],
)
def test_rejects_nonwildcard_tls_publication(
    host_ip: str,
) -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["broker"]["ports"][0]["host_ip"] = host_ip

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_8883_publication_invalid",
    ):
        tool.validate_compose_document(document)


def test_rejects_extra_8883_owner() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["other"] = {
        "ports": [
            _publication("127.0.0.1", 8883),
        ]
    }

    with pytest.raises(
        tool.DeploymentContractError,
        match="broker_8883_publication_count_invalid",
    ):
        tool.validate_compose_document(document)


def test_rejects_shared_manager_and_provisioning_secret_source() -> None:
    tool = load_tool()
    document = rendered_compose()
    mounts = document["services"]["manager"]["volumes"]
    mounts[1]["source"] = mounts[0]["source"]

    with pytest.raises(
        tool.DeploymentContractError,
        match="manager_secret_sources_not_distinct",
    ):
        tool.validate_compose_document(document)


def test_rejects_shared_homeassistant_mount_source() -> None:
    tool = load_tool()
    document = rendered_compose()
    mounts = document["services"]["homeassistant"]["volumes"]
    mounts[1]["source"] = mounts[0]["source"]

    with pytest.raises(
        tool.DeploymentContractError,
        match="homeassistant_mount_sources_not_distinct",
    ):
        tool.validate_compose_document(document)
