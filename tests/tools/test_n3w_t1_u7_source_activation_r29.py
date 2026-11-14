from __future__ import annotations

import ast
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
    / "u7_source_activation_r29"
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
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U7_SOURCE_ACTIVATION_R29_20261114_01"
)
CONFIRM = "EXECUTE U7 R29 SOURCE ACTIVATION: YES"


def load_executor():
    spec = importlib.util.spec_from_file_location("n3w_u7_r29_test", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_starts_ungranted_after_r28_terminal_stop() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["authorization_id"] == GATE
    assert document["confirmation"] == CONFIRM
    assert document["live_execution_authorized"] is False
    assert document["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    authority = document["source_authority"]
    assert authority["r28_result"] == "TERMINAL_STOP_ROLLBACK_PASS"
    assert authority["r28_authorization_consumed"] is True
    assert authority["r28_replay_permitted"] is False
    assert authority["r28_rollback_status"] == "PASS"


def test_r29_expands_activation_to_dependency_closure_nodes() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["execution_contract"]["activated_source_file_count"] == 6
    assert set(document["remote_paths"]) == {
        "backup",
        "usb",
        "install",
        "host",
        "common",
        "v2_state",
    }
    assert document["dynamic_predecessor_git_blobs"]["common"] == [
        "ABSENT",
        "63a0377b7df509fd44194a1752a19c013ce55858",
    ]
    assert set(document["dynamic_predecessor_git_blobs"]["v2_state"]) == {
        "ABSENT",
        "a5260f1097983cad4818f626826accbb185e4a37",
        "d89d4696409d7c451ec0b37a8be87e29092806b6",
    }


def _n3w_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root.startswith("n3w_"):
                    imports.add(root)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".", 1)[0]
            if root.startswith("n3w_"):
                imports.add(root)
    return imports


def test_declared_source_set_covers_transitive_n3w_import_closure() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    declared_paths = {
        Path(path).name
        for path in document["remote_paths"].values()
    }
    declared_paths.update(
        Path(path).name
        for path in document["unchanged_source_sha256"]
    )
    declared_modules = {
        name[:-3]
        for name in declared_paths
        if name.startswith("n3w_") and name.endswith(".py")
    }

    roots = {
        "n3w_t1_core_updater_ha_backup",
        "n3w_t1_core_updater_ha_usb",
        "n3w_t1_core_updater_ha_install",
        "n3w_t1_core_updater_host",
        "n3w_t1_core_updater_common",
        "n3w_t1_core_updater_v2_state",
    }
    queue = list(roots)
    visited: set[str] = set()
    while queue:
        module = queue.pop()
        if module in visited:
            continue
        visited.add(module)
        path = ROOT / "tools" / f"{module}.py"
        assert path.is_file(), module
        for dependency in _n3w_imports(path):
            assert dependency in declared_modules, (
                module,
                dependency,
                sorted(declared_modules),
            )
            if dependency not in visited:
                queue.append(dependency)


def test_executor_and_embedded_remote_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<u7-r29>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == CONFIRM
    assert set(module.TARGETS) == {
        "backup",
        "usb",
        "install",
        "host",
        "common",
        "v2_state",
    }


def test_staged_import_runs_before_claim_and_surfaces_safe_error() -> None:
    remote = load_executor().REMOTE_SCRIPT
    staged = remote.index("staged_import = staged_import_preflight(plan)")
    claim = remote.index('durable_json(state_root / "authorization_claim.json", claim)')
    assert staged < claim
    assert "sanitize_import_error" in remote
    assert '"staged_import_failed:"' in remote
    assert '"installed_import_failed:"' in remote


def test_preflight_is_readonly_and_binds_r26_u6_runtime() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"U6_PREDECESSOR_RECOVERY_PREPARING"' in remote
    assert '"U6_R26_PREDECESSOR_RECOVERY_PASS"' in remote
    assert '"u7_u6_transaction_invalid"' in remote
    assert '"r26_claim_invalid"' in remote
    assert '"host_source_mutation": False' in remote
    assert '"service_stop": False' in remote
    assert '"service_restart": False' in remote
    assert '"transaction_mutation": False' in remote
    assert '"usb_mutation": False' in remote
    assert '"u7_transition": False' in remote


def test_activation_does_not_stop_services_or_cross_u7() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '["systemctl", "stop"' not in remote
    assert '["systemctl", "start"' not in remote
    assert '["systemctl", "restart"' not in remote
    assert "create_consistent_backup" not in remote
    assert "record_predecessor_recovery_and_ha_quiesced" not in remote
    assert "record_recovery_admission" not in remote
    assert "transaction_store.write" not in remote
    assert '"service_stop": False' in remote
    assert '"service_restart": False' in remote
    assert '"transaction_mutation": False' in remote
    assert '"usb_mutation": False' in remote
    assert '"u7_transition": False' in remote
    assert '"u8_plus": False' in remote


def test_runtime_continuity_covers_units_and_containers() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert '"NRestarts") != "0"' in remote
    assert 'result["restart_count"] != 0' in remote
    assert '"unit_pid_drift:"' in remote
    assert '"container_runtime_drift_after_activation:"' in remote


def test_rollback_uses_observed_preclaim_state() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert "copy_preclaim_backups" in remote
    assert '"source_prestate.json"' in remote
    assert 'state.get("state") == "ABSENT"' in remote
    assert "atomic_install(backup, destination)" in remote
    assert '"rollback_source_prestate_mismatch"' in remote
    assert 'result["rollback_required"] = bool(result["host_source_mutation"])' in remote


def test_rollback_is_armed_before_first_atomic_replace() -> None:
    remote = load_executor().REMOTE_SCRIPT
    armed = remote.index('result["host_source_mutation"] = True')
    loop = remote.index('for key, destination in plan["remote_paths"].items():')
    assert armed < loop


def test_claim_and_transport_uncertainty_are_consumed_no_replay() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    remote = load_executor().REMOTE_SCRIPT
    assert '"authorization_claim_persistence_unknown"' in remote
    assert 'status="STOP_UNKNOWN"' in remote
    assert "authorization_claimed=True" in remote
    assert "authorization_consumed=True" in remote
    assert "replay_permitted=False" in remote
    assert 'result["remote_execute_invoked"] = True' in source
    assert 'reason="remote_execute_claim_state_unknown"' in source


def test_success_is_durable_and_stops_before_live_u7() -> None:
    remote = load_executor().REMOTE_SCRIPT
    assert 'durable_json(state_root / "success.json", result)' in remote
    assert '"U7_R29_SOURCE_ACTIVATION_PASS"' in remote
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["stop_boundary"] == (
        "STOP_AFTER_R29_U7_SOURCE_ACTIVATION_"
        "BEFORE_U7_HA_QUIESCE_DATA_BACKUP_LIVE_EXECUTION"
    )


def test_target_binding_workflow_covers_r29() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/u7_source_activation_r29/**"
    )
    executor = (
        "tools/execution_packages/n3w/r7a/"
        "u7_source_activation_r29/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_u7_source_activation_r29.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor) == 1
    assert workflow.count(test_path) == 2
