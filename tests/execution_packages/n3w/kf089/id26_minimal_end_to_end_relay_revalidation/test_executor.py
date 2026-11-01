from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[5]
    / "tools/execution_packages/n3w/kf089/"
    "id26_minimal_end_to_end_relay_revalidation/executor.py"
)
SPEC = importlib.util.spec_from_file_location("id26_executor", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
executor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(executor)


def runtime_item(
    *,
    cid: str,
    image: str,
    started_at: str,
    restart_count: int = 0,
) -> dict:
    return {
        "Id": cid,
        "RestartCount": restart_count,
        "Config": {"Image": image},
        "State": {"Running": True, "StartedAt": started_at},
    }


def test_relay_parser_counts_one_unique_route_with_multiple_accepts() -> None:
    logs = "\n".join(
        [
            "2026-09-14T00:00:01Z Accepted simplified N3-W telemetry source=relay node=node-b gateway=node-a key=k1",
            "2026-09-14T00:00:02Z Accepted simplified N3-W telemetry source=relay node=node-b gateway=node-a key=k2",
            "2026-09-14T00:00:03Z Rejected simplified N3-W ingress source=relay node=node-b gateway=node-a code=example",
        ]
    )

    result = executor.parse_relay_logs(logs)

    assert result["accepted_relay_count"] == 2
    assert result["rejected_relay_count"] == 1
    assert result["unique_accepted_relay_route_count"] == 1
    assert result["accepted_routes_private"] == [
        {"node": "node-b", "gateway": "node-a"}
    ]


def test_relay_parser_detects_multiple_accepted_routes() -> None:
    logs = "\n".join(
        [
            "Accepted simplified N3-W telemetry source=relay node=node-b gateway=node-a key=k1",
            "Accepted simplified N3-W telemetry source=relay node=node-c gateway=node-a key=k2",
        ]
    )

    result = executor.parse_relay_logs(logs)

    assert result["accepted_relay_count"] == 2
    assert result["unique_accepted_relay_route_count"] == 2


def test_relay_parser_accepts_zero_baseline() -> None:
    result = executor.parse_relay_logs("INFO unrelated direct telemetry\n")

    assert result["accepted_relay_count"] == 0
    assert result["unique_accepted_relay_route_count"] == 0


def test_runtime_stability_accepts_identical_manager_and_broker() -> None:
    manager = runtime_item(
        cid="m" * 64,
        image="greenhouse-manager:fc4",
        started_at="2026-09-14T01:00:00Z",
    )
    broker = runtime_item(
        cid="b" * 64,
        image="local/mosquitto:test",
        started_at="2026-09-14T00:30:00Z",
    )

    result = executor.runtime_stability(manager, broker, dict(manager), dict(broker))

    assert result == {
        "manager_runtime_stable": True,
        "broker_runtime_stable": True,
    }


def test_runtime_stability_rejects_manager_restart() -> None:
    manager = runtime_item(
        cid="m" * 64,
        image="greenhouse-manager:fc4",
        started_at="2026-09-14T01:00:00Z",
    )
    broker = runtime_item(
        cid="b" * 64,
        image="local/mosquitto:test",
        started_at="2026-09-14T00:30:00Z",
    )
    restarted_manager = runtime_item(
        cid="m" * 64,
        image="greenhouse-manager:fc4",
        started_at="2026-09-14T01:10:00Z",
        restart_count=1,
    )

    with pytest.raises(executor.StopExecution) as error:
        executor.runtime_stability(manager, broker, restarted_manager, broker)

    assert error.value.operation == "T1_RUNTIME_POSTCHECK"


def test_manifest_freezes_single_power_window_and_no_host_board_access() -> None:
    manifest = json.loads(
        (MODULE_PATH.parent / "manifest.json").read_text(encoding="utf-8")
    )
    contract = manifest["live_revalidation_contract"]
    forbidden = manifest["forbidden"]

    assert contract["board_b_power_window_count"] == 1
    assert contract["board_b_power_window_min_seconds"] == 180
    assert contract["prewindow_quiescence_seconds"] == 10
    assert contract["prewindow_accepted_relay_count_required"] == 0
    assert contract["window_accepted_relay_count_min"] == 1
    assert contract["window_unique_accepted_relay_route_count"] == 1

    assert forbidden["board_a_usb_access"] is True
    assert forbidden["board_b_usb_access"] is True
    assert forbidden["serial_open"] is True
    assert forbidden["manager_restart"] is True
    assert forbidden["broker_restart"] is True
    assert forbidden["dynsec_mutation"] is True
    assert forbidden["mqtt_test_publish"] is True
    assert forbidden["mqtt_extra_subscriber"] is True
    assert forbidden["automatic_retry"] is True


def test_executor_contains_no_restart_publish_subscribe_or_board_usb_callsite() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8").lower()

    assert "docker restart " not in source
    assert "docker stop " not in source
    assert "docker start " not in source
    assert "docker rm " not in source
    assert "mosquitto_pub" not in source
    assert "mosquitto_sub" not in source
    assert "esptool" not in source
    assert "/dev/cu." not in source
