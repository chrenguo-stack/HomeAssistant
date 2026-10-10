from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_clean_product_deployment_gate.py"
IMAGE_LOCK = ROOT / "infra/n3w-t1/production/image-lock.json"


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


def _bind(
    source: str,
    target: str,
    *,
    read_only: bool = True,
) -> dict:
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
                "image": "local/greenhouse-manager:s20-511db028",
                "pull_policy": "never",
                "user": "999:999",
                "network_mode": "host",
                "restart": "no",
                "profiles": ["application"],
                "read_only": True,
                "depends_on": {
                    "broker": {
                        "condition": "service_started",
                    }
                },
                "environment": {
                    "GH_SYSTEM_ID": "greenhouse",
                    "GH_MQTT_HOST": "127.0.0.1",
                    "GH_MQTT_PORT": "8883",
                    "GH_MQTT_USERNAME": "ghs_greenhouse_manager",
                    "GH_MQTT_PASSWORD_FILE": (
                        "/run/secrets/gh_manager_mqtt_password"
                    ),
                    "GH_MQTT_CLIENT_ID": "gh-manager-greenhouse",
                    "GH_MQTT_TLS": "true",
                    "GH_MQTT_CA_FILE": "/run/n3w/tls/ca.pem",
                    "GH_HA_DISCOVERY_ENABLED": "true",
                    "GH_N3W_RUNTIME_ENABLED": "true",
                    "GH_N3W_PRODUCT_PAIRING_ENABLED": "true",
                    "GH_N3W_PAIRING_MANAGER_ID": (
                        "gh-manager-greenhouse"
                    ),
                    "GH_N3W_PAIRING_ADVERTISED_HOST": "auto",
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
                    "GH_N3W_NODE_BROKER_CA_FILE": (
                        "/run/n3w/tls/ca.pem"
                    ),
                },
                "volumes": [
                    _bind(
                        "/var/lib/greenhouse-manager",
                        "/var/lib/greenhouse-manager",
                        read_only=False,
                    ),
                    _bind(
                        "/opt/greenhouse-secrets/mqtt/manager/password",
                        "/run/secrets/gh_manager_mqtt_password",
                    ),
                    _bind(
                        (
                            "/opt/greenhouse-secrets/mqtt/"
                            "provisioning/password"
                        ),
                        (
                            "/run/secrets/"
                            "gh_n3w_provisioning_mqtt_password"
                        ),
                    ),
                    _bind(
                        "/etc/n3wfc4/tls/ca.pem",
                        "/run/n3w/tls/ca.pem",
                    ),
                ],
            },
            "homeassistant": {
                "image": (
                    "ghcr.io/home-assistant/home-assistant:2026.10.0"
                    "@sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae"
                    "70656ecddb0e02ad31ad122be4"
                ),
                "network_mode": "host",
                "restart": "no",
                "profiles": ["application"],
                "depends_on": {
                    "broker": {
                        "condition": "service_started",
                    }
                },
                "volumes": [
                    _bind(
                        "/var/lib/n3wfc4-homeassistant",
                        "/config",
                        read_only=False,
                    ),
                    _bind(
                        (
                            "/opt/HomeAssistant/infra/n3w-t1/"
                            "production/homeassistant-configuration.yaml"
                        ),
                        "/config/configuration.yaml",
                    ),
                    _bind(
                        (
                            "/opt/HomeAssistant/infra/n3w-t1/"
                            "homeassistant/custom_components/"
                            "n3w_mqtt_bootstrap"
                        ),
                        (
                            "/config/custom_components/"
                            "n3w_mqtt_bootstrap"
                        ),
                    ),
                    _bind(
                        (
                            "/opt/greenhouse-secrets/mqtt/"
                            "homeassistant/password"
                        ),
                        "/run/secrets/gh_homeassistant_mqtt_password",
                    ),
                    _bind(
                        (
                            "/opt/greenhouse-secrets/mqtt/"
                            "homeassistant/mqtt-bootstrap.json"
                        ),
                        "/run/n3w/ha-mqtt-bootstrap.json",
                    ),
                ],
            },
            "broker": {
                "image": (
                    "m.daocloud.io/docker.io/library/"
                    "eclipse-mosquitto:2.1.2-alpine"
                    "@sha256:3184566df484a083411a0e70e92c87a264b8f064"
                    "8df632f10eb23d54d99f4549"
                ),
                "restart": "no",
                "ports": [
                    _publication("0.0.0.0", 8883),
                    _publication("127.0.0.1", 1883),
                ],
                "volumes": [
                    _bind(
                        (
                            "/opt/HomeAssistant/infra/n3w-t1/"
                            "broker/mosquitto.conf"
                        ),
                        "/mosquitto/config/mosquitto.conf",
                    ),
                    _bind(
                        "/etc/n3wfc4/tls/ca.pem",
                        "/mosquitto/tls/ca.pem",
                    ),
                    _bind(
                        "/etc/n3wfc4/tls/server.pem",
                        "/mosquitto/tls/server.pem",
                    ),
                    _bind(
                        "/etc/n3wfc4/tls/server.key",
                        "/mosquitto/tls/server.key",
                    ),
                    _bind(
                        "/var/lib/n3wfc4-broker",
                        "/mosquitto/data",
                        read_only=False,
                    ),
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
    assert report["manager_runtime_uid_gid"] == "999:999"
    assert report["manager_secret_file_count"] == 2
    assert report["homeassistant_password_mount_readonly"] is True
    assert report["broker_tls_publication"] == "ipv4_wildcard_8883"
    assert report["broker_homeassistant_publication"] == (
        "ipv4_loopback_1883"
    )
    assert report["bare_compose_up_starts_application_services"] is False


def test_accepts_repository_image_lock() -> None:
    tool = load_tool()
    document = json.loads(IMAGE_LOCK.read_text(encoding="utf-8"))

    report = tool.validate_image_lock_document(document)

    assert report["manager_runtime_uid"] == 999
    assert report["manager_runtime_gid"] == 999
    assert report["homeassistant_arm64_digest"].startswith("sha256:")
    assert report["broker_arm64_digest"].startswith("sha256:")


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


def test_rejects_manager_inline_password() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["manager"]["environment"][
        "GH_MQTT_PASSWORD"
    ] = "forbidden"

    with pytest.raises(
        tool.DeploymentContractError,
        match="manager_inline_password_forbidden",
    ):
        tool.validate_compose_document(document)


def test_rejects_manager_endpoint_drift() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["manager"]["environment"][
        "GH_MQTT_HOST"
    ] = "mosquitto"

    with pytest.raises(
        tool.DeploymentContractError,
        match="manager_runtime_environment_invalid",
    ):
        tool.validate_compose_document(document)


@pytest.mark.parametrize(
    "target",
    [
        "/run/secrets/gh_homeassistant_mqtt_password",
        "/run/n3w/ha-mqtt-bootstrap.json",
    ],
)
def test_rejects_writable_homeassistant_private_mount(
    target: str,
) -> None:
    tool = load_tool()
    document = rendered_compose()
    for mount in document["services"]["homeassistant"]["volumes"]:
        if mount["target"] == target:
            mount["read_only"] = False

    with pytest.raises(
        tool.DeploymentContractError,
        match="bind_mount_contract_invalid",
    ):
        tool.validate_compose_document(document)


def test_rejects_manager_runtime_user_drift() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["manager"]["user"] = "1000:1000"

    with pytest.raises(
        tool.DeploymentContractError,
        match="manager_runtime_user_invalid",
    ):
        tool.validate_compose_document(document)


@pytest.mark.parametrize("service", ["manager", "homeassistant"])
def test_rejects_application_profile_removal(service: str) -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"][service]["profiles"] = []

    with pytest.raises(
        tool.DeploymentContractError,
        match=f"{service}_profile_invalid",
    ):
        tool.validate_compose_document(document)


def test_rejects_broker_tls_mount_target_drift() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["services"]["broker"]["volumes"][1][
        "target"
    ] = "/mosquitto/config/n3w-ca.pem"

    with pytest.raises(
        tool.DeploymentContractError,
        match="bind_mount_target_count_invalid",
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


def test_rejects_extra_compose_network() -> None:
    tool = load_tool()
    document = rendered_compose()
    document["networks"]["unexpected"] = {
        "name": "unexpected",
    }

    with pytest.raises(
        tool.DeploymentContractError,
        match="compose_network_set_invalid",
    ):
        tool.validate_compose_document(document)


def test_rejects_image_lock_drift() -> None:
    tool = load_tool()
    document = json.loads(IMAGE_LOCK.read_text(encoding="utf-8"))
    document["manager"]["runtime_uid"] = 1000

    with pytest.raises(
        tool.DeploymentContractError,
        match="manager_image_lock_invalid",
    ):
        tool.validate_image_lock_document(document)
