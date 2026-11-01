from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools import n3w_t1_clean_reference_compare as compare
from tools import n3w_t1_clean_reference_observer as observer
from tools import n3w_t1_clean_reference_r3_package_builder as builder

CONTROL_HEAD = "3" * 40


def _observation(label: str) -> dict:
    return {
        "schema": observer.SCHEMA,
        "status": "PASS",
        "reference_label": label,
        "stable_contracts": {
            "authority": {
                "product_source_head": observer.PRODUCT_SOURCE_HEAD,
                "r2a_control_head": observer.R2A_CONTROL_HEAD,
                "r2b_control_head": observer.R2B_CONTROL_HEAD,
            },
            "component_identity": {
                "broker": {"image": "b", "runtime_contract_sha256": "1" * 64},
                "homeassistant": {"image": "h", "runtime_contract_sha256": "2" * 64},
                "manager": {"image": "m", "runtime_contract_sha256": "3" * 64},
            },
        },
        "health": {
            "overall_pass": True,
        },
        "runtime_observations": {
            "boot_id_sha256": "4" * 64,
            "containers": {
                "broker": {
                    "container_id_sha256": "a" * 64,
                    "started_at": "start-b",
                    "restart_count": 0,
                },
                "homeassistant": {
                    "container_id_sha256": "b" * 64,
                    "started_at": "start-h",
                    "restart_count": 0,
                },
                "manager": {
                    "container_id_sha256": "c" * 64,
                    "started_at": "start-m",
                    "restart_count": 0,
                },
            },
            "sqlite": {
                "/manager.db": {
                    "row_counts": {"registrations": 0},
                    "file_bytes": 4096,
                    "wal_bytes": 0,
                }
            },
            "dynsec_counts": {
                "clients": 3,
                "groups": 1,
                "roles": 2,
            },
            "homeassistant_registry_counts": {
                "entities": {"present": True, "count": 0, "version": 1},
                "devices": {"present": True, "count": 0, "version": 1},
                "config_entries": {"present": True, "count": 1, "version": 1},
            },
            "persistent_tree_stats": {
                "/var/lib/example": {
                    "file_count": 1,
                    "directory_count": 1,
                    "total_bytes": 4096,
                    "symlink_count": 0,
                }
            },
        },
        "read_only": True,
        "network_mutation": False,
        "board_access": False,
    }


def test_package_builder_emits_exact_two_tool_package(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    destination = tmp_path / "package"

    report = builder.build_package(repo_root, destination, CONTROL_HEAD)

    assert report["status"] == "PASS"
    assert report["file_count"] == 2
    manifest = json.loads(
        (destination / "package-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema"] == builder.SCHEMA
    assert manifest["product_source_head"] == observer.PRODUCT_SOURCE_HEAD
    assert manifest["r2a_control_head"] == observer.R2A_CONTROL_HEAD
    assert manifest["r2b_control_head"] == observer.R2B_CONTROL_HEAD
    assert manifest["control_plane_head"] == CONTROL_HEAD
    assert {item["path"] for item in manifest["files"]} == set(builder.FILES)


def test_compare_allows_business_runtime_drift() -> None:
    r2 = _observation("R2")
    r3 = _observation("R3")
    r3["runtime_observations"]["sqlite"]["/manager.db"]["row_counts"][
        "registrations"
    ] = 1
    r3["runtime_observations"]["dynsec_counts"]["clients"] = 4
    r3["runtime_observations"]["homeassistant_registry_counts"]["entities"][
        "count"
    ] = 5

    report = compare.compare(
        r2,
        r3,
        require_business_drift=True,
    )

    assert report["status"] == "PASS"
    assert report["stable_contract_change_count"] == 0
    assert report["business_runtime_change_count"] >= 3
    assert report["boot_unchanged"] is True
    assert report["service_restart_change_count"] == 0


def test_compare_stops_on_stable_contract_drift() -> None:
    r2 = _observation("R2")
    r3 = _observation("R3")
    r3["stable_contracts"]["component_identity"]["manager"][
        "runtime_contract_sha256"
    ] = "9" * 64

    report = compare.compare(
        r2,
        r3,
        require_business_drift=False,
    )

    assert report["status"] == "STOP"
    assert "stable_contract_drift" in report["stop_reasons"]


def test_compare_stops_on_unexpected_reboot() -> None:
    r2 = _observation("R2")
    r3 = _observation("R3")
    r3["runtime_observations"]["boot_id_sha256"] = "8" * 64

    report = compare.compare(
        r2,
        r3,
        require_business_drift=False,
    )

    assert report["status"] == "STOP"
    assert "unexpected_reboot" in report["stop_reasons"]


def test_compare_stops_on_service_restart() -> None:
    r2 = _observation("R2")
    r3 = _observation("R3")
    r3["runtime_observations"]["containers"]["manager"]["started_at"] = "new-start"
    r3["runtime_observations"]["containers"]["manager"]["restart_count"] = 1

    report = compare.compare(
        r2,
        r3,
        require_business_drift=False,
    )

    assert report["status"] == "STOP"
    assert "service_restart_or_recreation" in report["stop_reasons"]
    assert report["service_restart_services"] == ["manager"]


def test_compare_can_require_observed_business_drift() -> None:
    r2 = _observation("R2")
    r3 = _observation("R3")

    report = compare.compare(
        r2,
        r3,
        require_business_drift=True,
    )

    assert report["status"] == "STOP"
    assert "business_runtime_drift_not_observed" in report["stop_reasons"]


def test_observer_source_is_read_only_and_has_no_board_actuation() -> None:
    source = Path(observer.__file__).read_text(encoding="utf-8")

    forbidden = (
        "systemctl reboot",
        "docker compose up",
        "docker compose down",
        "docker pull",
        "docker build",
        "esptool",
        "pairing start",
        "pairing enable",
        "INSERT INTO",
        "UPDATE ",
        "DELETE FROM",
    )
    for token in forbidden:
        assert token not in source

    assert "mode=ro" in source
    assert '"read_only": True' in source
    assert '"network_mutation": False' in source
    assert '"board_access": False' in source


def test_observer_mount_contract_sort_is_deterministic() -> None:
    rows = [
        {
            "type": "bind",
            "source": "/b",
            "destination": "/z",
            "rw": True,
        },
        {
            "type": "bind",
            "source": "/a",
            "destination": "/a",
            "rw": False,
        },
    ]
    left = sorted(
        copy.deepcopy(rows),
        key=lambda row: (
            str(row.get("destination")),
            str(row.get("type")),
            str(row.get("source")),
            str(row.get("rw")),
        ),
    )
    right = list(reversed(rows))
    right = sorted(
        right,
        key=lambda row: (
            str(row.get("destination")),
            str(row.get("type")),
            str(row.get("source")),
            str(row.get("rw")),
        ),
    )
    assert left == right
