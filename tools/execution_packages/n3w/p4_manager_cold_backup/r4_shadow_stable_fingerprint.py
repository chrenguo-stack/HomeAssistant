from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import cutover_contract as contract
import fresh_manager_deploy as deploy
import r3_forensic_seal as r3


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
