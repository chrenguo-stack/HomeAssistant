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
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from types import ModuleType

SCHEMA_INSTALL = "gh.n3w-t1-f4-reboot-successor-install-authorization/1"
SCHEMA_REBOOT = "gh.n3w-t1-f4-reboot-authorization/1"
PACKAGE_SCHEMA = "gh.n3w-t1-f4-reboot-successor-control-package/1"
MANIFEST_NAME = "reboot-successor-manifest.json"

STATE_ROOT = Path("/var/lib/n3w-t1-provisioning")
LOCK_PATH = STATE_ROOT / ".f4-reboot-successor-authority.lock"
INSTALL_CLAIM_PATH = STATE_ROOT / "F4_REBOOT_SUCCESSOR_INSTALL_AUTHORIZATION.json"
REBOOT_CLAIM_PATH = STATE_ROOT / "F4_REBOOT_AUTHORIZATION.json"
F4_TRANSACTION = STATE_ROOT / "F4_ACTIVATION_TRANSACTION.json"

F4_HOST = Path("/usr/local/sbin/n3w-t1-f4-activation")
RUNTIME_GUARD = Path("/usr/local/sbin/n3w-t1-f4-certificate-runtime-guard")
REBOOT_AUTHORITY = Path("/usr/local/sbin/n3w-t1-f4-reboot-authority")
REBOOT_VERIFY = Path("/usr/local/sbin/n3w-t1-f4-reboot-verify")
CONTROL_MANIFEST = Path(
    "/usr/local/share/n3w-t1-f4-reboot-successor/reboot-successor-manifest.json"
)
DROPIN = Path(
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service.d/"
    "10-runtime-status-evolution.conf"
)
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")

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
AUTH_PATTERN = re.compile(r"^N3W_T1_F4_[A-Z0-9_]{8,160}$")
EXPECTED_SERVICES = {"broker", "manager", "homeassistant"}


class AuthorityError(RuntimeError):
    pass


@contextmanager
def _exclusive() -> Iterator[None]:
    if STATE_ROOT.is_symlink() or not STATE_ROOT.is_dir():
        raise AuthorityError("state_root_invalid")
    metadata = STATE_ROOT.stat()
    if (
        metadata.st_uid != 0
        or metadata.st_gid != 0
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise AuthorityError("state_root_metadata_invalid")
    descriptor = os.open(LOCK_PATH, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, 0, 0)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _atomic_write_record(
    path: Path,
    document: dict[str, object],
) -> None:
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise AuthorityError("record_parent_invalid")
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


def _install_exact_file(source: Path, target: Path, mode: int) -> None:
    if source.is_symlink() or not source.is_file():
        raise AuthorityError(f"install_source_invalid:{source.name}")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    if target.parent.is_symlink() or not target.parent.is_dir():
        raise AuthorityError(f"install_parent_invalid:{target.name}")
    if target.exists() or target.is_symlink():
        raise AuthorityError(f"install_target_preexisting:{target.name}")
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
            while True:
                block = input_stream.read(1024 * 1024)
                if not block:
                    break
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


def _record(path: Path, mode: int) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise AuthorityError(f"record_invalid:{path.name}")
    metadata = path.stat()
    if (
        metadata.st_uid != 0
        or metadata.st_gid != 0
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != mode
    ):
        raise AuthorityError(f"record_metadata_invalid:{path.name}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AuthorityError(f"record_json_invalid:{path.name}") from error
    if not isinstance(document, dict):
        raise AuthorityError(f"record_document_invalid:{path.name}")
    return document


def _load_f4() -> ModuleType:
    if F4_HOST.is_symlink() or not F4_HOST.is_file():
        raise AuthorityError("f4_host_invalid")
    loader = importlib.machinery.SourceFileLoader(
        "n3w_f4_reboot_authority",
        str(F4_HOST),
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise AuthorityError("f4_host_import_invalid")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


def _boot_id_sha256() -> str:
    if BOOT_ID.is_symlink() or not BOOT_ID.is_file():
        raise AuthorityError("boot_id_invalid")
    value = BOOT_ID.read_text(encoding="ascii").strip().lower()
    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        value,
    ) is None:
        raise AuthorityError("boot_id_invalid")
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _systemctl(mode: str, unit: str) -> str:
    result = subprocess.run(
        ("systemctl", mode, unit),
        check=False,
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=20,
    )
    return result.stdout.strip() or "unknown"


def _run(argv: Sequence[str], timeout: float = 60.0) -> str:
    result = subprocess.run(
        tuple(argv),
        check=False,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip()
        raise AuthorityError(
            f"command_failed:{argv[0]}:{result.returncode}:{reason[:300]}"
        )
    return result.stdout


def _prior_authorizations(transaction: dict[str, object]) -> set[str]:
    result: set[str] = set()
    for key, value in transaction.items():
        if key.endswith("_authorization_id") and isinstance(value, str):
            result.add(value)
        if key.endswith("_authorization_history"):
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                raise AuthorityError(f"authorization_history_invalid:{key}")
            result.update(value)
    return result


def _fresh_authorization(
    authorization_id: str,
    *,
    f4_transaction: dict[str, object],
    additional: set[str] = frozenset(),
) -> None:
    if AUTH_PATTERN.fullmatch(authorization_id) is None:
        raise AuthorityError("authorization_id_invalid")
    if authorization_id in _prior_authorizations(f4_transaction) | set(additional):
        raise AuthorityError("authorization_replay_forbidden")


def _base_pre_reboot(
    expected_transaction_sha256: str,
) -> tuple[ModuleType, dict[str, object]]:
    if re.fullmatch(r"[0-9a-f]{64}", expected_transaction_sha256) is None:
        raise AuthorityError("transaction_sha256_invalid")
    if _sha256(F4_TRANSACTION) != expected_transaction_sha256:
        raise AuthorityError("f4_transaction_sha256_mismatch")
    transaction = _record(F4_TRANSACTION, 0o600)
    if (
        transaction.get("stage") != "PERSISTENCE_ENABLED"
        or transaction.get("runtime_acceptance_passed") is not True
        or transaction.get("persistence_enabled") is not True
        or transaction.get("broker_services_persistence_enabled") is not True
        or transaction.get("certificate_first_audit_passed") is not True
        or transaction.get("certificate_timer_enabled") is not True
        or transaction.get("certificate_timer_active_before_reboot") is not False
        or transaction.get("pre_reboot_ready") is not True
    ):
        raise AuthorityError("f4_transaction_not_pre_reboot")

    module = _load_f4()
    status = module._status()
    if (
        status.get("status") != "PASS"
        or status.get("transaction_stage") != "PERSISTENCE_ENABLED"
        or status.get("production_service_start") is not True
        or set(status.get("running_services") or []) != EXPECTED_SERVICES
        or status.get("board_access") is not False
    ):
        raise AuthorityError("f4_runtime_not_pre_reboot")
    verified = module._provision_verify()
    module._validate_factory_binding(verified)
    module._verify_installed_material(transaction)
    module._validate_runtime_acceptance_binding(transaction)
    if (
        _systemctl("is-enabled", module.GUARD_UNIT) != "enabled"
        or _systemctl("is-enabled", module.PROVISION_UNIT) != "enabled"
        or _systemctl("is-enabled", module.BROKER_UNIT) != "enabled"
        or _systemctl("is-enabled", module.SERVICES_UNIT) != "enabled"
        or _systemctl("is-enabled", module.CERT_TIMER) != "enabled"
        or _systemctl("is-active", module.CERT_TIMER) != "inactive"
        or _systemctl("is-active", module.CERT_SERVICE) != "inactive"
    ):
        raise AuthorityError("pre_reboot_unit_contract_invalid")
    return module, transaction


def _safe_package_file(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if (
        pure.is_absolute()
        or not pure.parts
        or any(part in {"", ".", ".."} for part in pure.parts)
        or pure.as_posix() != relative
    ):
        raise AuthorityError("package_path_invalid")
    current = root
    for part in pure.parts:
        current /= part
        if current.is_symlink():
            raise AuthorityError(f"package_symlink:{relative}")
    if not current.is_file():
        raise AuthorityError(f"package_file_missing:{relative}")
    return current


def _package(
    package_root: Path,
    *,
    source_head: str,
    manifest_sha256: str,
) -> dict[str, object]:
    root = Path(os.path.abspath(os.fspath(package_root)))
    if root.is_symlink() or not root.is_dir():
        raise AuthorityError("package_root_invalid")
    if re.fullmatch(r"[0-9a-f]{40}", source_head) is None:
        raise AuthorityError("source_head_invalid")
    if re.fullmatch(r"[0-9a-f]{64}", manifest_sha256) is None:
        raise AuthorityError("manifest_sha256_invalid")
    manifest_path = root / MANIFEST_NAME
    if (
        manifest_path.is_symlink()
        or not manifest_path.is_file()
        or _sha256(manifest_path) != manifest_sha256
    ):
        raise AuthorityError("manifest_binding_invalid")
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AuthorityError("manifest_json_invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("schema") != PACKAGE_SCHEMA
        or document.get("source_head") != source_head
        or document.get("secret_values_included") is not False
        or document.get("live_runtime_mutation") is not False
        or document.get("reboot_executed") is not False
        or document.get("board_access") is not False
    ):
        raise AuthorityError("manifest_contract_invalid")

    records = document.get("files")
    if not isinstance(records, list):
        raise AuthorityError("manifest_files_invalid")
    observed: dict[str, dict[str, object]] = {}
    for item in records:
        if not isinstance(item, dict):
            raise AuthorityError("manifest_file_record_invalid")
        relative = item.get("path")
        if not isinstance(relative, str) or relative in observed:
            raise AuthorityError("manifest_file_path_invalid")
        source = _safe_package_file(root, relative)
        binding = {"sha256": _sha256(source), "size": source.stat().st_size}
        if (
            item.get("sha256") != binding["sha256"]
            or item.get("size") != binding["size"]
        ):
            raise AuthorityError(f"manifest_file_binding_invalid:{relative}")
        observed[relative] = binding
    if set(observed) != set(CONTROL_TARGETS):
        raise AuthorityError("manifest_file_set_invalid")
    return {
        "root": root,
        "manifest": document,
        "manifest_sha256": manifest_sha256,
        "source_head": source_head,
        "files": observed,
    }


def install_claim_payload(
    *,
    package_root: Path,
    source_head: str,
    manifest_sha256: str,
    authorization_id: str,
    expected_transaction_sha256: str,
) -> dict[str, object]:
    if INSTALL_CLAIM_PATH.exists() or INSTALL_CLAIM_PATH.is_symlink():
        raise AuthorityError("install_claim_preexisting")
    package = _package(
        package_root,
        source_head=source_head,
        manifest_sha256=manifest_sha256,
    )
    module, transaction = _base_pre_reboot(expected_transaction_sha256)
    _fresh_authorization(
        authorization_id,
        f4_transaction=transaction,
    )
    return {
        "schema": SCHEMA_INSTALL,
        "stage": "INSTALL_CLAIMED",
        "source_head": source_head,
        "control_manifest_sha256": manifest_sha256,
        "f4_transaction_sha256": expected_transaction_sha256,
        "pre_runtime_snapshot_sha256": _canonical_sha(
            module._runtime_container_snapshot()
        ),
        "pre_certificate_snapshot_sha256": _canonical_sha(
            module._certificate_identity_snapshot()
        ),
        "control_repair_authorization_id": authorization_id,
        "control_repair_authorization_claimed": True,
        "control_repair_authorization_consumed": True,
        "control_repair_authorization_replay_allowed": False,
        "files": {
            relative: {
                "sha256": package["files"][relative]["sha256"],
                "size": package["files"][relative]["size"],
                "target": str(CONTROL_TARGETS[relative][0]),
                "mode": CONTROL_TARGETS[relative][1],
            }
            for relative in CONTROL_TARGETS
        },
        "live_runtime_mutation": False,
        "reboot_executed": False,
        "board_access": False,
    }


def claim_install(
    *,
    package_root: Path,
    source_head: str,
    manifest_sha256: str,
    authorization_id: str,
    expected_transaction_sha256: str,
) -> dict[str, object]:
    with _exclusive():
        payload = install_claim_payload(
            package_root=package_root,
            source_head=source_head,
            manifest_sha256=manifest_sha256,
            authorization_id=authorization_id,
            expected_transaction_sha256=expected_transaction_sha256,
        )
        _atomic_write_record(INSTALL_CLAIM_PATH, payload)
        persisted = _record(INSTALL_CLAIM_PATH, 0o600)
        if persisted != payload:
            raise AuthorityError("install_claim_persistence_mismatch")
        return {
            "schema": SCHEMA_INSTALL,
            "status": "PASS",
            "state": "INSTALL_CLAIMED",
            "control_repair_authorization_claimed": True,
            "control_repair_authorization_consumed": True,
            "control_repair_authorization_replay_allowed": False,
            "claim_sha256": _sha256(INSTALL_CLAIM_PATH),
            "live_runtime_mutation": False,
            "reboot_executed": False,
            "board_access": False,
        }


def _verify_installed_control(
    *,
    source_head: str,
    manifest_sha256: str,
    expected_transaction_sha256: str,
    allowed_stages: frozenset[str] = frozenset({"CONTROL_READY"}),
) -> tuple[ModuleType, dict[str, object], dict[str, object]]:
    claim = _record(INSTALL_CLAIM_PATH, 0o600)
    if (
        claim.get("schema") != SCHEMA_INSTALL
        or claim.get("stage") not in allowed_stages
        or claim.get("source_head") != source_head
        or claim.get("control_manifest_sha256") != manifest_sha256
        or claim.get("f4_transaction_sha256") != expected_transaction_sha256
        or claim.get("control_repair_authorization_claimed") is not True
        or claim.get("control_repair_authorization_consumed") is not True
        or claim.get("control_repair_authorization_replay_allowed") is not False
        or claim.get("board_access") is not False
    ):
        raise AuthorityError("install_claim_contract_invalid")

    manifest = _record(CONTROL_MANIFEST, 0o644)
    if (
        _sha256(CONTROL_MANIFEST) != manifest_sha256
        or manifest.get("schema") != PACKAGE_SCHEMA
        or manifest.get("source_head") != source_head
    ):
        raise AuthorityError("installed_manifest_invalid")
    bindings = claim.get("files")
    if not isinstance(bindings, dict) or set(bindings) != set(CONTROL_TARGETS):
        raise AuthorityError("install_claim_file_set_invalid")
    for relative, (target, mode) in CONTROL_TARGETS.items():
        binding = bindings.get(relative)
        if not isinstance(binding, dict):
            raise AuthorityError(f"installed_binding_invalid:{relative}")
        if target.is_symlink() or not target.is_file():
            raise AuthorityError(f"installed_target_missing:{relative}")
        metadata = target.stat()
        if (
            metadata.st_uid != 0
            or metadata.st_gid != 0
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != mode
            or binding.get("target") != str(target)
            or binding.get("mode") != mode
            or binding.get("sha256") != _sha256(target)
            or binding.get("size") != metadata.st_size
        ):
            raise AuthorityError(f"installed_target_binding_invalid:{relative}")

    module, transaction = _base_pre_reboot(expected_transaction_sha256)
    if (
        _canonical_sha(module._runtime_container_snapshot())
        != claim.get("pre_runtime_snapshot_sha256")
        or _canonical_sha(module._certificate_identity_snapshot())
        != claim.get("pre_certificate_snapshot_sha256")
    ):
        raise AuthorityError("runtime_or_certificate_changed_during_install")

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
        raise AuthorityError("runtime_guard_dropin_not_loaded")
    guard = json.loads(_run((str(RUNTIME_GUARD), "check"), timeout=60))
    if guard.get("status") != "PASS":
        raise AuthorityError("runtime_guard_not_pass")
    return module, transaction, claim


def install_control(
    *,
    package_root: Path,
    source_head: str,
    manifest_sha256: str,
    expected_transaction_sha256: str,
) -> dict[str, object]:
    with _exclusive():
        claim = _record(INSTALL_CLAIM_PATH, 0o600)
        if (
            claim.get("schema") != SCHEMA_INSTALL
            or claim.get("stage") != "INSTALL_CLAIMED"
            or claim.get("source_head") != source_head
            or claim.get("control_manifest_sha256") != manifest_sha256
            or claim.get("f4_transaction_sha256")
            != expected_transaction_sha256
            or claim.get("control_repair_authorization_claimed") is not True
            or claim.get("control_repair_authorization_consumed") is not True
            or claim.get("control_repair_authorization_replay_allowed") is not False
        ):
            raise AuthorityError("install_control_prestate_invalid")
        package = _package(
            package_root,
            source_head=source_head,
            manifest_sha256=manifest_sha256,
        )
        module, transaction = _base_pre_reboot(expected_transaction_sha256)
        if (
            _canonical_sha(module._runtime_container_snapshot())
            != claim.get("pre_runtime_snapshot_sha256")
            or _canonical_sha(module._certificate_identity_snapshot())
            != claim.get("pre_certificate_snapshot_sha256")
        ):
            raise AuthorityError("install_control_prestate_drift")
        for _relative, (target, _mode) in CONTROL_TARGETS.items():
            if target.exists() or target.is_symlink():
                raise AuthorityError(f"install_target_preexisting:{target.name}")
        if CONTROL_MANIFEST.exists() or CONTROL_MANIFEST.is_symlink():
            raise AuthorityError("installed_manifest_preexisting")
        applying = dict(claim)
        applying.update(
            {
                "stage": "CONTROL_APPLYING",
                "installation_apply_started": True,
            }
        )
        _atomic_write_record(INSTALL_CLAIM_PATH, applying)

        for relative, (target, mode) in CONTROL_TARGETS.items():
            _install_exact_file(
                package["root"] / relative,
                target,
                mode,
            )
        _install_exact_file(
            package["root"] / MANIFEST_NAME,
            CONTROL_MANIFEST,
            0o644,
        )
        _run(("systemctl", "daemon-reload"), timeout=30)

        _verify_installed_control(
            source_head=source_head,
            manifest_sha256=manifest_sha256,
            expected_transaction_sha256=expected_transaction_sha256,
            allowed_stages=frozenset({"CONTROL_APPLYING"}),
        )
        ready = _record(INSTALL_CLAIM_PATH, 0o600)
        ready.update(
            {
                "stage": "CONTROL_READY",
                "installation_verified": True,
            }
        )
        _atomic_write_record(INSTALL_CLAIM_PATH, ready)
        return {
            "schema": SCHEMA_INSTALL,
            "status": "PASS",
            "state": "CONTROL_READY",
            "installation_verified": True,
            "f4_transaction_unchanged": True,
            "runtime_identity_unchanged": True,
            "certificate_identity_unchanged": True,
            "live_runtime_mutation": True,
            "reboot_executed": False,
            "board_access": False,
        }


def verify_install(
    *,
    source_head: str,
    manifest_sha256: str,
    expected_transaction_sha256: str,
) -> dict[str, object]:
    _verify_installed_control(
        source_head=source_head,
        manifest_sha256=manifest_sha256,
        expected_transaction_sha256=expected_transaction_sha256,
        allowed_stages=frozenset({"CONTROL_READY"}),
    )
    return {
        "schema": SCHEMA_INSTALL,
        "status": "PASS",
        "state": "CONTROL_READY",
        "installation_verified": True,
        "f4_transaction_unchanged": True,
        "runtime_identity_unchanged": True,
        "certificate_identity_unchanged": True,
        "live_runtime_mutation": True,
        "reboot_executed": False,
        "board_access": False,
    }


def reboot_claim_payload(
    *,
    source_head: str,
    manifest_sha256: str,
    authorization_id: str,
    expected_transaction_sha256: str,
) -> dict[str, object]:
    if REBOOT_CLAIM_PATH.exists() or REBOOT_CLAIM_PATH.is_symlink():
        raise AuthorityError("reboot_claim_preexisting")
    _module, transaction, install_claim = _verify_installed_control(
        source_head=source_head,
        manifest_sha256=manifest_sha256,
        expected_transaction_sha256=expected_transaction_sha256,
        allowed_stages=frozenset({"CONTROL_READY"}),
    )
    install_auth = install_claim.get("control_repair_authorization_id")
    additional = {install_auth} if isinstance(install_auth, str) else set()
    _fresh_authorization(
        authorization_id,
        f4_transaction=transaction,
        additional=additional,
    )
    return {
        "schema": SCHEMA_REBOOT,
        "stage": "REBOOT_PENDING",
        "source_head": source_head,
        "control_manifest_sha256": manifest_sha256,
        "f4_transaction_sha256": expected_transaction_sha256,
        "reboot_authorization_id": authorization_id,
        "reboot_authorization_claimed": True,
        "reboot_authorization_consumed": True,
        "reboot_authorization_replay_allowed": False,
        "pre_boot_id_sha256": _boot_id_sha256(),
        "reboot_acceptance_passed": False,
        "board_access": False,
    }


def claim_reboot(
    *,
    source_head: str,
    manifest_sha256: str,
    authorization_id: str,
    expected_transaction_sha256: str,
) -> dict[str, object]:
    with _exclusive():
        payload = reboot_claim_payload(
            source_head=source_head,
            manifest_sha256=manifest_sha256,
            authorization_id=authorization_id,
            expected_transaction_sha256=expected_transaction_sha256,
        )
        _atomic_write_record(REBOOT_CLAIM_PATH, payload)
        persisted = _record(REBOOT_CLAIM_PATH, 0o600)
        if persisted != payload:
            raise AuthorityError("reboot_claim_persistence_mismatch")
        return {
            "schema": SCHEMA_REBOOT,
            "status": "PASS",
            "state": "REBOOT_PENDING",
            "reboot_authorization_claimed": True,
            "reboot_authorization_consumed": True,
            "reboot_authorization_replay_allowed": False,
            "reboot_acceptance_passed": False,
            "claim_sha256": _sha256(REBOOT_CLAIM_PATH),
            "host_reboot_actuation_required": True,
            "board_access": False,
        }


def verify_reboot_claim(
    *,
    source_head: str,
    manifest_sha256: str,
    expected_transaction_sha256: str,
) -> dict[str, object]:
    claim = _record(REBOOT_CLAIM_PATH, 0o600)
    _verify_installed_control(
        source_head=source_head,
        manifest_sha256=manifest_sha256,
        expected_transaction_sha256=expected_transaction_sha256,
        allowed_stages=frozenset({"CONTROL_READY"}),
    )
    if (
        claim.get("schema") != SCHEMA_REBOOT
        or claim.get("stage") != "REBOOT_PENDING"
        or claim.get("source_head") != source_head
        or claim.get("control_manifest_sha256") != manifest_sha256
        or claim.get("f4_transaction_sha256") != expected_transaction_sha256
        or claim.get("reboot_authorization_claimed") is not True
        or claim.get("reboot_authorization_consumed") is not True
        or claim.get("reboot_authorization_replay_allowed") is not False
        or claim.get("reboot_acceptance_passed") is not False
        or claim.get("pre_boot_id_sha256") != _boot_id_sha256()
        or claim.get("board_access") is not False
    ):
        raise AuthorityError("reboot_claim_contract_invalid")
    return {
        "schema": SCHEMA_REBOOT,
        "status": "PASS",
        "state": "REBOOT_PENDING",
        "reboot_authorization_claimed": True,
        "reboot_authorization_consumed": True,
        "reboot_authorization_replay_allowed": False,
        "reboot_acceptance_passed": False,
        "host_reboot_actuation_required": True,
        "board_access": False,
    }


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--expected-transaction-sha256", required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser("claim-install")
    install.add_argument("--package-root", type=Path, required=True)
    install.add_argument("--authorization-id", required=True)
    _common(install)

    apply_control = sub.add_parser("install-control")
    apply_control.add_argument("--package-root", type=Path, required=True)
    _common(apply_control)

    verify_install_parser = sub.add_parser("verify-install")
    _common(verify_install_parser)

    reboot = sub.add_parser("claim-reboot")
    reboot.add_argument("--authorization-id", required=True)
    _common(reboot)

    verify_reboot_parser = sub.add_parser("verify-reboot-claim")
    _common(verify_reboot_parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "claim-install":
            document = claim_install(
                package_root=args.package_root,
                source_head=args.source_head,
                manifest_sha256=args.manifest_sha256,
                authorization_id=args.authorization_id,
                expected_transaction_sha256=args.expected_transaction_sha256,
            )
        elif args.command == "install-control":
            document = install_control(
                package_root=args.package_root,
                source_head=args.source_head,
                manifest_sha256=args.manifest_sha256,
                expected_transaction_sha256=args.expected_transaction_sha256,
            )
        elif args.command == "verify-install":
            document = verify_install(
                source_head=args.source_head,
                manifest_sha256=args.manifest_sha256,
                expected_transaction_sha256=args.expected_transaction_sha256,
            )
        elif args.command == "claim-reboot":
            document = claim_reboot(
                source_head=args.source_head,
                manifest_sha256=args.manifest_sha256,
                authorization_id=args.authorization_id,
                expected_transaction_sha256=args.expected_transaction_sha256,
            )
        else:
            document = verify_reboot_claim(
                source_head=args.source_head,
                manifest_sha256=args.manifest_sha256,
                expected_transaction_sha256=args.expected_transaction_sha256,
            )
    except (
        AuthorityError,
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
