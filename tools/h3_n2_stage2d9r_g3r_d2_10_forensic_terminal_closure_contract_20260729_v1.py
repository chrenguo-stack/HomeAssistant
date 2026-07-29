#!/usr/bin/env python3
"""Exact, public-only forensic contract for the failed physical D2-10 run."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

DECISION_ID = (
    "D1-H3N2-STAGE2D9R-G3R-D2-10-FORENSIC-TERMINAL-CLOSURE-"
    "AND-EXECUTOR-REPAIR-20260729-01"
)
D2_REQUEST_ID = (
    "D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-"
    "PHYSICAL-20260729-10"
)
STAGE = "H3/N2 Stage 2D-9R G3R watchdog-repaired payload execution binding"
BASE_PR = 205
BASE_HEAD_SHA = "0ca39a8a284fca70fc69474aadb13ca85492b10d"
LOAD_BEARING_ARTIFACT_ID = 8718562956
LOAD_BEARING_ARTIFACT_SHA256 = (
    "218b2138640dc3d5a21d3a0a6f455b9708de11eac7ca4b6908c167776a36c479"
)
REQUEST_BINDING_SHA256 = (
    "599b0cc7f9468a0fd9b68e1cee0998a69f9c240f6a69324abd24ca900061cc54"
)
AUTHORIZATION_RECORD_SHA256 = (
    "d7b9a37e9272dc834af13c054d15e336f11dafcc0471b268f9557410b84bf287"
)
AUTHORIZATION_FILE_SHA256 = (
    "e4adc24ba07f81dc6286f9cdb0fb8d4632a00e27fbaa12c34cab66c1ab82dd91"
)
EXECUTION_CLOSURE_SHA256 = (
    "6a85e8ec5380db7ee3a09d6de458bd74fa2dfc09d1249c0bbc6a00b32f0ed868"
)
EXECUTION_PACKAGE_SHA256 = (
    "ec02afe63c894ef5bbea4f8537ad588a5cf15f8a9cc2f382092f35e9c0b9ccd2"
)
EXECUTION_CORE_SHA256 = (
    "1fa9428e940f65e98716f20a5ae78904c96db53e94bdfb0ee5da845894c6d3aa"
)
EXECUTION_WRAPPER_SHA256 = (
    "07cf8d68073126a29db6404e4388ce55c339ead76f3f54f57129bdd2a121720b"
)
SOURCE_FORENSIC_TRANSCRIPT_SHA256 = (
    "53eeb04fd5f128068bd947f1b60a896d2f0cb38ed68f7cadbda54f149f1d7e64"
)

MARKER_NAME = (
    "650790fd2f289783aa6c18ed39c5169d498d19f17d4000acd8121bf9d43d154d.json"
)
MARKER_FILE_SHA256 = (
    "af478d31abc45d99fc3beebf9ca1ba5ed42f530a5f34efd2d133db2196bf7af6"
)
CONTRACT_CHECK_FILE_SHA256 = (
    "9a40fb234756e64eaf38ca291e9e53a1bad0634b10c97e6b72b4f55bcd0cf912"
)
TERMINAL_OUTPUT_FILE_SHA256 = (
    "cca7dc73d8540e967d5472389cca3069f135c06c03ad05f6276bcad2f3b8c04f"
)

EVIDENCE_DIGESTS = {
    "broker.redacted.jsonl": (
        "dddca5c42afe8c802cdd272632dc6b1cd555cf64e9db26cdafc2818ebd202434"
    ),
    "prepare-evidence-manifest.json": (
        "46a1c786e21eef26a331f68ceb4a53d95643f2321306ef97135d2be125c15cb2"
    ),
    "prepare-panic-evidence-manifest.json": (
        "2c93b3f7709ae3262a26254b7d8a2c528d09f19182ac495be7b6c3daa03f585a"
    ),
    "prepare-reset-signatures.json": (
        "5b8dc8dcdf842087509f9536c0972dddfa42223bbdeb0648f9948b3471231b3e"
    ),
    "prepare-serial.realtime.redacted.jsonl": (
        "ed9c1cf6d5b1331b2e3b5e12430bf24377cdcfd92f521be6a0081826c5bb6387"
    ),
    "prepare-serial.redacted.jsonl": (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ),
    "prepare-timeline.json": (
        "fc79ad9911a7c35d4728ffd2ba2db4bd16eb1bf547aab1609e67022c49bf0f92"
    ),
    "prepare-timeline.realtime.json": (
        "37daffccf190c4890c35e6a4602dd09679cec774ed210d43c44e4b3a811c449a"
    ),
}

ORIGINAL_MARKER_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-watchdog-repaired-payload-physical-d2-marker/1"
)
FORENSIC_RESULT_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-10-forensic-terminal-result/1"
)
FORENSIC_PLAN_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-10-forensic-terminal-closure-plan/1"
)
CLOSURE_AUTH_SCHEMA = (
    "gh.h3.n2.stage2d9r-g3r-d2-10-forensic-terminal-closure-authorization/1"
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ContractError(RuntimeError):
    """Stable contract failure."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_regular(path: Path, digest: str, code: str) -> bytes:
    require(path.is_file() and not path.is_symlink(), code)
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == digest, code + "_DIGEST")
    return data


def load_json(path: Path, digest: str, code: str) -> dict[str, Any]:
    data = load_regular(path, digest, code)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(code + "_JSON") from exc
    require(isinstance(value, dict), code + "_JSON")
    return value


def _validate_marker(value: dict[str, Any]) -> None:
    require(value.get("schema") == ORIGINAL_MARKER_SCHEMA, "MARKER_SCHEMA")
    require(value.get("stage") == STAGE, "MARKER_STAGE")
    require(value.get("d2_request_id") == D2_REQUEST_ID, "MARKER_REQUEST")
    require(value.get("status") == "CLAIMED", "MARKER_NOT_STALE_CLAIMED")
    require(
        value.get("authorization_record_sha256") == AUTHORIZATION_RECORD_SHA256,
        "MARKER_AUTHORIZATION",
    )
    require(
        value.get("request_binding_sha256") == REQUEST_BINDING_SHA256,
        "MARKER_REQUEST_BINDING",
    )
    require(
        value.get("claimed_at") == "2026-07-29T09:51:02.581896Z",
        "MARKER_CLAIMED_AT",
    )
    require(value.get("one_shot") is True, "MARKER_ONE_SHOT")
    require(value.get("replay_permitted") is False, "MARKER_REPLAY")
    require(
        value.get("automatic_retry_permitted") is False,
        "MARKER_AUTOMATIC_RETRY",
    )


def _validate_contract_check(value: dict[str, Any]) -> None:
    require(value.get("status") == "PASS", "CONTRACT_CHECK_STATUS")
    require(value.get("d2_request_id") == D2_REQUEST_ID, "CONTRACT_CHECK_REQUEST")
    require(
        value.get("request_binding_sha256") == REQUEST_BINDING_SHA256,
        "CONTRACT_CHECK_BINDING",
    )
    for key in (
        "board_operation",
        "usb_enumeration",
        "serial_operation",
        "esptool_operation",
        "flash_operation",
        "network_operation",
        "authorization_claimed",
        "authorization_consumed",
    ):
        require(value.get(key) is False, "CONTRACT_CHECK_" + key.upper())


def _validate_terminal_output(data: bytes) -> None:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("TERMINAL_OUTPUT_JSON") from exc
    require(isinstance(value, dict), "TERMINAL_OUTPUT_JSON")
    require(value.get("status") == "FAIL", "TERMINAL_OUTPUT_STATUS")
    require(value.get("failure_code") == "KeyError", "TERMINAL_OUTPUT_FAILURE")
    require(value.get("d2_request_id") == D2_REQUEST_ID, "TERMINAL_OUTPUT_REQUEST")
    require(value.get("replay_permitted") is False, "TERMINAL_OUTPUT_REPLAY")
    require(
        value.get("automatic_retry_permitted") is False,
        "TERMINAL_OUTPUT_AUTOMATIC_RETRY",
    )


def _validate_timeline(value: dict[str, Any]) -> None:
    require(
        value.get("schema")
        == "gh.h3.n2.stage2d9r-g3r-prepare-timeout-timeline/1",
        "TIMELINE_SCHEMA",
    )
    events = value.get("events")
    require(isinstance(events, list), "TIMELINE_EVENTS")
    kinds = [
        event.get("kind")
        for event in events
        if isinstance(event, dict) and isinstance(event.get("kind"), str)
    ]
    require(kinds.count("PREPARE_COMMAND_SENT") == 1, "PREPARE_COUNT")
    require(kinds.count("PREPARE_RESULT_TIMEOUT") == 1, "PREPARE_TIMEOUT_COUNT")
    require(not any(kind.startswith("VERIFY_") for kind in kinds), "VERIFY_EXECUTED")
    require(kinds.count("BROKER_STARTED") == 1, "BROKER_START_COUNT")
    require(kinds.count("BROKER_STOPPED") == 1, "BROKER_STOP_COUNT")
    before_recovery = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("kind") == "TERMINAL_EVIDENCE_PERSIST_REQUESTED"
        and event.get("before_recovery") is True
        and event.get("failure_code") == "PREPARE_RESULT_TIMEOUT"
    ]
    require(bool(before_recovery), "RECOVERY_ENTRY_EVIDENCE_MISSING")


def validate_forensic_inputs(
    *,
    marker_path: Path,
    contract_check_path: Path,
    terminal_output_path: Path,
    evidence_root: Path,
) -> dict[str, Any]:
    require(marker_path.name == MARKER_NAME, "MARKER_NAME")
    marker = load_json(marker_path, MARKER_FILE_SHA256, "MARKER_FILE")
    _validate_marker(marker)
    contract_check = load_json(
        contract_check_path, CONTRACT_CHECK_FILE_SHA256, "CONTRACT_CHECK_FILE"
    )
    _validate_contract_check(contract_check)
    terminal_output = load_regular(
        terminal_output_path, TERMINAL_OUTPUT_FILE_SHA256, "TERMINAL_OUTPUT_FILE"
    )
    _validate_terminal_output(terminal_output)
    require(
        evidence_root.is_dir() and not evidence_root.is_symlink(),
        "EVIDENCE_ROOT",
    )
    observed = {
        path.name
        for path in evidence_root.iterdir()
        if path.is_file() and not path.is_symlink()
    }
    require(observed == set(EVIDENCE_DIGESTS), "EVIDENCE_INVENTORY")
    for name, digest in EVIDENCE_DIGESTS.items():
        load_regular(evidence_root / name, digest, "EVIDENCE_" + name.upper())
    timeline = load_json(
        evidence_root / "prepare-timeline.json",
        EVIDENCE_DIGESTS["prepare-timeline.json"],
        "TIMELINE",
    )
    _validate_timeline(timeline)
    evidence_set = {
        "marker_file_sha256": MARKER_FILE_SHA256,
        "contract_check_file_sha256": CONTRACT_CHECK_FILE_SHA256,
        "terminal_output_file_sha256": TERMINAL_OUTPUT_FILE_SHA256,
        "evidence_files": [
            {"name": name, "sha256": EVIDENCE_DIGESTS[name]}
            for name in sorted(EVIDENCE_DIGESTS)
        ],
    }
    return {
        "marker": marker,
        "timeline": timeline,
        "evidence_set_sha256": canonical_sha256(evidence_set),
    }


def build_terminal_result(validated: dict[str, Any]) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": FORENSIC_RESULT_SCHEMA,
        "decision_id": DECISION_ID,
        "stage": STAGE,
        "d2_request_id": D2_REQUEST_ID,
        "status": "CONSUMED_FAILED",
        "primary_failure_code": "PREPARE_RESULT_TIMEOUT",
        "secondary_failure_code": "KeyError",
        "secondary_failure_detail": "missing_authorization_main_sha",
        "terminalization_state": "POST_CLAIM_TERMINALIZATION_FAILED",
        "source_pr": BASE_PR,
        "source_sha": BASE_HEAD_SHA,
        "load_bearing_artifact_id": LOAD_BEARING_ARTIFACT_ID,
        "load_bearing_artifact_sha256": LOAD_BEARING_ARTIFACT_SHA256,
        "request_binding_sha256": REQUEST_BINDING_SHA256,
        "authorization_record_sha256": AUTHORIZATION_RECORD_SHA256,
        "authorization_file_sha256": AUTHORIZATION_FILE_SHA256,
        "execution_closure_sha256": EXECUTION_CLOSURE_SHA256,
        "execution_package_sha256": EXECUTION_PACKAGE_SHA256,
        "execution_core_sha256": EXECUTION_CORE_SHA256,
        "execution_wrapper_sha256": EXECUTION_WRAPPER_SHA256,
        "claimed_at": validated["marker"]["claimed_at"],
        "flash_completed": True,
        "prepare_count": 1,
        "verify_count": 0,
        "locked_recovery_attempted": True,
        "locked_recovery_succeeded": None,
        "locked_recovery_outcome": "UNKNOWN",
        "on_disk_marker_before_closure": "CLAIMED_STALE",
        "forensic_evidence_set_sha256": validated["evidence_set_sha256"],
        "source_forensic_transcript_sha256": SOURCE_FORENSIC_TRANSCRIPT_SHA256,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "board_operation_by_closure": False,
        "usb_enumeration_by_closure": False,
        "serial_operation_by_closure": False,
        "esptool_operation_by_closure": False,
        "flash_operation_by_closure": False,
        "network_operation_by_closure": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }
    value["terminal_result_sha256"] = canonical_sha256(value)
    return value


def build_terminal_marker(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": ORIGINAL_MARKER_SCHEMA,
        "stage": STAGE,
        "d2_request_id": D2_REQUEST_ID,
        "status": "CONSUMED_FAILED",
        "primary_failure_code": "PREPARE_RESULT_TIMEOUT",
        "secondary_failure_code": "KeyError",
        "terminalization_state": "FORENSIC_TERMINAL_CLOSED",
        "terminal_result_sha256": result["terminal_result_sha256"],
        "previous_marker_sha256": MARKER_FILE_SHA256,
        "authorization_record_sha256": AUTHORIZATION_RECORD_SHA256,
        "request_binding_sha256": REQUEST_BINDING_SHA256,
        "prepare_count": 1,
        "verify_count": 0,
        "locked_recovery_attempted": True,
        "locked_recovery_succeeded": None,
        "locked_recovery_outcome": "UNKNOWN",
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }


def utc(value: object, code: str) -> datetime:
    require(isinstance(value, str), code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(code) from exc
    require(parsed.tzinfo is not None, code)
    return parsed.astimezone(timezone.utc)


def validate_closure_authorization(
    value: dict[str, Any],
    *,
    result: dict[str, Any],
    marker: dict[str, Any],
    tool_sha256: str,
    now: datetime | None = None,
) -> None:
    require(value.get("schema") == CLOSURE_AUTH_SCHEMA, "CLOSURE_AUTH_SCHEMA")
    require(value.get("decision_id") == DECISION_ID, "CLOSURE_AUTH_DECISION")
    require(value.get("d2_request_id") == D2_REQUEST_ID, "CLOSURE_AUTH_REQUEST")
    require(value.get("authorized") is True, "CLOSURE_AUTH_NOT_GRANTED")
    require(value.get("one_shot") is True, "CLOSURE_AUTH_ONE_SHOT")
    require(value.get("replay_permitted") is False, "CLOSURE_AUTH_REPLAY")
    require(
        value.get("physical_operation_authorized") is False,
        "CLOSURE_AUTH_PHYSICAL_OPERATION",
    )
    issued = utc(value.get("issued_at"), "CLOSURE_AUTH_ISSUED")
    expires = utc(value.get("expires_at"), "CLOSURE_AUTH_EXPIRES")
    current = now or datetime.now(timezone.utc)
    require(issued <= current <= expires, "CLOSURE_AUTH_NOT_CURRENT")
    require(
        (expires - issued).total_seconds() <= 7200,
        "CLOSURE_AUTH_WINDOW_TOO_LONG",
    )
    exact = {
        "stale_marker_sha256": MARKER_FILE_SHA256,
        "terminal_result_sha256": result["terminal_result_sha256"],
        "terminal_marker_sha256": canonical_sha256(marker),
        "closure_tool_sha256": tool_sha256,
        "request_binding_sha256": REQUEST_BINDING_SHA256,
        "authorization_record_sha256": AUTHORIZATION_RECORD_SHA256,
    }
    for key, expected in exact.items():
        require(value.get(key) == expected, "CLOSURE_AUTH_" + key.upper())
    unbound = dict(value)
    observed = unbound.pop("closure_authorization_sha256", None)
    require(observed == canonical_sha256(unbound), "CLOSURE_AUTH_BINDING")
