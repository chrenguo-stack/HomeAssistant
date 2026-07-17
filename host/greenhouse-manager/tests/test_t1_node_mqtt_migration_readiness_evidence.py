from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from greenhouse_manager import t1_node_mqtt_migration_readiness_evidence as module

SYSTEM_ID = "greenhouse"
NODE_ID = "gh-n1-a9f2f8"
DISCOVERY_TOPIC = f"homeassistant/device/{NODE_ID}/config"
CANONICAL_TOPIC = f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/telemetry"
AVAILABILITY_TOPIC = f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/availability"
INGRESS_TOPIC = f"gh/v1/{SYSTEM_ID}/ingress/node/{NODE_ID}/telemetry"


def _state() -> dict[str, object]:
    plan = module.build_node_provisioning_plan(
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        generation=1,
    )
    return {
        "defaultACLAccess": {
            "publishClientSend": False,
            "publishClientReceive": False,
            "subscribe": False,
            "unsubscribe": True,
        },
        "clients": [
            {
                "username": plan.username,
                "clientid": plan.client_id,
                "encoded_password": "encoded-secret",
                "roles": [{"rolename": plan.role_name, "priority": 100}],
            }
        ],
        "roles": [
            {
                "rolename": plan.role_name,
                "acls": [
                    {
                        "acltype": acl.acl_type,
                        "topic": acl.topic,
                        "allow": acl.allow,
                        "priority": acl.priority,
                    }
                    for acl in reversed(plan.acls)
                ],
            }
        ],
    }


def _discovery() -> dict[str, object]:
    return {
        "device": {"identifiers": [f"gh_{SYSTEM_ID}_{NODE_ID}"]},
        "components": {
            "air_temperature": {"unique_id": f"{NODE_ID}_air_temperature"},
            "soil_temperature": {"unique_id": f"{NODE_ID}_soil_temperature"},
        },
        "state_topic": CANONICAL_TOPIC,
        "availability": [{"topic": AVAILABILITY_TOPIC}],
    }


class Runner:
    def __init__(
        self,
        *,
        state: Mapping[str, object] | None = None,
        connection_username: str | None = None,
        include_connection: bool = True,
    ) -> None:
        self.state = dict(state or _state())
        self.connection_username = connection_username
        self.include_connection = include_connection
        self.commands: list[tuple[str, ...]] = []

    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        assert input_text is None
        self.commands.append(command)
        if command[:2] == ("docker", "inspect"):
            name = command[2]
            return 0, json.dumps(
                [
                    {
                        "Id": f"{name}-id",
                        "Image": f"{name}-image",
                        "RestartCount": 0,
                        "State": {
                            "Status": "running",
                            "StartedAt": "2026-07-17T00:00:00Z",
                        },
                    }
                ]
            )
        joined = " ".join(command)
        if "cat /mosquitto/config/mosquitto.conf" in joined:
            return 0, (
                "listener 1883\n"
                "allow_anonymous true\n"
                "plugin /usr/lib/mosquitto_dynamic_security.so\n"
                "plugin_opt_config_file /mosquitto/data/dynamic-security.json\n"
            )
        if "cat /mosquitto/data/dynamic-security.json" in joined:
            return 0, json.dumps(self.state)
        if "stat -c '%a:%u:%g:%h:%s'" in joined:
            return 0, "600:1883:1883:1:4096\n1883:1883\n"
        if command[:4] == (
            "docker",
            "exec",
            "mosquitto",
            "mosquitto_sub",
        ):
            topic = command[-1]
            if topic in {CANONICAL_TOPIC, INGRESS_TOPIC}:
                return 0, json.dumps({"schema": "gh.telemetry/1", "node_id": NODE_ID})
            if topic == AVAILABILITY_TOPIC:
                return 0, json.dumps({"node_id": NODE_ID, "state": "online"})
            if topic == DISCOVERY_TOPIC:
                return 0, json.dumps(_discovery())
            return 1, "unexpected topic"
        if command[:3] == ("docker", "logs", "--tail"):
            if not self.include_connection:
                return 0, "other log line\n"
            suffix = (
                f", u'{self.connection_username}'"
                if self.connection_username is not None
                else ""
            )
            return 0, (
                "New client connected from 192.0.2.1:1234 as "
                f"{NODE_ID} (p2, c1, k60{suffix}).\n"
            )
        return 1, f"unexpected command: {command!r}"


def test_builds_exact_read_only_node_evidence() -> None:
    runner = Runner()
    report = module.build_node_mqtt_migration_readiness_evidence(
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        discovery_topic=DISCOVERY_TOPIC,
        runner=runner,
        repository_sha="a" * 40,
        manager_source_version="0.4.87",
    )

    assert report["evidence_verified"] is True
    assert report["read_only"] is True
    assert report["node_identity"]["identity_exact"] is True
    assert report["continuity"]["fresh_ingress_observed"] is True
    assert report["node_runtime"]["runtime_connection_anonymous"] is True
    assert report["node_credentials_delivered"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert report["homeassistant_storage_read"] is False
    assert report["production_manager_upgraded"] is False
    assert report["ready_for_live_apply"] is False
    assert not any(".storage" in " ".join(command) for command in runner.commands)


def test_rejects_node_acl_drift() -> None:
    state = _state()
    roles = state["roles"]
    assert isinstance(roles, list)
    role = roles[0]
    assert isinstance(role, dict)
    acls = role["acls"]
    assert isinstance(acls, list)
    acls.pop()

    with pytest.raises(
        module.NodeMigrationReadinessEvidenceError,
        match="ACLs have drifted",
    ):
        module.build_node_mqtt_migration_readiness_evidence(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            discovery_topic=DISCOVERY_TOPIC,
            runner=Runner(state=state),
        )


def test_rejects_authenticated_node_before_authorization() -> None:
    with pytest.raises(
        module.NodeMigrationReadinessEvidenceError,
        match="authenticated runtime was observed",
    ):
        module.build_node_mqtt_migration_readiness_evidence(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            discovery_topic=DISCOVERY_TOPIC,
            runner=Runner(connection_username=f"ghn_{NODE_ID}"),
        )


def test_rejects_missing_exact_connection_attribution() -> None:
    with pytest.raises(
        module.NodeMigrationReadinessEvidenceError,
        match="connection attribution is unavailable",
    ):
        module.build_node_mqtt_migration_readiness_evidence(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            discovery_topic=DISCOVERY_TOPIC,
            runner=Runner(include_connection=False),
        )


def test_rejects_invalid_repository_sha_before_runtime() -> None:
    runner = Runner()
    with pytest.raises(ValueError, match="40-character"):
        module.build_node_mqtt_migration_readiness_evidence(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            discovery_topic=DISCOVERY_TOPIC,
            runner=runner,
            repository_sha="bad",
        )
    assert runner.commands == []


def test_rejects_unpaired_expected_baseline_hashes_before_runtime() -> None:
    runner = Runner()
    with pytest.raises(ValueError, match="paired SHA-256"):
        module.build_node_mqtt_migration_readiness_evidence(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            discovery_topic=DISCOVERY_TOPIC,
            runner=runner,
            expected_broker_config_sha256="a" * 64,
        )
    assert runner.commands == []


def test_rejects_bound_baseline_drift() -> None:
    with pytest.raises(
        module.NodeMigrationReadinessEvidenceError,
        match="bound Broker baseline has drifted",
    ):
        module.build_node_mqtt_migration_readiness_evidence(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            discovery_topic=DISCOVERY_TOPIC,
            runner=Runner(),
            expected_broker_config_sha256="a" * 64,
            expected_dynamic_security_state_sha256="b" * 64,
        )
