from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from typing import Any

import controlled_window as window
import cutover_contract as contract
import fresh_manager_deploy as deploy
import fresh_state_contract as fresh

R2_STATE_FILE = "fresh-manager-deploy-state-private.json"
R2_SHADOW = "greenhouse-manager-p4-shadow"
R2_PARKED = "greenhouse-manager-p4-rollback"
R2_FAILED = "greenhouse-manager-p4-failed"
R3_SEAL_FILE = "fresh-manager-r3-r2-forensic-seal-private.json"
R2_EXPECTED_PHASE = "FRESH_SOURCES_PREPARED_EMPTY"
R3_SEAL_SCHEMA = "gh.n3w.p4.r3-r2-forensic-seal/1"


class SealStop(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise SealStop(code)


def _private_json(path: Path) -> tuple[dict[str, Any], bytes]:
    require(
        path.is_file() and not path.is_symlink()
        and stat.S_IMODE(path.stat().st_mode) == 0o600,
        "R2_JOURNAL_MISSING_OR_INSECURE",
    )
    raw = path.read_bytes()
    try:
        result = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SealStop("R2_JOURNAL_UNREADABLE") from error
    require(isinstance(result, dict), "R2_JOURNAL_INVALID")
    return result, raw


def verify_r2(private: Path) -> dict[str, Any]:
    deploy.verify_r5_rollback_authority(private)
    original, saved_broker = window.get_private_origin(private)
    window.check_old_running(original, saved_broker)
    old = deploy.docker_json("container", contract.MANAGER_NAME)
    broker = deploy.docker_json("container", contract.BROKER_NAME)
    require(old.get("Id") == original.get("Id"), "R2_ORIGINAL_MANAGER_ID_CHANGED")
    deploy.broker_unchanged(saved_broker, broker)
    state, raw = _private_json(private / R2_STATE_FILE)
    require(
        state.get("schema") == "gh.n3w.p4.fresh-manager-deploy/1"
        and state.get("phase") == R2_EXPECTED_PHASE
        and state.get("committed") is False
        and state.get("rollback_result") == "PASS"
        and state.get("rollback_phase") == "ORIGINAL_MANAGER_RESTORED"
        and state.get("candidate_id") is None
        and state.get("old_manager_id") == original.get("Id")
        and state.get("broker_id") == broker.get("Id"),
        "R2_JOURNAL_NOT_SAFE_FOR_R3",
    )
    require(
        not deploy.container_exists(R2_PARKED)
        and not deploy.container_exists(R2_FAILED),
        "R2_PARKED_OR_FAILED_CONTAINER_PRESENT",
    )
    require(deploy.container_exists(R2_SHADOW), "R2_STOPPED_SHADOW_MISSING")
    shadow = deploy.docker_json("container", R2_SHADOW)
    require(
        shadow.get("State", {}).get("Running") is False
        and shadow.get("Image") == state.get("candidate_image_id"),
        "R2_SHADOW_IMAGE_OR_STATE_CHANGED",
    )
    sources = state.get("fresh_sources")
    require(isinstance(sources, dict), "R2_FRESH_SOURCES_INVALID")
    base = private / "fresh-manager-runtime-state"
    require(
        base.is_dir() and not base.is_symlink()
        and stat.S_IMODE(base.stat().st_mode) == 0o700,
        "R2_FRESH_BASE_MISSING_OR_UNSAFE",
    )
    require(
        all(
            isinstance(value, str)
            and Path(value).parent == base
            for value in sources.values()
        ),
        "R2_FRESH_SOURCE_OUTSIDE_PRIVATE_BASE",
    )
    fresh.validate_fresh_sources(
        original, sources,
        expected_uid=state.get("manager_uid"),
        expected_gid=state.get("manager_gid"),
    )
    contract.verify_stopped_shadow_matches_origin(
        original, shadow, state["candidate_image_id"], sources,
    )
    normalized = json.dumps(
        shadow,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "schema": R3_SEAL_SCHEMA,
        "r2_journal_sha256": hashlib.sha256(raw).hexdigest(),
        "r2_shadow_inspect_sha256": hashlib.sha256(normalized).hexdigest(),
        "r2_shadow_container_id": shadow.get("Id"),
        "r2_original_manager_id": original.get("Id"),
        "r2_broker_container_id": broker.get("Id"),
        "r2_original_manager_still_running": True,
        "r2_rollback_result": "PASS",
        "r2_phase": R2_EXPECTED_PHASE,
        "r2_shadow_stopped": True,
        "r3_fresh_state_must_be_independent": True,
    }


def seal_r2(private: Path) -> None:
    doc = verify_r2(private)
    path = private / R3_SEAL_FILE
    require(
        not path.exists() and not path.is_symlink(),
        "R3_FORENSIC_SEAL_ALREADY_EXISTS_NO_REPLAY",
    )
    deploy._atomic_json(path, doc, create=True)


def require_r3_seal(private: Path) -> None:
    saved, _ = _private_json(private / R3_SEAL_FILE)
    require(saved == verify_r2(private), "R3_SEAL_R2_EVIDENCE_DRIFT")
