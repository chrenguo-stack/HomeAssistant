from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REPORT_SCHEMA = "gh.c06-history-fault-matrix-report/1"
REQUIRED_FILES = (
    "execution.json",
    "images.json",
    "prepare.json",
    "manager-db-init.json",
    "observer-ready.json",
    "mqtt-capture.json",
    "initial.json",
    "fault-seed.json",
    "fault-retry.json",
    "fault-recovery.json",
    "fault-broker-restart.json",
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


def safe_document(document: dict[str, Any]) -> bool:
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
    seed = documents["fault-seed.json"]
    retry = documents["fault-retry.json"]
    recovery = documents["fault-recovery.json"]
    broker = documents["fault-broker-restart.json"]
    cleanup = documents["cleanup.json"]
    checks = {
        "execution_passed": (
            args.execution_exit_code == 0 and execution.get("status") == "passed"
        ),
        "exact_base_verified": args.exact_base_verified,
        "base_ancestor_verified": args.base_ancestor_verified,
        "authorized_file_boundary_verified": args.authorized_file_boundary_verified,
        "revision_two_seeded_pending": (
            seed.get("revision") == 2
            and seed.get("state") == "pending"
            and seed.get("attempts") == 0
        ),
        "homeassistant_outage_produced_retry": (
            retry.get("revision") == 2
            and retry.get("state") == "retry"
            and retry.get("attempts", 0) >= 1
            and retry.get("retry_fail_closed") is True
        ),
        "durable_restart_reconciled": (
            recovery.get("revision") == 2
            and recovery.get("manager_job_state") == "completed"
            and recovery.get("target_ledger_state") == "verified"
            and recovery.get("recorder_readback_exact") is True
            and recovery.get("durable_retry_reconciled") is True
        ),
        "broker_restart_idempotent": (
            broker.get("broker_restarted") is True
            and broker.get("mqtt_clients_reconnected") is True
            and broker.get("same_revision_idempotent_status") == "verified"
            and broker.get("projection_hash_exact") is True
            and broker.get("result_qos") == 1
            and broker.get("result_retain") is False
        ),
        "cleanup_complete": (
            cleanup.get("cleanup_complete") is True
            and cleanup.get("remaining_test_containers") == 0
            and cleanup.get("remaining_test_volumes") == 0
            and cleanup.get("remaining_test_networks") == 0
            and cleanup.get("host_ports_published") == 0
        ),
        "all_documents_secret_free_and_nonproduction": all(
            safe_document(document) for document in documents.values() if document
        ),
    }
    status = "passed" if not missing and all(checks.values()) else "failed"
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
        "evidence_file_sha256": {
            name: sha256_file(root / name)
            for name in REQUIRED_FILES
            if (root / name).is_file()
        },
        "runtime_code_changed": False,
        "runtime_defaults_changed": False,
        "t1_accessed": False,
        "production_services_accessed": False,
        "physical_board_accessed": False,
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
        json.dumps(report, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
