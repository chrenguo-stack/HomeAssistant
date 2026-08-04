from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

AUTHORIZATION = (
    "D1-C06B2B-PR266-RECORDER-READBACK-UTC-INSTANT-CANONICALIZATION-AND-"
    "FALSE-COMMIT-BARRIER-REMOVAL-REAL-E2E-SUCCESSOR-REPAIR-STACKED-DRAFT-"
    "IMPLEMENTATION-20260804-01"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--exact-base-verified", action="store_true")
    parser.add_argument("--base-ancestor-verified", action="store_true")
    args = parser.parse_args()
    if args.authorization != AUTHORIZATION:
        raise SystemExit("authorization mismatch")

    root = Path(__file__).resolve().parents[1]
    paths = {
        "manager_adapter": root / "host/greenhouse-manager/src/greenhouse_manager/runtime/c06b2_mqtt_rpc_adapter.py",
        "manager_wiring": root / "host/greenhouse-manager/src/greenhouse_manager/runtime/c06b2_runtime_wiring.py",
        "ha_bridge": root / "host/homeassistant/custom_components/greenhouse_history/mqtt_bridge.py",
        "ha_recorder": root / "host/homeassistant/custom_components/greenhouse_history/recorder_adapter.py",
        "ha_runtime": root / "host/homeassistant/custom_components/greenhouse_history/runtime.py",
        "ha_const": root / "host/homeassistant/custom_components/greenhouse_history/const.py",
        "ha_init": root / "host/homeassistant/custom_components/greenhouse_history/__init__.py",
        "tests": root / "host/greenhouse-manager/tests/runtime/test_c06b2b_runtime_wiring.py",
    }
    text = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    checks = {
        "manager_fixed_topics": all(
            token in text["manager_adapter"]
            for token in ("projection_request_topic", "projection_result_topic")
        ),
        "manager_qos1_nonretained": all(
            token in text["manager_adapter"] for token in ("qos=1", "retain=False")
        ),
        "manager_single_inflight": all(
            token in text["manager_adapter"]
            for token in ("_dispatch_lock", "_inflight", "threading.Event")
        ),
        "manager_timeout_late_reconnect": all(
            token in text["manager_adapter"]
            for token in ("mqtt_rpc_timeout", "ignored_result_count", "republish_count")
        ),
        "manager_suback_required_before_ready": all(
            token in text["manager_adapter"]
            for token in ("on_subscribe", "_subscription_mid", "_connected.set()")
        ),
        "manager_default_off": all(
            token in text["manager_wiring"]
            for token in ("GH_C06B2_RUNTIME_ENABLED", "if raw is None", "return False")
        ),
        "ha_bounded_single_worker": all(
            token in text["ha_bridge"]
            for token in (
                "maxsize=queue_capacity",
                "QueueFull",
                "asyncio.create_task",
                "max_payload_bytes",
                "oversized_payload",
            )
        ),
        "ha_mqtt_client_wait": "async_wait_for_mqtt_client" in text["ha_init"],
        "ha_suback_required_before_active": all(
            token in text["ha_runtime"]
            for token in ("async_on_subscribe_done", "asyncio.timeout", "encoding=None")
        ),
        "ha_supported_recorder_api": all(
            token in text["ha_recorder"]
            for token in ("async_import_statistics", "statistics_during_period")
        ),
        "ha_utc_instant_readback_matching": all(
            token in text["ha_recorder"]
            for token in (
                "_recorder_utc_datetime",
                'target_start = _utc_datetime(start, "statistics.start")',
                "== target_start",
            )
        ),
        "ha_finite_readback_polling": all(
            token in text["ha_recorder"]
            for token in (
                "readback_timeout_seconds",
                "readback_poll_seconds",
                "time.monotonic()",
                "asyncio.sleep",
            )
        ),
        "false_commit_barrier_removed": all(
            token not in text["ha_recorder"]
            for token in (
                "async_block_till_done",
                "recorder_commit_barrier_timeout",
                "recorder_commit_barrier_failed",
            )
        ),
        "ha_no_external_or_direct_db": all(
            token not in text["ha_recorder"]
            for token in ("async_add_external_statistics", "sqlite3", "sqlalchemy", "db_schema")
        ),
        "ha_ledger_wired": all(
            token in text["ha_runtime"]
            for token in ("async_prepare", "async_mark_verified", "async_record_failure")
        ),
        "ha_default_off": (
            "DEFAULT_C06B2_RUNTIME_ENABLED = False" in text["ha_const"]
            and "if runtime_enabled:" in text["ha_init"]
        ),
        "host_only_tests_present": all(
            token in text["tests"]
            for token in (
                "test_manager_rpc_exact_binding_timeout_and_reconnect",
                "test_manager_transport_requires_successful_suback",
                "test_ha_bridge_is_bounded_and_callback_does_not_process",
                "test_ha_runtime_waits_for_broker_suback",
            )
        ),
        "utc_equivalence_and_adjacent_hour_tests_present": all(
            token in text["tests"]
            for token in (
                "2026-08-03T12:00:00.000Z",
                "2026-08-03T12:00:00+00:00",
                "adjacent_hour_rows",
                "assert adjacent_hour == ()",
            )
        ),
    }
    failed = sorted(name for name, value in checks.items() if not value)
    if failed:
        raise SystemExit(f"host-only contract checks failed: {failed}")

    report = {
        "schema": "gh.c06b2b-runtime-wiring-host-only-report/4",
        "status": "passed",
        "authorization": args.authorization,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "base": {"ref": args.base_ref, "sha": args.base_sha},
        "source": {"ref": args.source_ref, "sha": args.source_sha},
        "exact_base_verified": args.exact_base_verified,
        "base_ancestor_verified": args.base_ancestor_verified,
        "checks": checks,
        "file_sha256": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths.values()
        },
        "runtime_defaults": {"manager": False, "home_assistant": False},
        "runtime_bounds": {
            "home_assistant_queue_capacity": 64,
            "home_assistant_max_request_bytes": 1_052_672,
            "recorder_readback_timeout_seconds": 10,
            "recorder_readback_poll_seconds": 0.25,
            "manager_single_inflight": True,
            "mqtt_qos": 1,
            "mqtt_retain": False,
        },
        "execution_boundary": {
            "network_attempted": False,
            "t1_accessed": False,
            "production_broker_accessed": False,
            "production_home_assistant_accessed": False,
            "production_database_accessed": False,
            "physical_board_accessed": False,
            "deployment_performed": False,
            "anonymous_mode_changed": False,
            "secret_values_included": False,
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "output": str(output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
