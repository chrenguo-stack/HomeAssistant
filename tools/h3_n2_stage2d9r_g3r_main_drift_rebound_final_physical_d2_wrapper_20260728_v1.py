#!/usr/bin/env python3
"""Final physical-D2 wrapper rebound to the accepted main-drift successor.

This module does not alter immutable/recovery payload bytes or the repaired
payload extraction implementation. With no exact physical authorization it is
inert and performs no board, serial, esptool, Flash/NVS, Broker, PREPARE or
VERIFY operation.
"""
from __future__ import annotations

from typing import Any

import h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1 as handoff
import h3_n2_stage2d9r_g3r_main_drift_successor_rebind_contract_20260728_v1 as contract

core = handoff.core
STAGE = contract.STAGE
D2_REQUEST_ID = contract.NEW_PHYSICAL_D2_REQUEST_ID
AUTH_SCHEMA = "gh.h3.n2.stage2d9r-g3r-main-drift-rebound-physical-d2-authorization/1"
RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-main-drift-rebound-physical-d2-result/1"
MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-main-drift-rebound-physical-d2-marker/1"
PRE_RESULT_SCHEMA = "gh.h3.n2.stage2d9r-g3r-main-drift-rebound-physical-d2-preclaim-result/1"
PRE_MARKER_SCHEMA = "gh.h3.n2.stage2d9r-g3r-main-drift-rebound-physical-d2-preclaim-marker/1"

_ORIGINAL_CONFIGURE_CORE = handoff.configure_core


def configure_core() -> Any:
    # The frozen wrapper reads this module global at configure time. Rebinding
    # only the accepted-main value preserves every immutable/recovery binding.
    handoff.frozen.ACCEPTED_CURRENT_MAIN_SHA = contract.ACCEPTED_CURRENT_MAIN_SHA
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
            "main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
            "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
            "main_drift_commit_sha": contract.MAIN_DRIFT_COMMIT_SHA,
            "main_drift_rebind_source_sha": value.get("source_sha"),
            "upstream_host_final_preflight_source_sha": contract.BASE_HEAD_SHA,
            "upstream_artifact_id": contract.UPSTREAM_ARTIFACT_ID,
            "upstream_artifact_sha256": contract.UPSTREAM_ARTIFACT_SHA256,
            "upstream_review_binding_sha256": contract.UPSTREAM_REVIEW_BINDING_SHA256,
            "upstream_execution_package_sha256": contract.UPSTREAM_EXECUTION_PACKAGE_SHA256,
            "h2_authorization_id": contract.H2_AUTHORIZATION_ID,
            "h2_status": "CONSUMED_PASS",
            "h2_replay_permitted": False,
            "h2_result_sha256": contract.H2_RESULT_CANONICAL_SHA256,
            "previous_request_id": contract.OLD_PHYSICAL_D2_REQUEST_ID,
            "previous_request_state": contract.OLD_PHYSICAL_D2_REQUEST_STATE,
            "previous_request_binding_sha256": contract.OLD_REQUEST_BINDING_SHA256,
            "previous_request_reuse_permitted": False,
        }
        for key, expected in required.items():
            core.require(
                value.get(key) == expected,
                "AUTHORIZATION_" + key.upper() + "_MISMATCH",
            )
        core.require(
            isinstance(value.get("source_sha"), str)
            and core.HEX40.fullmatch(value["source_sha"]) is not None
            and value["source_sha"] != contract.BASE_HEAD_SHA
            and value.get("host_final_preflight_source_sha") == value.get("source_sha"),
            "AUTHORIZATION_REBOUND_SOURCE_MISMATCH",
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
