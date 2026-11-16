from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u11_target_install_readonly_preflight_r39"
    / "executor.py"
)
MANIFEST = EXECUTOR.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location("u11_r39_executor", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r39_manifest_grants_readonly_only_and_stops_before_u11():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["read_only_preflight"] is True
    assert manifest["real_t1_readonly_execution_authorized"] is True
    assert manifest["live_execution_authorized"] is False
    assert manifest["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert manifest["expected_u10_entry"]["transaction_sha256"] == (
        "c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3"
    )
    assert manifest["expected_u10_entry"]["r38_execution_id"] == (
        "u10-r38-live01-20261116T034011Z"
    )
    assert manifest["internal_capacity_policy"]["required_internal_free_bytes"] == (
        3339788321 + 1610612736
    )
    contract = manifest["execution_contract"]
    assert contract["exact_u10_transaction_required"] is True
    assert contract["r38_consumed_no_replay_required"] is True
    assert contract["predecessor_internal_container_absent_required"] is True
    assert contract["predecessor_internal_image_absent_required"] is True
    assert contract["target_internal_image_absent_required"] is True
    assert contract[
        "compose_homeassistant_binding_must_still_reference_predecessor"
    ] is True
    assert contract["internal_target_import_capacity_required"] is True
    assert contract["real_t1_readonly_preflight_authorized"] is True
    assert contract["u11_live_execution_authorized"] is False
    for key in (
        "transaction_mutation",
        "usb_mutation",
        "target_image_load",
        "compose_binding_mutation",
        "service_mutation",
        "u11_transition",
        "u12_plus",
        "board_access",
        "merge",
    ):
        assert contract[key] is False


def test_r39_remote_payload_compiles_and_has_no_u11_mutation_commands():
    executor = load_executor()
    compile(executor.REMOTE_SCRIPT, "<r39-remote>", "exec")
    source = executor.REMOTE_SCRIPT
    forbidden = (
        '["docker", "rm"',
        '["docker", "image", "rm"',
        '["docker", "load"',
        '["systemctl", "stop"',
        '["systemctl", "start"',
        '["systemctl", "restart"',
        "mkfs",
        "wipefs",
        "sgdisk",
        "parted",
        "record_target_started(",
        "rewrite_component_image(",
        "activate_component(",
        "start_services(",
    )
    for token in forbidden:
        assert token not in source


def test_r39_local_entry_has_no_execute_switch_and_requires_readonly_grant():
    source = EXECUTOR.read_text(encoding="utf-8")
    assert 'parser.add_argument("--execute"' not in source
    assert "r39_real_t1_readonly_execution_not_authorized" in source
    assert "real_t1_readonly_execution_authorized" in source
    assert '"u11_live_execution_authorized": False' in source
    assert '"target_image_load": False' in source
    assert '"service_mutation": False' in source
    assert '"u11_transition": False' in source
    assert '"u12_plus": False' in source


def test_r39_binds_r38_closed_pass_and_exact_u10_mirror():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = manifest["source_authority"]
    entry = manifest["expected_u10_entry"]
    assert authority["r38_authorized_head"] == (
        "b38a43b11beecb1dc73680aed933ad05db084c9b"
    )
    assert authority["r38_authorized_head_ci"] == "16_OF_16_SUCCESS"
    assert authority["r38_result"] == (
        "U10_R38_PREDECESSOR_CAPACITY_RELEASE_PASS"
    )
    assert authority["r38_rc"] == 0
    assert entry["mirror_sha256"]["phase"] == (
        "005285eb177803b2fd387725730abf8e28b30f4727f422672e88cc998c14b589"
    )
    assert entry["mirror_sha256"]["manifest"] == (
        "3aa5e247636b1bb891aa151a8fb0219294d4803ea22dc7b66d821f6250d9e728"
    )


def test_r39_checks_r38_no_replay_and_internal_capacity_before_eligibility():
    source = load_executor().REMOTE_SCRIPT
    assert "verify_r38_ledger(plan)" in source
    assert 'claim.get("claimed") is not True' in source
    assert 'claim.get("consumed") is not True' in source
    assert 'claim.get("replay_permitted") is not False' in source
    assert "verify_usb_mirror_u10(plan, transaction)" in source
    assert "verify_recovery_assets_and_capacity(" in source
    assert "verify_u11_runtime_prestate(plan)" in source
    assert "verify_internal_target_capacity(plan)" in source
    required = source.index("verify_internal_target_capacity(plan)")
    eligible = source.index('"u11_readonly_eligible": True')
    assert required < eligible


def test_r39_capacity_formula_excludes_external_usb_archive_staging():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    policy = manifest["internal_capacity_policy"]
    assert policy["target_archive_is_external_usb"] is True
    assert policy["target_import_worst_case_allowance_bytes"] == 3339788321
    assert policy["derived_post_peak_reserve_bytes"] == 1610612736
    assert policy["required_internal_free_bytes"] == 4950401057
    source = load_executor().REMOTE_SCRIPT
    assert (
        'plan["target_import_worst_case_allowance_bytes"]'
        in source
    )
    assert 'plan["derived_post_peak_reserve_bytes"]' in source
