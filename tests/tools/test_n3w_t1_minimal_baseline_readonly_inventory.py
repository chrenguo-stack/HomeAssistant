from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_minimal_baseline_readonly_inventory.py"


def load_tool():
    name = "n3w_t1_minimal_baseline_readonly_inventory"
    specification = importlib.util.spec_from_file_location(name, TOOL)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def sample_report() -> dict:
    return {
        "schema": "gh.n3w-t1-minimal-baseline-remote-inventory/1",
        "host_baseline": {
            "architecture": "aarch64",
            "os_release": {"ID": "armbian"},
            "ssh_active": "active",
            "networkmanager_active": "active",
            "docker_active": "active",
            "docker_compose_version": "2.40.0",
            "default_route_present": True,
            "dns_config_present": True,
            "ntp_synchronized": "yes",
            "root_free_bytes": 12_000_000_000,
        },
        "docker": {
            "containers": [],
            "images": [],
            "networks": [{"Name": "bridge"}, {"Name": "n3wfc4-private"}],
            "volumes": [{"Name": "n3wfc4_data"}, {"Name": "mystery_volume"}],
            "volume_inspect": [
                {
                    "Name": "n3wfc4_data",
                    "Labels": {"com.docker.compose.project": "n3wfc4"},
                },
                {"Name": "mystery_volume", "Labels": None},
            ],
        },
        "systemd": {
            "units": [
                {
                    "name": "n3wfc4-broker-ingress-guard.service",
                    "active": "active",
                    "enabled": "enabled",
                    "fragment_path": "/etc/systemd/system/n3wfc4-broker-ingress-guard.service",
                }
            ]
        },
        "product_paths": [
            {"path": "/etc/n3wfc4", "exists": True, "kind": "directory"},
            {"path": "/var/lib/n3wfc4-broker", "exists": False},
        ],
        "listeners": {"records": [], "error": ""},
        "firewall": [
            {
                "command": "iptables -S",
                "rc": 0,
                "relevant_lines": ["-A N3WFC4 -p tcp --dport 8883 -j ACCEPT"],
                "error": "",
            }
        ],
        "mutation_performed": False,
        "production_service_start": False,
        "board_access": False,
        "inventory_sha256": "a" * 64,
    }


def test_self_check_contains_no_mutating_remote_commands() -> None:
    tool = load_tool()
    result = tool.self_check()
    assert result["status"] == "PASS"
    assert result["forbidden_mutation_markers"] == []
    assert result["read_only"] is True
    assert result["mutation_performed"] is False


def test_classification_fail_closes_unknown_volume() -> None:
    tool = load_tool()
    classified = tool._classify(sample_report())

    candidates = classified["DELETE_PRODUCT_STATE_CANDIDATE"]
    unknown = classified["UNKNOWN_STOP"]

    assert any(item["name"] == "n3wfc4_data" for item in candidates)
    assert any(item["name"] == "/etc/n3wfc4" for item in candidates)
    assert any(item["name"] == "mystery_volume" for item in unknown)


def test_failed_firewall_read_is_unknown_stop() -> None:
    tool = load_tool()
    report = sample_report()
    report["firewall"][0] = {
        "command": "iptables -S",
        "rc": 1,
        "relevant_lines": [],
        "error": "permission denied",
    }

    classified = tool._classify(report)

    assert any(
        item["type"] == "firewall_visibility"
        for item in classified["UNKNOWN_STOP"]
    )


def test_collect_uses_ssh_n_and_hashes_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    report = sample_report()
    report["docker"]["volumes"] = [{"Name": "n3wfc4_data"}]
    report["docker"]["volume_inspect"] = [
        {
            "Name": "n3wfc4_data",
            "Labels": {"com.docker.compose.project": "n3wfc4"},
        }
    ]
    report["docker"]["networks"] = [{"Name": "n3wfc4-private"}]

    class Result:
        returncode = 0
        stdout = json.dumps(report)
        stderr = ""

    calls = []

    def fake_run(command, **_kwargs):
        calls.append(tuple(command))
        return Result()

    monkeypatch.setattr(tool, "_run", fake_run)
    result = tool.collect("operator@t1.example")

    assert calls[0][0:3] == ("ssh", "-n", "operator@t1.example")
    assert result["status"] == "PASS"
    assert result["target_sha256"] != "operator@t1.example"
    assert result["mutation_performed"] is False
    assert result["destructive_authorization_claimed"] is False
