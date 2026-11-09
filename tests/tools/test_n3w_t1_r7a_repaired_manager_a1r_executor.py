from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR_PATH = ROOT / "tools/execution_packages/n3w/r7a/repaired_manager_a1_reactivation/executor.py"
MANIFEST_PATH = EXECUTOR_PATH.with_name("manifest.json")
CLOSURE_PATH = ROOT / "docs/development/N3W_T1_R7A_REPAIRED_MANAGER_A0R_A1R_LIVE_EXECUTION_CLOSURE_20261108.md"
HISTORICAL_A1R_HEAD = "70aaa4070641dd73c1a97738e6332be31403d45e"

def load_executor():
    spec = importlib.util.spec_from_file_location("r7a_repaired_manager_a1r_executor", EXECUTOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_a1r_manifest_is_live_authorized_and_separate_from_a0r() -> None:
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert document["schema"] == "gh.n3w-t1-r7a-repaired-manager-a1r-live-reactivation-package/1"
    assert document["live_execution_authorized"] is True
    assert document["expected_live_entry"]["manager_image"] == "local/greenhouse-manager:fresh-7807271e4c48"
    assert document["expected_live_entry"]["manager_v2_transaction_target_required"] is True
    assert document["expected_live_entry"]["fresh_readonly_post_a0r_required"] is True
    split = document["authorization_separation"]
    assert split["a0r_authorization_must_be_consumed_before_entry"] is True
    assert split["a1r_authorization_is_distinct"] is True
    assert split["old_a1_authorization_replay"] is False
    assert split["old_boundary_b_authorization_replay"] is False

def test_a1r_authorization_is_historical_consumed_live_authority() -> None:
    executor = load_executor()
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    closure = CLOSURE_PATH.read_text(encoding="utf-8")

    assert executor.AUTHORIZATION == "N3W_T1_R7A_REPAIRED_MANAGER_A1R_LIVE_REACTIVATION_20261108_01"
    assert executor.AUTHORIZATION != "N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261108_02"
    assert executor.AUTHORIZATION != "N3W_T1_R7A_HOST_DAEMON_COMPOSE_A1_LIVE_ACTIVATION_20261107_01"
    assert document["live_execution_authorized"] is True
    assert f"LIVE_AUTHORIZED_HEAD={HISTORICAL_A1R_HEAD}" in closure
    assert "A1R_AUTHORIZATION_CLAIMED=true" in closure
    assert "A1R_STATUS=PASS" in closure

def test_a1r_source_authority_matches_consumed_historical_head() -> None:
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for path, expected in document["source_authority"].items():
        observed = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", f"{HISTORICAL_A1R_HEAD}:{path}"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        assert observed == expected

def test_a1r_requires_committed_repaired_manager_transaction() -> None:
    executor = load_executor()
    assert executor.EXPECTED_MANAGER == "local/greenhouse-manager:fresh-7807271e4c48"
    assert executor.EXPECTED_A0R_AUTHORIZATION == "N3W_T1_CORE_UPDATER_R7A_REPAIRED_MANAGER_A0R_LIVE_APPLY_20261108_01"
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    helper = source[source.index("def require_manager_transaction("):source.index("def require_recovery_clear(")]
    assert 'transaction.get("component") != "manager"' in helper
    assert 'transaction.get("status") != "COMMITTED"' in helper
    assert 'transaction.get("phase") != "COMMITTED"' in helper
    assert 'transaction.get("authorization_consumed") is not True' in helper
    assert 'transaction.get("authorization_id_sha256")' in helper
    assert "EXPECTED_A0R_AUTHORIZATION_SHA256" in helper
    assert 'transaction.get("target", {}).get("target_image_ref") != EXPECTED_MANAGER' in helper

def test_a1r_preserves_15s_same_container_stability_guard() -> None:
    executor = load_executor()
    assert executor.POST_ACTIVATION_STABILITY_SECONDS == 15.0
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    stability = source[source.index("def require_post_activation_stability("):source.index("def env_map(")]
    assert '["sleep", str(POST_ACTIVATION_STABILITY_SECONDS)]' in stability
    assert '"services_owner_unstable_post"' in stability
    assert 'document.get("Id") != expected_id' in stability

def test_a1r_has_no_usb_destructive_or_prepare_path() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    for token in ('"wipefs"', '"sfdisk"', '"mkfs.ext4"', '"mount"', '"umount"', "CONFIRM_USB_ERASE", "request_prepare(", "confirm_and_prepare("):
        assert token not in source
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    contract = document["execution_contract"]
    assert contract["usb_mutation"] is False
    assert contract["prepare_intent"] is False
    assert contract["confirm_usb_erase"] is False
    assert contract["u2_plus"] is False
    assert contract["manager_image_rollback"] is False

def test_a1r_execution_order_and_failure_rollback_are_bounded() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    execute_source = source[source.index("def execute("):source.index("def parser(")]
    assert execute_source.index("collect_preflight(transport)") < execute_source.index("stage_bundle(")
    assert execute_source.index("stage_bundle(") < execute_source.index("snapshot_rollback(")
    assert execute_source.index('"authorization_claim.json"') < execute_source.index("activate(transport, staging_root)")
    assert execute_source.index("activate(transport, staging_root)") < execute_source.index("validate_post_activation(")
    rollback = source[source.index("def rollback_activation("):source.index("def execute(")]
    assert '["systemctl", "restart", SERVICES_UNIT]' in rollback
    assert "T1_CORE_UPDATER_APPLY" not in rollback
    assert "greenhouse-manager-arm64.tar" not in rollback


def test_a1r_manifest_binds_exact_a0r_authorization_chain() -> None:
    executor = load_executor()
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    separation = document["authorization_separation"]
    assert separation["a0r_authorization_id"] == executor.EXPECTED_A0R_AUTHORIZATION
    assert separation["a0r_authorization_must_be_consumed_before_entry"] is True
    assert executor.EXPECTED_A0R_AUTHORIZATION_SHA256 == __import__("hashlib").sha256(
        executor.EXPECTED_A0R_AUTHORIZATION.encode("utf-8")
    ).hexdigest()
