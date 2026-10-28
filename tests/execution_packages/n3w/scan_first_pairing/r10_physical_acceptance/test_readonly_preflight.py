from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = (
    ROOT
    / "tools/execution_packages/n3w/scan_first_pairing/"
      "r10_physical_acceptance/readonly_preflight.py"
)
spec = importlib.util.spec_from_file_location("r10_readonly_preflight", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def good_t1() -> dict:
    active = {"active": "active", "load_state": "loaded", "result": "success"}
    container = {
        "ok": True,
        "count": 1,
        "id_sha256": "a" * 64,
        "image": "local/test",
        "restart_count": 0,
        "started_at": "2026-10-28T00:00:00Z",
    }
    manager = {
        **container,
        "pairing_disabled": True,
        "runtime_enabled": True,
        "advertised_host_auto": True,
    }
    return {
        "services": {
            "broker_activation": dict(active),
            "services_activation": dict(active),
            "broker_guard": dict(active),
            "registration_guard": dict(active),
        },
        "containers": {
            "broker": dict(container),
            "manager": manager,
            "homeassistant": dict(container),
        },
        "trusted_lan": {
            "ok": True,
            "interface": "eth0",
            "subnet_sha256": "b" * 64,
            "available": True,
        },
        "listeners": {
            "47110_tcp": 1,
            "47111_udp": 1,
            "47112_tcp": 0,
        },
        "manager_capabilities": {
            "ok": True,
            "ttl_1800": True,
            "transaction_service": True,
            "registration_runtime": True,
            "identity_bound_window": True,
        },
        "database": {
            "ok": True,
            "first_registration_by_state": {},
            "unresolved_first_registration": 0,
            "current_registration_count": 0,
        },
        "pairing_window": {
            "ok": True,
            "state": "CLOSED",
            "raw_locator_in_output": False,
        },
    }


def test_frozen_r9_authority() -> None:
    assert module.R9_SOURCE_HEAD == "e299c937a7b89bb8a7b9a7432186ba46a416cd44"
    assert module.R9_BUILD_HEAD == "d6c3e09464c7bcb8e30bdcbbc7a1cdc8fbcec303"
    assert module.R9_ARTIFACT_ID == 12783234959
    assert module.OUTER_SHA256 == (
        "6b31001da3a4dff44f8c8cf605b885bcafcfd084d35969351938aa4904cc9995"
    )
    assert module.EXPECTED_MEMBERS["firmware.factory.bin"] == (
        1525680,
        "b734c343b3caf725c3991e6dc408b471a607f0c10cfe641346a78228b65c3bbf",
    )


def test_readonly_surface_has_no_flash_or_erase_command() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    for token in (
        '"write-flash"',
        "'write-flash'",
        '"erase-flash"',
        "'erase-flash'",
        '"erase-region"',
        "'erase-region'",
    ):
        assert token not in source

    parser = module.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["write"])
    with pytest.raises(SystemExit):
        parser.parse_args(["erase"])


def test_readonly_t1_probe_forbids_mutating_operations() -> None:
    probe = module.T1_PROBE
    for forbidden in (
        "docker restart",
        "docker rm",
        "docker compose up",
        "force-recreate",
        "systemctl restart",
        "systemctl stop",
        "systemctl start",
        "sqlite3.connect(path)",
    ):
        assert forbidden not in probe
    assert "mode=ro&immutable=1" in probe
    assert 'greenhouse-manager-pairing", "window-status"' in probe


def test_t1_ssh_requires_pretrusted_host_key() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert '"StrictHostKeyChecking=yes"' in source


def test_t1_happy_path_passes() -> None:
    assert module.accept_t1(good_t1()) == []


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda d: d["listeners"].__setitem__("47112_tcp", 1),
            "listener:47112_not_idle_closed",
        ),
        (
            lambda d: d["database"].__setitem__("unresolved_first_registration", 1),
            "manager:predecessor_unresolved",
        ),
        (
            lambda d: d["pairing_window"].__setitem__("state", "OPEN"),
            "manager:pairing_window_not_closed",
        ),
        (
            lambda d: d["trusted_lan"].__setitem__("ok", False),
            "trusted_lan",
        ),
        (
            lambda d: d["manager_capabilities"].__setitem__("ok", False),
            "manager:scan_first_registration_capability",
        ),
    ],
)
def test_t1_fail_closed(mutator, expected: str) -> None:
    doc = good_t1()
    mutator(doc)
    assert expected in module.accept_t1(doc)


def test_hardware_identity_is_public_hash_only() -> None:
    raw = ":".join(("12", "34", "56", "78", "9a", "bc"))
    expected = module.sha256_bytes(("ghw-c6-" + raw.replace(":", "")).encode())
    assert module.hardware_hash_from_mac(raw) == expected


def test_direct_factory_route_requires_clean_phy_and_r9_app1_source_contract() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "direct_factory_route_eligible = phy_all_ff and app1_matches" in source
    assert "current_partition_table_not_r9_compatible" in source
    assert "app1-full-slot-prewrite.bin" in source
    assert "nvs-prewrite.bin" in source
    assert "factory-covered-range-prewrite.bin" in source


def test_private_evidence_directory_contract(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    result = module.evidence_root(root)
    assert result == root.resolve()
    assert (result.stat().st_mode & 0o777) == 0o700

    (result / "already-present").write_text("x", encoding="utf-8")
    with pytest.raises(module.StopExecution):
        module.evidence_root(result)


def test_private_file_mode(tmp_path: Path) -> None:
    target = tmp_path / "private.json"
    module.write_private_json(target, {"ok": True})
    assert (target.stat().st_mode & 0o777) == 0o600


def test_confirmation_is_explicit_and_write_authorization_not_consumed() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert module.PREFLIGHT_CONFIRMATION == "R10 READONLY PREFLIGHT: YES"
    assert '"write_authorization_consumed": False' in source
    assert '"flash_write": False' in source
    assert '"nvs_write": False' in source
    assert '"t1_mutation": False' in source
