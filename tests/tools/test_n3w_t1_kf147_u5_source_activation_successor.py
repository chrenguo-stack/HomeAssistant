from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "kf147_u5_source_activation_successor"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
)

GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "U5_SOURCE_ACTIVATION_R10_20261111_01"
)
CONFIRMATION = "EXECUTE KF147 U5 SOURCE ACTIVATION R10: YES"

EXPECTED_SOURCE_FILES = {
    "tools/n3w_t1_core_updater_ha_prepare.py": (
        "9139dc652eb992963c21d4fda171eef2bf685e1bbe0cbcea2319244c7e963475",
        "4dc6226ae493f18b3dab2c8773c1d3687a8f5f1750a6b4d9fa791cebe22db596",
        "9ca7f0411a9e45d488e6cba4a3526bfaa7c77e20",
    ),
    "tools/n3w_t1_core_updater_ha_prepare_host.py": (
        "a11089ef57cf68c40a648c85ac7e7569a281f7fad13f75a09c0a3b04bad80ecf",
        "d7f1e5468e24446f3ade0e22778cebecc8cda0fed07179a8fccb55b9f7e4ff8a",
        "85f0765050c025f3d68a5667fda0d4772b4f15a6",
    ),
    "tools/n3w_t1_core_updater_ha_ipc.py": (
        "3aca46350c2fce9818dbc635f5343f01b06ff80081d93205ce7d28fc4ca2f771",
        "a7d335c597771b0297f690d0e97fb3288f5f1c83fd670d8af00d76ca983e56ac",
        "ebd71331eaef4ef5a9fb76a130a66c714370d92e",
    ),
}


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_u5_source_activation_successor_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_authorized_once_and_exact_three_file_source_slice() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["gate_id"] == GATE
    assert doc["authorization_id"] == GATE
    assert doc["confirmation"] == CONFIRMATION
    assert doc["live_execution_authorized"] is True
    assert doc["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }

    observed = {item["repo_path"]: item for item in doc["source_files"]}
    assert set(observed) == set(EXPECTED_SOURCE_FILES)
    for repo_path, (predecessor, target, blob) in EXPECTED_SOURCE_FILES.items():
        item = observed[repo_path]
        assert item["predecessor_sha256"] == predecessor
        assert item["target_sha256"] == target
        assert item["target_blob"] == blob
        assert item["remote_path"].startswith("/opt/HomeAssistant/tools/")

    contract = doc["execution_contract"]
    assert contract["read_only_preflight"] is True
    assert contract["source_deployment_on_execute"] is True
    assert contract["exact_three_file_source_slice"] is True
    assert contract["host_daemon_restart_on_execute"] is True
    assert contract["services_owner_restart_on_execute"] is True
    assert contract["transaction_mutation"] is False
    assert contract["usb_mutation"] is False
    assert contract["target_archive_mutation"] is False
    assert contract["u5_transition"] is False
    assert contract["u6_plus"] is False
    assert contract["automatic_retry"] is False
    assert contract["automatic_source_rollback"] is True
    assert contract["maximum_rollback_attempts"] == 1
    assert doc["stop_boundary"] == (
        "STOP_AFTER_U5_SOURCE_ACTIVATION_AND_U4_POSTVALIDATION_"
        "BEFORE_NEW_INSTALL_INTENT_PREFLIGHT"
    )


def test_r9_terminal_failure_is_required_as_successor_prestate() -> None:
    module = load_executor()
    source = module.REMOTE_SCRIPT
    assert 'def verify_r9_terminal(plan):' in source
    assert '"Stop:ipc_request_rejected:ha_ota_ipc_action_invalid"' in source
    assert 'failure.get("authorization_claimed") is not True' in source
    assert 'failure.get("authorization_consumed") is not True' in source
    assert 'failure.get("transaction_mutation") is not False' in source
    assert 'failure.get("usb_mutation") is not False' in source
    assert 'failure.get("u5_transition") is not False' in source
    assert 'failure.get("u6_plus") is not False' in source
    assert 'failure.get("split_state_detected") is not False' in source


def test_execute_requires_granted_unclaimed_unconsumed_nonreplayable_authorization() -> None:
    source = load_executor().REMOTE_SCRIPT
    execute_start = source.index("def execute(plan, authorization, confirmation):")
    execute_body = source[execute_start:]
    assert 'plan.get("live_execution_authorized") is not True' in execute_body
    assert '"granted": True' in execute_body
    assert '"claimed": False' in execute_body
    assert '"consumed": False' in execute_body
    assert '"replay_permitted": False' in execute_body
    assert 'authorization != plan["authorization_id"]' in execute_body
    assert 'confirmation != plan["confirmation"]' in execute_body


def test_remote_script_compiles_and_preflight_is_read_only() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<kf147-r10-remote>", "exec")
    preflight = module.REMOTE_SCRIPT[
        module.REMOTE_SCRIPT.index('if mode == "preflight":'):
        module.REMOTE_SCRIPT.index('elif mode == "execute":')
    ]
    assert 'baseline(plan, target_sources=False)' in preflight
    assert 'source_activation_eligible' in preflight
    assert 'systemctl", "stop"' not in preflight
    assert 'atomic_install(' not in preflight


def test_execute_uses_services_owner_then_host_and_stops_before_u5() -> None:
    source = load_executor().REMOTE_SCRIPT
    execute_start = source.index("def execute(plan, authorization, confirmation):")
    claim = source.index('state_root / "authorization_claim.json"', execute_start)
    lifecycle = source.index('result["lifecycle_mutation_started"] = True', claim)
    services_stop = source.index(
        'run(["systemctl", "stop", SERVICES_UNIT]',
        lifecycle,
    )
    host_stop = source.index(
        'run(["systemctl", "stop", HOST_UNIT]',
        services_stop,
    )
    install = source.index(
        'atomic_install(',
        source.index('result["host_source_mutation"] = True', host_stop),
    )
    host_start = source.index(
        'run(["systemctl", "start", HOST_UNIT]',
        install,
    )
    services_start = source.index(
        'run(["systemctl", "start", SERVICES_UNIT]',
        host_start,
    )
    post = source.index(
        'post = baseline(plan, target_sources=True)',
        services_start,
    )
    assert (
        claim
        < lifecycle
        < services_stop
        < host_stop
        < install
        < host_start
        < services_start
        < post
    )

    execute_body = source[execute_start:]
    assert '"action": "INSTALL"' not in execute_body
    assert "revalidate_and_request_install" not in execute_body
    assert "request_install(" not in execute_body
    assert '"U5_INSTALL_REQUESTED_REVALIDATING"' not in execute_body
    assert 'transaction_mutation": False' in execute_body
    assert 'usb_mutation": False' in execute_body
    assert 'u5_transition": False' in execute_body
    assert 'u6_plus": False' in execute_body


def test_partial_source_or_lifecycle_failure_requires_single_rollback() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'result["lifecycle_mutation_started"] = True' in source
    assert 'result["host_source_mutation"] = True' in source
    assert (
        'result["lifecycle_mutation_started"] or result["host_source_mutation"]'
        in source
    )
    assert 'result["rollback"] = rollback(plan, backup_dir)' in source
    rollback_start = source.index("def rollback(plan, backup_dir):")
    execute_start = source.index("def execute(plan, authorization, confirmation):")
    rollback_body = source[rollback_start:execute_start]
    assert 'run(["systemctl", "stop", SERVICES_UNIT]' in rollback_body
    assert 'run(["systemctl", "stop", HOST_UNIT]' in rollback_body
    assert 'atomic_install(backup, item["remote_path"])' in rollback_body
    assert 'run(["systemctl", "start", HOST_UNIT]' in rollback_body
    assert 'run(["systemctl", "start", SERVICES_UNIT]' in rollback_body
    assert 'baseline(plan, target_sources=False)' in rollback_body


def test_u4_host_usb_target_and_runtime_continuity_are_all_bound() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'def verify_transaction(plan):' in source
    assert '"U4_READY_TO_INSTALL"' in source
    assert 'def verify_usb_metadata(plan, tx):' in source
    assert '"gh.n3w-t1-ha-usb-transaction-phase/1"' in source
    assert 'def verify_media_and_target(plan):' in source
    assert 'sha_file(target_path) != plan["target_sha256"]' in source
    assert 'def verify_source_set(plan, *, target):' in source
    assert 'def verify_containers(plan):' in source
    assert 'ipc.get("phase") != "READY_TO_INSTALL"' in source


def test_local_execute_stages_only_after_successful_remote_preflight() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    preflight = source.index('remote_mode(transport, "preflight", plan')
    preflight_check = source.index('if rc != 0 or pre.get("status") != "PASS":', preflight)
    create_stage = source.index('["install", "-d", "-m", "0700"', preflight_check)
    stream = source.index("stream_file(", create_stage)
    execute = source.index('"execute"', stream)
    assert preflight < preflight_check < create_stage < stream < execute


def test_target_binding_workflow_covers_r10_package_and_test() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u5_source_activation_successor/**"
    )
    executor_path = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u5_source_activation_successor/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_kf147_u5_source_activation_successor.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor_path) == 1
    assert workflow.count(test_path) == 2

def test_r10_ipc_status_probe_uses_real_newline_frame_terminator() -> None:
    source = load_executor().REMOTE_SCRIPT
    start = source.index("def ipc_status(manager_id):")
    end = source.index("def verify_r9_terminal(plan):", start)
    probe = source[start:end]
    assert 'b"\\n"' in probe
    assert 'b"\\\\n"' not in probe

