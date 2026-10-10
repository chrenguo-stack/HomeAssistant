#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

SCHEMA = "gh.n3w-t1-clean-product-deployment-gate/2"
IMAGE_LOCK_SCHEMA = "gh.n3w-t1-s20-production-image-lock/1"
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
APPLICATION_PROFILE = "application"

EXPECTED_MANAGER_IMAGE = "local/greenhouse-manager:s20-511db028"
EXPECTED_MANAGER_IMAGE_ID = (
    "sha256:ef0f28c2fd339430a85acb6cb65158c71c61cd8fc3c6330c375da27d0f2440f1"
)
EXPECTED_MANAGER_SOURCE = "511db028780988a7c07cb9342c8be507380bae0f"
EXPECTED_MANAGER_TAR_SHA256 = (
    "2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081"
)
EXPECTED_MANAGER_UID = 999
EXPECTED_MANAGER_GID = 999

EXPECTED_HA_SOURCE_REF = "ghcr.io/home-assistant/home-assistant:2026.10.0"
EXPECTED_HA_DIGEST = (
    "sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4"
)
EXPECTED_HA_IMAGE = f"{EXPECTED_HA_SOURCE_REF}@{EXPECTED_HA_DIGEST}"
EXPECTED_HA_IMAGE_ID = (
    "sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879"
)

EXPECTED_BROKER_SOURCE_REF = (
    "m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine"
)
EXPECTED_BROKER_DIGEST = (
    "sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549"
)
EXPECTED_BROKER_IMAGE = (
    f"{EXPECTED_BROKER_SOURCE_REF}@{EXPECTED_BROKER_DIGEST}"
)
EXPECTED_BROKER_IMAGE_ID = (
    "sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b"
)

MANAGER_PASSWORD_TARGET = "/run/secrets/gh_manager_mqtt_password"
PROVISIONING_PASSWORD_TARGET = (
    "/run/secrets/gh_n3w_provisioning_mqtt_password"
)
HA_PASSWORD_TARGET = "/run/secrets/gh_homeassistant_mqtt_password"
HA_BOOTSTRAP_TARGET = "/run/n3w/ha-mqtt-bootstrap.json"
MANAGER_CA_TARGET = "/run/n3w/tls/ca.pem"

MANAGER_SECRET_SOURCE = "/opt/greenhouse-secrets/mqtt/manager/password"
PROVISIONING_SECRET_SOURCE = (
    "/opt/greenhouse-secrets/mqtt/provisioning/password"
)
HA_PASSWORD_SOURCE = "/opt/greenhouse-secrets/mqtt/homeassistant/password"
HA_BOOTSTRAP_SOURCE = (
    "/opt/greenhouse-secrets/mqtt/homeassistant/mqtt-bootstrap.json"
)
BROKER_CONFIG_SOURCE = "/opt/HomeAssistant/infra/n3w-t1/broker/mosquitto.conf"
BROKER_DATA_SOURCE = "/var/lib/n3wfc4-broker"
TLS_CA_SOURCE = "/etc/n3wfc4/tls/ca.pem"
TLS_CERT_SOURCE = "/etc/n3wfc4/tls/server.pem"
TLS_KEY_SOURCE = "/etc/n3wfc4/tls/server.key"
HA_CONFIG_SOURCE = (
    "/opt/HomeAssistant/infra/n3w-t1/production/homeassistant-configuration.yaml"
)
HA_COMPONENT_SOURCE = (
    "/opt/HomeAssistant/infra/n3w-t1/homeassistant/custom_components/"
    "n3w_mqtt_bootstrap"
)
HA_STATE_SOURCE = "/var/lib/n3wfc4-homeassistant"
MANAGER_STATE_SOURCE = "/var/lib/greenhouse-manager"


class DeploymentContractError(ValueError):
    pass


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


def _require_bind(
    service: Mapping[object, object],
    *,
    source: str,
    target: str,
    read_only: bool,
) -> None:
    matches = [
        item
        for item in _mounts(service)
        if item.get("target") == target
    ]
    if len(matches) != 1:
        raise DeploymentContractError("bind_mount_target_count_invalid")
    mount = matches[0]
    if (
        mount.get("type") != "bind"
        or mount.get("source") != source
        or bool(mount.get("read_only", False)) is not read_only
    ):
        raise DeploymentContractError("bind_mount_contract_invalid")


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
        raise DeploymentContractError(
            f"{label}_host_network_ports_must_be_absent"
        )


def _require_profile(
    service: Mapping[object, object],
    label: str,
) -> None:
    profiles = service.get("profiles")
    if profiles != [APPLICATION_PROFILE]:
        raise DeploymentContractError(f"{label}_profile_invalid")


def _require_restart_no(
    service: Mapping[object, object],
    label: str,
) -> None:
    if service.get("restart") != "no":
        raise DeploymentContractError(f"{label}_restart_policy_invalid")


def _require_broker_dependency(
    service: Mapping[object, object],
    label: str,
) -> None:
    depends_on = service.get("depends_on")
    if not isinstance(depends_on, Mapping):
        raise DeploymentContractError(f"{label}_broker_dependency_invalid")
    broker = depends_on.get("broker")
    if isinstance(broker, str):
        if broker != "service_started":
            raise DeploymentContractError(
                f"{label}_broker_dependency_invalid"
            )
        return
    if not isinstance(broker, Mapping):
        raise DeploymentContractError(f"{label}_broker_dependency_invalid")
    if broker.get("condition") != "service_started":
        raise DeploymentContractError(f"{label}_broker_dependency_invalid")


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
        raise DeploymentContractError(
            "broker_network_attachment_set_invalid"
        )

    definitions = document.get("networks")
    if not isinstance(definitions, Mapping):
        raise DeploymentContractError("compose_networks_invalid")
    if set(definitions) != EXPECTED_BROKER_NETWORKS:
        raise DeploymentContractError("compose_network_set_invalid")
    for key in EXPECTED_BROKER_NETWORKS:
        definition = definitions.get(key)
        if (
            not isinstance(definition, Mapping)
            or definition.get("name") != key
        ):
            raise DeploymentContractError(
                "broker_effective_network_name_invalid"
            )
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
                raise DeploymentContractError(
                    "compose_port_protocol_invalid"
                )
            target = _port(item.get("target"))
            published = _port(item.get("published"))
            if target is None or published is None:
                raise DeploymentContractError("compose_port_spec_invalid")
            if protocol == "tcp" and (
                target == port or published == port
            ):
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
        raise DeploymentContractError(
            f"broker_{port}_publication_count_invalid"
        )
    owner, publication = matches[0]
    if owner != broker_name:
        raise DeploymentContractError(
            f"broker_{port}_publication_owner_invalid"
        )
    if (
        _port(publication.get("target")) != port
        or _port(publication.get("published")) != port
        or publication.get("protocol", "tcp") != "tcp"
        or publication.get("host_ip") != host_ip
    ):
        raise DeploymentContractError(
            f"broker_{port}_publication_invalid"
        )


def _require_manager_environment(
    manager: Mapping[object, object],
) -> None:
    environment = _environment(manager)
    required = {
        "GH_SYSTEM_ID": "greenhouse",
        "GH_MQTT_HOST": "armbian",
        "GH_MQTT_PORT": "8883",
        "GH_MQTT_USERNAME": "ghs_greenhouse_manager",
        "GH_MQTT_PASSWORD_FILE": MANAGER_PASSWORD_TARGET,
        "GH_MQTT_CLIENT_ID": "gh-manager-greenhouse",
        "GH_MQTT_TLS": "true",
        "GH_MQTT_CA_FILE": MANAGER_CA_TARGET,
        "GH_HA_DISCOVERY_ENABLED": "true",
        "GH_N3W_RUNTIME_ENABLED": "true",
        "GH_N3W_PRODUCT_PAIRING_ENABLED": "false",
        "GH_N3W_PAIRING_MANAGER_ID": "gh-manager-greenhouse",
        "GH_N3W_PAIRING_ADVERTISED_HOST": "auto",
        "GH_N3W_PROVISIONING_USERNAME": (
            "ghs_greenhouse_provisioning"
        ),
        "GH_N3W_PROVISIONING_PASSWORD_FILE": (
            PROVISIONING_PASSWORD_TARGET
        ),
        "GH_N3W_PROVISIONING_CLIENT_ID": (
            "gh-provisioning-greenhouse"
        ),
        "GH_N3W_NODE_BROKER_HOST": "gate-f-unbound.invalid",
        "GH_N3W_NODE_BROKER_PORT": "8883",
        "GH_N3W_NODE_BROKER_TLS_SERVER_NAME": "armbian",
        "GH_N3W_NODE_BROKER_CA_FILE": MANAGER_CA_TARGET,
    }
    if any(environment.get(key) != value for key, value in required.items()):
        raise DeploymentContractError("manager_runtime_environment_invalid")
    if environment.get("GH_MQTT_PASSWORD", ""):
        raise DeploymentContractError("manager_inline_password_forbidden")


def validate_image_lock_document(document: object) -> dict[str, object]:
    if not isinstance(document, Mapping):
        raise DeploymentContractError("image_lock_invalid")
    if document.get("schema") != IMAGE_LOCK_SCHEMA:
        raise DeploymentContractError("image_lock_schema_invalid")

    manager = document.get("manager")
    homeassistant = document.get("homeassistant")
    broker = document.get("broker")
    if not all(
        isinstance(item, Mapping)
        for item in (manager, homeassistant, broker)
    ):
        raise DeploymentContractError("image_lock_services_invalid")

    assert isinstance(manager, Mapping)
    assert isinstance(homeassistant, Mapping)
    assert isinstance(broker, Mapping)

    manager_required = {
        "source_sha": EXPECTED_MANAGER_SOURCE,
        "image": EXPECTED_MANAGER_IMAGE,
        "image_id": EXPECTED_MANAGER_IMAGE_ID,
        "tar_sha256": EXPECTED_MANAGER_TAR_SHA256,
        "platform": "linux/arm64",
        "runtime_uid": EXPECTED_MANAGER_UID,
        "runtime_gid": EXPECTED_MANAGER_GID,
        "pull_policy": "never",
    }
    if any(
        manager.get(key) != value
        for key, value in manager_required.items()
    ):
        raise DeploymentContractError("manager_image_lock_invalid")
    if manager.get("entrypoint") != ["greenhouse-manager"]:
        raise DeploymentContractError("manager_image_entrypoint_invalid")
    if manager.get("user") != "greenhouse":
        raise DeploymentContractError("manager_image_user_invalid")

    if (
        homeassistant.get("source_ref") != EXPECTED_HA_SOURCE_REF
        or homeassistant.get("image") != EXPECTED_HA_IMAGE
        or homeassistant.get("manifest_digest") != EXPECTED_HA_DIGEST
        or homeassistant.get("image_id") != EXPECTED_HA_IMAGE_ID
        or homeassistant.get("platform") != "linux/arm64"
        or homeassistant.get("entrypoint") != ["/init"]
        or homeassistant.get("effective_default_uid") != 0
        or homeassistant.get("effective_default_gid") != 0
    ):
        raise DeploymentContractError("homeassistant_image_lock_invalid")

    if (
        broker.get("source_ref") != EXPECTED_BROKER_SOURCE_REF
        or broker.get("image") != EXPECTED_BROKER_IMAGE
        or broker.get("manifest_digest") != EXPECTED_BROKER_DIGEST
        or broker.get("image_id") != EXPECTED_BROKER_IMAGE_ID
        or broker.get("platform") != "linux/arm64"
        or broker.get("entrypoint") != ["/docker-entrypoint.sh"]
    ):
        raise DeploymentContractError("broker_image_lock_invalid")

    return {
        "image_lock_schema": IMAGE_LOCK_SCHEMA,
        "manager_image_id": EXPECTED_MANAGER_IMAGE_ID,
        "homeassistant_arm64_digest": EXPECTED_HA_DIGEST,
        "broker_arm64_digest": EXPECTED_BROKER_DIGEST,
        "manager_runtime_uid": EXPECTED_MANAGER_UID,
        "manager_runtime_gid": EXPECTED_MANAGER_GID,
    }


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
        raise DeploymentContractError(
            "compose_project_identity_invalid"
        )

    services = _services(document)
    expected_services = {
        manager_service_name,
        broker_service_name,
        homeassistant_service_name,
    }
    if set(services) != expected_services:
        raise DeploymentContractError("compose_service_set_invalid")
    manager = _service(services, manager_service_name)
    broker = _service(services, broker_service_name)
    homeassistant = _service(services, homeassistant_service_name)

    if manager.get("image") != EXPECTED_MANAGER_IMAGE:
        raise DeploymentContractError("manager_image_invalid")
    if manager.get("pull_policy") != "never":
        raise DeploymentContractError("manager_pull_policy_invalid")
    if str(manager.get("user")) != (
        f"{EXPECTED_MANAGER_UID}:{EXPECTED_MANAGER_GID}"
    ):
        raise DeploymentContractError("manager_runtime_user_invalid")
    _require_restart_no(manager, "manager")
    _require_profile(manager, "manager")
    _require_host_network_no_ports(manager, "manager")
    _require_broker_dependency(manager, "manager")
    _require_manager_environment(manager)
    if manager.get("read_only") is not True:
        raise DeploymentContractError("manager_rootfs_not_read_only")

    _require_bind(
        manager,
        source=MANAGER_STATE_SOURCE,
        target=MANAGER_STATE_SOURCE,
        read_only=False,
    )
    _require_bind(
        manager,
        source=MANAGER_SECRET_SOURCE,
        target=MANAGER_PASSWORD_TARGET,
        read_only=True,
    )
    _require_bind(
        manager,
        source=PROVISIONING_SECRET_SOURCE,
        target=PROVISIONING_PASSWORD_TARGET,
        read_only=True,
    )
    _require_bind(
        manager,
        source=TLS_CA_SOURCE,
        target=MANAGER_CA_TARGET,
        read_only=True,
    )

    if homeassistant.get("image") != EXPECTED_HA_IMAGE:
        raise DeploymentContractError("homeassistant_image_invalid")
    _require_restart_no(homeassistant, "homeassistant")
    _require_profile(homeassistant, "homeassistant")
    _require_host_network_no_ports(homeassistant, "homeassistant")
    _require_broker_dependency(homeassistant, "homeassistant")
    _require_bind(
        homeassistant,
        source=HA_STATE_SOURCE,
        target="/config",
        read_only=False,
    )
    _require_bind(
        homeassistant,
        source=HA_CONFIG_SOURCE,
        target="/config/configuration.yaml",
        read_only=True,
    )
    _require_bind(
        homeassistant,
        source=HA_COMPONENT_SOURCE,
        target="/config/custom_components/n3w_mqtt_bootstrap",
        read_only=True,
    )
    _require_bind(
        homeassistant,
        source=HA_PASSWORD_SOURCE,
        target=HA_PASSWORD_TARGET,
        read_only=True,
    )
    _require_bind(
        homeassistant,
        source=HA_BOOTSTRAP_SOURCE,
        target=HA_BOOTSTRAP_TARGET,
        read_only=True,
    )

    if broker.get("image") != EXPECTED_BROKER_IMAGE:
        raise DeploymentContractError("broker_image_invalid")
    _require_restart_no(broker, "broker")
    broker_networks = _broker_networks(document, broker)
    _require_bind(
        broker,
        source=BROKER_CONFIG_SOURCE,
        target="/mosquitto/config/mosquitto.conf",
        read_only=True,
    )
    _require_bind(
        broker,
        source=TLS_CA_SOURCE,
        target="/mosquitto/tls/ca.pem",
        read_only=True,
    )
    _require_bind(
        broker,
        source=TLS_CERT_SOURCE,
        target="/mosquitto/tls/server.pem",
        read_only=True,
    )
    _require_bind(
        broker,
        source=TLS_KEY_SOURCE,
        target="/mosquitto/tls/server.key",
        read_only=True,
    )
    _require_bind(
        broker,
        source=BROKER_DATA_SOURCE,
        target="/mosquitto/data",
        read_only=False,
    )
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
        "service_set": sorted(expected_services),
        "manager_image": EXPECTED_MANAGER_IMAGE,
        "manager_runtime_uid_gid": (
            f"{EXPECTED_MANAGER_UID}:{EXPECTED_MANAGER_GID}"
        ),
        "manager_host_network": True,
        "manager_ports_absent": True,
        "manager_secret_file_count": 2,
        "manager_secret_targets_distinct": True,
        "homeassistant_image": EXPECTED_HA_IMAGE,
        "homeassistant_host_network": True,
        "homeassistant_ports_absent": True,
        "homeassistant_password_mount_readonly": True,
        "homeassistant_bootstrap_mount_readonly": True,
        "broker_image": EXPECTED_BROKER_IMAGE,
        "broker_restart_policy": "no",
        "broker_networks": sorted(broker_networks),
        "broker_tls_publication": "ipv4_wildcard_8883",
        "broker_homeassistant_publication": "ipv4_loopback_1883",
        "host_8883_owner": broker_service_name,
        "host_1883_owner": broker_service_name,
        "host_1883_non_loopback_publication_count": 0,
        "application_profile": APPLICATION_PROFILE,
        "bare_compose_up_starts_application_services": False,
        "authenticated_readiness_external_gate_required": True,
        "manager_tls_server_name": "armbian",
        "manager_exact_namespace_tls_runtime_probe_required": True,
        "product_pairing_enabled": False,
        "node_broker_host_gate_f_unbound": True,
        "node_broker_tls_server_name": "armbian",
        "secret_values_included": False,
    }


def validate_deployment(
    compose_document: object,
    image_lock_document: object,
) -> dict[str, object]:
    report = validate_compose_document(compose_document)
    report.update(validate_image_lock_document(image_lock_document))
    return report


def _load_document(path: str) -> object:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--compose-json",
        default="-",
    )
    parser.add_argument(
        "--image-lock-json",
        default="infra/n3w-t1/production/image-lock.json",
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
        compose_document = _load_document(args.compose_json)
        image_lock_document = _load_document(args.image_lock_json)
        report = validate_deployment(
            compose_document,
            image_lock_document,
        )
    except (
        DeploymentContractError,
        OSError,
        json.JSONDecodeError,
    ) as error:
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
