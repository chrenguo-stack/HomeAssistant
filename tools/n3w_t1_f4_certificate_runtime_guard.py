#!/usr/bin/python3
from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import re
import ssl
import stat
import sys
from pathlib import Path
from types import ModuleType

TRANSACTION_PATH = Path("/var/lib/n3w-t1-provisioning/F4_ACTIVATION_TRANSACTION.json")
F4_HOST = Path("/usr/local/sbin/n3w-t1-f4-activation")
CERT_STATUS_FILE = Path("/var/lib/n3wfc4-certificate-lifecycle/status.json")
CA_CERT = Path("/etc/n3wfc4/tls/ca.pem")
SERVER_CERT = Path("/etc/n3wfc4/tls/server.pem")
SYSTEM_CA = Path("/var/lib/greenhouse-manager/identity/system-ca.pem")
SCHEMA = "gh.n3w-t1-f4-certificate-runtime-guard/1"
STATUS_SCHEMA = "gh.n3w-broker-certificate-lifecycle/1"
ALLOWED_STAGES = frozenset({"PERSISTENCE_ENABLED"})
EXPECTED_SERVICES = frozenset({"broker", "manager", "homeassistant"})
ALLOWED_RESULTS = frozenset({"ok", "monitoring_warning", "renewed", "ca_rollover_required"})
ALLOWED_STATES = frozenset({"HEALTHY", "WARNING", "RENEW_DUE", "CRITICAL", "EXPIRED", "CA_ROLLOVER_REQUIRED"})


class GuardError(RuntimeError):
    pass


def _json(path: Path, mode: int) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise GuardError(f"record_invalid:{path.name}")
    metadata = path.stat()
    if metadata.st_uid != 0 or metadata.st_gid != 0 or metadata.st_nlink != 1:
        raise GuardError(f"record_metadata_invalid:{path.name}")
    if stat.S_IMODE(metadata.st_mode) != mode:
        raise GuardError(f"record_mode_invalid:{path.name}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GuardError(f"record_json_invalid:{path.name}") from error
    if not isinstance(document, dict):
        raise GuardError(f"record_document_invalid:{path.name}")
    return document


def _load_f4() -> ModuleType:
    if F4_HOST.is_symlink() or not F4_HOST.is_file():
        raise GuardError("f4_host_invalid")
    loader = importlib.machinery.SourceFileLoader(
        "n3w_f4_certificate_runtime_guard",
        str(F4_HOST),
    )
    specification = importlib.util.spec_from_loader(loader.name, loader)
    if specification is None:
        raise GuardError("f4_host_import_invalid")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    loader.exec_module(module)
    return module


def _f4_control_contract(
    transaction: dict[str, object],
) -> None:
    module = _load_f4()
    verified = module._provision_verify()
    verified_transaction = module._validate_transaction_binding(verified)
    module._validate_factory_binding(verified)
    module._verify_installed_material(verified_transaction)
    if verified_transaction != transaction:
        raise GuardError("f4_transaction_binding_mismatch")
    runtime = module._runtime_activity()
    if (
        runtime.get("production_service_start") is not True
        or set(runtime.get("running_services") or []) != EXPECTED_SERVICES
        or runtime.get("board_access") is not False
    ):
        raise GuardError("f4_runtime_contract_invalid")


def _certificate_fingerprint(path: Path, mode: int) -> str:
    if path.is_symlink() or not path.is_file():
        raise GuardError(f"certificate_invalid:{path.name}")
    metadata = path.stat()
    if metadata.st_uid != 0 or metadata.st_gid != 0 or metadata.st_nlink != 1:
        raise GuardError(f"certificate_metadata_invalid:{path.name}")
    if stat.S_IMODE(metadata.st_mode) != mode:
        raise GuardError(f"certificate_mode_invalid:{path.name}")
    try:
        pem = path.read_text(encoding="ascii")
        der = ssl.PEM_cert_to_DER_cert(pem)
    except (OSError, UnicodeError, ValueError) as error:
        raise GuardError(f"certificate_parse_invalid:{path.name}") from error
    return hashlib.sha256(der).hexdigest()


def check() -> dict[str, object]:
    transaction = _json(TRANSACTION_PATH, 0o600)
    _f4_control_contract(transaction)
    first_audit_sha = transaction.get("certificate_status_sha256")
    if (
        transaction.get("stage") not in ALLOWED_STAGES
        or transaction.get("broker_services_persistence_enabled") is not True
        or transaction.get("persistence_enabled") is not True
        or transaction.get("certificate_first_audit_passed") is not True
        or transaction.get("certificate_timer_enabled") is not True
        or transaction.get("pre_reboot_ready") is not True
        or not isinstance(first_audit_sha, str)
        or re.fullmatch(r"[0-9a-f]{64}", first_audit_sha) is None
    ):
        raise GuardError("transaction_not_authorized")

    status_document = _json(CERT_STATUS_FILE, 0o600)
    if (
        status_document.get("schema") != STATUS_SCHEMA
        or status_document.get("result") not in ALLOWED_RESULTS
        or status_document.get("server_state") not in ALLOWED_STATES
        or status_document.get("ca_state") not in ALLOWED_STATES
        or status_document.get("system_ca_state") not in ALLOWED_STATES
        or not isinstance(status_document.get("checked_at"), str)
        or not status_document.get("checked_at")
        or status_document.get("action") not in {"audit", "renew_server_certificate"}
        or not isinstance(status_document.get("renewal_attempted"), bool)
        or not isinstance(status_document.get("rollback_attempted"), bool)
        or status_document.get("rollback_attempted") is not False
    ):
        raise GuardError("certificate_status_invalid")
    if (
        status_document.get("result") == "renewed"
        and status_document.get("renewal_attempted") is not True
    ):
        raise GuardError("certificate_status_transition_invalid")
    if (
        status_document.get("action") == "audit"
        and status_document.get("renewal_attempted") is not False
    ):
        raise GuardError("certificate_status_transition_invalid")

    observed = {
        "server_sha256_fingerprint": _certificate_fingerprint(SERVER_CERT, 0o644),
        "ca_sha256_fingerprint": _certificate_fingerprint(CA_CERT, 0o644),
        "system_ca_sha256_fingerprint": _certificate_fingerprint(SYSTEM_CA, 0o600),
    }
    for key, value in observed.items():
        if status_document.get(key) != value:
            raise GuardError(f"certificate_status_binding_invalid:{key}")

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "transaction_stage": transaction["stage"],
        "first_audit_binding_present": True,
        "f4_control_contract": "PASS",
        "runtime_service_contract": "PASS",
        "runtime_status_sha256": hashlib.sha256(CERT_STATUS_FILE.read_bytes()).hexdigest(),
        "server_state": status_document["server_state"],
        "ca_state": status_document["ca_state"],
        "system_ca_state": status_document["system_ca_state"],
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check",))
    return parser


def main(argv: list[str] | None = None) -> int:
    _parser().parse_args(argv)
    try:
        document = check()
    except (GuardError, OSError, ValueError) as error:
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
