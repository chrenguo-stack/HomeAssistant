from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import n3w_t1_clean_reference_pairing_readiness_bridge as bridge
from tools import (
    n3w_t1_clean_reference_pairing_readiness_bridge_package_builder as builder,
)

CONTROL_HEAD = "7" * 40


def _runtime() -> dict:
    return {
        "boot_id_sha256": "1" * 64,
        "containers": {
            "broker": {
                "container_id_sha256": "a" * 64,
                "started_at": "b-start",
                "restart_count": 0,
            },
            "homeassistant": {
                "container_id_sha256": "b" * 64,
                "started_at": "h-start",
                "restart_count": 0,
            },
            "manager": {
                "container_id_sha256": "c" * 64,
                "started_at": "m-start",
                "restart_count": 0,
            },
        },
        "sqlite": {
            "/manager.db": {
                "row_counts": {
                    "registrations": 0,
                    "pairing_sessions": 0,
                },
                "file_bytes": 4096,
                "wal_bytes": 0,
            }
        },
        "dynsec_counts": {
            "clients": 4,
            "groups": 1,
            "roles": 10,
        },
        "homeassistant_registry_counts": {
            "entities": {"present": True, "count": 14, "version": 1},
            "devices": {"present": True, "count": 3, "version": 3},
            "config_entries": {"present": True, "count": 6, "version": 1},
        },
        "mqtt_session": {
            "manager": {
                "count": 1,
                "identity_sha256": "d" * 64,
                "authenticated_event_count": 1,
                "fingerprint": "e" * 64,
            },
            "homeassistant": {
                "count": 1,
                "identity_sha256": "f" * 64,
                "authenticated_event_count": 5,
                "fingerprint": "0" * 64,
            },
        },
        "persistent_tree_stats": {
            "/state": {
                "file_count": 1,
                "directory_count": 1,
                "total_bytes": 100,
                "symlink_count": 0,
            }
        },
    }


def _reference() -> dict:
    return {
        "schema": "gh.n3w-t1-clean-reference-observation/1",
        "status": "PASS",
        "reference_label": "R2",
        "stable_contracts": {
            "authority": {
                "product_source_head": bridge.PRODUCT_SOURCE_HEAD,
                "r2a_control_head": bridge.R2A_CONTROL_HEAD,
                "r2b_control_head": bridge.R2B_CONTROL_HEAD,
                "r2a_transaction_sha256": "2" * 64,
                "r2b_transaction_sha256": "3" * 64,
            },
            "component_identity": {
                "broker": {"image": "broker"},
                "homeassistant": {"image": "ha"},
                "manager": {"image": "manager"},
            },
        },
        "health": {
            "overall_pass": True,
            "failed_unit_count": 0,
        },
        "runtime_observations": _runtime(),
        "read_only": True,
        "network_mutation": False,
        "board_access": False,
    }


def _test_private_writer(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _relax_runner_root_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_read_json = bridge._read_json

    def relaxed_read_json(path: Path, *, mode: int | None = None) -> dict:
        return real_read_json(path, mode=None)

    monkeypatch.setattr(bridge, "_read_json", relaxed_read_json)


def _preflight() -> dict:
    return {
        "manifest": {
            "control_plane_head": CONTROL_HEAD,
        },
        "transactions": {
            "r2a_transaction_sha256": "2" * 64,
            "r2b_transaction_sha256": "3" * 64,
        },
        "identity": {
            "release_id": bridge.PRODUCT_SOURCE_HEAD,
            "host_instance_id": "t1h-example",
            "system_id": "system-example",
            "host_instance_id_sha256": "4" * 64,
            "system_id_sha256": "5" * 64,
        },
        "current": _reference(),
    }


def test_package_builder_emits_bridge_and_exact_observer(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    destination = tmp_path / "package"

    report = builder.build_package(repo_root, destination, CONTROL_HEAD)

    assert report["status"] == "PASS"
    assert report["file_count"] == 2
    manifest = json.loads(
        (destination / "package-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema"] == builder.SCHEMA
    assert manifest["product_source_head"] == bridge.PRODUCT_SOURCE_HEAD
    assert manifest["r2a_control_head"] == bridge.R2A_CONTROL_HEAD
    assert manifest["r2b_control_head"] == bridge.R2B_CONTROL_HEAD
    assert (
        manifest["r3_observer_control_head"]
        == bridge.R3_OBSERVER_CONTROL_HEAD
    )
    assert manifest["r2_reference_sha256"] == bridge.R2_REFERENCE_SHA256
    assert manifest["control_plane_head"] == CONTROL_HEAD
    assert {row["path"] for row in manifest["files"]} == set(builder.FILES)


def test_relevant_runtime_ignores_persistent_size_but_not_business_state() -> None:
    baseline = _reference()
    current = _reference()

    current["runtime_observations"]["persistent_tree_stats"]["/state"][
        "total_bytes"
    ] = 9999

    assert bridge._relevant_runtime(current) == bridge._relevant_runtime(baseline)

    current["runtime_observations"]["sqlite"]["/manager.db"]["row_counts"][
        "registrations"
    ] = 1

    assert bridge._relevant_runtime(current) != bridge._relevant_runtime(baseline)


def test_factory_document_is_standard_compatible_and_provenance_bound() -> None:
    document = bridge._factory_document(_preflight())

    assert document["schema"] == "gh.n3w.t1-factory-accepted/1"
    assert document["status"] == "PASS"
    assert document["factory_accepted"] is True
    assert document["release_id"] == bridge.PRODUCT_SOURCE_HEAD
    assert document["host_instance_id"] == "t1h-example"
    assert document["system_id"] == "system-example"
    assert document["system_id_sha256"] == "5" * 64
    assert document["acceptance_route"] == "clean_reference_r2_bridge_v1"
    assert document["r2_reference_sha256"] == bridge.R2_REFERENCE_SHA256
    assert document["r2a_transaction_sha256"] == "2" * 64
    assert document["r2b_transaction_sha256"] == "3" * 64
    assert document["bridge_control_head"] == CONTROL_HEAD


def test_apply_consumes_one_shot_and_finishes_factory_accepted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provisioning = tmp_path / "provisioning"
    provisioning.mkdir()
    state_root = tmp_path / "bridge-state"
    transaction = state_root / "transaction.json"
    marker = provisioning / "FACTORY_ACCEPTED.json"

    monkeypatch.setattr(bridge, "PROVISIONING_ROOT", provisioning)
    monkeypatch.setattr(bridge, "FACTORY_ACCEPTED", marker)
    monkeypatch.setattr(bridge, "BRIDGE_ROOT", state_root)
    monkeypatch.setattr(bridge, "BRIDGE_TRANSACTION", transaction)
    _relax_runner_root_metadata(monkeypatch)
    monkeypatch.setattr(bridge, "_preflight", lambda *_args: _preflight())
    monkeypatch.setattr(
        bridge,
        "_create_bridge_root",
        lambda: state_root.mkdir(),
    )
    monkeypatch.setattr(bridge, "_atomic_private_json", _test_private_writer)
    monkeypatch.setattr(bridge, "_baseline", lambda _path: _reference())
    monkeypatch.setattr(
        bridge,
        "_current_reference",
        lambda _root, _baseline: _reference(),
    )
    monkeypatch.setattr(
        bridge,
        "_onboarding_inspect",
        lambda: {
            "status": "PASS",
            "operation": "inspect",
            "factory_accepted": True,
            "transaction_present": False,
            "successor_recovery_present": False,
            "mutation": False,
            "pairing_udp_listener_count": 0,
            "pairing_http_listener_count": 0,
            "pairing_window_state": "CLOSED",
            "raw_locator_in_output": False,
        },
    )

    report = bridge.apply(
        tmp_path,
        tmp_path / "r2-reference.json",
        bridge.CONFIRMATION,
        bridge.AUTHORIZATION_PREFIX + "TEST_01",
    )

    assert report["status"] == "PASS"
    assert report["state"] == "FACTORY_ACCEPTED"
    assert report["authorization_consumed"] is True
    assert report["authorization_replay_allowed"] is False
    assert report["factory_accepted"] is True
    assert report["first_pairing_inspect_passed"] is True
    assert report["pairing_window_state"] == "CLOSED"
    assert report["service_restart"] is False
    assert report["network_mutation"] is False
    assert report["board_access"] is False

    marker_document = json.loads(marker.read_text(encoding="utf-8"))
    assert marker_document["acceptance_route"] == "clean_reference_r2_bridge_v1"

    transaction_document = json.loads(transaction.read_text(encoding="utf-8"))
    assert transaction_document["stage"] == "FACTORY_ACCEPTED"
    assert transaction_document["authorization_consumed"] is True
    assert transaction_document["authorization_replay_allowed"] is False


def test_apply_rolls_marker_back_when_standard_inspect_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provisioning = tmp_path / "provisioning"
    provisioning.mkdir()
    state_root = tmp_path / "bridge-state"
    transaction = state_root / "transaction.json"
    marker = provisioning / "FACTORY_ACCEPTED.json"

    monkeypatch.setattr(bridge, "PROVISIONING_ROOT", provisioning)
    monkeypatch.setattr(bridge, "FACTORY_ACCEPTED", marker)
    monkeypatch.setattr(bridge, "BRIDGE_ROOT", state_root)
    monkeypatch.setattr(bridge, "BRIDGE_TRANSACTION", transaction)
    _relax_runner_root_metadata(monkeypatch)
    monkeypatch.setattr(bridge, "_preflight", lambda *_args: _preflight())
    monkeypatch.setattr(
        bridge,
        "_create_bridge_root",
        lambda: state_root.mkdir(),
    )
    monkeypatch.setattr(bridge, "_atomic_private_json", _test_private_writer)
    monkeypatch.setattr(
        bridge,
        "_onboarding_inspect",
        lambda: (_ for _ in ()).throw(bridge.BridgeError("inspect_failed")),
    )
    monkeypatch.setattr(bridge, "_fsync_directory", lambda _path: None)

    with pytest.raises(bridge.BridgeError, match="inspect_failed"):
        bridge.apply(
            tmp_path,
            tmp_path / "r2-reference.json",
            bridge.CONFIRMATION,
            bridge.AUTHORIZATION_PREFIX + "TEST_02",
        )

    assert marker.exists() is False
    transaction_document = json.loads(transaction.read_text(encoding="utf-8"))
    assert transaction_document["stage"] == "STOPPED_ROLLED_BACK"
    assert transaction_document["authorization_consumed"] is True
    assert transaction_document["authorization_replay_allowed"] is False
    assert transaction_document["marker_rollback_proven"] is True


def test_preexisting_bridge_state_blocks_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "bridge-state"
    state_root.mkdir()
    monkeypatch.setattr(bridge, "BRIDGE_ROOT", state_root)
    monkeypatch.setattr(bridge.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        bridge,
        "_package",
        lambda _root: {"control_plane_head": CONTROL_HEAD},
    )

    with pytest.raises(bridge.BridgeError, match="bridge_transaction_already_claimed"):
        bridge._preflight(tmp_path, tmp_path / "r2-reference.json")


def test_clean_security_state_is_required() -> None:
    bridge._require_clean_security_state(
        {
            "credential_assignments": 0,
            "peer_trust_records": 0,
            "application_key_active_nodes": 0,
            "application_key_epochs": 0,
        }
    )

    with pytest.raises(bridge.BridgeError, match="first_pair_security_state_not_clean"):
        bridge._require_clean_security_state(
            {
                "credential_assignments": 1,
                "peer_trust_records": 0,
                "application_key_active_nodes": 0,
                "application_key_epochs": 0,
            }
        )


def test_authorization_contract_is_bounded() -> None:
    valid = bridge.AUTHORIZATION_PREFIX + "HOST_MARKER_20261101_01"
    assert bridge._authorization(valid) == valid

    with pytest.raises(bridge.BridgeError, match="authorization_id_invalid"):
        bridge._authorization("OTHER_AUTHORIZATION")


def test_bridge_source_cannot_reboot_restart_pair_or_touch_board() -> None:
    source = Path(bridge.__file__).read_text(encoding="utf-8")

    forbidden = (
        "systemctl reboot",
        "systemctl restart",
        "docker compose up",
        "docker compose down",
        "docker pull",
        "docker build",
        "esptool",
        "erase-region",
        "OPEN FIRST PAIRING WINDOW",
        "CLOSE FIRST PAIRING WINDOW",
    )

    for token in forbidden:
        assert token not in source

    assert '"inspect"' in source
    assert '"network_mutation": False' in source
    assert '"service_restart": False' in source
    assert '"board_access": False' in source
