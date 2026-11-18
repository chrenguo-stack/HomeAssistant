from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_EXECUTOR = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "u13b_p3_fresh_readonly_preflight" / "executor.py"
)
PREFLIGHT_MANIFEST = PREFLIGHT_EXECUTOR.with_name("manifest.json")
LIVE_EXECUTOR = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "u13b_p3_live_to_u11" / "executor.py"
)
LIVE_MANIFEST = LIVE_EXECUTOR.with_name("manifest.json")
RESET_EXECUTOR = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "u13b_p3_single_usb_reuse_reset" / "executor.py"
)
RESET_MANIFEST = RESET_EXECUTOR.with_name("manifest.json")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_fresh_readonly_manifest_is_non_live_and_preserves_old_usb():
    value = manifest(PREFLIGHT_MANIFEST)
    assert value["read_only_preflight"] is True
    assert value["real_t1_readonly_execution_authorized"] is True
    assert value["new_clean_ota_mutation_authorized"] is False
    assert value["u13b_live_execution_authorized"] is False
    assert value["controlled_rollback_mutation_authorized"] is False
    contract = value["execution_contract"]
    assert contract["exactly_one_fresh_usb_candidate_required"] is True
    assert contract["historical_usb_reuse_forbidden"] is False
    assert contract["historical_usb_reuse_without_destructive_reset_forbidden"] is True
    assert contract["single_usb_reuse_after_destructive_reset_authorized"] is True
    assert contract["current_terminal_transaction_write"] is False
    assert contract["usb_format"] is False
    assert value["execution_contract"]["execute_mode_forbidden_until_separate_authorization"] is False
    assert value["stop_boundary"] == (
        "STOP_AFTER_POST_RESET_READONLY_PREFLIGHT_BEFORE_P3_LIVE_AUTHORIZATION"
    )


def test_fresh_readonly_remote_compiles_and_has_no_mutation_calls():
    module = load(PREFLIGHT_EXECUTOR, "p3_fresh_readonly")
    compile(module.REMOTE_SCRIPT, "<p3-fresh-readonly>", "exec")
    remote = module.REMOTE_SCRIPT
    forbidden = (
        ".prepare_new(",
        ".write(",
        "format_and_mount(",
        "sync_transaction_metadata(",
        "systemctl",
        '"docker", "rm"',
        '"docker", "image", "rm"',
        "record_recovery_admission(",
        "claim_live_authorization(",
        "record_predecessor_capacity_released(",
        "record_target_started(",
        "record_target_accepted(",
        "record_commit(",
    )
    for token in forbidden:
        assert token not in remote
    assert "backend.inventory()" in remote
    assert "candidate.public_fingerprint != old_fingerprint" in remote
    assert "filesystem_uuids_for_candidate" in remote
    assert 'old_filesystem_uuid = expected["filesystem_uuid"].lower()' in remote
    assert "old_filesystem_uuid not in observed_filesystem_uuids" in remote
    assert "expected_reuse_fingerprint" in remote
    assert "single_usb_reuse_after_reset" in remote


def test_fresh_readonly_execute_mode_requires_true_manifest_authority():
    source = PREFLIGHT_EXECUTOR.read_text(encoding="utf-8")
    assert 'choices=("source-check", "execute-readonly")' in source
    assert "require_authorized=True if execute else None" in source
    assert "require_authorized is not None" in source
    assert (
        'document.get("real_t1_readonly_execution_authorized")'
        in source
    )
    source_check = source.index("if not execute:")
    evidence = source.index("evidence = prepare_evidence_root", source_check)
    assert source_check < evidence


def test_live_manifest_is_source_only_not_authorized():
    value = manifest(LIVE_MANIFEST)
    assert value["live_execution_authorized"] is False
    assert value["new_clean_ota_mutation_authorized"] is False
    assert value["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert value["u13b_live_execution_authorized"] is False
    assert value["controlled_rollback_mutation_authorized"] is False
    contract = value["execution_contract"]
    assert contract["fresh_real_t1_readonly_preflight_required"] is True
    assert contract["historical_usb_reuse_forbidden"] is False
    assert contract["historical_usb_reuse_without_destructive_reset_forbidden"] is True
    assert contract["single_usb_reuse_after_destructive_reset_required"] is True
    assert contract["exactly_one_fresh_usb_candidate_required"] is True
    assert contract["acceptance_staged_artifact_adapter_only"] is True
    assert contract["manager_version_rule_modified"] is False
    assert contract["stop_at_u11_before_u12"] is True
    assert contract["record_target_accepted_forbidden"] is True
    assert contract["record_commit_forbidden"] is True
    target = value["acceptance_target"]
    assert target["target_image_ref"] == "local/n3w-homeassistant:2026.10.4-u13b-acceptance-v1"
    assert target["target_ci_runtime_image_id"] == "sha256:59b51fc720f83eac91881937337e439e2a2a1a8bb58c9e760cbdf95ce8653fbc"
    assert target["cross_store_runtime_id_rebound_required"] is True
    assert target["live_target_runtime_id_must_differ_from_predecessor"] is True


def test_live_remote_compiles_and_stops_at_u11():
    module = load(LIVE_EXECUTOR, "p3_live")
    compile(module.REMOTE_SCRIPT, "<p3-live>", "exec")
    remote = module.REMOTE_SCRIPT
    order = [
        'ipc.submit("PREPARE"',
        "prepare.confirm_and_prepare()",
        "u6.prepare_or_resume()",
        "u7.prepare_or_resume()",
        "admitted = record_recovery_admission(",
        "claimed = claim_live_authorization(",
        "u10 = record_predecessor_capacity_released(",
        "installed = u11.install()",
    ]
    positions = [remote.index(token) for token in order]
    assert positions == sorted(positions)
    assert "record_target_accepted(" not in remote
    assert "record_commit(" not in remote
    assert "U12_TARGET_ACCEPTANCE" not in remote
    assert '"u12_plus": False' in remote
    assert '"U11_TARGET_INSTALLED_STARTED"' in remote
    assert "u11_target_runtime_id_not_distinct_from_predecessor" in remote
    assert "target_runtime_image_id_rebound=True" in remote


def test_live_revalidates_same_fresh_usb_before_outer_claim():
    module = load(LIVE_EXECUTOR, "p3_live_usb_recheck")
    remote = module.REMOTE_SCRIPT
    fresh_check = remote.index('expected_fresh = plan["preflight"]["fresh_usb_public_fingerprint"]')
    drift_stop = remote.index('raise Stop("preclaim_fresh_usb_candidate_drift")')
    state_root = remote.index("root.mkdir(mode=0o700)", fresh_check)
    claim_write = remote.index('durable_json_once(root / "authorization_claim.json", claim)')
    assert fresh_check < drift_stop < state_root < claim_write
    assert "candidate.public_fingerprint != old_fingerprint" in remote


def test_live_uses_staged_exact_artifact_without_network_fetch():
    module = load(LIVE_EXECUTOR, "p3_live_staged_artifact")
    remote = module.REMOTE_SCRIPT
    assert "class StagedArtifactBackend(SubprocessPrepareBackend)" in remote
    assert "with staged.open" in remote
    assert "portable.parse_image_archive(" in remote
    assert "urllib.request" not in remote
    assert "response.read(" not in remote


def test_live_runs_fresh_readonly_before_one_shot_claim_and_scp():
    source = LIVE_EXECUTOR.read_text(encoding="utf-8")
    preflight = source.index("preflight_module.run_readonly(")
    epoch = source.index("transport.start_epoch()", preflight)
    init = source.index('"init",', epoch)
    first_scp = source.index("transport.scp_to(", init)
    execute = source.index('"execute",', first_scp)
    assert preflight < epoch < init < first_scp < execute


def test_live_source_bundle_and_authorization_fail_closed():
    source = LIVE_EXECUTOR.read_text(encoding="utf-8")
    assert "source_bundle_sha256" in source
    assert "product_source_sha256" in source
    assert "source_bundle_member_hash_drift" in source
    assert 'value.get("live_execution_authorized") is not require_authorized' in source
    assert (
        'value.get("new_clean_ota_mutation_authorized")'
        in source
    )
    assert '"granted": bool(require_authorized)' in source
    assert 'result["t1_access"] = True' not in source


def test_live_reports_authorization_truth_from_manifest():
    source = LIVE_EXECUTOR.read_text(encoding="utf-8")
    assert (
        'result["live_execution_authorized"] = manifest['
        in source
    )
    assert (
        'result["new_clean_ota_mutation_authorized"] = manifest['
        in source
    )


def test_single_usb_reuse_reset_manifest_is_narrow_and_authorized():
    value = manifest(RESET_MANIFEST)
    assert value["destructive_usb_reset_authorized"] is True
    assert value["transaction_mutation_authorized"] is False
    assert value["service_mutation_authorized"] is False
    assert value["image_mutation_authorized"] is False
    assert value["ha_data_mutation_authorized"] is False
    assert value["p3_live_execution_authorized"] is False
    assert value["expected_historical_media"]["filesystem_uuid"] == (
        value["expected_terminal_u13a"]["filesystem_uuid"]
    )
    contract = value["execution_contract"]
    assert contract["unmount_exact_historical_mount"] is True
    assert contract["remove_historical_filesystem_signature"] is True
    assert contract["repartition"] is False
    assert contract["mkfs"] is False
    assert contract["transaction_write"] is False


def test_single_usb_reuse_reset_remote_is_usb_only_and_fail_closed():
    module = load(RESET_EXECUTOR, "p3_single_usb_reuse_reset")
    compile(module.REMOTE_SCRIPT, "<p3-single-usb-reuse-reset>", "exec")
    remote = module.REMOTE_SCRIPT
    assert 'run(["umount", media["mount_target"]])' in remote
    assert 'run(["wipefs", "--all", "--force", partition_path])' in remote
    assert 'run(["udevadm", "settle"])' in remote
    assert "mkfs" not in remote
    assert "sfdisk" not in remote
    forbidden = (
        ".write(",
        "systemctl",
        '"docker", "rm"',
        '"docker", "image", "rm"',
        "record_recovery_admission(",
        "claim_live_authorization(",
        "record_predecessor_capacity_released(",
        "record_target_started(",
        "record_target_accepted(",
        "record_commit(",
    )
    for token in forbidden:
        assert token not in remote
    assert "single_usb_historical_uuid_drift" in remote
    assert "single_usb_historical_mount_drift" in remote
    assert "single_usb_historical_uuid_still_present" in remote


def test_single_usb_reset_runs_exact_historical_binding_before_destruction():
    source = RESET_EXECUTOR.read_text(encoding="utf-8")
    binding = source.index("p1.run_status_only(")
    reset = source.index("value = remote_reset(", binding)
    assert binding < reset
    module = load(RESET_EXECUTOR, "p3_single_usb_reset_partial_mutation")
    remote = module.REMOTE_SCRIPT
    assert 'MUTATION_STATE["usb_mutation"] = True' in remote
    assert 'MUTATION_STATE["destructive_usb_reset"] = True' in remote


def test_live_requires_verified_single_usb_reset_preflight():
    source = LIVE_EXECUTOR.read_text(encoding="utf-8")
    assert 'preflight.get("single_usb_reuse_after_reset") is not True' in source
    module = load(LIVE_EXECUTOR, "p3_live_single_usb_reset")
    remote = module.REMOTE_SCRIPT
    assert "single_usb_reuse_reset_not_verified" in remote
