#!/usr/bin/python3
from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.machinery
import importlib.util
import json
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

CLAIM_SCHEMA = "gh.n3w-t1-f4-reboot-authorization/1"
REPORT_SCHEMA = "gh.n3w-t1-f4-reboot-acceptance/1"
READINESS_SCHEMA = "gh.n3w-t1-f4-reboot-readiness/1"
REPOSITORY_DEFINED_ERROR_CODES = frozenset(
    {
        "boot_id_invalid",
        "broker_authenticated_connection_evidence_missing",
        "broker_authenticated_connection_identity_mismatch",
        "broker_authenticated_connection_state_invalid",
        "broker_current_session_authentication_evidence_missing",
        "broker_log_coverage_insufficient",
        "certificate_identity_changed_across_reboot",
        "certificate_runtime_guard_dropin_missing",
        "certificate_runtime_guard_not_pass",
        "certificate_service_not_quiescent",
        "certificate_service_post_reboot_invalid",
        "certificate_unit_state_invalid",
        "control_binding_claim_invalid",
        "control_manifest_binding_invalid",
        "control_manifest_file_path_invalid",
        "control_manifest_file_record_invalid",
        "control_manifest_file_set_invalid",
        "control_manifest_files_invalid",
        "critical_systemd_unit_failed",
        "critical_systemd_unit_not_active",
        "evidence_insufficient",
        "f4_host_import_invalid",
        "f4_host_invalid",
        "f4_transaction_changed_across_reboot",
        "f4_transaction_post_reboot_invalid",
        "homeassistant_mqtt_socket_missing",
        "manager_mqtt_socket_count_invalid",
        "manager_runtime_identity_invalid",
        "mqtt_owned_socket_not_unique",
        "post_reboot_business_state_invalid",
        "post_reboot_unit_contract_invalid",
        "readiness_certificate_service_invalid",
        "readiness_certificate_timer_failed",
        "readiness_certificate_timer_not_enabled",
        "readiness_certificate_timer_state_invalid",
        "readiness_required_unit_failed",
        "readiness_required_unit_missing",
        "readiness_required_unit_state_invalid",
        "readiness_runtime_service_name_invalid",
        "readiness_systemd_not_operational",
        "readiness_systemd_state_invalid",
        "readiness_unit_evidence_invalid",
        "readiness_unit_load_state_invalid",
        "readiness_unit_state_invalid",
        "reboot_claim_invalid",
        "reboot_not_observed",
        "runtime_container_name_missing",
        "runtime_homeassistant_not_ready",
        "runtime_identity_invalid",
        "runtime_service_set_invalid",
        "runtime_snapshot_command_evidence_unavailable",
        "runtime_socket_auth_evidence_unstable",
        "runtime_socket_evidence_invalid",
        "snapshot_container_not_running",
        "snapshot_transaction_binding_changed",
        "systemd_error_coverage_insufficient",
        "systemd_error_cursor_missing",
        "verification_error",
        "verify_failed",
    }
)
REPOSITORY_DEFINED_ERROR_CODE_PATTERNS = (
    re.compile(
        r"record_(?:invalid|metadata_invalid|json_invalid|document_invalid):"
        r"[A-Za-z0-9_.-]+"
    ),
    re.compile(
        r"(?:unit_not_successful|oneshot_not_successful):[A-Za-z0-9_.@-]+"
    ),
    re.compile(
        r"runtime_service_set_unexpected:"
        r"[A-Za-z0-9_.-]+(?:,[A-Za-z0-9_.-]+)*"
    ),
)
SANITIZED_COMMAND_FAILURE_RE = re.compile(
    r"command_failed:[A-Za-z0-9_.-]+:[0-9]+"
)


def _repository_defined_error_code(value: str) -> bool:
    return (
        value in REPOSITORY_DEFINED_ERROR_CODES
        or SANITIZED_COMMAND_FAILURE_RE.fullmatch(value) is not None
        or any(
            pattern.fullmatch(value) is not None
            for pattern in REPOSITORY_DEFINED_ERROR_CODE_PATTERNS
        )
    )
CLAIM_PATH = Path("/var/lib/n3w-t1-provisioning/F4_REBOOT_AUTHORIZATION.json")
F4_TRANSACTION = Path("/var/lib/n3w-t1-provisioning/F4_ACTIVATION_TRANSACTION.json")
F4_HOST = Path("/usr/local/sbin/n3w-t1-f4-activation")
RUNTIME_GUARD = Path("/usr/local/sbin/n3w-t1-f4-certificate-runtime-guard")
REBOOT_AUTHORITY = Path("/usr/local/sbin/n3w-t1-f4-reboot-authority")
REBOOT_VERIFY = Path("/usr/local/sbin/n3w-t1-f4-reboot-verify")
CONTROL_MANIFEST = Path(
    "/usr/local/share/n3w-t1-f4-reboot-successor/reboot-successor-manifest.json"
)
PACKAGE_SCHEMA = "gh.n3w-t1-f4-reboot-successor-control-package/1"
DROPIN = Path(
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service.d/"
    "10-runtime-status-evolution.conf"
)
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
EXPECTED_SERVICES = frozenset({"broker", "manager", "homeassistant"})
CONTROL_TARGETS = {
    "tools/n3w_t1_f4_certificate_runtime_guard.py": (RUNTIME_GUARD, 0o755),
    "tools/n3w_t1_f4_reboot_authority.py": (REBOOT_AUTHORITY, 0o755),
    "tools/n3w_t1_f4_reboot_verify.py": (REBOOT_VERIFY, 0o755),
    (
        "infra/n3w-t1/f4/reboot-successor/"
        "n3wfc4-broker-certificate-lifecycle.service.d/"
        "10-runtime-status-evolution.conf"
    ): (DROPIN, 0o644),
}


class VerifyError(RuntimeError):
    pass


class EvidenceInsufficientError(VerifyError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha(document: object) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _json(path: Path, mode: int) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise VerifyError(f"record_invalid:{path.name}")
    metadata = path.stat()
    if (
        metadata.st_uid != 0
        or metadata.st_gid != 0
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != mode
    ):
        raise VerifyError(f"record_metadata_invalid:{path.name}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerifyError(f"record_json_invalid:{path.name}") from error
    if not isinstance(document, dict):
        raise VerifyError(f"record_document_invalid:{path.name}")
    return document


def _installed_control_binding(claim: dict[str, object]) -> None:
    source_head = claim.get("source_head")
    manifest_sha256 = claim.get("control_manifest_sha256")
    if (
        not isinstance(source_head, str)
        or re.fullmatch(r"[0-9a-f]{40}", source_head) is None
        or not isinstance(manifest_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", manifest_sha256) is None
    ):
        raise VerifyError("control_binding_claim_invalid")
    manifest = _json(CONTROL_MANIFEST, 0o644)
    if (
        _sha256(CONTROL_MANIFEST) != manifest_sha256
        or manifest.get("schema") != PACKAGE_SCHEMA
        or manifest.get("source_head") != source_head
    ):
        raise VerifyError("control_manifest_binding_invalid")
    records = manifest.get("files")
    if not isinstance(records, list):
        raise VerifyError("control_manifest_files_invalid")
    bindings = {}
    for item in records:
        if not isinstance(item, dict):
            raise VerifyError("control_manifest_file_record_invalid")
        relative = item.get("path")
        if not isinstance(relative, str) or relative in bindings:
            raise VerifyError("control_manifest_file_path_invalid")
        bindings[relative] = item
    if set(bindings) != set(CONTROL_TARGETS):
        raise VerifyError("control_manifest_file_set_invalid")
    for relative, (target, mode) in CONTROL_TARGETS.items():
        item = bindings[relative]
        if target.is_symlink() or not target.is_file():
            raise VerifyError(f"control_target_invalid:{relative}")
        metadata = target.stat()
        if (
            metadata.st_uid != 0
            or metadata.st_gid != 0
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != mode
            or item.get("sha256") != _sha256(target)
            or item.get("size") != metadata.st_size
        ):
            raise VerifyError(f"control_target_binding_invalid:{relative}")


def _boot_id_sha256() -> str:
    if BOOT_ID.is_symlink() or not BOOT_ID.is_file():
        raise VerifyError("boot_id_invalid")
    value = BOOT_ID.read_text(encoding="ascii").strip().lower()
    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        value,
    ) is None:
        raise VerifyError("boot_id_invalid")
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _load_f4() -> ModuleType:
    if F4_HOST.is_symlink() or not F4_HOST.is_file():
        raise VerifyError("f4_host_invalid")
    loader = importlib.machinery.SourceFileLoader("n3w_f4_reboot_verify", str(F4_HOST))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise VerifyError("f4_host_import_invalid")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


def _run(argv: tuple[str, ...], timeout: float = 60.0) -> str:
    completed = subprocess.run(
        argv,
        check=False,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        reason = completed.stderr.strip() or completed.stdout.strip()
        raise VerifyError(
            f"command_failed:{argv[0]}:{completed.returncode}:{reason[:300]}"
        )
    return completed.stdout


def _unit_success(unit: str) -> None:
    output = _run(
        (
            "systemctl",
            "show",
            unit,
            "--property=ActiveState,Result,ExecMainStatus",
        ),
        timeout=20,
    )
    values = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    if (
        values.get("ActiveState") != "active"
        or values.get("Result") != "success"
        or values.get("ExecMainStatus") != "0"
    ):
        raise VerifyError(f"unit_not_successful:{unit}")


def _inactive_oneshot_success(unit: str) -> None:
    output = _run(
        (
            "systemctl",
            "show",
            unit,
            "--property=ActiveState,Result,ExecMainStatus",
        ),
        timeout=20,
    )
    values = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    if (
        values.get("ActiveState") != "inactive"
        or values.get("Result") != "success"
        or values.get("ExecMainStatus") != "0"
    ):
        raise VerifyError(f"oneshot_not_successful:{unit}")



def _readiness_systemd_state() -> str:
    try:
        completed = subprocess.run(
            ("systemctl", "is-system-running"),
            check=False,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    state = completed.stdout.strip().casefold()
    if state in {"starting", "initializing", "running", "degraded", "maintenance", "offline"}:
        return state
    return "unavailable" if state in {"", "unknown"} else "invalid"


def _readiness_unit_state(unit: str) -> dict[str, str] | None:
    try:
        completed = subprocess.run(
            (
                "systemctl",
                "show",
                unit,
                "--property=LoadState,ActiveState,Result,ExecMainStatus",
            ),
            check=False,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    values = {}
    for line in completed.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    if not values:
        return None
    if not {"LoadState", "ActiveState", "Result", "ExecMainStatus"}.issubset(values):
        raise VerifyError("readiness_unit_evidence_invalid")
    return values


def _readiness_timer_enabled(unit: str) -> str | None:
    try:
        completed = subprocess.run(
            ("systemctl", "is-enabled", unit),
            check=False,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip().casefold()
    return value or None


def _readiness_running_services(module: ModuleType) -> frozenset[str] | None:
    try:
        completed = subprocess.run(
            (
                "docker",
                "compose",
                "--project-name",
                str(module.BROKER_PROJECT),
                "--env-file",
                str(module.COMPOSE_ENV),
                "-f",
                str(module.COMPOSE_TARGET),
                "--profile",
                "application",
                "ps",
                "--status",
                "running",
                "--services",
            ),
            check=False,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    services = frozenset(
        line.strip() for line in completed.stdout.splitlines() if line.strip()
    )
    if any(re.fullmatch(r"[a-zA-Z0-9_.-]+", service) is None for service in services):
        raise VerifyError("readiness_runtime_service_name_invalid")
    return services


def _readiness_report(
    claim: dict[str, object],
    boot_id_sha256: str,
    *,
    status: str,
    reason: str | None = None,
) -> dict[str, object]:
    document: dict[str, object] = {
        "schema": READINESS_SCHEMA,
        "status": status,
        "state": "READY" if status == "PASS" else "WAITING_FOR_BOOT_CONVERGENCE",
        "source_head": claim["source_head"],
        "control_manifest_sha256": claim["control_manifest_sha256"],
        "boot_id_sha256": boot_id_sha256,
        "board_access": False,
        "target_mutation": False,
    }
    if reason is not None:
        document["wait_reason"] = reason
    return document


def readiness() -> dict[str, object]:
    claim = _json(CLAIM_PATH, 0o600)
    if (
        claim.get("schema") != CLAIM_SCHEMA
        or claim.get("stage") != "REBOOT_PENDING"
        or claim.get("reboot_authorization_claimed") is not True
        or claim.get("reboot_authorization_consumed") is not True
        or claim.get("reboot_authorization_replay_allowed") is not False
        or claim.get("reboot_acceptance_passed") is not False
        or claim.get("board_access") is not False
    ):
        raise VerifyError("reboot_claim_invalid")

    _installed_control_binding(claim)
    pre_boot = claim.get("pre_boot_id_sha256")
    current_boot = _boot_id_sha256()
    if (
        not isinstance(pre_boot, str)
        or re.fullmatch(r"[0-9a-f]{64}", pre_boot) is None
        or current_boot == pre_boot
    ):
        raise VerifyError("reboot_not_observed")

    expected_f4_sha = claim.get("f4_transaction_sha256")
    if (
        not isinstance(expected_f4_sha, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_f4_sha) is None
        or _sha256(F4_TRANSACTION) != expected_f4_sha
    ):
        raise VerifyError("f4_transaction_changed_across_reboot")

    transaction = _json(F4_TRANSACTION, 0o600)
    if (
        transaction.get("stage") != "PERSISTENCE_ENABLED"
        or transaction.get("runtime_acceptance_passed") is not True
        or transaction.get("persistence_enabled") is not True
        or transaction.get("certificate_first_audit_passed") is not True
        or transaction.get("certificate_timer_enabled") is not True
        or transaction.get("pre_reboot_ready") is not True
    ):
        raise VerifyError("f4_transaction_post_reboot_invalid")

    module = _load_f4()
    systemd_state = _readiness_systemd_state()
    if systemd_state == "invalid":
        raise VerifyError("readiness_systemd_state_invalid")
    if systemd_state not in {
        "starting", "initializing", "unavailable", "running", "degraded"
    }:
        raise VerifyError("readiness_systemd_not_operational")

    required_units = (
        module.PROVISION_UNIT,
        module.GUARD_UNIT,
        module.BROKER_UNIT,
        module.SERVICES_UNIT,
        module.CERT_TIMER,
        module.CERT_SERVICE,
    )
    states: dict[str, dict[str, str]] = {}
    unit_status_unavailable = False
    for unit in required_units:
        state = _readiness_unit_state(unit)
        if state is None:
            unit_status_unavailable = True
            continue
        states[unit] = state
        if state.get("LoadState") != "loaded":
            if state.get("LoadState") == "not-found":
                raise VerifyError("readiness_required_unit_missing")
            raise VerifyError("readiness_unit_load_state_invalid")
        active = state.get("ActiveState")
        result = state.get("Result")
        exit_status = state.get("ExecMainStatus")
        if (
            active == "failed"
            or result not in {"", "success"}
            or exit_status not in {"", "0"}
        ):
            raise VerifyError("readiness_required_unit_failed")
        if active not in {
            "active", "activating", "reloading", "inactive", "deactivating"
        }:
            raise VerifyError("readiness_unit_state_invalid")

    timer_enabled = _readiness_timer_enabled(module.CERT_TIMER)
    if timer_enabled is not None and timer_enabled != "enabled":
        raise VerifyError("readiness_certificate_timer_not_enabled")

    running_services = _readiness_running_services(module)
    if running_services is not None:
        unexpected = running_services - EXPECTED_SERVICES
        if unexpected:
            raise VerifyError(
                "runtime_service_set_unexpected:" + ",".join(sorted(unexpected))
            )

    if systemd_state in {"starting", "initializing"}:
        return _readiness_report(
            claim, current_boot, status="WAIT", reason="systemd_starting"
        )
    if systemd_state == "unavailable":
        return _readiness_report(
            claim, current_boot, status="WAIT", reason="systemd_state_unavailable"
        )
    if unit_status_unavailable:
        return _readiness_report(
            claim, current_boot, status="WAIT", reason="unit_status_unavailable"
        )
    if timer_enabled is None:
        return _readiness_report(
            claim, current_boot, status="WAIT",
            reason="certificate_timer_enablement_unavailable",
        )
    if running_services is None:
        return _readiness_report(
            claim, current_boot, status="WAIT",
            reason="runtime_service_probe_unavailable",
        )

    for unit in (
        module.PROVISION_UNIT,
        module.GUARD_UNIT,
        module.BROKER_UNIT,
        module.SERVICES_UNIT,
    ):
        state = states[unit]
        if state["ActiveState"] != "active":
            if state["ActiveState"] in {"inactive", "activating", "reloading"}:
                return _readiness_report(
                    claim, current_boot, status="WAIT", reason="required_unit_not_active"
                )
            raise VerifyError("readiness_required_unit_state_invalid")
        if state["Result"] != "success" or state["ExecMainStatus"] != "0":
            raise VerifyError("readiness_required_unit_failed")

    timer = states[module.CERT_TIMER]
    if timer["ActiveState"] != "active":
        if timer["ActiveState"] in {"inactive", "activating", "reloading"}:
            return _readiness_report(
                claim, current_boot, status="WAIT", reason="certificate_timer_not_active"
            )
        raise VerifyError("readiness_certificate_timer_state_invalid")
    if timer["Result"] not in {"", "success"}:
        raise VerifyError("readiness_certificate_timer_failed")

    certificate_service = states[module.CERT_SERVICE]
    certificate_state = certificate_service["ActiveState"]
    if certificate_state in {"active", "activating", "reloading", "deactivating"}:
        return _readiness_report(
            claim, current_boot, status="WAIT",
            reason="certificate_service_in_progress",
        )
    if (
        certificate_state != "inactive"
        or certificate_service["Result"] != "success"
        or certificate_service["ExecMainStatus"] != "0"
    ):
        raise VerifyError("readiness_certificate_service_invalid")

    if running_services != EXPECTED_SERVICES:
        return _readiness_report(
            claim, current_boot, status="WAIT", reason="runtime_service_set_incomplete"
        )
    return _readiness_report(claim, current_boot, status="PASS")


def _safe_error_code(error: BaseException) -> str:
    value = str(error)
    command_failure = re.match(r"^command_failed:(.+?):([0-9]+)(?::.*)?$", value)
    if command_failure is not None:
        command = Path(command_failure.group(1)).name
        code = f"command_failed:{command}:{command_failure.group(2)}"
        if SANITIZED_COMMAND_FAILURE_RE.fullmatch(code) is not None:
            return code
    if isinstance(error, EvidenceInsufficientError):
        if _repository_defined_error_code(value):
            return value
        return "evidence_insufficient"
    if isinstance(error, VerifyError):
        if _repository_defined_error_code(value):
            return value
        return "verify_failed"
    return "verification_error"

def verify() -> dict[str, object]:
    claim = _json(CLAIM_PATH, 0o600)
    if (
        claim.get("schema") != CLAIM_SCHEMA
        or claim.get("stage") != "REBOOT_PENDING"
        or claim.get("reboot_authorization_claimed") is not True
        or claim.get("reboot_authorization_consumed") is not True
        or claim.get("reboot_authorization_replay_allowed") is not False
        or claim.get("reboot_acceptance_passed") is not False
        or claim.get("board_access") is not False
    ):
        raise VerifyError("reboot_claim_invalid")

    _installed_control_binding(claim)

    pre_boot = claim.get("pre_boot_id_sha256")
    current_boot = _boot_id_sha256()
    if (
        not isinstance(pre_boot, str)
        or re.fullmatch(r"[0-9a-f]{64}", pre_boot) is None
        or current_boot == pre_boot
    ):
        raise VerifyError("reboot_not_observed")

    expected_f4_sha = claim.get("f4_transaction_sha256")
    if (
        not isinstance(expected_f4_sha, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_f4_sha) is None
        or _sha256(F4_TRANSACTION) != expected_f4_sha
    ):
        raise VerifyError("f4_transaction_changed_across_reboot")

    module = _load_f4()
    transaction = _json(F4_TRANSACTION, 0o600)
    if (
        transaction.get("stage") != "PERSISTENCE_ENABLED"
        or transaction.get("runtime_acceptance_passed") is not True
        or transaction.get("persistence_enabled") is not True
        or transaction.get("certificate_first_audit_passed") is not True
        or transaction.get("certificate_timer_enabled") is not True
        or transaction.get("pre_reboot_ready") is not True
    ):
        raise VerifyError("f4_transaction_post_reboot_invalid")

    verified = module._provision_verify()
    module._validate_factory_binding(verified)
    module._verify_installed_material(transaction)
    module._validate_runtime_acceptance_binding(transaction)
    pre_certificate_snapshot_sha256 = claim.get(
        "pre_certificate_snapshot_sha256"
    )
    if (
        not isinstance(pre_certificate_snapshot_sha256, str)
        or re.fullmatch(
            r"[0-9a-f]{64}",
            pre_certificate_snapshot_sha256,
        )
        is None
        or _canonical_sha(module._certificate_identity_snapshot())
        != pre_certificate_snapshot_sha256
    ):
        raise VerifyError("certificate_identity_changed_across_reboot")

    _unit_success(module.PROVISION_UNIT)
    _unit_success(module.GUARD_UNIT)
    if (
        module._systemctl("is-active", module.BROKER_UNIT) != "active"
        or module._systemctl("is-active", module.SERVICES_UNIT) != "active"
        or module._systemctl("is-enabled", module.GUARD_UNIT) != "enabled"
        or module._systemctl("is-enabled", module.PROVISION_UNIT) != "enabled"
        or module._systemctl("is-enabled", module.BROKER_UNIT) != "enabled"
        or module._systemctl("is-enabled", module.SERVICES_UNIT) != "enabled"
        or module._systemctl("is-enabled", module.CERT_TIMER) != "enabled"
        or module._systemctl("is-active", module.CERT_TIMER) != "active"
    ):
        raise VerifyError("post_reboot_unit_contract_invalid")

    dropins = _run(
        (
            "systemctl",
            "show",
            module.CERT_SERVICE,
            "--property=DropInPaths",
            "--value",
        ),
        timeout=20,
    )
    if str(DROPIN) not in dropins:
        raise VerifyError("certificate_runtime_guard_dropin_missing")

    deadline = time.monotonic() + 300.0
    while module._systemctl("is-active", module.CERT_SERVICE) in {
        "active",
        "activating",
        "reloading",
    }:
        if time.monotonic() >= deadline:
            raise VerifyError("certificate_service_not_quiescent")
        time.sleep(2.0)
    if module._systemctl("is-active", module.CERT_SERVICE) != "inactive":
        raise VerifyError("certificate_service_post_reboot_invalid")
    _inactive_oneshot_success(module.CERT_SERVICE)

    running = module._wait_for_runtime_service_set(
        timeout_seconds=300.0,
        poll_seconds=2.0,
    )
    if running != EXPECTED_SERVICES:
        raise VerifyError("runtime_service_set_invalid")

    release = module._read_release()
    inspects = {
        label: module._compose_service_inspect(label)
        for label in ("broker", "manager", "homeassistant")
    }
    module._runtime_image_acceptance(release, inspects)
    module._product_container_guard(release, inspects)
    module._broker_runtime_contract(inspects["broker"])
    module._manager_runtime_contract(inspects["manager"])
    module._homeassistant_runtime_contract(inspects["homeassistant"])
    module._service_identity_runtime_binding(
        inspects["manager"],
        expected_system_id=str(verified["system_id"]),
    )
    module._guard_runtime_verify()
    module._verified_tls_runtime()

    manager_name = str(inspects["manager"].get("Name", "")).lstrip("/")
    homeassistant_name = str(inspects["homeassistant"].get("Name", "")).lstrip("/")
    if not manager_name or not homeassistant_name:
        raise VerifyError("runtime_container_name_missing")

    manager_state = module._manager_state_audit(manager_name)
    manager_id = inspects["manager"].get("Id")
    manager_runtime_state = inspects["manager"].get("State")
    if (
        not isinstance(manager_id, str)
        or not isinstance(manager_runtime_state, dict)
        or not isinstance(manager_runtime_state.get("StartedAt"), str)
    ):
        raise VerifyError("manager_runtime_identity_invalid")
    module._manager_runtime_stability(
        manager_name,
        expected_id=manager_id,
        expected_started_at=str(manager_runtime_state["StartedAt"]),
    )
    homeassistant = module._homeassistant_private_audit(homeassistant_name)
    if (
        manager_state.get("status") != "PASS"
        or homeassistant.get("entry_id_sha256")
        != transaction.get("homeassistant_mqtt_entry_id_sha256")
    ):
        raise VerifyError("post_reboot_business_state_invalid")
    module._homeassistant_http_readiness()

    if module._container_established_socket_count(manager_name, 8883) != 1:
        raise VerifyError("manager_mqtt_socket_count_invalid")
    if module._container_established_socket_count(homeassistant_name, 1883) < 1:
        raise VerifyError("homeassistant_mqtt_socket_missing")

    manager_image = str(release["images"]["manager"]["image"])
    module._root_identity_runtime_audit(manager_image)
    module._broker_auth_negative_and_provisioning_probe(manager_image)

    guard = json.loads(_run((str(RUNTIME_GUARD), "check"), timeout=60))
    if guard.get("status") != "PASS":
        raise VerifyError("certificate_runtime_guard_not_pass")

    return {
        "schema": REPORT_SCHEMA,
        "status": "PASS",
        "state": "REBOOT_ACCEPTED",
        "reboot_acceptance_passed": True,
        "pre_boot_id_sha256": pre_boot,
        "post_boot_id_sha256": current_boot,
        "f4_transaction_unchanged": True,
        "provision_resume_verified": True,
        "broker_services_persistence_verified": True,
        "certificate_timer_runtime_verified": True,
        "certificate_service_result_verified": True,
        "certificate_status_sha256": guard["runtime_status_sha256"],
        "certificate_identity_unchanged": True,
        "manager_runtime_stability_verified": True,
        "homeassistant_mqtt_integration_not_duplicated": True,
        "manager_business_state_fresh": True,
        "board_access": False,
    }


SNAPSHOT_SCHEMA = "gh.n3w-t1-runtime-snapshot/2"
LOG_LIMIT = 10000

# Read /proc inside the service PID/network namespaces. Export hashes, never
# socket addresses, credentials or broker log text, to the Mac executor.
SOCKET_SCRIPT = r"""
import glob, hashlib, ipaddress, json, os, socket, struct, sys
host, port = sys.argv[1], int(sys.argv[2])
expected = {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
assert expected and all(ipaddress.ip_address(ip).is_loopback for ip in expected)
rows = {}
for path, family in (("/proc/net/tcp", socket.AF_INET), ("/proc/net/tcp6", socket.AF_INET6)):
    for row in open(path, encoding="ascii").read().splitlines()[1:]:
        fields = row.split()
        if fields[3] != "01":
            continue
        address, remote_port = fields[2].split(":")
        packed = b"".join(struct.pack("=I", int(address[i:i+8], 16)) for i in range(0, len(address), 8))
        ip = socket.inet_ntop(family, packed)
        if int(remote_port, 16) == port and ip in expected:
            rows[fields[9]] = fields[1:4]
owned = set()
for fd in glob.glob("/proc/[0-9]*/fd/*"):
    try:
        link = os.readlink(fd)
        inode = link[8:-1] if link.startswith("socket:[") else ""
        if inode in rows:
            pid = fd.split("/")[2]
            start = open("/proc/" + pid + "/stat").read().rsplit(")", 1)[1].split()[19]
            owned.add((inode, pid, start, *rows[inode]))
    except (OSError, IndexError):
        continue
owned_socket_count = len({r[0] for r in owned})
print(json.dumps({
    "owned_socket_count": owned_socket_count,
    "owned_socket_sha256": hashlib.sha256(json.dumps(sorted(owned)).encode()).hexdigest(),
}))
"""


def _snapshot_run(argv: tuple[str, ...]) -> str:
    try:
        return _run(argv, timeout=8)
    except VerifyError as error:
        raise EvidenceInsufficientError(
            "runtime_snapshot_command_evidence_unavailable"
        ) from error
    except subprocess.SubprocessError as error:
        raise EvidenceInsufficientError(
            "runtime_snapshot_command_evidence_unavailable"
        ) from error


def _broker_auth_evidence(logs: str, identity: dict[str, object]) -> str:
    client_id, username = identity.get("client_id"), identity.get("username")
    if not all(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]+", value)
               for value in (client_id, username)):
        raise VerifyError("runtime_identity_invalid")
    lines = logs.splitlines()
    if len(lines) >= LOG_LIMIT:
        raise EvidenceInsufficientError("broker_log_coverage_insufficient")
    connected = re.compile(
        r"New client connected from .+ as " + re.escape(client_id)
        + r" \(p5, c[01], k[0-9]+, u'" + re.escape(username) + r"'\)\."
    )
    any_connection = re.compile(
        r"New client connected from .+ as " + re.escape(client_id) + r" \("
    )
    terminal = re.compile(
        r"(?:Client|client) " + re.escape(client_id)
        + r"(?: disconnected\b| closed its connection\b"
        + r"| already connected, closing old connection\b"
        + r"| has exceeded timeout, disconnecting\b)"
    )
    authenticated: list[str] = []
    current_session_authenticated = False
    for line in lines:
        if any_connection.search(line):
            if connected.search(line) is None:
                raise VerifyError(
                    "broker_authenticated_connection_identity_mismatch"
                )
            authenticated.append(line)
            current_session_authenticated = True
            continue
        if terminal.search(line):
            current_session_authenticated = False
    if not authenticated:
        raise EvidenceInsufficientError(
            "broker_authenticated_connection_evidence_missing"
        )
    if not current_session_authenticated:
        raise EvidenceInsufficientError(
            "broker_current_session_authentication_evidence_missing"
        )
    return _canonical_sha(authenticated)


def _runtime_socket_evidence(
    service: str,
    report: dict[str, object],
) -> tuple[int, str]:
    count = report.get("owned_socket_count")
    fingerprint = report.get("owned_socket_sha256")
    if (
        type(count) is not int
        or count < 0
        or not isinstance(fingerprint, str)
        or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
    ):
        raise EvidenceInsufficientError("runtime_socket_evidence_invalid")
    if service == "manager":
        if count != 1:
            raise VerifyError("manager_mqtt_socket_count_invalid")
    elif service == "homeassistant":
        if count < 1:
            raise VerifyError("homeassistant_mqtt_socket_missing")
    else:
        raise VerifyError("runtime_service_invalid")
    return count, fingerprint


def _service_socket_evidence(
    inspects: dict[str, dict[str, object]],
    service: str,
    host: str,
    port: int,
) -> tuple[int, str]:
    report = json.loads(_snapshot_run((
        "docker", "exec", str(inspects[service]["Id"]),
        "python3", "-c", SOCKET_SCRIPT, host, str(port),
    )))
    return _runtime_socket_evidence(service, report)


def _systemd_snapshot(module: ModuleType) -> tuple[str, str]:
    core = (module.PROVISION_UNIT, module.GUARD_UNIT, module.BROKER_UNIT,
            module.SERVICES_UNIT, module.CERT_TIMER)
    stable = {}
    for unit in (*core, module.CERT_SERVICE):
        output = _snapshot_run((
            "systemctl", "show", unit,
            "--property=ActiveState,Result,ExecMainStatus,NRestarts,ExecMainStartTimestampMonotonic",
        ))
        state = dict(line.split("=", 1) for line in output.splitlines() if "=" in line)
        if (state.get("Result", "success") != "success"
                or state.get("ExecMainStatus", "0") != "0"):
            raise VerifyError("critical_systemd_unit_failed")
        if unit == module.CERT_SERVICE:
            # A healthy scheduled oneshot may run and return to inactive.
            if state.get("ActiveState") not in {"active", "activating", "inactive", "deactivating"}:
                raise VerifyError("certificate_unit_state_invalid")
        else:
            if state.get("ActiveState") != "active":
                raise VerifyError("critical_systemd_unit_not_active")
            stable[unit] = state
    command = ["journalctl", "--boot=0", "--no-pager", "--output=json", "--priority=0..3", "--lines=1000"]
    for unit in (*core, module.CERT_SERVICE):
        command.extend(("--unit", unit))
    journal = _snapshot_run(tuple(command))
    lines = journal.splitlines()
    if len(lines) >= 1000:
        raise EvidenceInsufficientError("systemd_error_coverage_insufficient")
    # Cursors preserve new errors even when a failed unit has already recovered.
    cursors = []
    for line in lines:
        record = json.loads(line)
        cursor = record.get("__CURSOR")
        if not isinstance(cursor, str) or not cursor:
            raise EvidenceInsufficientError("systemd_error_cursor_missing")
        cursors.append(cursor)
    return _canonical_sha(stable), _canonical_sha(cursors)


def runtime_snapshot() -> dict[str, object]:
    claim = _json(CLAIM_PATH, 0o600)
    _installed_control_binding(claim)
    if _sha256(F4_TRANSACTION) != claim.get("f4_transaction_sha256"):
        raise VerifyError("snapshot_transaction_binding_changed")
    module = _load_f4()
    inspects = {name: module._compose_service_inspect(name) for name in sorted(EXPECTED_SERVICES)}
    containers = {}
    for name, item in inspects.items():
        state = item.get("State", {})
        if (state.get("Running") is not True or state.get("Paused") is not False
                or state.get("Restarting") is not False
                or not item.get("Id") or not state.get("StartedAt")
                or type(item.get("RestartCount")) is not int):
            raise VerifyError("snapshot_container_not_running")
        containers[name] = {
            "identity_sha256": _canonical_sha([item["Id"], state["StartedAt"]]),
            "restart_count": item["RestartCount"], "running": True,
        }
    broker = inspects["broker"]
    auth = {}
    for service, host, port in (("manager", "armbian", 8883), ("homeassistant", "127.0.0.1", 1883)):
        owner = 999 if service == "manager" else 0
        identity = module._private_service_json(
            Path("/opt/greenhouse-secrets/mqtt") / service / "identity.json", uid=owner, gid=owner,
        )
        before_count, before_fingerprint = _service_socket_evidence(
            inspects, service, host, port
        )
        service_state = inspects[service].get("State")
        if not isinstance(service_state, dict) or not isinstance(
            service_state.get("StartedAt"), str
        ):
            raise VerifyError("snapshot_container_not_running")
        logs = _snapshot_run((
            "docker", "logs", "--timestamps", "--since",
            service_state["StartedAt"], "--tail", str(LOG_LIMIT), broker["Id"],
        ))
        authenticated_connection = _broker_auth_evidence(logs, identity)
        after_count, after_fingerprint = _service_socket_evidence(
            inspects, service, host, port
        )
        if (
            before_count != after_count
            or before_fingerprint != after_fingerprint
        ):
            raise EvidenceInsufficientError(
                "runtime_socket_auth_evidence_unstable"
            )
        auth[service] = {
            "authenticated": True, "endpoint_port": port,
            "identity_sha256": _canonical_sha([identity["username"], identity["client_id"]]),
            "owned_socket_count": after_count,
            "owned_socket_sha256": after_fingerprint,
            "authenticated_connection_sha256": authenticated_connection,
        }
    state_sha, errors_sha = _systemd_snapshot(module)
    connection = http.client.HTTPConnection("127.0.0.1", 8123, timeout=4)
    try:
        connection.request("GET", "/api/")
        response = connection.getresponse()
        response.read(1024)
        if response.status not in {200, 401}:
            raise VerifyError("runtime_homeassistant_not_ready")
    finally:
        connection.close()
    return {
        "schema": SNAPSHOT_SCHEMA, "status": "PASS",
        "boot_id_sha256": _boot_id_sha256(), "source_head": claim["source_head"],
        "control_manifest_sha256": claim["control_manifest_sha256"],
        "containers": containers, "runtime_service_auth": auth,
        "systemd_state_sha256": state_sha, "critical_errors_sha256": errors_sha,
        "homeassistant_http_ready": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--snapshot", action="store_true")
    mode.add_argument("--readiness", action="store_true")
    args = parser.parse_args()
    try:
        if args.snapshot:
            document = runtime_snapshot()
        elif args.readiness:
            document = readiness()
        else:
            document = verify()
    except (
        VerifyError,
        ImportError,
        KeyError,
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as error:
        print(
            json.dumps(
                {
                    "schema": REPORT_SCHEMA,
                    "status": "FAIL",
                    "failure_class": (
                        "EVIDENCE_INSUFFICIENT"
                        if isinstance(error, EvidenceInsufficientError)
                        else "VERIFY_FAILED"
                    ),
                    "error_code": _safe_error_code(error),
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(document, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
