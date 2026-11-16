from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u11_postclaim_successor_recovery_r42"
    / "executor.py"
)
MANIFEST = EXECUTOR.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_r42_test_executor", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_r42_manifest_is_one_shot_and_authorization_state_is_exact():
    value = manifest()
    live = value["live_recovery_authorized"]
    assert type(live) is bool
    assert value["authorization_state"] == {
        "granted": live,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert value["r40_replay_permitted"] is False
    assert value["execution_contract"][
        "explicit_successor_live_authorization_required"
    ] is True
    assert value["execution_contract"][
        "explicit_successor_live_authorization_granted"
    ] is live
    if live:
        assert value["next_boundary"] == "EXECUTE_REAL_T1_R42_ONCE"
    else:
        assert value["next_boundary"] == (
            "EXPLICIT_SUCCESSOR_LIVE_RECOVERY_AUTHORIZATION"
        )


def test_r42_manifest_binds_r41_physical_pass_and_partial_u10():
    value = manifest()
    assert value["r41"]["execution_id"] == (
        "u11-r41-readonly04-20261116T140219Z"
    )
    assert value["r41"]["status"] == (
        "U11_R41_POST_R40_READONLY_PREFLIGHT_PASS"
    )
    assert value["r41"]["rc"] == 0
    assert value["r41"]["successor_live_recovery_eligible"] is True
    assert value["r41"]["successor_live_recovery_authorized"] is False
    assert value["expected_u10_entry"]["transaction_sha256"] == (
        "c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3"
    )
    assert value["expected_target_runtime_image_id"] == (
        "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365"
    )


def test_r42_manifest_binds_current_commit_blobs():
    value = manifest()
    for path, expected in value["package_source_authority"].items():
        observed = subprocess.check_output(
            ["git", "rev-parse", "HEAD:" + path],
            cwd=ROOT,
            text=True,
        ).strip()
        assert observed == expected


def test_r42_remote_script_compiles():
    executor = load_executor()
    compile(executor.REMOTE_SCRIPT, "<r42-remote>", "exec")


def test_r42_embedded_r41_preclaim_precedes_claim_and_recovery():
    source = load_executor().REMOTE_SCRIPT
    preclaim = source.index("pre = run_successor_readonly(plan)")
    state_root = source.index("state_root.mkdir(mode=0o700)")
    claim = source.index(
        'durable_json_once(state_root / "authorization_claim.json", claim)'
    )
    postclaim = source.index("postclaim = run_successor_readonly(plan)")
    recovery = source.index("started = owner.start_target_owner(")
    assert preclaim < state_root < claim < postclaim < recovery


def test_r42_recovery_never_reloads_target_or_republishes_binding():
    source = load_executor().REMOTE_SCRIPT
    start = source.index("def execute(plan, authorization_id, confirmation):")\n    execute = source[start:source.index("\\ndef main():", start)]
    assert ".load_target_archive(" not in execute
    assert ".publish_homeassistant_target_binding(" not in execute
    assert "u11_r42_preloaded_target_missing" in execute
    assert "u11_r42_target_binding_drift" in execute


def test_r42_success_persists_usb_before_host_and_stops_before_u12():
    source = load_executor().REMOTE_SCRIPT
    start = source.index("def execute(plan, authorization_id, confirmation):")\n    execute = source[start:source.index("\\ndef main():", start)]
    usb = execute.index("backend.sync_transaction_metadata(")
    host = execute.index("store.write(next_transaction)")
    assert usb < host
    assert "record_target_accepted(" not in execute
    assert "U12_TARGET_ACCEPTANCE" not in execute
    assert '"u12_plus": False' in execute
    assert '"u13_plus": False' in execute


def test_r42_local_authorization_gate_precedes_evidence_and_transport():
    source = EXECUTOR.read_text(encoding="utf-8")
    gate = source.index(
        'if manifest["live_recovery_authorized"] is not True:'
    )
    evidence = source.index("evidence = base.prepare_evidence_root(")
    transport = source.index("transport_type = base.load_transport()")
    assert gate < evidence < transport
    assert "r42_live_recovery_not_authorized" in source


def test_r42_uses_stdin_streaming_not_large_remote_argv():
    source = EXECUTOR.read_text(encoding="utf-8")
    remote = source[source.index("def remote_mode"):source.index("def reconcile_after_invoke")]
    assert '"python3 -B -"' in remote
    assert "input=program" in remote
    assert "transport.run_remote(" not in remote


def test_r42_postclaim_failure_is_no_replay_and_requires_recovery():
    source = load_executor().REMOTE_SCRIPT
    start = source.index("def execute(plan, authorization_id, confirmation):")\n    execute = source[start:source.index("\\ndef main():", start)]
    assert 'result["status"] = "STOP_POSTCLAIM"' in execute
    assert 'result["recovery_required"] = True' in execute
    assert 'result["replay_permitted"] = False' in execute
    assert 'result["target_image_load"] = False' in execute
    assert 'result["compose_binding_mutation"] = False' in execute
    assert 'durable_json_once(state_root / "failure.json", result)' in execute


def test_r42_transport_ambiguity_reconciles_without_replay():
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "reconcile_after_invoke(" in source
    assert 'status="STOP_UNKNOWN"' in source
    assert "authorization_claimed=True" in source
    assert "authorization_consumed=True" in source
    assert "replay_permitted=False" in source
    assert "recovery_required=True" in source


def test_r42_contract_forbids_scope_expansion():
    contract = manifest()["execution_contract"]
    assert contract["embedded_r41_preclaim_required"] is True
    assert contract["postclaim_r41_revalidation_required"] is True
    assert contract["target_image_reload_forbidden"] is True
    assert contract["compose_binding_rewrite_forbidden"] is True
    assert contract["production_owner_start_required"] is True
    assert contract["usb_u11_metadata_before_host_transaction"] is True
    assert contract["u12_acceptance_forbidden"] is True
    assert contract["r40_replay_forbidden"] is True
    assert contract["partial_failure_requires_new_recovery"] is True


def test_r42_postclaim_usb_failure_compares_all_mirror_files():
    source = load_executor().REMOTE_SCRIPT
    start = source.index("def execute(plan, authorization_id, confirmation):")
    execute = source[start:source.index("\ndef main():", start)]
    assert '"manifest": sha_file(mirror_root / "manifest.json")' in execute
    assert '"phase": sha_file(mirror_root / "phase.json")' in execute
    assert '"content_authority": sha_file(' in execute
    assert '"checksums": sha_file(mirror_root / "checksums.json")' in execute
    assert 'observed_mirror != plan["r41_mirror_sha256"]' in execute
    assert 'result["usb_mutation"] = True' in execute
    assert 'result["usb_mutation_unknown"] = True' in execute


def test_r42_interrupted_status_never_implies_target_reload_or_binding_rewrite():
    source = load_executor().REMOTE_SCRIPT
    start = source.index("def status(plan):")
    status = source[start:source.index("\ndef execute(", start)]
    assert '"target_image_load": False' in status
    assert '"compose_binding_mutation": False' in status
    assert "target_image_load_may_have_occurred" not in status
    assert '"r40_replay": False' in status
    assert '"u13_plus": False' in status


def test_r42_status_reconciles_durable_u11_before_failure_ledger():
    source = load_executor().REMOTE_SCRIPT
    start = source.index("def status(plan):")
    status = source[start:source.index("\ndef execute(", start)]
    durable = status.index(
        'transaction.get("phase") == "U11_TARGET_INSTALLED_STARTED"'
    )
    terminal = status.index("terminal = verify_terminal_u11(plan)", durable)
    failure = status.index("if failure_path.exists():", durable)
    assert durable < terminal < failure
    assert '"success_ledger_present": False' in status
    assert '"failure_ledger_present": failure_path.exists()' in status
    assert '"recovery_required": False' in status
