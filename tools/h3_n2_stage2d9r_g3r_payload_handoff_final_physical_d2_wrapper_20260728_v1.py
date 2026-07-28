#!/usr/bin/env python3
"""Final physical-D2 binding over the frozen payload-handoff repair wrapper.

The module remains inert without a future exact authorization. It does not alter
immutable/recovery payload bytes or the repaired extraction implementation.
"""
from __future__ import annotations

from typing import Any

import h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1 as handoff
import h3_n2_stage2d9r_g3r_payload_handoff_host_final_preflight_contract_20260728_v1 as contract

core = handoff.core
STAGE = contract.STAGE
D2_REQUEST_ID = contract.PHYSICAL_D2_REQUEST_ID
AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-payload-handoff-repaired-physical-d2-authorization/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-payload-handoff-repaired-physical-d2-result/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-payload-handoff-repaired-physical-d2-marker/1"
PRE_RESULT_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-payload-handoff-repaired-physical-d2-preclaim-result/1"
)
PRE_MARKER_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-payload-handoff-repaired-physical-d2-preclaim-marker/1"
)

_ORIGINAL_CONFIGURE_CORE = handoff.configure_core


def configure_core() -> Any:
    configured = _ORIGINAL_CONFIGURE_CORE()
    configured.STAGE = STAGE
    configured.D2_REQUEST_ID = D2_REQUEST_ID
    configured.AUTH_SCHEMA = AUTH_SCHEMA
    configured.RESULT_SCHEMA = RESULT_SCHEMA
    configured.MARKER_SCHEMA = MARKER_SCHEMA

    original_validate = configured.validate_authorization

    def validate_authorization(*args: Any, **kwargs: Any) -> dict[str, Any]:
        value = original_validate(*args, **kwargs)
        required = {
            "payload_handoff_repair_source_sha": contract.BASE_HEAD_SHA,
            "payload_handoff_base_pr": contract.BASE_PR,
            "payload_handoff_base_head_sha": contract.BASE_HEAD_SHA,
            "payload_repair_artifact_id": contract.PAYLOAD_REPAIR_ARTIFACT_ID,
            "payload_repair_artifact_sha256": contract.PAYLOAD_REPAIR_ARTIFACT_SHA256,
            "payload_repair_review_binding_sha256": (
                contract.PAYLOAD_REPAIR_REVIEW_BINDING_SHA256
            ),
            "payload_repair_execution_package_sha256": (
                contract.PAYLOAD_REPAIR_EXECUTION_PACKAGE_SHA256
            ),
            "payload_handoff_contract": contract.PAYLOAD_HANDOFF_CONTRACT,
            "preclaim_failure_contract": contract.PRECLAIM_FAILURE_CONTRACT,
            "old_physical_d2_id": contract.OLD_PHYSICAL_D2_ID,
            "old_physical_d2_status": contract.OLD_PHYSICAL_D2_STATUS,
            "old_physical_d2_failure_code": contract.OLD_PHYSICAL_D2_FAILURE,
            "old_physical_d2_replay_permitted": False,
        }
        for key, expected in required.items():
            core.require(
                value.get(key) == expected,
                "AUTHORIZATION_" + key.upper() + "_MISMATCH",
            )
        core.require(
            value.get("host_final_preflight_source_sha") == value.get("source_sha")
            and isinstance(value.get("source_sha"), str)
            and core.HEX40.fullmatch(value["source_sha"]) is not None
            and value["source_sha"] != contract.BASE_HEAD_SHA,
            "AUTHORIZATION_HOST_FINAL_PREFLIGHT_SOURCE_MISMATCH",
        )
        return value

    configured.validate_authorization = validate_authorization
    configured.__file__ = __file__
    return configured


def install() -> None:
    handoff.STAGE = STAGE
    handoff.D2_REQUEST_ID = D2_REQUEST_ID
    handoff.AUTH_SCHEMA = AUTH_SCHEMA
    handoff.RESULT_SCHEMA = RESULT_SCHEMA
    handoff.MARKER_SCHEMA = MARKER_SCHEMA
    handoff.PRE_RESULT_SCHEMA = PRE_RESULT_SCHEMA
    handoff.PRE_MARKER_SCHEMA = PRE_MARKER_SCHEMA
    handoff.configure_core = configure_core


def main() -> int:
    install()
    return handoff.main()


if __name__ == "__main__":
    raise SystemExit(main())
