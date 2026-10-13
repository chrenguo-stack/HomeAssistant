from __future__ import annotations

from typing import Any

import pytest
from n3w_t1_r2c_evidence_schema import (
    EvidenceSchemaError,
    REQUIREMENT_FIELDS,
    REQUIREMENT_IDS,
    public_requirement_projection,
    validate_report,
)


def _field(value: Any = None, status: str = "NOT_EXECUTED") -> dict[str, Any]:
    return {"value": value, "status": status}


def _requirement(requirement_id: str) -> dict[str, Any]:
    return {
        "status": "NOT_EXECUTED",
        "complete": False,
        "reason_code": None,
        "method_ids": [],
        "provenance": [],
        "fields": {
            name: _field() for name in sorted(REQUIREMENT_FIELDS[requirement_id])
        },
    }


def _report() -> dict[str, Any]:
    return {
        "schema": "gh.n3w.t1-r2c-readonly-evidence/1",
        "execution_id": "r2c-test-execution",
        "source_head": "a" * 40,
        "probe_sha256": "b" * 64,
        "contract_sha256": "c" * 64,
        "authorization": {
            "grant_id": "",
            "granted": False,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        },
        "target_binding": {},
        "requirements": {
            requirement_id: _requirement(requirement_id)
            for requirement_id in REQUIREMENT_IDS
        },
        "capture_status": "NOT_EXECUTED",
        "static_review_status": "NOT_EXECUTED",
        "stop_reasons": [],
        "boundaries": {
            "t1_access": False,
            "intentional_target_write": False,
            "service_mutation": False,
            "board_access": False,
            "merge": False,
        },
        "os_identity_semantics_proven": False,
        "controlled_clone_boot_required": True,
        "disk_capture_ready": False,
        "public_projection_review": "NOT_REVIEWED",
    }


def test_schema_accepts_exact_not_executed_report() -> None:
    validate_report(_report())


def test_schema_rejects_extra_top_level_key() -> None:
    report = _report()
    report["unexpected"] = True
    with pytest.raises(EvidenceSchemaError, match="top_level_keys"):
        validate_report(report)


def test_schema_requires_exact_e1_to_e9_and_exact_fields() -> None:
    report = _report()
    del report["requirements"]["E9"]
    with pytest.raises(EvidenceSchemaError, match="requirements_keys"):
        validate_report(report)

    report = _report()
    del report["requirements"]["E4"]["fields"]["contents_equal"]
    with pytest.raises(EvidenceSchemaError, match="E4_fields_keys"):
        validate_report(report)


def test_schema_keeps_clone_semantics_and_disk_readiness_false() -> None:
    report = _report()
    report["os_identity_semantics_proven"] = True
    with pytest.raises(EvidenceSchemaError, match="os_identity_semantics_proven"):
        validate_report(report)

    report = _report()
    report["controlled_clone_boot_required"] = False
    with pytest.raises(EvidenceSchemaError, match="controlled_clone_boot_required"):
        validate_report(report)

    report = _report()
    report["disk_capture_ready"] = True
    with pytest.raises(EvidenceSchemaError, match="disk_capture_ready"):
        validate_report(report)


def test_schema_rejects_unknown_method_id() -> None:
    report = _report()
    report["requirements"]["E1"]["method_ids"] = ["SHELL"]
    with pytest.raises(EvidenceSchemaError, match="E1_method_ids"):
        validate_report(report)


def test_public_projection_never_copies_private_values() -> None:
    e4 = _requirement("E4")
    e4["fields"]["etc_machine_id"] = _field("raw-machine-id", "OBSERVED")
    e4["fields"]["path_relation"] = _field("raw-sensitive-path-value", "OBSERVED")
    projected = public_requirement_projection("E4", e4)
    rendered = repr(projected)
    assert "raw-machine-id" not in rendered
    assert "raw-sensitive-path-value" not in rendered
    assert "etc_machine_id" not in projected["fields"]
    assert projected["fields"]["path_relation"] == {"status": "OBSERVED"}


def test_public_projection_drops_values_even_for_public_field_names() -> None:
    e6 = _requirement("E6")
    e6["fields"]["nm_state_inventory"] = _field(
        {"raw_ip": "10.0.0.7", "raw_mac": "aa:bb:cc:dd:ee:ff"},
        "OBSERVED",
    )
    projected = public_requirement_projection("E6", e6)
    rendered = repr(projected)
    assert "10.0.0.7" not in rendered
    assert "aa:bb:cc:dd:ee:ff" not in rendered
    assert projected["fields"]["nm_state_inventory"] == {"status": "OBSERVED"}
