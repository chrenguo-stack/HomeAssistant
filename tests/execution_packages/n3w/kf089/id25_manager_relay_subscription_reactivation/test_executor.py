from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[5]
    / "tools/execution_packages/n3w/kf089/"
    "id25_manager_relay_subscription_reactivation/executor.py"
)
SPEC = importlib.util.spec_from_file_location("id25_executor", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
executor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(executor)


def manager_container(*, started_at: str = "2026-09-14T01:00:00Z") -> dict:
    return {
        "Id": "m" * 64,
        "Name": "/greenhouse-manager",
        "RestartCount": 0,
        "Config": {
            "Image": "greenhouse-manager:fc4",
            "Labels": {
                "org.opencontainers.image.revision": executor.id24.DEPLOYED_MANAGER_SOURCE,
            },
        },
        "HostConfig": {"NetworkMode": "host"},
        "State": {"Running": True, "StartedAt": started_at},
    }


def broker_container(*, started_at: str = "2026-09-14T00:30:00Z") -> dict:
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
        "HostConfig": {"NetworkMode": "private"},
        "State": {"Running": True, "StartedAt": started_at},
    }


def test_postrestart_runtime_accepts_same_manager_container_with_new_started_at() -> None:
    before_manager = manager_container()
    before_broker = broker_container()
    after_manager = manager_container(started_at="2026-09-14T01:10:00Z")

    result = executor.require_postrestart_runtime(
        before_manager,
        before_broker,
        [after_manager, before_broker],
    )

    assert result == {
        "manager_container_id_preserved": True,
        "manager_image_preserved": True,
        "manager_started_at_changed": True,
        "manager_running": True,
        "broker_runtime_stable": True,
    }


def test_postrestart_runtime_rejects_missing_restart() -> None:
    before_manager = manager_container()
    before_broker = broker_container()

    with pytest.raises(executor.StopExecution) as error:
        executor.require_postrestart_runtime(
            before_manager,
            before_broker,
            [manager_container(), before_broker],
        )

    assert error.value.operation == "T1_RUNTIME_POSTCHECK"


def test_postrestart_runtime_rejects_broker_restart() -> None:
    before_manager = manager_container()
    before_broker = broker_container()
    after_manager = manager_container(started_at="2026-09-14T01:10:00Z")
    after_broker = broker_container(started_at="2026-09-14T01:09:00Z")

    with pytest.raises(executor.StopExecution) as error:
        executor.require_postrestart_runtime(
            before_manager,
            before_broker,
            [after_manager, after_broker],
        )

    assert error.value.operation == "T1_RUNTIME_POSTCHECK"


def test_postrestart_logs_require_direct_and_exact_relay_subscription() -> None:
    logs = "\n".join(
        [
            "INFO Subscribed to gh/v1/greenhouse/ingress/node/+/telemetry",
            "INFO Subscribed to gh/v1/greenhouse/ingress/gateway/+/+/frame",
        ]
    )

    result = executor.analyze_postrestart_logs(logs, "greenhouse")

    assert result["postrestart_relay_subscription_request_observed"] is True
    assert result["postrestart_direct_subscription_request_observed"] is True
    assert result["postrestart_failure_log_absent"] is True


def test_postrestart_logs_reject_missing_relay_subscription() -> None:
    logs = "INFO Subscribed to gh/v1/greenhouse/ingress/node/+/telemetry"

    with pytest.raises(executor.StopExecution) as error:
        executor.analyze_postrestart_logs(logs, "greenhouse")

    assert error.value.operation == "T1_MANAGER_SUBSCRIPTION_POSTCHECK"


def test_postrestart_logs_reject_local_subscribe_failure_marker() -> None:
    logs = "\n".join(
        [
            "INFO Subscribed to gh/v1/greenhouse/ingress/node/+/telemetry",
            "INFO Subscribed to gh/v1/greenhouse/ingress/gateway/+/+/frame",
            "ERROR MQTT simplified Relay subscribe failed topic=x rc=1",
        ]
    )

    with pytest.raises(executor.StopExecution) as error:
        executor.analyze_postrestart_logs(logs, "greenhouse")

    assert error.value.operation == "T1_MANAGER_SUBSCRIPTION_POSTCHECK"


def test_package_contains_exactly_one_manager_restart_callsite() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert source.count("docker restart --time 10 ") == 1
    assert source.count("docker restart ") == 1
    assert "docker stop " not in source
    assert "docker start " not in source
    assert "docker rm " not in source
    assert "addRoleACL" not in source
    assert "removeRoleACL" not in source


def test_manifest_freezes_no_retry_and_no_broker_or_dynsec_mutation() -> None:
    manifest = json.loads(
        (
            MODULE_PATH.parent / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["live_reactivation_contract"]["manager_restart_command_count"] == 1
    assert manifest["forbidden"]["automatic_retry"] is True
    assert manifest["forbidden"]["automatic_rollback"] is True
    assert manifest["forbidden"]["broker_restart"] is True
    assert manifest["forbidden"]["dynsec_mutation"] is True
    assert manifest["forbidden"]["mqtt_test_publish"] is True
    assert manifest["forbidden"]["application_topic_subscriber"] is True
