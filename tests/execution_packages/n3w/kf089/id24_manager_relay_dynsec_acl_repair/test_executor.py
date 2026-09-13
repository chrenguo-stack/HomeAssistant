from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[5]
    / "tools/execution_packages/n3w/kf089/"
    "id24_manager_relay_dynsec_acl_repair/executor.py"
)
SPEC = importlib.util.spec_from_file_location("id24_executor", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
executor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(executor)


def manager_container() -> dict:
    return {
        "Id": "m" * 64,
        "Name": "/greenhouse-manager",
        "RestartCount": 0,
        "Config": {
            "Image": "greenhouse-manager:fc4",
            "Labels": {
                "org.opencontainers.image.revision":
                    executor.DEPLOYED_MANAGER_SOURCE,
            },
            "Env": [
                "GH_MQTT_USERNAME=ghs_greenhouse_manager",
                "GH_MQTT_CLIENT_ID=gh-manager-greenhouse",
                "GH_N3W_PROVISIONING_USERNAME=ghs_greenhouse_provisioning",
                "GH_N3W_PROVISIONING_CLIENT_ID=gh-provisioning-greenhouse",
                "GH_N3W_PROVISIONING_PASSWORD_FILE=/run/secrets/provisioning",
                "GH_MQTT_HOST=127.0.0.1",
                "GH_MQTT_PORT=8883",
                "GH_MQTT_TLS=true",
                "GH_MQTT_CA_FILE=/run/secrets/ca.pem",
            ],
        },
        "HostConfig": {"NetworkMode": "host"},
        "State": {
            "Running": True,
            "StartedAt": "2026-09-13T00:00:00Z",
        },
    }


def broker_container() -> dict:
    return {
        "Id": "b" * 64,
        "Name": "/n3wfc4-broker-1",
        "RestartCount": 0,
        "Config": {
            "Image": "local/mosquitto:test",
            "Labels": {
                "com.docker.compose.service": "broker",
                "com.docker.compose.project": "n3wfc4",
            },
        },
        "HostConfig": {"NetworkMode": "n3wfc4-private"},
        "State": {
            "Running": True,
            "StartedAt": "2026-09-13T00:00:00Z",
        },
    }


def dynsec_document(*, repaired: bool = False, duplicate_manager: bool = False) -> str:
    relay = "gh/v1/greenhouse/ingress/gateway/+/+/frame"
    direct = "gh/v1/greenhouse/ingress/node/+/telemetry"
    manager_acls = [
        {
            "acltype": acl_type,
            "topic": direct,
            "allow": True,
            "priority": 100,
        }
        for acl_type in executor.TARGET_ACL_TYPES
    ]
    if repaired:
        manager_acls.extend(
            {
                "acltype": acl_type,
                "topic": relay,
                "allow": True,
                "priority": 100,
            }
            for acl_type in executor.TARGET_ACL_TYPES
        )
    clients = [
        {
            "username": "ghs_greenhouse_manager",
            "clientid": "gh-manager-greenhouse",
            "roles": [{"rolename": "gh-service-greenhouse-manager"}],
        },
        {
            "username": "ghs_old_manager",
            "clientid": "gh-manager-old",
            "roles": [{"rolename": "gh-service-old-manager"}],
        },
    ]
    if duplicate_manager:
        clients.append(
            {
                "username": "ghs_greenhouse_manager",
                "clientid": "gh-manager-greenhouse",
                "roles": [{"rolename": "gh-service-greenhouse-manager"}],
            }
        )
    return json.dumps(
        {
            "defaultACLAccess": {
                "publishClientSend": False,
                "publishClientReceive": False,
                "subscribe": False,
                "unsubscribe": True,
            },
            "clients": clients,
            "roles": [
                {
                    "rolename": "gh-service-greenhouse-manager",
                    "acls": manager_acls,
                },
                {
                    "rolename": "gh-service-old-manager",
                    "acls": [],
                },
            ],
        }
    )


def test_runtime_binding_uses_standalone_manager_and_n3wfc4_broker() -> None:
    manager, broker = executor.bind_runtime(
        [broker_container(), manager_container()]
    )
    assert manager["Id"] == "m" * 64
    assert broker["Id"] == "b" * 64


def test_prestate_selects_active_manager_exactly_even_with_stale_candidate() -> None:
    analysis = executor.analyze_dynsec(
        dynsec_document(),
        executor.env_map(manager_container()),
        require_defect=True,
    )
    assert analysis["defect"] is True
    assert analysis["relay_exact_count"] == 0
    assert analysis["direct_contract_ok"] is True


def test_duplicate_exact_active_manager_is_rejected() -> None:
    with pytest.raises(executor.StopExecution) as error:
        executor.analyze_dynsec(
            dynsec_document(duplicate_manager=True),
            executor.env_map(manager_container()),
            require_defect=True,
        )
    assert error.value.operation == "T1_DYNSEC_STATE"


def test_repaired_poststate_has_exact_three_target_acls() -> None:
    analysis = executor.analyze_dynsec(
        dynsec_document(repaired=True),
        executor.env_map(manager_container()),
        require_defect=False,
    )
    assert analysis["relay_exact_count"] == 3
    assert all(analysis["relay_exact_present"].values())
    assert analysis["relay_subscribe_broad_allow_count"] == 1
    assert analysis["relay_receive_broad_allow_count"] == 1


def test_repaired_state_is_not_accepted_as_mutation_prestate() -> None:
    with pytest.raises(executor.StopExecution) as error:
        executor.analyze_dynsec(
            dynsec_document(repaired=True),
            executor.env_map(manager_container()),
            require_defect=True,
        )
    assert "no longer matches" in error.value.reason


def test_mutator_result_requires_sanitized_pass() -> None:
    assert executor.mutator_result_ok(
        (0, '{"result":"PASS","response_error":false}', "")
    )
    assert not executor.mutator_result_ok(
        (0, '{"result":"STOP","response_error":true}', "")
    )
    assert not executor.mutator_result_ok((2, "", "failed"))


def test_runtime_stability_rejects_restart_or_replacement() -> None:
    before_manager = manager_container()
    before_broker = broker_container()
    changed = manager_container()
    changed["State"]["StartedAt"] = "2026-09-13T00:01:00Z"
    with pytest.raises(executor.StopExecution) as error:
        executor.require_runtime_stable(
            before_manager,
            before_broker,
            [changed, before_broker],
        )
    assert error.value.operation == "T1_RUNTIME_POSTCHECK"
