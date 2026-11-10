from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import n3w_t1_kf147_exact_ha_cleanup as cleanup


def sample_capture() -> dict:
    runtime = {
        "units": {
            "n3wfc4-broker-activation.service": {"ActiveState": "active", "NRestarts": "0"},
            "n3wfc4-services-activation.service": {"ActiveState": "active", "NRestarts": "0"},
        },
        "containers": {
            "broker": {"id": "b", "running": True, "restart_count": 0, "started_at": "1"},
            "manager": {"id": "m", "running": True, "restart_count": 0, "started_at": "2"},
            "homeassistant": {"id": "h", "running": True, "restart_count": 0, "started_at": "3"},
        },
        "transaction": {"sha256": cleanup.EXPECTED_U1_TRANSACTION_SHA256, "phase": "U1_PREPARE_REQUESTED"},
        "prepare": {"confirmation_required": True, "confirmation_consumed": False},
        "observed_mutable_allocated_bytes": 1,
    }
    return {
        "runtime": runtime,
        "live": {"transaction_sha256": cleanup.EXPECTED_U1_TRANSACTION_SHA256},
        "target": {
            "target": {
                "present": True,
                "id": cleanup.TARGET_IMAGE_ID,
                "repo_tags": [cleanup.TARGET_IMAGE_REF],
                "size_bytes": 5_000_000_000,
            },
            "target_container_references": [],
            "root_free_bytes": 589_463_552,
        },
    }


def test_exact_cleanup_authority_constants_match_handoff() -> None:
    assert cleanup.AUTHORIZATION_ID == "N3W_T1_KF147_EXACT_HA_2026_10_4_IMAGE_CLEANUP_20261110_01"
    assert cleanup.TARGET_IMAGE_REF == "local/n3w-homeassistant:2026.10.4-5881590f"
    assert cleanup.TARGET_IMAGE_ID == "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365"
    assert cleanup.RUNNING_HA_REF == "local/n3w-homeassistant:2026.10.0-0c73235a"
    assert cleanup.EXPECTED_U1_TRANSACTION_SHA256 == "6e1f0b5d262e346674b62ac79bf2ffbc1c63a8dd22379a0a82c952f0e3626b49"


def test_target_probe_compiles_and_is_read_only() -> None:
    compile(cleanup.TARGET_PROBE, "<kf147-target-probe>", "exec")
    source = cleanup.TARGET_PROBE
    assert '"docker", "ps", "-aq", "--no-trunc"' in source
    assert '"docker", "container", "inspect"' in source
    assert '"docker", "image", "inspect"' in source
    for forbidden in ("docker system prune", "docker image prune", "docker image rm", "--force", "unlink", "rmtree"):
        assert forbidden not in source


def test_executor_has_one_exact_delete_and_no_broad_cleanup() -> None:
    source = Path(cleanup.__file__).read_text(encoding="utf-8")
    exact = '["sudo", "-n", "docker", "image", "rm", TARGET_IMAGE_ID]'
    assert source.count(exact) == 1
    for forbidden in ("docker system prune", "docker image prune", "docker container prune", "docker volume prune"):
        assert forbidden not in source
    assert "--force" not in source
    assert "verify_repository_authority(args.expected_package_commit, live=True)" in source


def test_preexecution_manifest_is_not_live_authorized() -> None:
    manifest = json.loads(cleanup.AUTHORIZATION_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["authorization_id"] == cleanup.AUTHORIZATION_ID
    assert manifest["live_execution_authorized"] is False
    assert manifest["delete"] == {
        "exact_image_id_only": True,
        "force_allowed": False,
        "prune_allowed": False,
        "wildcard_allowed": False,
        "manager_predecessor_in_scope": False,
        "historical_var_tmp_packages_in_scope": False,
        "volume_cleanup_in_scope": False,
    }


def test_validate_pair_passes_stable_preclaim_and_ignores_free_space_noise() -> None:
    before = sample_capture()
    after = copy.deepcopy(before)
    after["target"]["root_free_bytes"] -= 4096
    result = cleanup.validate_pair(before, after, target_present=True)
    assert result["target_container_reference_count"] == 0
    assert result["three_service_runtime_stable"] is True
    assert result["u1_transaction_unchanged"] is True
    assert result["confirmation_unconsumed"] is True


def test_validate_pair_rejects_runtime_change() -> None:
    before = sample_capture()
    after = copy.deepcopy(before)
    after["runtime"]["containers"]["manager"]["started_at"] = "changed"
    with pytest.raises(cleanup.CleanupStop, match="runtime_or_u1_changed"):
        cleanup.validate_pair(before, after, target_present=True)


def test_validate_pair_rejects_target_authority_change() -> None:
    before = sample_capture()
    after = copy.deepcopy(before)
    after["target"]["target"]["size_bytes"] += 1
    with pytest.raises(cleanup.CleanupStop, match="target_authority_changed"):
        cleanup.validate_pair(before, after, target_present=True)


def test_execute_requires_exact_authorization_and_confirmation() -> None:
    args = cleanup.parser().parse_args([
        "--execute",
        "--expected-package-commit", "a" * 40,
        "--execution-id", "test",
        "--t1-ssh-target", "root@example.invalid",
        "--known-hosts", "/tmp/known_hosts",
        "--expected-host-key-sha256", "b" * 64,
        "--evidence-root", "/tmp/evidence",
    ])
    with pytest.raises(cleanup.CleanupStop, match="authorization_or_confirmation_invalid"):
        cleanup.run_execute(args)
