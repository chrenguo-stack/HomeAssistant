from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REPORT_SCHEMA = "gh.c06b2c-isolated-e2e-report/2"
REQUIRED_FILES = (
    "execution.json",
    "images.json",
    "prepare.json",
    "manager-db-init.json",
    "observer-ready.json",
    "mqtt-capture.json",
    "initial.json",
    "monotonic-attempt.json",
    "monotonic.json",
    "restart.json",
    "cleanup.json",
)


def read_document(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def false_boundary(document: dict[str, Any]) -> bool:
    return (
        document.get("production_state_modified") is not True
        and document.get("production_services_modified") is not True
        and document.get("secret_values_included") is not True
        and document.get("direct_home_assistant_database_read") is not True
        and document.get("direct_home_assistant_database_write") is not True
    )


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.input_dir)
    documents = {name: read_document(root / name) for name in REQUIRED_FILES}
    missing = [name for name, document in documents.items() if not document]

    execution = documents["execution.json"]
    prepare = documents["prepare.json"]
    database_init = documents["manager-db-init.json"]
    observer = documents["observer-ready.json"]
    capture = documents["mqtt-capture.json"]
    initial = documents["initial.json"]
    monotonic_attempt = documents["monotonic-attempt.json"]
    monotonic = documents["monotonic.json"]
    restart = documents["restart.json"]
    cleanup = documents["cleanup.json"]
    images = documents["images.json"]

    request = capture.get("request") if isinstance(capture.get("request"), dict) else {}
    result = capture.get("result") if isinstance(capture.get("result"), dict) else {}
    attempts = (
        monotonic_attempt.get("attempts")
        if isinstance(monotonic_attempt.get("attempts"), dict)
        else {}
    )

    checks = {
        "execution_passed": (
            args.execution_exit_code == 0
            and execution.get("status") == "passed"
            and execution.get("isolated_github_runner") is True
        ),
        "exact_base_verified": args.exact_base_verified,
        "base_ancestor_verified": args.base_ancestor_verified,
        "authorized_file_boundary_verified": args.authorized_file_boundary_verified,
        "runtime_opt_in_isolated_only": (
            prepare.get("runtime_loaded") is True
            and prepare.get("runtime_enabled") is True
            and prepare.get("mqtt_bridge_active") is True
            and prepare.get("recorder_write_active") is True
        ),
        "mqtt_discovery_targets_created": (
            prepare.get("mqtt_discovery_used") is True
            and len(prepare.get("entity_unique_ids", [])) == 2
        ),
        "manager_store_initialized_pending": (
            database_init.get("state") == "pending"
            and database_init.get("revision") == 1
            and database_init.get("record_count") == 1
        ),
        "mqtt_observer_subacknowledged": observer.get("subscribed") is True,
        "request_qos1_nonretained": (
            request.get("qos") == 1 and request.get("retain") is False
        ),
        "result_qos1_nonretained": (
            result.get("qos") == 1 and result.get("retain") is False
        ),
        "initial_request_result_bound": (
            request.get("request_id") == result.get("request_id")
            and request.get("projection_hash") == result.get("projection_hash")
            and request.get("revision") == result.get("revision") == 1
            and result.get("status") == "verified"
        ),
        "manager_job_completed": initial.get("manager_job_state") == "completed",
        "target_ledger_verified": initial.get("target_ledger_state") == "verified",
        "recorder_readback_exact": initial.get("recorder_readback_exact") is True,
        "monotonic_attempt_evidence_complete": set(attempts) == {
            "idempotent",
            "higher_revision",
            "lower_revision",
            "same_revision_conflict",
        },
        "idempotent_same_revision_verified": (
            monotonic.get("idempotent_status") == "verified"
        ),
        "higher_revision_verified": (
            monotonic.get("higher_revision") == 2
            and monotonic.get("higher_revision_status") == "verified"
            and monotonic.get("higher_readback_exact") is True
        ),
        "lower_revision_blocked": (
            monotonic.get("lower_revision_status") == "blocked"
            and monotonic.get("lower_revision_code") == "target_newer_revision"
        ),
        "same_revision_conflict_blocked": (
            monotonic.get("same_revision_conflict_status") == "blocked"
            and monotonic.get("same_revision_conflict_code")
            == "target_same_revision_hash_conflict"
        ),
        "homeassistant_restart_observed": (
            restart.get("homeassistant_restarted") is True
            and restart.get("old_boot_token")
            and restart.get("new_boot_token")
            and restart.get("old_boot_token") != restart.get("new_boot_token")
        ),
        "ledger_reloaded_after_restart": restart.get("target_ledger_reloaded") is True,
        "recorder_persisted_after_restart": (
            restart.get("recorder_statistics_persisted") is True
        ),
        "restart_idempotent_verified": (
            restart.get("same_revision_idempotent_status") == "verified"
        ),
        "no_duplicate_target_curve": (
            restart.get("duplicate_entity_created") is False
            and restart.get("second_external_statistic_created") is False
        ),
        "cleanup_complete": (
            cleanup.get("cleanup_complete") is True
            and cleanup.get("remaining_test_containers") == 0
            and cleanup.get("remaining_test_volumes") == 0
            and cleanup.get("remaining_test_networks") == 0
            and cleanup.get("host_ports_published") == 0
        ),
        "image_identities_recorded": (
            bool(images.get("mosquitto"))
            and bool(images.get("homeassistant"))
            and bool(images.get("manager"))
        ),
        "all_documents_secret_free_and_nonproduction": all(
            false_boundary(document)
            for document in documents.values()
            if document
        ),
    }
    status = "passed" if not missing and all(checks.values()) else "failed"
    evidence_files = {
        name: sha256_file(root / name)
        for name in REQUIRED_FILES
        if (root / name).is_file()
    }
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
        "authorization": args.authorization,
        "source": {
            "ref": args.source_ref,
            "sha": args.source_sha,
            "base_ref": args.base_ref,
            "base_sha": args.base_sha,
        },
        "missing_evidence_files": missing,
        "checks": checks,
        "monotonic_attempts": attempts,
        "images": images,
        "evidence_file_sha256": evidence_files,
        "runtime_defaults_changed": False,
        "t1_accessed": False,
        "production_broker_accessed": False,
        "production_home_assistant_accessed": False,
        "production_recorder_accessed": False,
        "production_manager_database_accessed": False,
        "physical_board_accessed": False,
        "direct_home_assistant_database_read": False,
        "direct_home_assistant_database_write": False,
        "anonymous_mode_changed": False,
        "ready_for_review": False,
        "ready_for_merge": False,
        "ready_for_deployment": False,
        "secret_values_included": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--execution-exit-code", type=int, required=True)
    parser.add_argument("--exact-base-verified", action="store_true")
    parser.add_argument("--base-ancestor-verified", action="store_true")
    parser.add_argument("--authorized-file-boundary-verified", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
