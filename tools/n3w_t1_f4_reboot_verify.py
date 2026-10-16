#!/usr/bin/python3
from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

CLAIM_SCHEMA = "gh.n3w-t1-f4-reboot-authorization/1"
REPORT_SCHEMA = "gh.n3w-t1-f4-reboot-acceptance/1"
CLAIM_PATH = Path("/var/lib/n3w-t1-provisioning/F4_REBOOT_AUTHORIZATION.json")
F4_TRANSACTION = Path("/var/lib/n3w-t1-provisioning/F4_ACTIVATION_TRANSACTION.json")
F4_HOST = Path("/usr/local/sbin/n3w-t1-f4-activation")
RUNTIME_GUARD = Path("/usr/local/sbin/n3w-t1-f4-certificate-runtime-guard")
DROPIN = Path(
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service.d/"
    "10-runtime-status-evolution.conf"
)
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
EXPECTED_SERVICES = frozenset({"broker", "manager", "homeassistant"})


class VerifyError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise VerifyError(f"record_invalid:{path.name}")
    metadata = path.stat()
    if metadata.st_uid != 0 or metadata.st_gid != 0 or metadata.st_nlink != 1:
        raise VerifyError(f"record_metadata_invalid:{path.name}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerifyError(f"record_json_invalid:{path.name}") from error
    if not isinstance(document, dict):
        raise VerifyError(f"record_document_invalid:{path.name}")
    return document


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


def verify() -> dict[str, object]:
    claim = _json(CLAIM_PATH)
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
    transaction = _json(F4_TRANSACTION)
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
        "certificate_status_sha256": guard["runtime_status_sha256"],
        "homeassistant_mqtt_integration_not_duplicated": True,
        "manager_business_state_fresh": True,
        "board_access": False,
    }


def main() -> int:
    try:
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
