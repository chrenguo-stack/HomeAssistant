#!/usr/bin/python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Iterator

SCHEMA = "gh.n3w-t1-f4-reboot-successor-postclaim-recovery/1"
PACKAGE_SCHEMA = "gh.n3w-t1-f4-reboot-successor-control-package/1"
STATE_ROOT = Path("/var/lib/n3w-t1-provisioning")
LOCK_PATH = STATE_ROOT / ".f4-reboot-successor-authority.lock"
INSTALL_CLAIM = STATE_ROOT / "F4_REBOOT_SUCCESSOR_INSTALL_AUTHORIZATION.json"
RECOVERY_CLAIM = STATE_ROOT / "F4_REBOOT_SUCCESSOR_RECOVERY_AUTHORIZATION.json"
REBOOT_CLAIM = STATE_ROOT / "F4_REBOOT_AUTHORIZATION.json"
F4_TRANSACTION = STATE_ROOT / "F4_ACTIVATION_TRANSACTION.json"
F4_HOST = Path("/usr/local/sbin/n3w-t1-f4-activation")
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
INSTALLED_MANIFEST = Path(
    "/usr/local/share/n3w-t1-f4-reboot-successor/reboot-successor-manifest.json"
)
RUNTIME_GUARD = Path("/usr/local/sbin/n3w-t1-f4-certificate-runtime-guard")
REBOOT_AUTHORITY = Path("/usr/local/sbin/n3w-t1-f4-reboot-authority")
REBOOT_VERIFY = Path("/usr/local/sbin/n3w-t1-f4-reboot-verify")
DROPIN = Path(
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service.d/"
    "10-runtime-status-evolution.conf"
)
TARGETS = {
    "tools/n3w_t1_f4_certificate_runtime_guard.py": (RUNTIME_GUARD, 0o755),
    "tools/n3w_t1_f4_reboot_authority.py": (REBOOT_AUTHORITY, 0o755),
    "tools/n3w_t1_f4_reboot_verify.py": (REBOOT_VERIFY, 0o755),
    (
        "infra/n3w-t1/f4/reboot-successor/"
        "n3wfc4-broker-certificate-lifecycle.service.d/"
        "10-runtime-status-evolution.conf"
    ): (DROPIN, 0o644),
}
GUARD_RELATIVE = "tools/n3w_t1_f4_certificate_runtime_guard.py"
AUTH_PATTERN = re.compile(r"^N3W_T1_F4_[A-Z0-9_]{8,160}$")
EXPECTED_SERVICES = {"broker", "manager", "homeassistant"}


class RecoveryError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha(document: object) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def read_record(path: Path, mode: int) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise RecoveryError(f"record_invalid:{path.name}")
    metadata = path.stat()
    if (
        metadata.st_uid != 0
        or metadata.st_gid != 0
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != mode
    ):
        raise RecoveryError(f"record_metadata_invalid:{path.name}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RecoveryError(f"record_json_invalid:{path.name}") from error
    if not isinstance(document, dict):
        raise RecoveryError(f"record_document_invalid:{path.name}")
    return document


def atomic_write_record(path: Path, document: dict[str, object]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, 0, 0)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(
                json.dumps(document, sort_keys=True, separators=(",", ":"))
                + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_replace_file(source: Path, target: Path, mode: int) -> None:
    if source.is_symlink() or not source.is_file():
        raise RecoveryError(f"repair_source_invalid:{source.name}")
    if target.is_symlink() or not target.is_file():
        raise RecoveryError(f"repair_target_invalid:{target.name}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        dir=str(target.parent),
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        os.fchown(descriptor, 0, 0)
        with source.open("rb") as input_stream, os.fdopen(
            descriptor,
            "wb",
        ) as output_stream:
            for block in iter(lambda: input_stream.read(1024 * 1024), b""):
                output_stream.write(block)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        os.replace(temporary, target)
        directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def exclusive() -> Iterator[None]:
    if STATE_ROOT.is_symlink() or not STATE_ROOT.is_dir():
        raise RecoveryError("state_root_invalid")
    metadata = STATE_ROOT.stat()
    if (
        metadata.st_uid != 0
        or metadata.st_gid != 0
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise RecoveryError("state_root_metadata_invalid")
    descriptor = os.open(LOCK_PATH, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, 0, 0)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def load_f4() -> ModuleType:
    if F4_HOST.is_symlink() or not F4_HOST.is_file():
        raise RecoveryError("f4_host_invalid")
    loader = importlib.machinery.SourceFileLoader(
        "n3w_f4_postclaim_recovery",
        str(F4_HOST),
    )
    specification = importlib.util.spec_from_loader(loader.name, loader)
    if specification is None:
        raise RecoveryError("f4_host_import_invalid")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    loader.exec_module(module)
    return module


def boot_id_sha256() -> str:
    value = BOOT_ID.read_text(encoding="ascii").strip().lower()
    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        value,
    ) is None:
        raise RecoveryError("boot_id_invalid")
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def systemctl(mode: str, unit: str) -> str:
    result = subprocess.run(
        ("systemctl", mode, unit),
        check=False,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=20,
    )
    return result.stdout.strip() or "unknown"


def run(argv: tuple[str, ...], timeout: float = 60.0) -> str:
    result = subprocess.run(
        argv,
        check=False,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip()
        raise RecoveryError(
            f"command_failed:{argv[0]}:{result.returncode}:{reason[:300]}"
        )
    return result.stdout


def authorization_ids(document: dict[str, object]) -> set[str]:
    observed: set[str] = set()
    for key, value in document.items():
        if key.endswith("_authorization_id") and isinstance(value, str):
            observed.add(value)
        if key.endswith("_authorization_history"):
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                raise RecoveryError(f"authorization_history_invalid:{key}")
            observed.update(value)
    return observed


def safe_package_file(root: Path, relative: str) -> Path:
    candidate = root / relative
    if candidate.is_symlink() or not candidate.is_file():
        raise RecoveryError(f"package_file_invalid:{relative}")
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise RecoveryError(f"package_path_escape:{relative}") from error
    return candidate


def package_contract(
    package_root: Path,
    *,
    source_head: str,
    manifest_sha256: str,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    root = package_root.resolve()
    if root.is_symlink() or not root.is_dir():
        raise RecoveryError("package_root_invalid")
    manifest_path = root / "reboot-successor-manifest.json"
    if (
        manifest_path.is_symlink()
        or not manifest_path.is_file()
        or sha256_file(manifest_path) != manifest_sha256
    ):
        raise RecoveryError("target_manifest_binding_invalid")
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        not isinstance(document, dict)
        or document.get("schema") != PACKAGE_SCHEMA
        or document.get("source_head") != source_head
        or document.get("secret_values_included") is not False
        or document.get("live_runtime_mutation") is not False
        or document.get("reboot_executed") is not False
        or document.get("board_access") is not False
    ):
        raise RecoveryError("target_manifest_contract_invalid")
    records = document.get("files")
    if not isinstance(records, list):
        raise RecoveryError("target_manifest_files_invalid")
    bindings: dict[str, dict[str, object]] = {}
    for item in records:
        if not isinstance(item, dict):
            raise RecoveryError("target_manifest_record_invalid")
        relative = item.get("path")
        if not isinstance(relative, str) or relative in bindings:
            raise RecoveryError("target_manifest_path_invalid")
        source = safe_package_file(root, relative)
        digest = sha256_file(source)
        size = source.stat().st_size
        if item.get("sha256") != digest or item.get("size") != size:
            raise RecoveryError(f"target_package_binding_invalid:{relative}")
        bindings[relative] = {"sha256": digest, "size": size}
    if set(bindings) != set(TARGETS):
        raise RecoveryError("target_manifest_file_set_invalid")
    return document, bindings


def installed_manifest_contract(
    *,
    source_head: str,
    manifest_sha256: str,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    document = read_record(INSTALLED_MANIFEST, 0o644)
    if (
        sha256_file(INSTALLED_MANIFEST) != manifest_sha256
        or document.get("schema") != PACKAGE_SCHEMA
        or document.get("source_head") != source_head
    ):
        raise RecoveryError("installed_manifest_binding_invalid")
    records = document.get("files")
    if not isinstance(records, list):
        raise RecoveryError("installed_manifest_files_invalid")
    bindings: dict[str, dict[str, object]] = {}
    for item in records:
        if not isinstance(item, dict):
            raise RecoveryError("installed_manifest_record_invalid")
        relative = item.get("path")
        if not isinstance(relative, str) or relative in bindings:
            raise RecoveryError("installed_manifest_path_invalid")
        bindings[relative] = item
    if set(bindings) != set(TARGETS):
        raise RecoveryError("installed_manifest_file_set_invalid")
    for relative, (target, mode) in TARGETS.items():
        item = bindings[relative]
        if target.is_symlink() or not target.is_file():
            raise RecoveryError(f"installed_target_invalid:{relative}")
        metadata = target.stat()
        if (
            metadata.st_uid != 0
            or metadata.st_gid != 0
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != mode
            or item.get("sha256") != sha256_file(target)
            or item.get("size") != metadata.st_size
        ):
            raise RecoveryError(f"installed_target_binding_invalid:{relative}")
    return document, bindings


def current_product_contract(
    *,
    expected_transaction_sha256: str,
    expected_runtime_snapshot_sha256: str,
    expected_certificate_snapshot_sha256: str,
    expected_boot_id_sha256: str,
) -> tuple[ModuleType, dict[str, object]]:
    if sha256_file(F4_TRANSACTION) != expected_transaction_sha256:
        raise RecoveryError("f4_transaction_sha256_mismatch")
    module = load_f4()
    verified = module._provision_verify()
    transaction = module._validate_transaction_binding(verified)
    module._validate_factory_binding(verified)
    module._verify_installed_material(transaction)
    module._validate_runtime_acceptance_binding(transaction)
    module._validate_tls_material()
    module._verified_tls_runtime()
    status = module._status()
    if (
        status.get("status") != "PASS"
        or status.get("production_service_start") is not True
        or set(status.get("running_services") or []) != EXPECTED_SERVICES
        or status.get("board_access") is not False
    ):
        raise RecoveryError("current_product_runtime_invalid")
    if canonical_sha(module._runtime_container_snapshot()) != expected_runtime_snapshot_sha256:
        raise RecoveryError("runtime_snapshot_drift")
    if canonical_sha(module._certificate_identity_snapshot()) != expected_certificate_snapshot_sha256:
        raise RecoveryError("certificate_snapshot_drift")
    if boot_id_sha256() != expected_boot_id_sha256:
        raise RecoveryError("boot_id_drift")
    if (
        systemctl("is-active", module.BROKER_UNIT) != "active"
        or systemctl("is-active", module.SERVICES_UNIT) != "active"
        or systemctl("is-enabled", module.CERT_TIMER) != "enabled"
        or systemctl("is-active", module.CERT_TIMER) != "inactive"
        or systemctl("is-active", module.CERT_SERVICE) != "inactive"
    ):
        raise RecoveryError("current_unit_contract_invalid")
    if REBOOT_CLAIM.exists() or REBOOT_CLAIM.is_symlink():
        raise RecoveryError("reboot_claim_present")
    return module, transaction


def old_control_applying_contract(
    *,
    old_source_head: str,
    old_manifest_sha256: str,
    old_claim_sha256: str,
    expected_transaction_sha256: str,
    expected_runtime_snapshot_sha256: str,
    expected_certificate_snapshot_sha256: str,
    expected_boot_id_sha256: str,
) -> tuple[ModuleType, dict[str, object], dict[str, object], dict[str, dict[str, object]]]:
    if sha256_file(INSTALL_CLAIM) != old_claim_sha256:
        raise RecoveryError("old_install_claim_sha256_mismatch")
    claim = read_record(INSTALL_CLAIM, 0o600)
    if (
        claim.get("schema")
        != "gh.n3w-t1-f4-reboot-successor-install-authorization/1"
        or claim.get("stage") != "CONTROL_APPLYING"
        or claim.get("source_head") != old_source_head
        or claim.get("control_manifest_sha256") != old_manifest_sha256
        or claim.get("f4_transaction_sha256") != expected_transaction_sha256
        or claim.get("control_repair_authorization_claimed") is not True
        or claim.get("control_repair_authorization_consumed") is not True
        or claim.get("control_repair_authorization_replay_allowed") is not False
        or claim.get("installation_apply_started") is not True
        or claim.get("installation_verified") is True
        or claim.get("pre_runtime_snapshot_sha256")
        != expected_runtime_snapshot_sha256
        or claim.get("pre_certificate_snapshot_sha256")
        != expected_certificate_snapshot_sha256
        or claim.get("board_access") is not False
    ):
        raise RecoveryError("old_install_claim_contract_invalid")
    _manifest, old_bindings = installed_manifest_contract(
        source_head=old_source_head,
        manifest_sha256=old_manifest_sha256,
    )
    module, transaction = current_product_contract(
        expected_transaction_sha256=expected_transaction_sha256,
        expected_runtime_snapshot_sha256=expected_runtime_snapshot_sha256,
        expected_certificate_snapshot_sha256=expected_certificate_snapshot_sha256,
        expected_boot_id_sha256=expected_boot_id_sha256,
    )
    dropins = run(
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
        raise RecoveryError("successor_dropin_not_loaded")
    return module, transaction, claim, old_bindings


def repair_delta_contract(
    *,
    package_root: Path,
    target_source_head: str,
    target_manifest_sha256: str,
    old_bindings: dict[str, dict[str, object]],
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    target_manifest, target_bindings = package_contract(
        package_root,
        source_head=target_source_head,
        manifest_sha256=target_manifest_sha256,
    )
    changed = {
        relative
        for relative in TARGETS
        if target_bindings[relative]["sha256"]
        != old_bindings[relative]["sha256"]
    }
    if changed != {GUARD_RELATIVE}:
        raise RecoveryError(
            "unexpected_repair_delta:" + ",".join(sorted(changed))
        )
    return target_manifest, target_bindings


def recovery_preflight(
    *,
    package_root: Path,
    old_source_head: str,
    old_manifest_sha256: str,
    old_claim_sha256: str,
    target_source_head: str,
    target_manifest_sha256: str,
    expected_transaction_sha256: str,
    expected_runtime_snapshot_sha256: str,
    expected_certificate_snapshot_sha256: str,
    expected_boot_id_sha256: str,
) -> dict[str, object]:
    _module, _transaction, _claim, old_bindings = old_control_applying_contract(
        old_source_head=old_source_head,
        old_manifest_sha256=old_manifest_sha256,
        old_claim_sha256=old_claim_sha256,
        expected_transaction_sha256=expected_transaction_sha256,
        expected_runtime_snapshot_sha256=expected_runtime_snapshot_sha256,
        expected_certificate_snapshot_sha256=expected_certificate_snapshot_sha256,
        expected_boot_id_sha256=expected_boot_id_sha256,
    )
    _target_manifest, target_bindings = repair_delta_contract(
        package_root=package_root,
        target_source_head=target_source_head,
        target_manifest_sha256=target_manifest_sha256,
        old_bindings=old_bindings,
    )
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "state": "RECOVERY_ELIGIBLE",
        "old_claim_sha256": old_claim_sha256,
        "old_source_head": old_source_head,
        "old_manifest_sha256": old_manifest_sha256,
        "target_source_head": target_source_head,
        "target_manifest_sha256": target_manifest_sha256,
        "repair_file": GUARD_RELATIVE,
        "old_guard_sha256": old_bindings[GUARD_RELATIVE]["sha256"],
        "target_guard_sha256": target_bindings[GUARD_RELATIVE]["sha256"],
        "live_runtime_mutation": False,
        "reboot_executed": False,
        "board_access": False,
    }


def claim_recovery(
    *,
    package_root: Path,
    authorization_id: str,
    old_source_head: str,
    old_manifest_sha256: str,
    old_claim_sha256: str,
    target_source_head: str,
    target_manifest_sha256: str,
    expected_transaction_sha256: str,
    expected_runtime_snapshot_sha256: str,
    expected_certificate_snapshot_sha256: str,
    expected_boot_id_sha256: str,
) -> dict[str, object]:
    with exclusive():
        if RECOVERY_CLAIM.exists() or RECOVERY_CLAIM.is_symlink():
            raise RecoveryError("recovery_claim_preexisting")
        if AUTH_PATTERN.fullmatch(authorization_id) is None:
            raise RecoveryError("recovery_authorization_id_invalid")
        module, transaction, install_claim, old_bindings = old_control_applying_contract(
            old_source_head=old_source_head,
            old_manifest_sha256=old_manifest_sha256,
            old_claim_sha256=old_claim_sha256,
            expected_transaction_sha256=expected_transaction_sha256,
            expected_runtime_snapshot_sha256=expected_runtime_snapshot_sha256,
            expected_certificate_snapshot_sha256=expected_certificate_snapshot_sha256,
            expected_boot_id_sha256=expected_boot_id_sha256,
        )
        _target_manifest, target_bindings = repair_delta_contract(
            package_root=package_root,
            target_source_head=target_source_head,
            target_manifest_sha256=target_manifest_sha256,
            old_bindings=old_bindings,
        )
        used = authorization_ids(transaction) | authorization_ids(install_claim)
        if authorization_id in used:
            raise RecoveryError("recovery_authorization_replay_forbidden")
        document = {
            "schema": SCHEMA,
            "stage": "RECOVERY_CLAIMED",
            "recovery_authorization_id": authorization_id,
            "recovery_authorization_claimed": True,
            "recovery_authorization_consumed": True,
            "recovery_authorization_replay_allowed": False,
            "old_install_claim_sha256": old_claim_sha256,
            "old_source_head": old_source_head,
            "old_manifest_sha256": old_manifest_sha256,
            "target_source_head": target_source_head,
            "target_manifest_sha256": target_manifest_sha256,
            "expected_transaction_sha256": expected_transaction_sha256,
            "pre_runtime_snapshot_sha256": canonical_sha(
                module._runtime_container_snapshot()
            ),
            "pre_certificate_snapshot_sha256": canonical_sha(
                module._certificate_identity_snapshot()
            ),
            "pre_boot_id_sha256": boot_id_sha256(),
            "old_guard_sha256": old_bindings[GUARD_RELATIVE]["sha256"],
            "target_guard_sha256": target_bindings[GUARD_RELATIVE]["sha256"],
            "repair_file": GUARD_RELATIVE,
            "live_runtime_mutation": False,
            "reboot_executed": False,
            "board_access": False,
        }
        atomic_write_record(RECOVERY_CLAIM, document)
        if read_record(RECOVERY_CLAIM, 0o600) != document:
            raise RecoveryError("recovery_claim_persistence_mismatch")
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "state": "RECOVERY_CLAIMED",
            "recovery_authorization_claimed": True,
            "recovery_authorization_consumed": True,
            "recovery_authorization_replay_allowed": False,
            "claim_sha256": sha256_file(RECOVERY_CLAIM),
            "live_runtime_mutation": False,
            "reboot_executed": False,
            "board_access": False,
        }


def recovery_claim_contract(
    *,
    authorization_id: str,
    old_source_head: str,
    old_manifest_sha256: str,
    old_claim_sha256: str,
    target_source_head: str,
    target_manifest_sha256: str,
    expected_transaction_sha256: str,
    expected_runtime_snapshot_sha256: str,
    expected_certificate_snapshot_sha256: str,
    expected_boot_id_sha256: str,
    allowed_stage: str,
) -> dict[str, object]:
    document = read_record(RECOVERY_CLAIM, 0o600)
    required = {
        "schema": SCHEMA,
        "stage": allowed_stage,
        "recovery_authorization_id": authorization_id,
        "recovery_authorization_claimed": True,
        "recovery_authorization_consumed": True,
        "recovery_authorization_replay_allowed": False,
        "old_install_claim_sha256": old_claim_sha256,
        "old_source_head": old_source_head,
        "old_manifest_sha256": old_manifest_sha256,
        "target_source_head": target_source_head,
        "target_manifest_sha256": target_manifest_sha256,
        "expected_transaction_sha256": expected_transaction_sha256,
        "pre_runtime_snapshot_sha256": expected_runtime_snapshot_sha256,
        "pre_certificate_snapshot_sha256": expected_certificate_snapshot_sha256,
        "pre_boot_id_sha256": expected_boot_id_sha256,
        "repair_file": GUARD_RELATIVE,
        "reboot_executed": False,
        "board_access": False,
    }
    for key, value in required.items():
        if document.get(key) != value:
            raise RecoveryError(f"recovery_claim_field_invalid:{key}")
    return document


def apply_recovery(
    *,
    package_root: Path,
    authorization_id: str,
    old_source_head: str,
    old_manifest_sha256: str,
    old_claim_sha256: str,
    target_source_head: str,
    target_manifest_sha256: str,
    expected_transaction_sha256: str,
    expected_runtime_snapshot_sha256: str,
    expected_certificate_snapshot_sha256: str,
    expected_boot_id_sha256: str,
) -> dict[str, object]:
    with exclusive():
        recovery = recovery_claim_contract(
            authorization_id=authorization_id,
            old_source_head=old_source_head,
            old_manifest_sha256=old_manifest_sha256,
            old_claim_sha256=old_claim_sha256,
            target_source_head=target_source_head,
            target_manifest_sha256=target_manifest_sha256,
            expected_transaction_sha256=expected_transaction_sha256,
            expected_runtime_snapshot_sha256=expected_runtime_snapshot_sha256,
            expected_certificate_snapshot_sha256=expected_certificate_snapshot_sha256,
            expected_boot_id_sha256=expected_boot_id_sha256,
            allowed_stage="RECOVERY_CLAIMED",
        )
        module, _transaction, install_claim, old_bindings = old_control_applying_contract(
            old_source_head=old_source_head,
            old_manifest_sha256=old_manifest_sha256,
            old_claim_sha256=old_claim_sha256,
            expected_transaction_sha256=expected_transaction_sha256,
            expected_runtime_snapshot_sha256=expected_runtime_snapshot_sha256,
            expected_certificate_snapshot_sha256=expected_certificate_snapshot_sha256,
            expected_boot_id_sha256=expected_boot_id_sha256,
        )
        _target_manifest, target_bindings = repair_delta_contract(
            package_root=package_root,
            target_source_head=target_source_head,
            target_manifest_sha256=target_manifest_sha256,
            old_bindings=old_bindings,
        )
        applying = dict(recovery)
        applying.update(
            {
                "stage": "RECOVERY_APPLYING",
                "recovery_apply_started": True,
            }
        )
        atomic_write_record(RECOVERY_CLAIM, applying)

        target_guard = safe_package_file(package_root.resolve(), GUARD_RELATIVE)
        atomic_replace_file(target_guard, RUNTIME_GUARD, 0o755)
        atomic_replace_file(
            package_root.resolve() / "reboot-successor-manifest.json",
            INSTALLED_MANIFEST,
            0o644,
        )

        guard_report = json.loads(run((str(RUNTIME_GUARD), "check"), timeout=60))
        if guard_report.get("status") != "PASS":
            raise RecoveryError("repaired_guard_not_pass")

        ready = dict(install_claim)
        ready.update(
            {
                "recovery_original_source_head": old_source_head,
                "recovery_original_control_manifest_sha256": old_manifest_sha256,
                "recovery_original_claim_sha256": old_claim_sha256,
                "postclaim_recovery_authorization_id": authorization_id,
                "postclaim_recovery_authorization_claimed": True,
                "postclaim_recovery_authorization_consumed": True,
                "postclaim_recovery_authorization_replay_allowed": False,
                "postclaim_recovery_applied": True,
                "source_head": target_source_head,
                "control_manifest_sha256": target_manifest_sha256,
                "files": {
                    relative: {
                        "sha256": target_bindings[relative]["sha256"],
                        "size": target_bindings[relative]["size"],
                        "target": str(TARGETS[relative][0]),
                        "mode": TARGETS[relative][1],
                    }
                    for relative in TARGETS
                },
                "stage": "CONTROL_READY",
                "installation_verified": True,
            }
        )
        atomic_write_record(INSTALL_CLAIM, ready)

        verify_report = json.loads(
            run(
                (
                    str(REBOOT_AUTHORITY),
                    "verify-install",
                    "--source-head",
                    target_source_head,
                    "--manifest-sha256",
                    target_manifest_sha256,
                    "--expected-transaction-sha256",
                    expected_transaction_sha256,
                ),
                timeout=120,
            )
        )
        if (
            verify_report.get("status") != "PASS"
            or verify_report.get("state") != "CONTROL_READY"
        ):
            raise RecoveryError("recovered_control_verify_not_pass")

        current_product_contract(
            expected_transaction_sha256=expected_transaction_sha256,
            expected_runtime_snapshot_sha256=expected_runtime_snapshot_sha256,
            expected_certificate_snapshot_sha256=expected_certificate_snapshot_sha256,
            expected_boot_id_sha256=expected_boot_id_sha256,
        )

        verified = dict(applying)
        verified.update(
            {
                "stage": "RECOVERY_VERIFIED",
                "recovery_verified": True,
                "target_install_claim_sha256": sha256_file(INSTALL_CLAIM),
                "target_guard_sha256": sha256_file(RUNTIME_GUARD),
                "target_manifest_sha256": sha256_file(INSTALLED_MANIFEST),
            }
        )
        atomic_write_record(RECOVERY_CLAIM, verified)
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "state": "RECOVERY_VERIFIED",
            "recovery_authorization_claimed": True,
            "recovery_authorization_consumed": True,
            "recovery_authorization_replay_allowed": False,
            "installation_state": "CONTROL_READY",
            "install_claim_sha256": sha256_file(INSTALL_CLAIM),
            "recovery_claim_sha256": sha256_file(RECOVERY_CLAIM),
            "guard_sha256": sha256_file(RUNTIME_GUARD),
            "manifest_sha256": sha256_file(INSTALLED_MANIFEST),
            "live_runtime_mutation": True,
            "reboot_executed": False,
            "board_access": False,
        }


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--old-source-head", required=True)
    parser.add_argument("--old-manifest-sha256", required=True)
    parser.add_argument("--old-claim-sha256", required=True)
    parser.add_argument("--target-source-head", required=True)
    parser.add_argument("--target-manifest-sha256", required=True)
    parser.add_argument("--expected-transaction-sha256", required=True)
    parser.add_argument("--expected-runtime-snapshot-sha256", required=True)
    parser.add_argument("--expected-certificate-snapshot-sha256", required=True)
    parser.add_argument("--expected-boot-id-sha256", required=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser("preflight")
    _common(preflight)
    claim = sub.add_parser("claim-recovery")
    claim.add_argument("--authorization-id", required=True)
    _common(claim)
    apply = sub.add_parser("apply-recovery")
    apply.add_argument("--authorization-id", required=True)
    _common(apply)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    kwargs = {
        "package_root": args.package_root,
        "old_source_head": args.old_source_head,
        "old_manifest_sha256": args.old_manifest_sha256,
        "old_claim_sha256": args.old_claim_sha256,
        "target_source_head": args.target_source_head,
        "target_manifest_sha256": args.target_manifest_sha256,
        "expected_transaction_sha256": args.expected_transaction_sha256,
        "expected_runtime_snapshot_sha256": args.expected_runtime_snapshot_sha256,
        "expected_certificate_snapshot_sha256": args.expected_certificate_snapshot_sha256,
        "expected_boot_id_sha256": args.expected_boot_id_sha256,
    }
    try:
        if args.command == "preflight":
            document = recovery_preflight(**kwargs)
        elif args.command == "claim-recovery":
            document = claim_recovery(
                authorization_id=args.authorization_id,
                **kwargs,
            )
        else:
            document = apply_recovery(
                authorization_id=args.authorization_id,
                **kwargs,
            )
    except (
        ImportError,
        json.JSONDecodeError,
        KeyError,
        OSError,
        RecoveryError,
        RuntimeError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "FAIL",
                    "error_code": str(error)[:300],
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
