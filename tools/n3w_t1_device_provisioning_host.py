#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

SCHEMA = "gh.n3w-t1-device-provisioning-host/1"
RELEASE_SCHEMA = "gh.n3w-t1-fresh-release/1"
RELEASE_PATH = Path(
    "/opt/HomeAssistant/infra/n3w-t1/production/fresh-release.json"
)
FRESH_TOOL_PATH = Path(
    "/opt/HomeAssistant/tools/n3w_t1_fresh_product_bootstrap.py"
)
FIRSTBOOT_TOOL_PATH = Path(
    "/opt/HomeAssistant/tools/n3w_t1_device_firstboot.py"
)
TRANSACTION_ROOT = Path("/var/lib/n3w-t1-provisioning")
CANDIDATE_ROOT = Path("/var/tmp/n3w-t1-provisioning-candidate")
MACHINE_ID_PATH = Path("/etc/machine-id")
SSH_HOST_PUBLIC_KEY = Path("/etc/ssh/ssh_host_ed25519_key.pub")
CONFIRMATION = "START DEVICE PROVISIONING: YES"
PRODUCTION_PHASE = "PROVISION"
PRODUCTION_EXECUTION_CLAIM_SCHEMA = (
    "gh.n3w-t1-provisioning-production-execution-claim/1"
)
PRODUCTION_EXECUTION_COMPLETE_SCHEMA = (
    "gh.n3w-t1-provisioning-production-execution-complete/1"
)
PRODUCTION_EXECUTION_LEDGER_ROOT = Path(
    "/var/lib/n3w-t1-provisioning-production-executions"
)


class ProvisionHostError(RuntimeError):
    pass


def _load_module(path: Path, name: str) -> ModuleType:
    if path.is_symlink() or not path.is_file():
        raise ProvisionHostError(f"module_source_invalid:{path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ProvisionHostError(f"module_spec_invalid:{path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _read_release(path: Path = RELEASE_PATH) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ProvisionHostError("fresh_release_missing")
    metadata = path.stat()
    if (
        metadata.st_uid != os.geteuid()
        or metadata.st_mode & 0o777 != 0o644
        or metadata.st_nlink != 1
    ):
        raise ProvisionHostError("fresh_release_metadata_invalid")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProvisionHostError("fresh_release_invalid") from error
    if not isinstance(document, dict) or document.get("schema") != RELEASE_SCHEMA:
        raise ProvisionHostError("fresh_release_schema_invalid")
    source_head = document.get("source_head")
    release_id = document.get("release_id")
    if (
        not isinstance(source_head, str)
        or re.fullmatch(r"[0-9a-f]{40}", source_head) is None
        or release_id != source_head
        or document.get("instance_material_absent") is not True
        or document.get("explicit_provisioning_required") is not True
    ):
        raise ProvisionHostError("fresh_release_binding_invalid")
    images = document.get("images")
    image_lock = document.get("image_lock")
    if not isinstance(images, dict) or set(images) != {
        "homeassistant",
        "manager",
        "broker",
    }:
        raise ProvisionHostError("fresh_release_images_invalid")
    if (
        not isinstance(image_lock, dict)
        or image_lock.get("source_head") != source_head
    ):
        raise ProvisionHostError("fresh_release_image_lock_invalid")
    for label in ("homeassistant", "manager", "broker"):
        record = images.get(label)
        locked = image_lock.get(label)
        if (
            not isinstance(record, dict)
            or not isinstance(locked, dict)
            or record.get("image") != locked.get("image")
            or record.get("image_id") != locked.get("image_id")
            or record.get("platform") != "linux/arm64"
        ):
            raise ProvisionHostError(f"fresh_release_image_binding_invalid:{label}")
    return document


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_sha256(document: object) -> str:
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_production_execution_root() -> None:
    root = PRODUCTION_EXECUTION_LEDGER_ROOT
    if root.is_symlink():
        raise ProvisionHostError("production_execution_ledger_root_invalid")
    if not root.exists():
        return
    metadata = root.stat()
    if (
        not root.is_dir()
        or metadata.st_uid != os.geteuid()
        or metadata.st_mode & 0o777 != 0o700
    ):
        raise ProvisionHostError("production_execution_ledger_root_invalid")


def _production_execution_paths(
    context: dict[str, Any],
) -> tuple[Path, Path]:
    digest = hashlib.sha256(
        (
            context["run_id"]
            + "\n"
            + context["phase"]
            + "\n"
            + context["claim_sha256"]
            + "\n"
        ).encode("utf-8")
    ).hexdigest()
    return (
        PRODUCTION_EXECUTION_LEDGER_ROOT / f"{digest}.claim.json",
        PRODUCTION_EXECUTION_LEDGER_ROOT / f"{digest}.complete.json",
    )


def _write_new_json(path: Path, document: dict[str, Any]) -> None:
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, 0o600)
    directory_fd = os.open(
        path.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _load_production_phase_context(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ProvisionHostError("production_phase_context_missing")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProvisionHostError("production_phase_context_invalid") from error
    required = {
        "schema",
        "run_id",
        "phase",
        "claim_sha256",
        "plan_sha256",
        "binding",
        "binding_sha256",
        "authorization_consumed",
        "replay_allowed",
        "board_access",
    }
    binding_fields = {
        "source_head",
        "release_id",
        "artifact_sha256",
        "predecessor_sha256",
        "target_binding_sha256",
    }
    binding = document.get("binding") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or set(document) != required
        or document.get("schema") != "gh.n3w-t1-production-phase-context/1"
        or document.get("phase") != PRODUCTION_PHASE
        or re.fullmatch(r"[0-9a-f]{64}", str(document.get("run_id"))) is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(document.get("claim_sha256")),
        )
        is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(document.get("plan_sha256")),
        )
        is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(document.get("binding_sha256")),
        )
        is None
        or document.get("authorization_consumed") is not True
        or document.get("replay_allowed") is not False
        or document.get("board_access") is not False
        or not isinstance(binding, dict)
        or set(binding) != binding_fields
        or re.fullmatch(
            r"[0-9a-f]{40}",
            str(binding.get("source_head")),
        )
        is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(binding.get("release_id")),
        )
        is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(binding.get("artifact_sha256")),
        )
        is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(binding.get("target_binding_sha256")),
        )
        is None
        or (
            binding.get("predecessor_sha256") is not None
            and re.fullmatch(
                r"[0-9a-f]{64}",
                str(binding.get("predecessor_sha256")),
            )
            is None
        )
    ):
        raise ProvisionHostError("production_phase_context_invalid")
    try:
        from n3w_t1_production_authority import validate_phase_context
    except ImportError as error:
        raise ProvisionHostError(
            "production_authority_dependency_missing"
        ) from error
    validated = validate_phase_context(
        document,
        required_phase=PRODUCTION_PHASE,
    )
    if (
        validated.get("status") != "PASS"
        or validated.get("run_id") != document["run_id"]
        or validated.get("phase") != PRODUCTION_PHASE
        or validated.get("claim_sha256") != document["claim_sha256"]
    ):
        raise ProvisionHostError("production_phase_context_not_authorized")
    return document


def _production_execution_claim_present(
    context: dict[str, Any],
) -> bool:
    _validate_production_execution_root()
    claim_path, _complete_path = _production_execution_paths(context)
    if not claim_path.exists() and not claim_path.is_symlink():
        return False
    if claim_path.is_symlink() or not claim_path.is_file():
        raise ProvisionHostError("production_execution_claim_invalid")
    metadata = claim_path.stat()
    if (
        metadata.st_uid != os.geteuid()
        or metadata.st_mode & 0o777 != 0o600
        or metadata.st_nlink != 1
    ):
        raise ProvisionHostError("production_execution_claim_invalid")
    try:
        record = json.loads(claim_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProvisionHostError("production_execution_claim_invalid") from error
    expected = {
        "schema",
        "run_id",
        "phase",
        "phase_claim_sha256",
        "plan_sha256",
        "binding_sha256",
        "source_head",
        "production_release_id",
        "provisioning_release_id",
        "target_binding_sha256",
        "authorization_consumed",
        "replay_allowed",
        "board_access",
    }
    binding = context["binding"]
    if (
        not isinstance(record, dict)
        or set(record) != expected
        or record.get("schema") != PRODUCTION_EXECUTION_CLAIM_SCHEMA
        or record.get("run_id") != context["run_id"]
        or record.get("phase") != PRODUCTION_PHASE
        or record.get("phase_claim_sha256") != context["claim_sha256"]
        or record.get("plan_sha256") != context["plan_sha256"]
        or record.get("binding_sha256") != context["binding_sha256"]
        or record.get("source_head") != binding["source_head"]
        or record.get("production_release_id") != binding["release_id"]
        or record.get("target_binding_sha256")
        != binding["target_binding_sha256"]
        or record.get("authorization_consumed") is not True
        or record.get("replay_allowed") is not False
        or record.get("board_access") is not False
    ):
        raise ProvisionHostError("production_execution_claim_invalid")
    return True


def _claim_production_execution(
    release: dict[str, object],
    context: dict[str, Any],
) -> None:
    _validate_production_execution_root()
    PRODUCTION_EXECUTION_LEDGER_ROOT.mkdir(mode=0o700, exist_ok=True)
    os.chmod(PRODUCTION_EXECUTION_LEDGER_ROOT, 0o700)
    _validate_production_execution_root()
    claim_path, complete_path = _production_execution_paths(context)
    if (
        claim_path.exists()
        or claim_path.is_symlink()
        or complete_path.exists()
        or complete_path.is_symlink()
    ):
        raise ProvisionHostError("production_execution_already_consumed")
    binding = context["binding"]
    record = {
        "schema": PRODUCTION_EXECUTION_CLAIM_SCHEMA,
        "run_id": context["run_id"],
        "phase": PRODUCTION_PHASE,
        "phase_claim_sha256": context["claim_sha256"],
        "plan_sha256": context["plan_sha256"],
        "binding_sha256": context["binding_sha256"],
        "source_head": release["source_head"],
        "production_release_id": binding["release_id"],
        "provisioning_release_id": release["release_id"],
        "target_binding_sha256": binding["target_binding_sha256"],
        "authorization_consumed": True,
        "replay_allowed": False,
        "board_access": False,
    }
    _write_new_json(claim_path, record)


def _complete_production_execution(
    firstboot: ModuleType,
    context: dict[str, Any],
    report: dict[str, Any],
) -> None:
    if not _production_execution_claim_present(context):
        raise ProvisionHostError("production_execution_claim_missing")
    claim_path, complete_path = _production_execution_paths(context)
    if complete_path.exists() or complete_path.is_symlink():
        raise ProvisionHostError("production_execution_complete_exists")
    transaction_name = getattr(firstboot, "TRANSACTION_NAME", None)
    complete_name = getattr(firstboot, "COMPLETE_NAME", None)
    if (
        not isinstance(transaction_name, str)
        or Path(transaction_name).name != transaction_name
        or not isinstance(complete_name, str)
        or Path(complete_name).name != complete_name
    ):
        raise ProvisionHostError("provisioning_record_names_invalid")
    transaction_path = TRANSACTION_ROOT / transaction_name
    firstboot_complete_path = TRANSACTION_ROOT / complete_name
    for path in (transaction_path, firstboot_complete_path):
        if path.is_symlink() or not path.is_file():
            raise ProvisionHostError("provisioning_durable_record_missing")
    record = {
        "schema": PRODUCTION_EXECUTION_COMPLETE_SCHEMA,
        "run_id": context["run_id"],
        "phase": PRODUCTION_PHASE,
        "production_claim_record_sha256": _sha256_file(claim_path),
        "transaction_sha256": _sha256_file(transaction_path),
        "firstboot_complete_sha256": _sha256_file(firstboot_complete_path),
        "result_sha256": _json_sha256(report),
        "device_ready": True,
        "production_service_start": False,
        "authorization_consumed": True,
        "replay_allowed": False,
        "board_access": False,
    }
    _write_new_json(complete_path, record)


def _start_device_provisioning(
    firstboot: ModuleType,
    adapters: HostAdapters,
    release: dict[str, object],
    *,
    confirmation: str | None,
    production_phase_context: Path | None,
) -> dict[str, Any]:
    release_id = str(release["release_id"])
    if production_phase_context is None:
        if confirmation != CONFIRMATION:
            raise ProvisionHostError("provisioning_confirmation_invalid")
        return firstboot.start_device_provisioning(
            adapters,
            TRANSACTION_ROOT,
            CANDIDATE_ROOT,
            release_id=release_id,
            confirmation=confirmation,
        )
    if confirmation is not None:
        raise ProvisionHostError("provisioning_authority_mode_conflict")
    context = _load_production_phase_context(production_phase_context)
    if context["binding"]["source_head"] != release["source_head"]:
        raise ProvisionHostError("production_context_source_head_mismatch")
    if _production_execution_claim_present(context):
        raise ProvisionHostError("production_execution_already_consumed")
    _claim_production_execution(release, context)
    try:
        report = firstboot.start_device_provisioning(
            adapters,
            TRANSACTION_ROOT,
            CANDIDATE_ROOT,
            release_id=release_id,
            confirmation=CONFIRMATION,
        )
        if (
            report.get("status") != "PASS"
            or report.get("state") != "DEVICE_READY"
            or report.get("production_service_start") is not False
        ):
            raise ProvisionHostError("production_provisioning_result_invalid")
        _complete_production_execution(firstboot, context, report)
    except Exception as error:
        try:
            setattr(error, "production_claimed", True)
        except Exception:
            pass
        raise
    return {
        **report,
        "production_run_id": context["run_id"],
        "production_phase": PRODUCTION_PHASE,
        "phase_claim_sha256": context["claim_sha256"],
        "authorization_consumed": True,
        "replay_allowed": False,
    }


def _host_identity() -> dict[str, object]:
    if (
        MACHINE_ID_PATH.is_symlink()
        or not MACHINE_ID_PATH.is_file()
        or SSH_HOST_PUBLIC_KEY.is_symlink()
        or not SSH_HOST_PUBLIC_KEY.is_file()
    ):
        raise ProvisionHostError("os_identity_material_missing")
    machine_id = MACHINE_ID_PATH.read_text(encoding="utf-8").strip()
    if re.fullmatch(r"[0-9a-f]{32}", machine_id) is None:
        raise ProvisionHostError("machine_id_invalid")
    ssh_public = SSH_HOST_PUBLIC_KEY.read_bytes().strip()
    if not ssh_public:
        raise ProvisionHostError("ssh_host_identity_invalid")
    digest = hashlib.sha256(
        machine_id.encode("ascii") + b"\0" + ssh_public
    ).hexdigest()
    return {
        "status": "PASS",
        "host_instance_id": f"t1h-{digest[:24]}",
        "machine_id_ready": True,
        "ssh_host_identity_ready": True,
        "production_service_start": False,
        "network_operation": False,
    }


class HostAdapters:
    def __init__(self, release: dict[str, object]) -> None:
        self.release = release
        self.fresh = _load_module(FRESH_TOOL_PATH, "n3w_installed_fresh_bootstrap")
        manifest = {
            "images": release["images"],
            "image_lock": release["image_lock"],
            "source_head": release["source_head"],
        }
        self.live = self.fresh.LiveFreshInstallerAdapters(
            Path("/opt/HomeAssistant"),
            manifest,
            self.fresh.Runner(),
        )
        for label in ("homeassistant", "manager", "broker"):
            record = release["images"][label]
            self.live.loaded_image_bindings[label] = self.fresh._verify_runtime_image(
                self.live.runner,
                label,
                record,
            )

    def preflight_fresh_host(self):
        report = self.live.master_postcheck(
            require_instance_absent=True,
            staged_units_enabled=True,
        )
        return {
            "status": "PASS",
            "fresh_host_ready": True,
            "release_id": self.release["release_id"],
            "release_binding_verified": True,
            "product_state_absent": report["instance_material_absent"],
            "production_service_start": False,
        }

    def ensure_os_identity(self):
        return _host_identity()

    def verify_os_identity(self):
        return _host_identity()

    def create_identity(self, candidate_root: Path):
        return self.live.create_identity(candidate_root)

    def create_state(self, candidate_root: Path, system_id_sha256: str):
        return self.live.create_state(candidate_root, system_id_sha256)

    def create_broker(self, candidate_root: Path, system_id: str):
        return self.live.create_broker(candidate_root, system_id)

    def initialize_dynsec(self, candidate_root: Path, system_id: str):
        return self.live.initialize_dynsec(candidate_root, system_id)

    def stage_instance_runtime(self, candidate_root: Path, system_id: str):
        return self.live.stage_instance_runtime(candidate_root, system_id)

    def commit_instance_candidate(self, candidate_root: Path, system_id: str):
        return self.live.commit_instance_candidate(candidate_root, system_id)

    def instance_stopped_postcheck(self, system_id: str):
        return self.live.instance_stopped_postcheck(system_id)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n3w-t1-provision")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    start = subparsers.add_parser("start")
    start.add_argument("--confirm")
    start.add_argument("--production-phase-context", type=Path)
    subparsers.add_parser("resume-if-needed")
    subparsers.add_parser("verify")
    return parser


def _emit(document: dict[str, object], *, error: bool = False) -> None:
    destination = sys.stderr if error else sys.stdout
    destination.write(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    )


def _reconcile(firstboot: ModuleType, adapters: HostAdapters, release_id: str):
    observed = firstboot.inspect_device_provisioning(
        adapters,
        TRANSACTION_ROOT,
        CANDIDATE_ROOT,
        release_id=release_id,
    )
    state = observed.get("state")
    if state == "UNPROVISIONED":
        return {
            **observed,
            "boot_action": "NOOP",
            "production_service_start": False,
        }
    if state == "INITIALIZING":
        report = firstboot.resume_device_provisioning(
            adapters,
            TRANSACTION_ROOT,
            CANDIDATE_ROOT,
            release_id=release_id,
        )
        return {
            **report,
            "boot_action": "RESUME_EXISTING",
            "production_service_start": False,
        }
    if state == "DEVICE_READY":
        report = firstboot.verify_device_ready(
            adapters,
            TRANSACTION_ROOT,
            CANDIDATE_ROOT,
            release_id=release_id,
        )
        return {
            **report,
            "boot_action": "VERIFY_ONLY",
            "production_service_start": False,
        }
    raise ProvisionHostError(
        f"provisioning_state_conflict:{observed.get('error_code') or 'unknown'}"
    )


def main() -> int:
    args = _parser().parse_args()
    try:
        if os.geteuid() != 0:
            raise ProvisionHostError("root_required")
        release = _read_release()
        release_id = str(release["release_id"])
        firstboot = _load_module(
            FIRSTBOOT_TOOL_PATH,
            "n3w_installed_device_firstboot",
        )
        adapters = HostAdapters(release)

        if args.command == "status":
            report = firstboot.inspect_device_provisioning(
                adapters,
                TRANSACTION_ROOT,
                CANDIDATE_ROOT,
                release_id=release_id,
            )
        elif args.command == "start":
            report = _start_device_provisioning(
                firstboot,
                adapters,
                release,
                confirmation=args.confirm,
                production_phase_context=args.production_phase_context,
            )
        elif args.command == "resume-if-needed":
            report = _reconcile(firstboot, adapters, release_id)
        else:
            report = firstboot.verify_device_ready(
                adapters,
                TRANSACTION_ROOT,
                CANDIDATE_ROOT,
                release_id=release_id,
            )

        _emit(
            {
                **report,
                "schema": SCHEMA,
                "release_id": release_id,
                "production_service_start": False,
                "board_access": False,
            }
        )
        return 0
    except (
        ImportError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        claimed = bool(getattr(error, "production_claimed", False))
        _emit(
            {
                "schema": SCHEMA,
                "status": "FAIL",
                "error_code": str(error)[:400] or type(error).__name__,
                "authorization_consumed": True if claimed else None,
                "replay_allowed": False if claimed else None,
                "production_service_start": False,
                "board_access": False,
            },
            error=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
