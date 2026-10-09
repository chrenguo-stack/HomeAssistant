from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any

import cutover_contract as contract
import fresh_manager_deploy as deploy
import r3_forensic_seal as r3


R4_SEAL_FILE = "fresh-manager-r4-protected-forensic-seal-private.json"
R3_TRANSACTION_FILE = "fresh-manager-r3-deploy-state-private.json"
R3_FRESH_BASE = "fresh-manager-r3-runtime-state"
R3_STAGE = "p4-fresh-manager-deploy-r3"
R3_SHADOW = "greenhouse-manager-p4-r3-shadow"
R3_PARKED = "greenhouse-manager-p4-r3-rollback"
R3_FAILED = "greenhouse-manager-p4-r3-failed"
R4_SEAL_SCHEMA = "gh.n3w.p4.r4-protected-forensic-seal/1"


class FingerprintStop(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise FingerprintStop(code)


def stable_shadow_document(shadow: dict[str, Any]) -> dict[str, Any]:
    require(isinstance(shadow, dict), "SHADOW_INSPECT_INVALID")
    state = shadow.get("State") or {}
    require(state.get("Running") is False, "SHADOW_MUST_REMAIN_STOPPED")
    require(
        isinstance(shadow.get("Id"), str) and bool(shadow["Id"])
        and isinstance(shadow.get("Image"), str) and bool(shadow["Image"]),
        "SHADOW_IDENTITY_INVALID",
    )
    config = shadow.get("Config") or {}
    host = shadow.get("HostConfig") or {}
    require(isinstance(config, dict) and isinstance(host, dict),
            "SHADOW_CONFIG_INVALID")
    raw_oom = host.get("OomKillDisable")
    require(raw_oom is None or raw_oom is False, "SHADOW_OOM_OVERRIDE_FORBIDDEN")
    projected_host = {key: host.get(key) for key in contract.HOST_COMPARE}
    projected_host["OomKillDisable"] = False
    mounts = contract._mounts(shadow)
    return {
        "schema": "gh.n3w.p4.shadow-protected-state/1",
        "id": shadow["Id"],
        "name": shadow.get("Name"),
        "image": shadow["Image"],
        "running": False,
        "config": {key: config.get(key) for key in contract.CONFIG_COMPARE},
        "environment": sorted(contract._env_map(config.get("Env", [])).items()),
        "labels": config.get("Labels") or {},
        "host": projected_host,
        "restart_policy": host.get("RestartPolicy"),
        "mounts": {
            destination: {
                key: mount.get(key)
                for key in ("Type", "Source", "Destination", "RW", "Propagation")
            }
            for destination, mount in sorted(mounts.items())
        },
    }


def stable_shadow_sha256(shadow: dict[str, Any]) -> str:
    document = stable_shadow_document(shadow)
    data = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def verify_legacy_r3_seal_readonly(private: Path) -> dict[str, Any]:
    saved, saved_raw = r3._private_json(private / r3.R3_SEAL_FILE)
    live = r3.verify_r2(private)
    require(
        set(saved) == set(live),
        "R3_LEGACY_SEAL_FIELD_SET_DRIFT",
    )
    mismatches = sorted(key for key in live if saved[key] != live[key])
    require(
        mismatches in ([], ["r2_shadow_inspect_sha256"]),
        "R3_LEGACY_SEAL_PROTECTED_EVIDENCE_DRIFT",
    )
    require(
        all(
            isinstance(document.get("r2_shadow_inspect_sha256"), str)
            and re.fullmatch(r"[a-f0-9]{64}", document["r2_shadow_inspect_sha256"])
            for document in (saved, live)
        ),
        "R3_LEGACY_RAW_HASH_FORMAT_INVALID",
    )
    shadow = deploy.docker_json("container", r3.R2_SHADOW)
    return {
        "schema": "gh.n3w.p4.r4-readonly-r3-legacy-seal-review/1",
        "r3_seal_file_sha256": hashlib.sha256(saved_raw).hexdigest(),
        "r2_journal_sha256": live["r2_journal_sha256"],
        "r2_shadow_container_id": live["r2_shadow_container_id"],
        "r2_original_manager_id": live["r2_original_manager_id"],
        "r2_broker_container_id": live["r2_broker_container_id"],
        "r2_stable_shadow_sha256": stable_shadow_sha256(shadow),
        "legacy_full_inspect_digest_mismatch": bool(mismatches),
        "legacy_full_inspect_digest_preserved_unchanged": True,
        "old_manager_and_broker_reverified": True,
        "r2_shadow_full_contract_reverified": True,
    }


def verify_r3_no_cutover_and_history_intact(private: Path) -> None:
    for name in (R3_TRANSACTION_FILE, R3_FRESH_BASE):
        child = private / name
        require(
            not child.exists() and not child.is_symlink(),
            "R3_HISTORICAL_TRANSACTION_OR_DATA_UNEXPECTED",
        )
    stage = private / R3_STAGE
    require(
        stage.is_dir() and not stage.is_symlink()
        and stat.S_IMODE(stage.stat().st_mode) == 0o700,
        "R3_HISTORICAL_STAGE_MISSING_OR_UNSAFE",
    )
    for name in (R3_SHADOW, R3_PARKED, R3_FAILED):
        require(
            not deploy.container_exists(name),
            "R3_HISTORICAL_DEPLOYMENT_CONTAINER_EXISTS",
        )


def r4_authority_document(private: Path) -> dict[str, Any]:
    verify_r3_no_cutover_and_history_intact(private)
    review = verify_legacy_r3_seal_readonly(private)
    return {
        "schema": R4_SEAL_SCHEMA,
        "r3_saved_seal_sha256": review["r3_seal_file_sha256"],
        "r2_journal_sha256": review["r2_journal_sha256"],
        "r2_stable_shadow_sha256": review["r2_stable_shadow_sha256"],
        "r2_shadow_container_id": review["r2_shadow_container_id"],
        "r2_original_manager_id": review["r2_original_manager_id"],
        "r2_broker_container_id": review["r2_broker_container_id"],
        "r3_legacy_digest_mismatch_classified": review["legacy_full_inspect_digest_mismatch"],
        "r2_full_contract_reverified": True,
        "r3_no_cutover_or_fresh_state": True,
        "r2_r3_history_untouched": True,
    }


def seal_r3_for_r4(private: Path) -> None:
    path = private / R4_SEAL_FILE
    require(
        not path.exists() and not path.is_symlink()
        and not path.with_name(path.name + ".tmp").exists(),
        "R4_FORENSIC_SEAL_ALREADY_EXISTS_NO_REPLAY",
    )
    document = r4_authority_document(private)
    deploy._atomic_json(path, document, create=True)


def require_r4_seal(private: Path) -> None:
    path = private / R4_SEAL_FILE
    try:
        saved, _ = r3._private_json(path)
    except r3.SealStop as error:
        raise FingerprintStop("R4_SEAL_NOT_PRESENT_OR_INSECURE") from error
    require(
        saved == r4_authority_document(private),
        "R4_SEAL_PROTECTED_STATE_DRIFT",
    )
