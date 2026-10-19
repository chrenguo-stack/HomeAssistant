#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import time
from pathlib import Path
from typing import Any

import n3w_t1_production_authority as authority

SCHEMA = "gh.n3w-t1-f5-unknown-run-adjudicator/1"
RECOVERY_SCHEMA = "gh.n3w-t1-f5-unknown-run-adjudication/1"
RUN_ID = "3e37993537f9317dfb8070fd53fa20384de86cbd7c2a234857b55602c1280799"
PHASE = "F3_DEPLOY"
SOURCE_HEAD = "9048dd7c6b48c0620471919c0cf96c96bdab71f1"
RELEASE_ID = "31c8a8cd2d8424f93aaa7b4d0b78cfe2b73f1b035f4bdbce08a181ac56619420"
RELEASE_SHA256 = "1bbcb81bd84ec899e4c1d37fffef99defbbcc40509c49ce41048f6a6d92039ad"
HOST_BASELINE_RESULT_SHA256 = "a9ce1c749617193f2da6b66374c7a287868085b87e8eca246da34ff149470806"
F3_FAILURE_CODE = "production_f3_claimed_or_unknown:production_f3_execution_not_proven"
ADJUDICATION_REASON = "KF123_FORENSIC_PROVED_F3_PRECLAIM_FAILURE"
PRODUCTION_EXECUTION_SCHEMA = "gh.n3w-t1-fresh-production-execution/1"
PRODUCTION_EXECUTION_ROOT = Path("/var/lib/n3w-fresh-bootstrap-production-executions")
RECOVERY_ROOT = Path("/var/lib/n3w-t1-f5-unknown-run-adjudications")
CONFIRMATION = "ADJUDICATE KF123 UNKNOWN F3 RUN: YES"
AUTHORIZATION_RE = re.compile(
    r"N3W_T1_F5_KF123_UNKNOWN_RUN_ADJUDICATION_LIVE_[A-Z0-9_]{8,160}"
)
DEFAULT_NETWORKS = frozenset(("bridge", "host", "none"))
PRODUCT_UNITS = (
    "n3wfc4-broker-ingress-guard.service",
    "n3wfc4-provision-resume.service",
    "n3wfc4-broker-activation.service",
    "n3wfc4-services-activation.service",
    "n3wfc4-broker-certificate-lifecycle.service",
    "n3wfc4-broker-certificate-lifecycle.timer",
)
PRODUCT_PATHS = (
    "/var/lib/greenhouse-manager",
    "/var/lib/n3wfc4-broker",
    "/var/lib/n3wfc4-homeassistant",
    "/opt/greenhouse-secrets",
    "/opt/HomeAssistant",
    "/etc/n3wfc4",
    "/usr/local/sbin/n3w-broker-ingress-guard",
    "/usr/local/sbin/n3w-t1-provision",
    "/usr/local/sbin/n3w-t1-systemd-staged-install",
    "/usr/local/sbin/n3w-t1-production-activation-enable",
    "/etc/systemd/system/n3wfc4-broker-ingress-guard.service",
    "/etc/systemd/system/n3wfc4-provision-resume.service",
    "/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard",
    "/usr/local/sbin/n3w-t1-broker-authenticated-readiness",
    "/usr/local/sbin/n3w-broker-certificate-lifecycle",
    "/etc/systemd/system/n3wfc4-broker-activation.service",
    "/etc/systemd/system/n3wfc4-services-activation.service",
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service",
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer",
)
STAGING_PATTERNS = (
    "n3w-f5-f3.*",
    "n3w-f5-f3-context.*",
)


class UnknownRunAdjudicationError(RuntimeError):
    def __init__(self, code: str, *, mutation_state: str = "NONE") -> None:
        super().__init__(code)
        self.mutation_state = mutation_state


def _run_command(
    argv: tuple[str, ...],
    *,
    allowed: frozenset[int] = frozenset({0}),
) -> str:
    completed = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if completed.returncode not in allowed:
        raise UnknownRunAdjudicationError(
            f"readonly_probe_failed:{Path(argv[0]).name}:{completed.returncode}"
        )
    return completed.stdout.strip()


def _runtime_state() -> dict[str, Any]:
    containers = tuple(
        value
        for value in _run_command(
            ("docker", "container", "ls", "-a", "-q")
        ).splitlines()
        if value
    )
    images = tuple(
        value
        for value in _run_command(
            ("docker", "image", "ls", "--format", "{{.ID}}")
        ).splitlines()
        if value
    )
    volumes = tuple(
        value
        for value in _run_command(
            ("docker", "volume", "ls", "-q")
        ).splitlines()
        if value
    )
    networks = frozenset(
        value
        for value in _run_command(
            ("docker", "network", "ls", "--format", "{{.Name}}")
        ).splitlines()
        if value
    )
    loaded_units = 0
    for unit in PRODUCT_UNITS:
        state = _run_command(
            ("systemctl", "show", unit, "--property=LoadState", "--value"),
            allowed=frozenset({0, 1, 3, 4}),
        )
        if state not in {"", "not-found"}:
            loaded_units += 1
    product_paths = sum(
        1
        for raw in PRODUCT_PATHS
        if Path(raw).exists() or Path(raw).is_symlink()
    )
    staging = 0
    staging_root = Path("/var/tmp")
    for pattern in STAGING_PATTERNS:
        staging += sum(1 for _ in staging_root.glob(pattern))
    docker_state = _run_command(
        ("systemctl", "is-active", "docker"),
        allowed=frozenset({0, 3}),
    )
    return {
        "container_count": len(containers),
        "image_count": len(set(images)),
        "volume_count": len(volumes),
        "product_network_count": len(networks - DEFAULT_NETWORKS),
        "product_path_count": product_paths,
        "product_unit_loaded_count": loaded_units,
        "remote_f3_staging_count": staging,
        "docker_active": docker_state == "active",
    }


def _validate_runtime_state(state: dict[str, Any]) -> dict[str, Any]:
    required = {
        "container_count",
        "image_count",
        "volume_count",
        "product_network_count",
        "product_path_count",
        "product_unit_loaded_count",
        "remote_f3_staging_count",
        "docker_active",
    }
    if not isinstance(state, dict) or set(state) != required:
        raise UnknownRunAdjudicationError("runtime_state_invalid")
    count_fields = required - {"docker_active"}
    if any(
        isinstance(state[field], bool)
        or not isinstance(state[field], int)
        or state[field] < 0
        for field in count_fields
    ):
        raise UnknownRunAdjudicationError("runtime_state_invalid")
    if state["docker_active"] is not True:
        raise UnknownRunAdjudicationError("docker_baseline_not_active")
    if any(state[field] != 0 for field in count_fields):
        raise UnknownRunAdjudicationError("product_material_present")
    return dict(state)


def _identity(
    run: dict[str, Any],
    expected: dict[str, str] | None,
) -> dict[str, str]:
    observed = authority.target_identity() if expected is None else expected
    plan = run.get("plan")
    if not isinstance(plan, dict):
        raise UnknownRunAdjudicationError("run_plan_invalid")
    if (
        observed.get("target_binding_sha256")
        != plan.get("target_binding_sha256")
        or observed.get("ssh_host_key_sha256")
        != plan.get("ssh_host_key_sha256")
    ):
        raise UnknownRunAdjudicationError("target_identity_mismatch")
    return observed


def _exact_run_binding(run: dict[str, Any]) -> bool:
    plan = run.get("plan")
    return bool(
        isinstance(plan, dict)
        and plan.get("source_head") == SOURCE_HEAD
        and plan.get("release_id") == RELEASE_ID
        and plan.get("release_sha256") == RELEASE_SHA256
        and run.get("authorization_consumed") is True
        and run.get("replay_allowed") is False
        and run.get("state") == "TERMINAL"
        and run.get("terminal_state") == "FAIL"
        and run.get("last_completed_phase") == "HOST_BASELINE"
        and run.get("last_claimed_phase") == PHASE
        and run.get("board_access") is False
    )


def _host_baseline_exact(
    ledger_root: Path,
    run: dict[str, Any],
) -> bool:
    host = authority._load_phase(ledger_root, RUN_ID, "HOST_BASELINE")
    plan = run["plan"]
    binding = host.get("binding", {})
    return bool(
        host.get("state") == "SUCCEEDED"
        and host.get("result_sha256") == HOST_BASELINE_RESULT_SHA256
        and host.get("failure_code") is None
        and host.get("authorization_consumed") is True
        and host.get("replay_allowed") is False
        and binding.get("source_head") == SOURCE_HEAD
        and binding.get("release_id") == RELEASE_ID
        and binding.get("artifact_sha256")
        == plan["phase_artifact_sha256"]["HOST_BASELINE"]
        and binding.get("predecessor_sha256") is None
        and binding.get("target_binding_sha256")
        == plan.get("target_binding_sha256")
    )


def _f3_predecessor_sha256(ledger_root: Path) -> str:
    return authority._sha256_file(
        authority._phase_path(ledger_root, RUN_ID, "HOST_BASELINE")
    )


def _phase_unknown_exact(
    phase: dict[str, Any],
    run: dict[str, Any],
    ledger_root: Path,
) -> bool:
    plan = run["plan"]
    binding = phase.get("binding", {})
    return bool(
        phase.get("state") == "UNKNOWN"
        and phase.get("failure_code") == F3_FAILURE_CODE
        and phase.get("result_sha256") is None
        and phase.get("authorization_consumed") is True
        and phase.get("replay_allowed") is False
        and binding.get("source_head") == SOURCE_HEAD
        and binding.get("release_id") == RELEASE_ID
        and binding.get("artifact_sha256")
        == plan["phase_artifact_sha256"][PHASE]
        and binding.get("predecessor_sha256")
        == _f3_predecessor_sha256(ledger_root)
        and binding.get("target_binding_sha256")
        == plan.get("target_binding_sha256")
    )


def _phase_failed_exact(
    phase: dict[str, Any],
    run: dict[str, Any],
    ledger_root: Path,
) -> bool:
    plan = run["plan"]
    binding = phase.get("binding", {})
    return bool(
        phase.get("state") == "FAILED"
        and phase.get("failure_code") == F3_FAILURE_CODE
        and phase.get("result_sha256") is None
        and phase.get("authorization_consumed") is True
        and phase.get("replay_allowed") is False
        and binding.get("source_head") == SOURCE_HEAD
        and binding.get("release_id") == RELEASE_ID
        and binding.get("artifact_sha256")
        == plan["phase_artifact_sha256"][PHASE]
        and binding.get("predecessor_sha256")
        == _f3_predecessor_sha256(ledger_root)
        and binding.get("target_binding_sha256")
        == plan.get("target_binding_sha256")
    )


def _execution_record_count(root: Path) -> int:
    if root.is_symlink():
        raise UnknownRunAdjudicationError("f3_execution_ledger_invalid")
    if not root.exists():
        return 0
    metadata = root.stat()
    if (
        not root.is_dir()
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise UnknownRunAdjudicationError("f3_execution_ledger_invalid")
    required = {
        "schema",
        "run_id",
        "phase",
        "phase_claim_sha256",
        "plan_sha256",
        "source_head",
        "payload_manifest_sha256",
        "release_id",
        "phase_artifact_sha256",
        "target_binding_sha256",
        "state",
        "result_sha256",
        "authorization_consumed",
        "replay_allowed",
    }
    count = 0
    for path in root.iterdir():
        if (
            re.fullmatch(r"[0-9a-f]{64}\.json", path.name) is None
            or path.is_symlink()
            or not path.is_file()
        ):
            raise UnknownRunAdjudicationError("f3_execution_ledger_invalid")
        item_metadata = path.stat()
        if (
            item_metadata.st_uid != os.geteuid()
            or stat.S_IMODE(item_metadata.st_mode) != 0o600
            or item_metadata.st_nlink != 1
        ):
            raise UnknownRunAdjudicationError("f3_execution_ledger_invalid")
        try:
            document = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=authority._strict_object,
            )
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            authority.ProductionAuthorityError,
        ) as error:
            raise UnknownRunAdjudicationError(
                "f3_execution_ledger_invalid"
            ) from error
        hash_fields = (
            "run_id",
            "phase_claim_sha256",
            "plan_sha256",
            "payload_manifest_sha256",
            "release_id",
            "phase_artifact_sha256",
            "target_binding_sha256",
        )
        if (
            not isinstance(document, dict)
            or set(document) != required
            or document.get("schema") != PRODUCTION_EXECUTION_SCHEMA
            or document.get("phase") != PHASE
            or re.fullmatch(
                r"[0-9a-f]{40}",
                str(document.get("source_head")),
            )
            is None
            or any(
                re.fullmatch(r"[0-9a-f]{64}", str(document.get(field)))
                is None
                for field in hash_fields
            )
            or document.get("authorization_consumed") is not True
            or document.get("replay_allowed") is not False
            or document.get("state") not in {"APPLYING", "SUCCEEDED"}
            or (
                document.get("state") == "APPLYING"
                and document.get("result_sha256") is not None
            )
            or (
                document.get("state") == "SUCCEEDED"
                and re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(document.get("result_sha256")),
                )
                is None
            )
        ):
            raise UnknownRunAdjudicationError(
                "f3_execution_ledger_invalid"
            )
        expected_name = (
            hashlib.sha256(
                (
                    document["run_id"]
                    + "\n"
                    + document["phase"]
                    + "\n"
                    + document["phase_claim_sha256"]
                    + "\n"
                ).encode("utf-8")
            ).hexdigest()
            + ".json"
        )
        if path.name != expected_name:
            raise UnknownRunAdjudicationError(
                "f3_execution_record_filename_binding_invalid"
            )
        if document["run_id"] == RUN_ID:
            count += 1
    return count


def _later_target_run_absent(
    ledger_root: Path,
    incident: dict[str, Any],
) -> None:
    target = incident["plan"]["target_binding_sha256"]
    incident_created = incident["created_at"]
    for entry in ledger_root.iterdir():
        if entry.name == RUN_ID:
            continue
        if authority.RUN_ID_RE.fullmatch(entry.name) is None:
            raise UnknownRunAdjudicationError("ledger_root_entry_invalid")
        other = authority._load_run(ledger_root, entry.name)
        if (
            other.get("plan", {}).get("target_binding_sha256") == target
            and other.get("created_at", 0) >= incident_created
        ):
            raise UnknownRunAdjudicationError("later_target_run_present")


def _recovery_path(root: Path) -> Path:
    return root / f"{RUN_ID}.json"


def _recovery_absent(root: Path) -> None:
    if root.exists() or root.is_symlink():
        raise UnknownRunAdjudicationError("recovery_root_already_present")


def _exact_unknown_prestate(
    *,
    ledger_root: Path,
    execution_root: Path,
    recovery_root: Path,
    identity: dict[str, str] | None,
    runtime_state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str, str]:
    authority._require_root()
    run = authority._load_run(ledger_root, RUN_ID)
    phase = authority._load_phase(ledger_root, RUN_ID, PHASE)
    if (
        not _exact_run_binding(run)
        or run.get("failure_class") != "UNKNOWN"
        or not _host_baseline_exact(ledger_root, run)
        or not _phase_unknown_exact(phase, run, ledger_root)
    ):
        raise UnknownRunAdjudicationError("unknown_run_prestate_mismatch")
    _identity(run, identity)
    if _execution_record_count(execution_root) != 0:
        raise UnknownRunAdjudicationError("f3_business_execution_present")
    observed_runtime = _validate_runtime_state(
        _runtime_state() if runtime_state is None else runtime_state
    )
    _recovery_absent(recovery_root)
    _later_target_run_absent(ledger_root, run)
    run_sha256 = authority._sha256_file(
        authority._run_path(ledger_root, RUN_ID)
    )
    phase_sha256 = authority._sha256_file(
        authority._phase_path(ledger_root, RUN_ID, PHASE)
    )
    return run, phase, observed_runtime, run_sha256, phase_sha256


def inspect_unknown_run(
    *,
    ledger_root: Path = authority.LEDGER_ROOT,
    execution_root: Path = PRODUCTION_EXECUTION_ROOT,
    recovery_root: Path = RECOVERY_ROOT,
    identity: dict[str, str] | None = None,
    runtime_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run, _phase, observed, run_sha256, phase_sha256 = _exact_unknown_prestate(
        ledger_root=ledger_root,
        execution_root=execution_root,
        recovery_root=recovery_root,
        identity=identity,
        runtime_state=runtime_state,
    )
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "state": "ELIGIBLE_FOR_ADJUDICATION",
        "run_id": RUN_ID,
        "phase": PHASE,
        "run_record_sha256": run_sha256,
        "phase_record_sha256": phase_sha256,
        "target_binding_sha256": run["plan"]["target_binding_sha256"],
        "f3_production_execution_record_count": 0,
        **observed,
        "recovery_root_absent": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "mutation_performed": False,
        "mutation_state": "NONE",
        "product_service_start": False,
        "reboot_executed": False,
        "board_access": False,
    }


def _validate_recovery_root(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise UnknownRunAdjudicationError("recovery_root_invalid")
    metadata = root.stat()
    if (
        metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise UnknownRunAdjudicationError("recovery_root_metadata_invalid")


def _ensure_recovery_root(root: Path) -> None:
    if not root.exists() and not root.is_symlink():
        root.mkdir(parents=True, mode=0o700)
        os.chmod(root, 0o700)
    _validate_recovery_root(root)


def _read_recovery(path: Path) -> dict[str, Any]:
    _validate_recovery_root(path.parent)
    if path.is_symlink() or not path.is_file():
        raise UnknownRunAdjudicationError("recovery_record_invalid")
    metadata = path.stat()
    if (
        metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != 1
    ):
        raise UnknownRunAdjudicationError("recovery_record_metadata_invalid")
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=authority._strict_object,
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        authority.ProductionAuthorityError,
    ) as error:
        raise UnknownRunAdjudicationError("recovery_record_invalid") from error
    required = {
        "schema",
        "run_id",
        "phase",
        "authorization_id",
        "authorization_consumed",
        "replay_allowed",
        "state",
        "original_run_record_sha256",
        "original_phase_record_sha256",
        "original_run_invariant_sha256",
        "original_phase_invariant_sha256",
        "target_binding_sha256",
        "ssh_host_key_sha256",
        "source_head",
        "release_id",
        "release_sha256",
        "original_failure_code",
        "adjudication_reason",
        "created_at",
        "updated_at",
        "board_access",
    }
    if (
        not isinstance(document, dict)
        or set(document) != required
        or document.get("schema") != RECOVERY_SCHEMA
        or document.get("run_id") != RUN_ID
        or document.get("phase") != PHASE
        or document.get("authorization_consumed") is not True
        or document.get("replay_allowed") is not False
        or document.get("state") not in {"CLAIMED", "APPLYING", "ADJUDICATED"}
        or document.get("source_head") != SOURCE_HEAD
        or document.get("release_id") != RELEASE_ID
        or document.get("release_sha256") != RELEASE_SHA256
        or document.get("original_failure_code") != F3_FAILURE_CODE
        or document.get("adjudication_reason") != ADJUDICATION_REASON
        or document.get("board_access") is not False
        or AUTHORIZATION_RE.fullmatch(
            str(document.get("authorization_id"))
        ) is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(document.get("original_run_record_sha256")),
        ) is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(document.get("original_phase_record_sha256")),
        ) is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(document.get("original_run_invariant_sha256")),
        ) is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(document.get("original_phase_invariant_sha256")),
        ) is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(document.get("target_binding_sha256")),
        ) is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(document.get("ssh_host_key_sha256")),
        ) is None
        or not isinstance(document.get("created_at"), int)
        or isinstance(document.get("created_at"), bool)
        or not isinstance(document.get("updated_at"), int)
        or isinstance(document.get("updated_at"), bool)
    ):
        raise UnknownRunAdjudicationError("recovery_record_invalid")
    return document


def _run_invariant_sha256(run: dict[str, Any]) -> str:
    preserved = dict(run)
    preserved.pop("failure_class", None)
    preserved.pop("updated_at", None)
    return authority.canonical_sha256(preserved)


def _phase_invariant_sha256(phase: dict[str, Any]) -> str:
    preserved = dict(phase)
    preserved.pop("state", None)
    preserved.pop("updated_at", None)
    return authority.canonical_sha256(preserved)


def _assert_preserved_historical_fields(
    *,
    recovery: dict[str, Any],
    run: dict[str, Any],
    phase: dict[str, Any],
    ledger_root: Path,
) -> None:
    if (
        _run_invariant_sha256(run)
        != recovery["original_run_invariant_sha256"]
        or _phase_invariant_sha256(phase)
        != recovery["original_phase_invariant_sha256"]
    ):
        raise UnknownRunAdjudicationError(
            "historical_record_invariant_drift"
        )
    if (
        run.get("failure_class") == "UNKNOWN"
        and authority._sha256_file(
            authority._run_path(ledger_root, RUN_ID)
        )
        != recovery["original_run_record_sha256"]
    ):
        raise UnknownRunAdjudicationError(
            "historical_run_preclassification_drift"
        )
    if (
        phase.get("state") == "UNKNOWN"
        and authority._sha256_file(
            authority._phase_path(ledger_root, RUN_ID, PHASE)
        )
        != recovery["original_phase_record_sha256"]
    ):
        raise UnknownRunAdjudicationError(
            "historical_phase_preclassification_drift"
        )


def _claim_recovery(
    *,
    recovery_root: Path,
    authorization_id: str,
    run: dict[str, Any],
    phase: dict[str, Any],
    expected_run_sha256: str,
    expected_phase_sha256: str,
) -> dict[str, Any]:
    if AUTHORIZATION_RE.fullmatch(authorization_id) is None:
        raise UnknownRunAdjudicationError("recovery_authorization_id_invalid")
    _ensure_recovery_root(recovery_root)
    path = _recovery_path(recovery_root)
    if path.exists() or path.is_symlink():
        raise UnknownRunAdjudicationError("recovery_record_already_present")
    now = int(time.time())
    record = {
        "schema": RECOVERY_SCHEMA,
        "run_id": RUN_ID,
        "phase": PHASE,
        "authorization_id": authorization_id,
        "authorization_consumed": True,
        "replay_allowed": False,
        "state": "CLAIMED",
        "original_run_record_sha256": expected_run_sha256,
        "original_phase_record_sha256": expected_phase_sha256,
        "original_run_invariant_sha256": _run_invariant_sha256(run),
        "original_phase_invariant_sha256": _phase_invariant_sha256(phase),
        "target_binding_sha256": run["plan"]["target_binding_sha256"],
        "ssh_host_key_sha256": run["plan"]["ssh_host_key_sha256"],
        "source_head": SOURCE_HEAD,
        "release_id": RELEASE_ID,
        "release_sha256": RELEASE_SHA256,
        "original_failure_code": F3_FAILURE_CODE,
        "adjudication_reason": ADJUDICATION_REASON,
        "created_at": now,
        "updated_at": now,
        "board_access": False,
    }
    try:
        authority._write_new(path, record)
    except Exception as error:
        raise UnknownRunAdjudicationError(
            "recovery_claim_write_failed",
            mutation_state="UNKNOWN",
        ) from error
    try:
        observed = _read_recovery(path)
    except Exception as error:
        raise UnknownRunAdjudicationError(
            "recovery_claim_persistence_unknown",
            mutation_state="UNKNOWN",
        ) from error
    if observed != record:
        raise UnknownRunAdjudicationError(
            "recovery_claim_persistence_mismatch",
            mutation_state="UNKNOWN",
        )
    return observed


def _set_recovery_state(
    record: dict[str, Any],
    *,
    recovery_root: Path,
    state: str,
) -> dict[str, Any]:
    _validate_recovery_root(recovery_root)
    updated = dict(record)
    updated["state"] = state
    updated["updated_at"] = int(time.time())
    try:
        authority._replace(_recovery_path(recovery_root), updated)
        observed = _read_recovery(_recovery_path(recovery_root))
    except Exception as error:
        raise UnknownRunAdjudicationError(
            "recovery_state_persistence_unknown",
            mutation_state="UNKNOWN",
        ) from error
    if observed != updated:
        raise UnknownRunAdjudicationError(
            "recovery_state_persistence_mismatch",
            mutation_state="UNKNOWN",
        )
    return observed


def _recovery_binding_exact(
    recovery: dict[str, Any],
    *,
    authorization_id: str,
    expected_run_sha256: str,
    expected_phase_sha256: str,
    run: dict[str, Any],
) -> None:
    if (
        recovery.get("authorization_id") != authorization_id
        or recovery.get("original_run_record_sha256")
        != expected_run_sha256
        or recovery.get("original_phase_record_sha256")
        != expected_phase_sha256
        or recovery.get("target_binding_sha256")
        != run["plan"]["target_binding_sha256"]
        or recovery.get("ssh_host_key_sha256")
        != run["plan"]["ssh_host_key_sha256"]
    ):
        raise UnknownRunAdjudicationError(
            "recovery_authorization_binding_mismatch"
        )


def _final_run_exact(run: dict[str, Any]) -> bool:
    return bool(
        _exact_run_binding(run)
        and run.get("failure_class") == "FAILED"
    )


def _runtime_and_business_clean(
    *,
    execution_root: Path,
    runtime_state: dict[str, Any] | None,
) -> dict[str, Any]:
    if _execution_record_count(execution_root) != 0:
        raise UnknownRunAdjudicationError("f3_business_execution_present")
    return _validate_runtime_state(
        _runtime_state() if runtime_state is None else runtime_state
    )


def _apply_or_resume(
    *,
    ledger_root: Path,
    execution_root: Path,
    runtime_state: dict[str, Any] | None,
    expected_run_sha256: str,
    expected_phase_sha256: str,
    recovery: dict[str, Any],
) -> str:
    with authority._exclusive(ledger_root, RUN_ID):
        run = authority._load_run(ledger_root, RUN_ID)
        phase = authority._load_phase(ledger_root, RUN_ID, PHASE)
        if not _exact_run_binding(run) or not _host_baseline_exact(
            ledger_root, run
        ):
            raise UnknownRunAdjudicationError(
                "adjudication_run_binding_drift"
            )
        _assert_preserved_historical_fields(
            recovery=recovery,
            run=run,
            phase=phase,
            ledger_root=ledger_root,
        )
        _runtime_and_business_clean(
            execution_root=execution_root,
            runtime_state=runtime_state,
        )

        run_path = authority._run_path(ledger_root, RUN_ID)
        phase_path = authority._phase_path(ledger_root, RUN_ID, PHASE)

        if (
            run.get("failure_class") == "UNKNOWN"
            and _phase_unknown_exact(phase, run, ledger_root)
        ):
            if authority._sha256_file(run_path) != expected_run_sha256:
                raise UnknownRunAdjudicationError("run_record_sha256_drift")
            if authority._sha256_file(phase_path) != expected_phase_sha256:
                raise UnknownRunAdjudicationError("phase_record_sha256_drift")
            updated_phase = dict(phase)
            updated_phase["state"] = "FAILED"
            updated_phase["updated_at"] = int(time.time())
            try:
                authority._replace(phase_path, updated_phase)
                phase = authority._load_phase(
                    ledger_root, RUN_ID, PHASE
                )
            except Exception as error:
                raise UnknownRunAdjudicationError(
                    "phase_adjudication_persistence_unknown",
                    mutation_state="UNKNOWN",
                ) from error
            if not _phase_failed_exact(phase, run, ledger_root):
                raise UnknownRunAdjudicationError(
                    "phase_adjudication_persistence_mismatch",
                    mutation_state="UNKNOWN",
                )
            _assert_preserved_historical_fields(
                recovery=recovery,
                run=run,
                phase=phase,
                ledger_root=ledger_root,
            )
            mutation_state = "PHASE_FAILED"
        elif (
            run.get("failure_class") == "UNKNOWN"
            and _phase_failed_exact(phase, run, ledger_root)
        ):
            mutation_state = "PHASE_FAILED"
        elif (
            run.get("failure_class") == "FAILED"
            and _phase_failed_exact(phase, run, ledger_root)
        ):
            return "ALREADY_CLASSIFIED"
        else:
            raise UnknownRunAdjudicationError(
                "adjudication_split_state_invalid"
            )

        run = authority._load_run(ledger_root, RUN_ID)
        if run.get("failure_class") == "UNKNOWN":
            updated_run = dict(run)
            updated_run["failure_class"] = "FAILED"
            updated_run["updated_at"] = int(time.time())
            try:
                authority._replace(run_path, updated_run)
                run = authority._load_run(ledger_root, RUN_ID)
            except Exception as error:
                raise UnknownRunAdjudicationError(
                    "run_adjudication_persistence_unknown",
                    mutation_state="UNKNOWN",
                ) from error
            if not _final_run_exact(run):
                raise UnknownRunAdjudicationError(
                    "run_adjudication_persistence_mismatch",
                    mutation_state="UNKNOWN",
                )
            _assert_preserved_historical_fields(
                recovery=recovery,
                run=run,
                phase=phase,
                ledger_root=ledger_root,
            )
            return "CLASSIFIED"
        if _final_run_exact(run):
            return "ALREADY_CLASSIFIED"
        raise UnknownRunAdjudicationError(
            "run_adjudication_state_invalid",
            mutation_state=mutation_state,
        )


def adjudicate_unknown_run(
    *,
    expected_run_sha256: str,
    expected_phase_sha256: str,
    authorization_id: str,
    confirmation: str,
    ledger_root: Path = authority.LEDGER_ROOT,
    execution_root: Path = PRODUCTION_EXECUTION_ROOT,
    recovery_root: Path = RECOVERY_ROOT,
    identity: dict[str, str] | None = None,
    runtime_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    authority._require_root()
    if confirmation != CONFIRMATION:
        raise UnknownRunAdjudicationError("adjudication_confirmation_invalid")
    for value, code in (
        (expected_run_sha256, "run_record_sha256_invalid"),
        (expected_phase_sha256, "phase_record_sha256_invalid"),
    ):
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise UnknownRunAdjudicationError(code)
    if AUTHORIZATION_RE.fullmatch(authorization_id) is None:
        raise UnknownRunAdjudicationError("recovery_authorization_id_invalid")

    recovery_path = _recovery_path(recovery_root)
    recovery_present = recovery_path.exists() or recovery_path.is_symlink()
    recovery_durable = False
    try:
        if recovery_present:
            recovery = _read_recovery(recovery_path)
            recovery_durable = True
            run = authority._load_run(ledger_root, RUN_ID)
            _identity(run, identity)
            _recovery_binding_exact(
                recovery,
                authorization_id=authorization_id,
                expected_run_sha256=expected_run_sha256,
                expected_phase_sha256=expected_phase_sha256,
                run=run,
            )
        else:
            preflight = inspect_unknown_run(
                ledger_root=ledger_root,
                execution_root=execution_root,
                recovery_root=recovery_root,
                identity=identity,
                runtime_state=runtime_state,
            )
            if preflight["run_record_sha256"] != expected_run_sha256:
                raise UnknownRunAdjudicationError(
                    "run_record_sha256_drift"
                )
            if preflight["phase_record_sha256"] != expected_phase_sha256:
                raise UnknownRunAdjudicationError(
                    "phase_record_sha256_drift"
                )
            with authority._exclusive(ledger_root, RUN_ID):
                run = authority._load_run(ledger_root, RUN_ID)
                phase = authority._load_phase(ledger_root, RUN_ID, PHASE)
                if (
                    authority._sha256_file(
                        authority._run_path(ledger_root, RUN_ID)
                    )
                    != expected_run_sha256
                ):
                    raise UnknownRunAdjudicationError(
                        "run_record_sha256_drift"
                    )
                if (
                    authority._sha256_file(
                        authority._phase_path(
                            ledger_root, RUN_ID, PHASE
                        )
                    )
                    != expected_phase_sha256
                ):
                    raise UnknownRunAdjudicationError(
                        "phase_record_sha256_drift"
                    )
                recovery = _claim_recovery(
                    recovery_root=recovery_root,
                    authorization_id=authorization_id,
                    run=run,
                    phase=phase,
                    expected_run_sha256=expected_run_sha256,
                    expected_phase_sha256=expected_phase_sha256,
                )
                recovery_durable = True

        if recovery["state"] == "ADJUDICATED":
            run = authority._load_run(ledger_root, RUN_ID)
            phase = authority._load_phase(ledger_root, RUN_ID, PHASE)
            _identity(run, identity)
            _assert_preserved_historical_fields(
                recovery=recovery,
                run=run,
                phase=phase,
                ledger_root=ledger_root,
            )
            _runtime_and_business_clean(
                execution_root=execution_root,
                runtime_state=runtime_state,
            )
            if not (
                _final_run_exact(run)
                and _host_baseline_exact(ledger_root, run)
                and _phase_failed_exact(phase, run, ledger_root)
            ):
                raise UnknownRunAdjudicationError(
                    "adjudicated_poststate_drift"
                )
            action = "ALREADY_ADJUDICATED"
        else:
            if recovery["state"] == "CLAIMED":
                run = authority._load_run(ledger_root, RUN_ID)
                phase = authority._load_phase(ledger_root, RUN_ID, PHASE)
                _identity(run, identity)
                if (
                    authority._sha256_file(
                        authority._run_path(ledger_root, RUN_ID)
                    )
                    != expected_run_sha256
                    or authority._sha256_file(
                        authority._phase_path(
                            ledger_root, RUN_ID, PHASE
                        )
                    )
                    != expected_phase_sha256
                    or run.get("failure_class") != "UNKNOWN"
                    or not _phase_unknown_exact(phase, run, ledger_root)
                ):
                    raise UnknownRunAdjudicationError(
                        "claimed_recovery_prestate_drift"
                    )
                _runtime_and_business_clean(
                    execution_root=execution_root,
                    runtime_state=runtime_state,
                )
                recovery = _set_recovery_state(
                    recovery,
                    recovery_root=recovery_root,
                    state="APPLYING",
                )
            if recovery["state"] != "APPLYING":
                raise UnknownRunAdjudicationError(
                    "recovery_state_invalid"
                )
            action = _apply_or_resume(
                ledger_root=ledger_root,
                execution_root=execution_root,
                runtime_state=runtime_state,
                expected_run_sha256=expected_run_sha256,
                expected_phase_sha256=expected_phase_sha256,
                recovery=recovery,
            )

        run = authority._load_run(ledger_root, RUN_ID)
        phase = authority._load_phase(ledger_root, RUN_ID, PHASE)
        _assert_preserved_historical_fields(
            recovery=recovery,
            run=run,
            phase=phase,
            ledger_root=ledger_root,
        )
        _runtime_and_business_clean(
            execution_root=execution_root,
            runtime_state=runtime_state,
        )
        if not (
            _final_run_exact(run)
            and _host_baseline_exact(ledger_root, run)
            and _phase_failed_exact(phase, run, ledger_root)
        ):
            raise UnknownRunAdjudicationError(
                "adjudication_poststate_invalid",
                mutation_state="UNKNOWN",
            )

        recovery = _read_recovery(recovery_path)
        recovery_transitioned = False
        if recovery["state"] != "ADJUDICATED":
            recovery = _set_recovery_state(
                recovery,
                recovery_root=recovery_root,
                state="ADJUDICATED",
            )
            recovery_transitioned = True
        if recovery["state"] != "ADJUDICATED":
            raise UnknownRunAdjudicationError(
                "recovery_terminal_state_invalid",
                mutation_state="UNKNOWN",
            )

        observed = _validate_runtime_state(
            _runtime_state() if runtime_state is None else runtime_state
        )
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "state": "UNKNOWN_RUN_ADJUDICATED",
            "action": action,
            "run_id": RUN_ID,
            "phase": PHASE,
            "phase_state": "FAILED",
            "failure_code": F3_FAILURE_CODE,
            "target_run_state": "TERMINAL",
            "target_terminal_state": "FAIL",
            "target_failure_class": "FAILED",
            "recovery_state": "ADJUDICATED",
            "recovery_authorization_id": authorization_id,
            "authorization_consumed": True,
            "replay_allowed": False,
            "mutation_performed": (
                action != "ALREADY_ADJUDICATED"
                or recovery_transitioned
            ),
            "mutation_state": "TERMINAL",
            "mutation_scope": (
                "f5_production_authority_and_adjudication_ledger_only"
            ),
            "f3_production_execution_record_count": 0,
            **observed,
            "product_service_start": False,
            "reboot_executed": False,
            "board_access": False,
        }
    except UnknownRunAdjudicationError as error:
        if (
            error.mutation_state == "NONE"
            and (recovery_present or recovery_durable)
        ):
            raise UnknownRunAdjudicationError(
                str(error),
                mutation_state="RECOVERY_PRESENT",
            ) from error
        raise


def verify_adjudicated_run(
    *,
    ledger_root: Path = authority.LEDGER_ROOT,
    execution_root: Path = PRODUCTION_EXECUTION_ROOT,
    recovery_root: Path = RECOVERY_ROOT,
    identity: dict[str, str] | None = None,
    runtime_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    authority._require_root()
    run = authority._load_run(ledger_root, RUN_ID)
    phase = authority._load_phase(ledger_root, RUN_ID, PHASE)
    _identity(run, identity)
    recovery = _read_recovery(_recovery_path(recovery_root))
    _assert_preserved_historical_fields(
        recovery=recovery,
        run=run,
        phase=phase,
        ledger_root=ledger_root,
    )
    observed = _runtime_and_business_clean(
        execution_root=execution_root,
        runtime_state=runtime_state,
    )
    if not (
        _final_run_exact(run)
        and _host_baseline_exact(ledger_root, run)
        and _phase_failed_exact(phase, run, ledger_root)
        and recovery.get("state") == "ADJUDICATED"
    ):
        raise UnknownRunAdjudicationError(
            "adjudicated_readonly_verify_failed"
        )
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "state": "ADJUDICATED_READONLY_VERIFIED",
        "run_id": RUN_ID,
        "phase": PHASE,
        "phase_state": "FAILED",
        "failure_code": F3_FAILURE_CODE,
        "target_run_state": "TERMINAL",
        "target_terminal_state": "FAIL",
        "target_failure_class": "FAILED",
        "recovery_state": "ADJUDICATED",
        "authorization_consumed": True,
        "replay_allowed": False,
        "f3_production_execution_record_count": 0,
        **observed,
        "mutation_performed": False,
        "mutation_state": "NONE",
        "product_service_start": False,
        "reboot_executed": False,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    adjudicate = sub.add_parser("adjudicate")
    adjudicate.add_argument("--expected-run-sha256", required=True)
    adjudicate.add_argument("--expected-phase-sha256", required=True)
    adjudicate.add_argument("--authorization-id", required=True)
    adjudicate.add_argument("--confirm", required=True)
    sub.add_parser("verify")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "inspect":
            report = inspect_unknown_run()
        elif args.command == "verify":
            report = verify_adjudicated_run()
        else:
            report = adjudicate_unknown_run(
                expected_run_sha256=args.expected_run_sha256,
                expected_phase_sha256=args.expected_phase_sha256,
                authorization_id=args.authorization_id,
                confirmation=args.confirm,
            )
    except (
        UnknownRunAdjudicationError,
        authority.ProductionAuthorityError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        mutation_state = (
            error.mutation_state
            if isinstance(error, UnknownRunAdjudicationError)
            else "UNKNOWN"
        )
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "error_code": str(error)[:300],
                    "mutation_state": mutation_state,
                    "mutation_performed": mutation_state != "NONE",
                    "product_service_start": False,
                    "reboot_executed": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
