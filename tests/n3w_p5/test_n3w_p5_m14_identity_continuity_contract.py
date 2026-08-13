from __future__ import annotations

import json
import sys
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANAGER_SRC = ROOT / "host/greenhouse-manager/src"
sys.path.insert(0, str(MANAGER_SRC))

HomeAssistantDiscovery = import_module(
    "greenhouse_manager.runtime.ha_discovery"
).HomeAssistantDiscovery

PLAN = ROOT / "docs/decisions/n3w-p5-m14-identity-continuity-host-only-plan.json"
MATRIX = ROOT / "docs/decisions/n3w-p5-two-board-isolated-e2e-execution-plan.json"
WORKFLOW = ROOT / ".github/workflows/n3w-p5-m14-identity-continuity-host-only-ci.yml"

SYSTEM_ID = "n3wp5lab"
NODE_ID = "n3wp5_child01"
DEVICE_IDENTIFIER = f"gh_{SYSTEM_ID}_{NODE_ID}"


def _canonical_document(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "schema": "gh.telemetry/1",
        "node_id": NODE_ID,
        "boot_id": "boot_077d07249ff2a19f",
        "seq": 100,
        "uptime_ms": 1000,
        "received_at": "2026-08-08T15:08:47.896Z",
        "cap_hash": "n3wp5lab01",
        "fw_version": "N3W-P5-LAB",
        "measurements": {"air_temperature_c": 25.0},
        "quality": {"air_temperature_c": "ok"},
        "power": {"source": "main", "low": False},
    }
    document.update(overrides)
    return document


def _identity_projection(messages: tuple[Any, ...]) -> dict[str, object]:
    assert len(messages) == 2
    device_message, connectivity_message = messages
    device_payload = device_message.payload
    connectivity_payload = connectivity_message.payload
    component_unique_ids = {
        component["unique_id"] for component in device_payload["components"].values()
    }
    component_unique_ids.add(connectivity_payload["unique_id"])
    return {
        "topics": (device_message.topic, connectivity_message.topic),
        "device_identifiers": tuple(device_payload["device"]["identifiers"]),
        "serial_number": device_payload["device"]["serial_number"],
        "state_topic": device_payload["state_topic"],
        "availability_topic": device_payload["availability"][0]["topic"],
        "unique_ids": tuple(sorted(component_unique_ids)),
    }


def _audit_registry(
    devices: list[dict[str, object]],
    entities: list[dict[str, object]],
) -> dict[str, object]:
    matching_devices = [
        device
        for device in devices
        if device.get("serial_number") == NODE_ID
        or ["mqtt", DEVICE_IDENTIFIER] in device.get("identifiers", [])
    ]
    if len(matching_devices) != 1:
        raise ValueError("NODE_ID must map to exactly one device")

    device_id = matching_devices[0]["id"]
    node_entities = [
        entity
        for entity in entities
        if str(entity.get("unique_id", "")).startswith(f"{NODE_ID}_")
    ]
    if not node_entities or any(
        entity.get("device_id") != device_id for entity in node_entities
    ):
        raise ValueError("NODE_ID entities must bind to the one matching device")

    unique_ids = [str(entity["unique_id"]) for entity in node_entities]
    if len(unique_ids) != len(set(unique_ids)):
        raise ValueError("NODE_ID entity unique_ids must be duplicate-free")
    return {
        "device_count": 1,
        "entity_count": len(unique_ids),
        "unique_ids": tuple(sorted(unique_ids)),
    }


def test_m14_plan_is_exactly_host_only_and_final_gate_is_separate() -> None:
    document = json.loads(PLAN.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))

    expected_matrix = {
        "id": "M14",
        "name": "identity_continuity",
        "action": "compare HA device/entity registries before/after all path switches",
        "expect": "same NODE_ID maps to one device; no duplicate Discovery",
    }
    assert document["status"] == "host_only_contract_ready_live_execution_prohibited"
    assert document["base"] == {
        "repository": "chrenguo-stack/HomeAssistant",
        "branch": "main",
        "commit_sha": "ec2525a7f552dd87702b42624488098c60c2ed05",
        "tree_sha": "a3084f26d1c45885599f761da4979660c9387e9b",
    }
    assert document["matrix_contract"] == expected_matrix
    assert expected_matrix in matrix["matrix"]
    assert document["m13_dependency"]["classification"] == (
        "M13_PASS_WITH_RECORDED_EXECUTION_DEVIATION"
    )
    assert document["m13_dependency"]["outage_cap_deviation_preserved"] is True
    assert document["m13_dependency"]["live_replay_allowed"] is False
    assert document["change_scope"]["manager_product_runtime_change"] is False
    assert document["change_scope"]["homeassistant_configuration_change"] is False
    assert document["future_readonly_final_gate"]["authorized_now"] is False
    assert document["future_readonly_final_gate"]["repeat_path_switches"] is False
    assert document["next_gate"]["m14_live_allowed"] is False
    assert document["next_gate"]["phase_exit_or_cleanup_allowed"] is False


def test_all_path_histories_resolve_to_one_homeassistant_identity() -> None:
    histories = (
        {"active_transport": "direct", "gateway_id": None, "seq": 101},
        {"active_transport": "relay", "gateway_id": "n3wp5_relay01", "seq": 102},
        {
            "active_transport": "direct",
            "gateway_id": None,
            "boot_id": "boot_077d07249ff2a1a0",
            "seq": 0,
        },
        {
            "active_transport": "relay",
            "gateway_id": "n3wp5_relay01",
            "key_epoch": 1,
            "seq": 103,
        },
        {
            "active_transport": "relay",
            "gateway_id": "n3wp5_relay01",
            "key_epoch": 2,
            "seq": 104,
        },
        {
            "active_transport": "relay",
            "gateway_id": "n3wp5_relay01",
            "recovered_from_broker_outage": True,
            "seq": 105,
        },
    )

    projections = []
    for history in histories:
        discovery = HomeAssistantDiscovery(system_id=SYSTEM_ID)
        projections.append(
            _identity_projection(
                discovery.messages_for_telemetry(_canonical_document(**history))
            )
        )

    assert all(projection == projections[0] for projection in projections)
    assert projections[0]["topics"] == (
        f"homeassistant/device/{NODE_ID}/config",
        f"homeassistant/binary_sensor/{NODE_ID}_connectivity/config",
    )
    assert projections[0]["device_identifiers"] == (DEVICE_IDENTIFIER,)
    assert projections[0]["serial_number"] == NODE_ID
    assert (
        projections[0]["state_topic"] == f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/telemetry"
    )
    assert projections[0]["availability_topic"] == (
        f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/availability"
    )


def test_path_boot_sequence_gateway_and_epoch_changes_do_not_republish_discovery() -> (
    None
):
    discovery = HomeAssistantDiscovery(system_id=SYSTEM_ID)
    first = discovery.messages_for_telemetry(_canonical_document())
    assert len(first) == 2

    path_variants = (
        {"active_transport": "direct", "gateway_id": None, "seq": 106},
        {"active_transport": "relay", "gateway_id": "n3wp5_relay01", "seq": 107},
        {
            "active_transport": "relay",
            "gateway_id": "n3wp5_relay01",
            "boot_id": "boot_077d07249ff2a1a0",
            "seq": 0,
            "key_epoch": 2,
        },
    )
    for variant in path_variants:
        assert discovery.messages_for_telemetry(_canonical_document(**variant)) == ()


def test_manager_restart_and_payload_updates_reuse_the_same_identity() -> None:
    document = _canonical_document()
    before_restart = HomeAssistantDiscovery(system_id=SYSTEM_ID)
    after_restart = HomeAssistantDiscovery(system_id=SYSTEM_ID)

    before = before_restart.messages_for_telemetry(document)
    after = after_restart.messages_for_telemetry(document)
    assert _identity_projection(before) == _identity_projection(after)
    assert before[0].payload == after[0].payload
    assert before[1].payload == after[1].payload

    changed = deepcopy(document)
    changed["fw_version"] = "N3W-P5-LAB.2"
    changed["measurements"] = {
        "air_temperature_c": 25.0,
        "air_humidity_pct": 60.0,
    }
    republished = before_restart.messages_for_telemetry(changed)
    changed_projection = _identity_projection(republished)
    assert changed_projection["topics"] == _identity_projection(before)["topics"]
    assert changed_projection["device_identifiers"] == (DEVICE_IDENTIFIER,)
    assert changed_projection["serial_number"] == NODE_ID
    assert len(changed_projection["unique_ids"]) == len(
        set(changed_projection["unique_ids"])
    )


def test_registry_reconciliation_stays_single_and_duplicate_free() -> None:
    device = {
        "id": "device-1",
        "identifiers": [["mqtt", DEVICE_IDENTIFIER]],
        "serial_number": NODE_ID,
    }
    unique_ids = (
        f"{NODE_ID}_air_temperature_c",
        f"{NODE_ID}_connectivity",
        f"{NODE_ID}_firmware_version",
        f"{NODE_ID}_low_battery",
        f"{NODE_ID}_node_id",
        f"{NODE_ID}_power_source",
    )
    entities = [
        {"device_id": "device-1", "unique_id": unique_id} for unique_id in unique_ids
    ]

    before = _audit_registry([device], entities)
    after = _audit_registry([deepcopy(device)], deepcopy(entities))
    assert before == after
    assert after == {
        "device_count": 1,
        "entity_count": 6,
        "unique_ids": tuple(sorted(unique_ids)),
    }

    duplicate_device = {
        "id": "device-relay",
        "identifiers": [["mqtt", f"{DEVICE_IDENTIFIER}_relay"]],
        "serial_number": NODE_ID,
    }
    with pytest.raises(ValueError, match="exactly one device"):
        _audit_registry([device, duplicate_device], entities)

    with pytest.raises(ValueError, match="duplicate-free"):
        _audit_registry([device], [*entities, deepcopy(entities[0])])

    foreign_binding = deepcopy(entities)
    foreign_binding[0]["device_id"] = "device-relay"
    with pytest.raises(ValueError, match="one matching device"):
        _audit_registry([device], foreign_binding)


def test_historical_anchor_is_bound_without_inventing_missing_hash_pair() -> None:
    document = json.loads(PLAN.read_text(encoding="utf-8"))
    history = document["historical_registry_binding"]

    assert history["m01_device_count"] == 1
    assert history["m01_entity_count"] == 6
    assert history["m01_single_device_pass"] is True
    assert history["current_device_count"] == 1
    assert history["current_entity_count"] == 6
    assert history["current_device_created_at"] < "2026-08-08T15:08:47.896Z"
    assert history["current_entities_modified_after_initial_creation"] is False
    assert history["explicit_pre_m01_registry_hash_pair_discovered"] is False
    assert "do not manufacture" in history["claim_boundary"].lower()


def test_host_only_scope_contains_no_live_execution_tokens() -> None:
    changed = [PLAN, Path(__file__), WORKFLOW]
    forbidden = (
        "docker" + " stop",
        "docker" + " start",
        "docker" + " restart",
        "mosquitto" + "_pub",
        "mosquitto" + "_sub",
        "esphome" + " run",
        "esp" + "tool",
        "/dev/" + "cu.",
        "/dev/" + "tty",
        "192." + "168.68.",
    )
    for path in changed:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text
