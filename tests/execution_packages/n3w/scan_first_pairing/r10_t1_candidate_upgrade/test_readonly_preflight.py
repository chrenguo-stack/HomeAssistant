from __future__ import annotations

import importlib.util
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = (
    ROOT
    / "tools/execution_packages/n3w/scan_first_pairing/"
      "r10_t1_candidate_upgrade/readonly_preflight.py"
)
spec = importlib.util.spec_from_file_location("r10_t1_candidate_preflight", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _absent() -> dict:
    return {"exists": False}


def good_t1() -> dict:
    active = {
        "active": "active",
        "load_state": "loaded",
        "result": "success",
        "drop_in_paths_empty": True,
    }
    container = {
        "ok": True,
        "count": 1,
        "id_sha256": "a" * 64,
        "image_id_sha256": "b" * 64,
        "restart_count": 0,
        "started_at": "2026-10-28T00:00:00Z",
    }
    manager = {
        **container,
        "image": module.CURRENT_MANAGER_IMAGE,
        "manager_pairing_disabled": True,
        "manager_runtime_enabled": True,
        "manager_advertised_host_auto": True,
    }
    broker = {**container, "image": module.EXPECTED_BROKER_IMAGE}
    ha = {**container, "image": module.EXPECTED_HA_IMAGE}
    files = {
        "live_compose": {
            "exists": True,
            "git_blob_sha1": module.EXPECTED_CURRENT_BLOBS["compose"],
        },
        "services_unit": {
            "exists": True,
            "git_blob_sha1": module.EXPECTED_CURRENT_BLOBS["installed_services_unit"],
        },
        "dispatcher": {
            "exists": True,
            "git_blob_sha1": module.EXPECTED_CURRENT_BLOBS["dispatcher"],
        },
        "runtime_compose": {
            "exists": True,
            "git_blob_sha1": module.EXPECTED_CURRENT_BLOBS["compose"],
        },
        "runtime_services_unit": {
            "exists": True,
            "git_blob_sha1": module.EXPECTED_CURRENT_BLOBS["runtime_services_unit"],
        },
        "runtime_dispatcher": {
            "exists": True,
            "git_blob_sha1": module.EXPECTED_CURRENT_BLOBS["dispatcher"],
        },
    }
    for name in (
        "registration_unit",
        "registration_guard",
        "trusted_lan_authority",
        "registration_certificate",
        "registration_private_key",
        "runtime_registration_unit",
        "runtime_registration_guard",
        "runtime_trusted_lan_authority",
        "trusted_lan_state",
    ):
        files[name] = _absent()

    return {
        "services": {
            "broker_activation": dict(active),
            "services_activation": dict(active),
            "broker_guard": dict(active),
            "registration_guard": {
                "active": "inactive",
                "load_state": "not-found",
                "result": "success",
                "drop_in_paths_empty": True,
            },
        },
        "containers": {
            "broker": broker,
            "manager": manager,
            "homeassistant": ha,
        },
        "activation": {
            "env_ok": True,
            "compose_file": module.EXPECTED_COMPOSE_FILE,
            "compose_env_file": module.EXPECTED_COMPOSE_ENV_FILE,
            "compose_project": module.EXPECTED_COMPOSE_PROJECT,
            "compose_env_ok": True,
            "manager_image": module.CURRENT_MANAGER_IMAGE,
        },
        "files": files,
        "listeners": {
            "47110_tcp": 0,
            "47111_udp": 0,
            "47112_tcp": 0,
        },
        "pairing_window": {
            "ok": True,
            "state": "CLOSED",
            "raw_locator_in_output": False,
        },
        "networkmanager": {
            "ok": True,
            "connected": True,
            "subnet_sha256": "c" * 64,
        },
        "database": {
            "ok": True,
            "integrity": "ok",
            "table_names": ["registrations"],
            "table_names_sha256": "d" * 64,
            "registrations_table_present": True,
            "first_registration_table_present": False,
            "current_registration_count": 0,
            "mode": 0o600,
            "uid": 999,
            "gid": 999,
        },
        "candidate_image": {"present": False},
        "versions": {
            "docker": "Docker version test",
            "compose": "2.test",
            "systemd": "systemd test",
        },
        "root_free_bytes": module.MIN_FREE_BYTES + 1,
    }


def test_exact_source_and_image_binding() -> None:
    assert module.CURRENT_SOURCE_HEAD == (
        "03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6"
    )
    assert module.TARGET_SOURCE_HEAD == (
        "e299c937a7b89bb8a7b9a7432186ba46a416cd44"
    )
    assert module.CURRENT_MANAGER_IMAGE == (
        "local/greenhouse-manager:fresh-03dab2bd04e7"
    )
    assert module.TARGET_MANAGER_IMAGE == (
        "local/greenhouse-manager:fresh-e299c937a7b8"
    )


def test_remote_probe_is_valid_python() -> None:
    compile(module.T1_PROBE, "<r10-t1-candidate-probe>", "exec")


def test_readonly_surface_has_no_mutation_subcommand() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    for token in (
        '"systemctl", "stop"',
        '"systemctl", "start"',
        '"systemctl", "restart"',
        '"systemctl", "reload"',
        '"docker", "load"',
        '"docker", "rm"',
        '"docker", "create"',
        '"docker", "start"',
        '"docker", "stop"',
        '"docker", "compose", "up"',
        '"docker", "compose", "down"',
        '"docker", "compose", "stop"',
        "write_text(",
        "write_bytes(",
        "os.replace(",
        "os.rename(",
        "sqlite3.connect(" + '"file:"' + " + str(path)",
    ):
        if token.startswith("sqlite3.connect"):
            continue
        assert token not in module.T1_PROBE


def test_database_probe_is_readonly() -> None:
    probe = module.T1_PROBE
    assert "?mode=ro" in probe
    assert "PRAGMA query_only=ON" in probe
    assert "CREATE TABLE" not in probe
    assert "INSERT INTO" not in probe
    assert "UPDATE " not in probe
    assert "DELETE FROM" not in probe


def test_happy_predecessor_baseline_passes() -> None:
    assert module.accept_t1(good_t1()) == []


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda d: d["containers"]["manager"].__setitem__(
                "image", "local/greenhouse-manager:fresh-wrong"
            ),
            "manager:image_not_expected_predecessor",
        ),
        (
            lambda d: d["listeners"].__setitem__("47112_tcp", 1),
            "listener:47112_not_closed",
        ),
        (
            lambda d: d["database"].__setitem__(
                "first_registration_table_present", True
            ),
            "database:first_registration_predecessor_not_absent",
        ),
        (
            lambda d: d["candidate_image"].__setitem__("present", True),
            "candidate_image:preexisting",
        ),
        (
            lambda d: d["files"].__setitem__(
                "registration_private_key",
                {"exists": True, "regular": True},
            ),
            "predecessor_residue:registration_private_key",
        ),
        (
            lambda d: d.__setitem__("root_free_bytes", module.MIN_FREE_BYTES - 1),
            "storage:free_space",
        ),
    ],
)
def test_fail_closed_on_live_drift(mutator, expected: str) -> None:
    doc = good_t1()
    mutator(doc)
    assert expected in module.accept_t1(doc)


def test_current_runtime_file_blobs_are_frozen() -> None:
    assert module.EXPECTED_CURRENT_BLOBS == {
        "compose": "ce864b1964bdca10c4d16a8a7824b34b358ad119",
        "installed_services_unit": "e25f4553177c009bbe019c5cd8a9ddd3b0c07e46",
        "runtime_services_unit": "b070303a53b16b15aa108d3e9a2e952a7bc02d08",
        "dispatcher": "f733f5a1cfc936f77d1fabc383ccf262264e33d2",
    }


def test_target_runtime_file_blobs_are_frozen() -> None:
    assert module.EXPECTED_TARGET_BLOBS["compose"] == (
        "c9038251d9ba1b05a472edda14b287470690815a"
    )
    assert module.EXPECTED_TARGET_BLOBS["installed_services_unit"] == (
        "3485b6c2f9341fda2fcbd2c82c83077ad78cf42c"
    )
    assert module.EXPECTED_TARGET_BLOBS["runtime_services_unit"] == (
        "ee7c4151e79368e6daca5d6bd1359a846397fc95"
    )
    assert module.EXPECTED_TARGET_BLOBS["registration_unit"] == (
        "d8f1a3c6d757284c72b8348773d0bc09f6904b35"
    )
    assert module.EXPECTED_TARGET_BLOBS["registration_guard"] == (
        "ef5077b6bc80c73bc8d3f35cf7a33a198ce918c7"
    )
    assert module.EXPECTED_TARGET_BLOBS["trusted_lan_authority"] == (
        "ea964cd2b9b9380785f3aee5e8d6383180be4ee0"
    )


def test_private_evidence_directory_contract(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    result = module.evidence_root(root)
    assert result == root.resolve()
    assert stat.S_IMODE(result.stat().st_mode) == 0o700

    (result / "occupied").write_text("x", encoding="utf-8")
    with pytest.raises(module.StopExecution):
        module.evidence_root(result)


def test_installed_f4_and_runtime_generic_services_units_are_distinct() -> None:
    assert (
        module.EXPECTED_CURRENT_BLOBS["installed_services_unit"]
        != module.EXPECTED_CURRENT_BLOBS["runtime_services_unit"]
    )
    doc = good_t1()
    doc["files"]["services_unit"]["git_blob_sha1"] = (
        module.EXPECTED_CURRENT_BLOBS["runtime_services_unit"]
    )
    assert "file:installed_services_unit_drift" in module.accept_t1(doc)

    doc = good_t1()
    doc["files"]["runtime_services_unit"]["git_blob_sha1"] = (
        module.EXPECTED_CURRENT_BLOBS["installed_services_unit"]
    )
    assert "runtime_source:services_unit_drift" in module.accept_t1(doc)
