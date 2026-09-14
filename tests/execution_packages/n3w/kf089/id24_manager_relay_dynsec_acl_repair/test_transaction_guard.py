from __future__ import annotations

from pathlib import Path


EXECUTOR_PATH = (
    Path(__file__).resolve().parents[5]
    / "tools/execution_packages/n3w/kf089/"
    "id24_manager_relay_dynsec_acl_repair/executor.py"
)


def test_any_failure_after_mutation_start_reaches_outer_rollback_guard() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")

    mutation_start = source.index("        mutation_started = True\n")
    stopped_handler = source.index("    except StopExecution as exc:\n")
    rollback_guard = source.index(
        "    if (\n"
        "        mutation_started\n"
        "        and not mutation_completed\n"
    )
    rollback_call = source.index("            next_op, rollback_ok, rollback_reason = rollback_target_acls(")
    closure_write = source.index("        dump(root / \"closure.json\", closure)\n")

    assert mutation_start < stopped_handler < rollback_guard < rollback_call < closure_write


def test_transaction_is_complete_only_after_exact_postcheck_and_runtime_stability() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")

    exact_postcheck = source.index("        require_exact_repaired_poststate(post)\n")
    runtime_postcheck = source.index("        stability = require_runtime_stable(\n")
    mutation_complete = source.index("        mutation_completed = True\n")
    stopped_handler = source.index("    except StopExecution as exc:\n")

    assert exact_postcheck < runtime_postcheck < mutation_complete < stopped_handler


def test_prechange_snapshot_authority_is_recorded_before_mutation_start() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")

    snapshot = source.index("        digest = save_prechange_snapshot(root, prestate_raw)\n")
    recorded = source.index(
        "        closure[\"prechange_dynsec_snapshot_sha256_recorded\"] = bool(digest)\n"
    )
    mutation_start = source.index("        mutation_started = True\n")

    assert snapshot < recorded < mutation_start
