#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ACCEPTANCE_BINDING = "a74ef9f82b4339ab3f066804127fdbcd050c0846c44ee44c3d064093215997d3"
PENDING_BINDING = "9d4ad3b74f1fdcb2094ad0e93b229b37d5b642ba9f341e3935b43c05dadb9710"
NEXT_GATE = "D1-H3N2-STAGE2D9R-G3R-D2-17-G10-PHYSICAL-EXECUTION-20260731-01"


class G10AcceptanceError(RuntimeError):
    pass


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise G10AcceptanceError("JSON_NOT_REGULAR")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G10AcceptanceError("JSON_NOT_OBJECT")
    return value


def verify_acceptance(value: dict[str, Any]) -> None:
    embedded = value.get("acceptance_binding_sha256")
    core = dict(value)
    core.pop("acceptance_binding_sha256", None)
    if embedded != ACCEPTANCE_BINDING or canonical_sha256(core) != ACCEPTANCE_BINDING:
        raise G10AcceptanceError("ACCEPTANCE_BINDING_DRIFT")

    required = {
        "status": "PASS",
        "state": "TARGET_MAC_STATIC_CHECK_ACCEPTED_AUTHORIZATION_UNCLAIMED_UNCONSUMED",
        "terminal_state": "TARGET_MAC_STATIC_CHECK_PASSED_AUTHORIZATION_UNCLAIMED_UNCONSUMED",
        "d2_request_id": "D2-H3N2-STAGE2D9R-G3R-EXECUTION-IDENTITY-FROZEN-PREFLIGHT-STABILIZED-PHYSICAL-20260730-17",
        "static_check_decision_id": "D1-H3N2-STAGE2D9R-G3R-D2-17-G10-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01",
        "acceptance_decision_id": "D1-H3N2-STAGE2D9R-G3R-D2-17-G10-TARGET-MAC-STATIC-CHECK-ACCEPTANCE-20260731-01",
        "package_generation": "G10",
        "public_source_pr": 238,
        "public_source_head_sha": "b830358b36491eb698703a259d4697099a1e6076",
        "private_delivery_binding_sha256": "db77e7a90cd2379d245f2bbe4293afede97cf6ac281a82c06fc66e1df1397b92",
        "terminal_record_sha256": "9cbf3a52192df3f0d4ecbb785ea220247e624e0503763d2b417ba01b2cd238cd",
        "authorization_file_sha256": "77836f0f687eb85f54cee043146cf3a4f8471a038007be5747ed485bf1704d9e",
        "authorization_record_sha256": "f9d0e6a4402a988e92e7832bb2bbef73806846b5fcf4725de8299f247e44ca23",
        "execution_identity_sha256": "9e234234aed566752ab8feb771e4cb84c3946d83857ee13d3d211d6c7e11f00c",
        "configured_runtime_validator_check_sha256": "00fe7f67bf7fee34b9882a3f36e8bbd55141bbfbcdaa2abe17517fc693691128",
        "export_summary_sha256": "d73aa8ccb29543e2e1c3dbf1b804ea3609ec92c694b230aaf4181636a5fbb4f7",
        "g09_failure_disposition_binding_sha256": "3430906e3b3fb7890e2bade085e5c7adb949444005fe421698c640a0913d35f0",
        "g10_marker_digest_repair_binding_sha256": "67a59fcfb78a6ad4805ec26239921a80d874a70ed128d9bc155c619aa7c4681e",
        "g10_marker_digest_repair_artifact_id": 8782989455,
        "g10_marker_digest_repair_artifact_sha256": "2ab42b044e30e9b8f324942bf3c4ac9e4facda98c55c6b8d7c665d9a15ed84ab",
        "authorization_created": True,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_decision_created": False,
        "all_physical_operation_flags_false": True,
        "hardware_sentinels_all_zero": True,
        "identity_adapter_installed": True,
        "marker_digest_adapter_installed": True,
        "marker_digest_compatibility_verified": True,
        "outer_configure_core_called": False,
        "g09_private_material_accessed": False,
        "g09_replay_permitted": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "configured_core_validate_authorization_executed": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise G10AcceptanceError("FIELD_DRIFT:" + key)


def verify_pending(value: dict[str, Any]) -> None:
    embedded = value.get("physical_pending_binding_sha256")
    core = dict(value)
    core.pop("physical_pending_binding_sha256", None)
    if embedded != PENDING_BINDING or canonical_sha256(core) != PENDING_BINDING:
        raise G10AcceptanceError("PHYSICAL_PENDING_BINDING_DRIFT")

    required = {
        "base_pr": 238,
        "base_head_sha": "b830358b36491eb698703a259d4697099a1e6076",
        "decision_id": "D1-H3N2-STAGE2D9R-G3R-D2-17-G10-TARGET-MAC-STATIC-CHECK-ACCEPTANCE-20260731-01",
        "g10_acceptance_binding_sha256": ACCEPTANCE_BINDING,
        "authorization_record_sha256": "f9d0e6a4402a988e92e7832bb2bbef73806846b5fcf4725de8299f247e44ca23",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_execution_authorized": False,
        "next_gate": NEXT_GATE,
        "state": "PHYSICAL_EXECUTION_PENDING_EXPLICIT_AUTHORIZATION",
        "automatic_retry_permitted": False,
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise G10AcceptanceError("PENDING_FIELD_DRIFT:" + key)
    for key in ("ready", "merge", "release", "tag", "deployment"):
        if value.get(key) is not False:
            raise G10AcceptanceError("FORBIDDEN_STATE:" + key)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    verify_acceptance(
        load_json(root / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g10-target-mac-static-check-pass-20260731-v1.json")
    )
    verify_pending(
        load_json(root / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g10-physical-execution-pending-20260731-v1.json")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
