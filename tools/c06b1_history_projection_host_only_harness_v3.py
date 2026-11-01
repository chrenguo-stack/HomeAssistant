from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from c06b1_history_projection_host_only_harness import run as run_base
from greenhouse_manager.runtime.history_projection import (
    FakeProjectionAdapter,
    aggregate_projection,
)
from greenhouse_manager.runtime.history_projection_store import ProjectionTask

NOW = datetime(2026, 8, 3, 4, 10, tzinfo=UTC)
HOUR = "2026-08-03T04:00:00.000Z"


def _record(temperature: float) -> dict[str, Any]:
    return {
        "boot_id": "boot-monotonic-0001",
        "seq": 1,
        "uptime_ms": 1_000,
        "sampled_at": "2026-08-03T04:00:00Z",
        "time_quality": "trusted",
        "time_anchor": None,
        "cap_hash": "cap-monotonic-0001",
        "fw_version": "1.0.0",
        "measurements": {
            "air_temperature_c": temperature,
            "air_humidity_pct": 65.0,
        },
        "quality": {
            "air_temperature_c": "ok",
            "air_humidity_pct": "ok",
        },
        "power": {"source": "battery", "battery_v": 3.9, "low": False},
    }


def _batch(revision: int, temperature: float):
    task = ProjectionTask(
        node_id="node-monotonic-0001",
        sample_hour=HOUR,
        projection_version=1,
        revision=revision,
        attempts=1,
        claimed_by="monotonic-probe",
        lease_until=NOW + timedelta(seconds=60),
    )
    return aggregate_projection(task, [_record(temperature)])


def _stateful_monotonic_probe() -> dict[str, bool | str | int]:
    adapter = FakeProjectionAdapter()
    revision_1 = _batch(1, 22.0)
    conflicting_revision_1 = _batch(1, 23.0)
    revision_2 = _batch(2, 24.0)

    created = adapter.dispatch(revision_1)
    idempotent = adapter.dispatch(revision_1)
    conflict = adapter.dispatch(conflicting_revision_1)
    replaced = adapter.dispatch(revision_2)
    rejected_lower = adapter.dispatch(revision_1)
    target = adapter.read_target(revision_1.idempotency_key)

    expected_operations = [
        "created",
        "verified-idempotent-readback",
        "rejected-same-revision-conflict",
        "replaced-higher-revision",
        "rejected-lower-revision",
    ]
    return {
        "stateful_fake_target_present": target is not None,
        "monotonic_create_verified": created.status == "verified",
        "monotonic_same_revision_idempotent": (
            idempotent.status == "verified"
            and idempotent.verified_projection_hash == revision_1.projection_hash
        ),
        "monotonic_same_revision_conflict_blocked": (
            conflict.status == "blocked"
            and conflict.code == "target_same_revision_hash_conflict"
        ),
        "monotonic_higher_revision_replaced": replaced.status == "verified",
        "monotonic_lower_revision_rejected": (
            rejected_lower.status == "blocked"
            and rejected_lower.code == "target_newer_revision"
        ),
        "monotonic_target_preserved_at_highest_revision": bool(
            target
            and target.revision == 2
            and target.projection_hash == revision_2.projection_hash
            and target.payload_json == revision_2.payload_json
        ),
        "monotonic_operation_sequence_verified": adapter.operations
        == expected_operations,
        "timeout_unknown_replay_readback_semantics": (
            "verified-idempotent-readback" in adapter.operations
        ),
        "monotonic_target_revision": target.revision if target else 0,
        "monotonic_target_hash": target.projection_hash if target else "",
    }


def run(
    *,
    authorization: str = "local-host-only",
    base_sha: str = "local",
    base_ref: str = "local",
    source_sha: str = "local",
    source_ref: str = "local",
    exact_base_verified: bool = False,
    base_ancestor_verified: bool = False,
) -> dict[str, Any]:
    report = run_base(
        authorization=authorization,
        base_sha=base_sha,
        base_ref=base_ref,
        source_sha=source_sha,
        source_ref=source_ref,
        exact_base_verified=exact_base_verified,
        base_ancestor_verified=base_ancestor_verified,
    )
    probe = _stateful_monotonic_probe()
    report["schema"] = "gh.c06b1-history-projection-host-only-report/3"
    report.update(probe)
    required = (
        "stateful_fake_target_present",
        "monotonic_create_verified",
        "monotonic_same_revision_idempotent",
        "monotonic_same_revision_conflict_blocked",
        "monotonic_higher_revision_replaced",
        "monotonic_lower_revision_rejected",
        "monotonic_target_preserved_at_highest_revision",
        "monotonic_operation_sequence_verified",
        "timeout_unknown_replay_readback_semantics",
    )
    report["monotonic_revision_contract_verified"] = all(
        report[key] is True for key in required
    )
    report["monotonic_evidence_false_positive_removed"] = report[
        "monotonic_revision_contract_verified"
    ]
    if report["monotonic_revision_contract_verified"] is not True:
        raise RuntimeError("stateful monotonic fake-adapter evidence did not verify")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--authorization", default="local-host-only")
    parser.add_argument("--base-sha", default="local")
    parser.add_argument("--base-ref", default="local")
    parser.add_argument("--source-sha", default="local")
    parser.add_argument("--source-ref", default="local")
    parser.add_argument("--exact-base-verified", action="store_true")
    parser.add_argument("--base-ancestor-verified", action="store_true")
    args = parser.parse_args()
    report = run(
        authorization=args.authorization,
        base_sha=args.base_sha,
        base_ref=args.base_ref,
        source_sha=args.source_sha,
        source_ref=args.source_ref,
        exact_base_verified=args.exact_base_verified,
        base_ancestor_verified=args.base_ancestor_verified,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
