#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ACCEPTANCE_BINDING = "f45a7a5865ff383378dd3fd0cbb0a035c600eb3271777a330fc9ceb486f92582"
PENDING_BINDING = "a7b3b259c45ef058111b15e5fbc67ccd0b0fa8474fd1762f3ac5cc483a1d4dfa"
NEXT_GATE = "D1-H3N2-STAGE2D9R-G3R-D2-17-G11-PHYSICAL-EXECUTION-20260731-01"


class G11AcceptanceError(RuntimeError):
    pass


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise G11AcceptanceError("JSON_NOT_REGULAR")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G11AcceptanceError("JSON_NOT_OBJECT")
    return value


def verify_acceptance(value: dict[str, Any]) -> None:
    embedded = value.get("acceptance_binding_sha256")
    core = dict(value)
    core.pop("acceptance_binding_sha256", None)
    if embedded != ACCEPTANCE_BINDING or canonical_sha256(core) != ACCEPTANCE_BINDING:
        raise G11AcceptanceError("ACCEPTANCE_BINDING_DRIFT")

    required = {
        "status": "PASS",
        "state": "TARGET_MAC_STATIC_CHECK_ACCEPTED_AUTHORIZATION_UNCLAIMED_UNCONSUMED",
        "terminal_state": "TARGET_MAC_STATIC_CHECK_PASSED_AUTHORIZATION_UNCLAIMED_UNCONSUMED",
        "d2_request_id": "D2-H3N2-STAGE2D9R-G3R-EXECUTION-IDENTITY-FROZEN-PREFLIGHT-STABILIZED-PHYSICAL-20260730-17",
        "static_check_decision_id": "D1-H3N2-STAGE2D9R-G3R-D2-17-G11-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01",
        "acceptance_decision_id": "D1-H3N2-STAGE2D9R-G3R-D2-17-G11-TARGET-MAC-STATIC-CHECK-ACCEPTANCE-20260731-01",
        "package_generation": "G11",
        "public_source_pr": 240,
        "public_source_head_sha": "b82c6c49729eabece02865e0c120b24ef6112511",
        "private_delivery_binding_sha256": "a488108f42e2a6f0a857aa6e14e7e00b1a1e8c9334e415c28d298890fab92cf2",
        "terminal_record_sha256": "308f7c426d7e4be1c7d31d595aa18b1abc79736857f2f730f377c6d48c6ac17c",
        "authorization_file_sha256": "18d8ea178ab571e6511c4e7ebad41f483657f10f26b09334a240db4e1ece7687",
        "authorization_record_sha256": "fe0e9a997e2e1674d8960a63fb87f1ad23e1dde486dec7639b2209a088b1fc09",
        "execution_identity_sha256": "9e234234aed566752ab8feb771e4cb84c3946d83857ee13d3d211d6c7e11f00c",
        "configured_runtime_validator_check_sha256": "037b39227757f1433dcfe45a4befbeda2f66774621819283f50b79f4d79892d7",
        "export_summary_sha256": "6d0a4c55f2467e544592951dae3f194f0fa4c43c82ccdd5ba15362e2a3e36f4f",
        "g09_failure_disposition_binding_sha256": "3430906e3b3fb7890e2bade085e5c7adb949444005fe421698c640a0913d35f0",
        "g10_expired_disposition_binding_sha256": "eca6986ee9fba51bcd877969a924203fd10f3f5f2954e6be1d1fc2f669282b5b",
        "g10_expired_disposition_artifact_id": 8786121320,
        "g10_expired_disposition_artifact_sha256": "77e9a40adbd97bb2cb4b28557bdd0d179015c19b861b0c46b8aaca1d2ebd869d",
        "g11_pending_binding_sha256": "db404b7ca1367c2bd5bd6adf82d3060d8ac34c7056e5576907e0e8d77fae7281",
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
        "g10_private_material_accessed": False,
        "g10_replay_permitted": False,
        "private_paths_included": False,
        "secret_values_included": False,
        "configured_core_validate_authorization_executed": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise G11AcceptanceError("FIELD_DRIFT:" + key)


def verify_pending(value: dict[str, Any]) -> None:
    embedded = value.get("physical_pending_binding_sha256")
    core = dict(value)
    core.pop("physical_pending_binding_sha256", None)
    if embedded != PENDING_BINDING or canonical_sha256(core) != PENDING_BINDING:
        raise G11AcceptanceError("PHYSICAL_PENDING_BINDING_DRIFT")

    required = {
        "base_pr": 240,
        "base_head_sha": "b82c6c49729eabece02865e0c120b24ef6112511",
        "decision_id": "D1-H3N2-STAGE2D9R-G3R-D2-17-G11-TARGET-MAC-STATIC-CHECK-ACCEPTANCE-20260731-01",
        "g11_acceptance_binding_sha256": ACCEPTANCE_BINDING,
        "authorization_record_sha256": "fe0e9a997e2e1674d8960a63fb87f1ad23e1dde486dec7639b2209a088b1fc09",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_execution_authorized": False,
        "next_gate": NEXT_GATE,
        "state": "PHYSICAL_EXECUTION_PENDING_EXPLICIT_AUTHORIZATION",
        "automatic_retry_permitted": False,
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise G11AcceptanceError("PENDING_FIELD_DRIFT:" + key)
    for key in ("ready", "merge", "release", "tag", "deployment"):
        if value.get(key) is not False:
            raise G11AcceptanceError("FORBIDDEN_STATE:" + key)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    verify_acceptance(
        load_json(root / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g11-target-mac-static-check-pass-20260731-v1.json")
    )
    verify_pending(
        load_json(root / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g11-physical-execution-pending-20260731-v1.json")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
