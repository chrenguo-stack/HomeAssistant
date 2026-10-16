#!/usr/bin/python3
from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import re
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Sequence

SCHEMA = "gh.n3w-t1-f4-reboot-authorization/1"
CLAIM_PATH = Path("/var/lib/n3w-t1-provisioning/F4_REBOOT_AUTHORIZATION.json")
F4_TRANSACTION = Path("/var/lib/n3w-t1-provisioning/F4_ACTIVATION_TRANSACTION.json")
F4_HOST = Path("/usr/local/sbin/n3w-t1-f4-activation")
RUNTIME_GUARD = Path("/usr/local/sbin/n3w-t1-f4-certificate-runtime-guard")
CONTROL_MANIFEST = Path(
    "/usr/local/share/n3w-t1-f4-reboot-successor/reboot-successor-manifest.json"
)
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
AUTH_PATTERN = re.compile(r"^N3W_T1_F4_[A-Z0-9_]{8,160}$")
EXPECTED_SERVICES = {"broker", "manager", "homeassistant"}


class AuthorityError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
    loader = importlib.machinery.SourceFileLoader("n3w_f4_reboot_authority", str(F4_HOST))
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


def _pre_reboot(
    *,
    source_head: str,
    manifest_sha256: str,
    expected_transaction_sha256: str,
) -> tuple[ModuleType, dict[str, object]]:
    if re.fullmatch(r"[0-9a-f]{40}", source_head) is None:
        raise AuthorityError("source_head_invalid")
    if re.fullmatch(r"[0-9a-f]{64}", manifest_sha256) is None:
        raise AuthorityError("manifest_sha256_invalid")
    if re.fullmatch(r"[0-9a-f]{64}", expected_transaction_sha256) is None:
        raise AuthorityError("transaction_sha256_invalid")
    if _sha256(F4_TRANSACTION) != expected_transaction_sha256:
        raise AuthorityError("f4_transaction_sha256_mismatch")
    if _sha256(CONTROL_MANIFEST) != manifest_sha256:
        raise AuthorityError("control_manifest_sha256_mismatch")
    manifest = _record(CONTROL_MANIFEST, 0o644)
    if manifest.get("source_head") != source_head:
        raise AuthorityError("control_manifest_source_head_mismatch")
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
    module._validate_factory_binding(module._provision_verify())
    module._verify_installed_material(transaction)
    module._validate_runtime_acceptance_binding(transaction)

    guard = json.loads(
        subprocess.run(
            (str(RUNTIME_GUARD), "check"),
            check=True,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        ).stdout
    )
    if guard.get("status") != "PASS":
        raise AuthorityError("certificate_runtime_guard_not_pass")

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


def claim_payload(
    *,
    authorization_id: str,
    source_head: str,
    manifest_sha256: str,
    expected_transaction_sha256: str,
) -> dict[str, object]:
    if AUTH_PATTERN.fullmatch(authorization_id) is None:
        raise AuthorityError("authorization_id_invalid")
    if CLAIM_PATH.exists() or CLAIM_PATH.is_symlink():
        raise AuthorityError("reboot_claim_preexisting")
    _module, transaction = _pre_reboot(
        source_head=source_head,
        manifest_sha256=manifest_sha256,
        expected_transaction_sha256=expected_transaction_sha256,
    )
    if authorization_id in _prior_authorizations(transaction):
        raise AuthorityError("authorization_replay_forbidden")
    return {
        "schema": SCHEMA,
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


def verify_claim(
    *,
    source_head: str,
    manifest_sha256: str,
    expected_transaction_sha256: str,
) -> dict[str, object]:
    claim = _record(CLAIM_PATH, 0o600)
    _pre_reboot(
        source_head=source_head,
        manifest_sha256=manifest_sha256,
        expected_transaction_sha256=expected_transaction_sha256,
    )
    if (
        claim.get("schema") != SCHEMA
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
        "schema": SCHEMA,
        "status": "PASS",
        "stage": "REBOOT_PENDING",
        "reboot_authorization_claimed": True,
        "reboot_authorization_consumed": True,
        "reboot_authorization_replay_allowed": False,
        "reboot_acceptance_passed": False,
        "host_reboot_actuation_required": True,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    claim = sub.add_parser("claim-payload")
    claim.add_argument("--authorization-id", required=True)
    for command in (claim, sub.add_parser("verify-claim")):
        command.add_argument("--source-head", required=True)
        command.add_argument("--manifest-sha256", required=True)
        command.add_argument("--expected-transaction-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "claim-payload":
            document = claim_payload(
                authorization_id=args.authorization_id,
                source_head=args.source_head,
                manifest_sha256=args.manifest_sha256,
                expected_transaction_sha256=args.expected_transaction_sha256,
            )
        else:
            document = verify_claim(
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
