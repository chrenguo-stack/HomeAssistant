from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from greenhouse_manager.bootstrap.device_firstboot import (
    DeviceFirstbootAdapters,
    inspect_device_provisioning,
    resume_device_provisioning,
    verify_device_ready,
)

SCHEMA = "gh.n3w.t1-device-provisioning-runtime/1"
FACTORY_ACCEPTED_SCHEMA = "gh.n3w.t1-factory-accepted/1"


class DeviceProvisioningRuntimeError(RuntimeError):
    pass


def _validate_factory_acceptance(path: Path) -> os.stat_result:
    if path.is_symlink() or not path.is_file():
        raise DeviceProvisioningRuntimeError("factory_acceptance_record_unsafe")
    metadata = path.stat()
    if metadata.st_uid != os.geteuid():
        raise DeviceProvisioningRuntimeError("factory_acceptance_owner_invalid")
    if metadata.st_mode & 0o777 != 0o600:
        raise DeviceProvisioningRuntimeError("factory_acceptance_mode_invalid")
    if metadata.st_nlink != 1:
        raise DeviceProvisioningRuntimeError("factory_acceptance_link_count_invalid")
    return metadata


def _read_factory_acceptance(path: Path) -> dict[str, Any]:
    _validate_factory_acceptance(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeviceProvisioningRuntimeError("factory_acceptance_record_invalid") from error
    if not isinstance(document, dict):
        raise DeviceProvisioningRuntimeError("factory_acceptance_record_invalid")
    return document


def reconcile_boot_device_provisioning(
    adapters: DeviceFirstbootAdapters,
    transaction_root: str | Path,
    candidate_root: str | Path,
    *,
    release_id: str,
) -> dict[str, Any]:
    observed = inspect_device_provisioning(
        adapters,
        transaction_root,
        candidate_root,
        release_id=release_id,
    )
    state = observed.get("state")

    if state == "UNPROVISIONED":
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "state": "UNPROVISIONED",
            "boot_action": "NOOP",
            "release_id": release_id,
            "activation_eligible": False,
            "production_service_start": False,
            "board_access": False,
        }

    if state == "INITIALIZING":
        report = resume_device_provisioning(
            adapters,
            transaction_root,
            candidate_root,
            release_id=release_id,
        )
        return {
            **report,
            "schema": SCHEMA,
            "boot_action": "RESUME_EXISTING",
            "activation_eligible": False,
            "production_service_start": False,
        }

    if state == "DEVICE_READY":
        report = verify_device_ready(
            adapters,
            transaction_root,
            candidate_root,
            release_id=release_id,
        )
        return {
            **report,
            "schema": SCHEMA,
            "boot_action": "VERIFY_ONLY",
            "activation_eligible": False,
            "production_service_start": False,
        }

    error_code = observed.get("error_code")
    raise DeviceProvisioningRuntimeError(
        f"provisioning_state_conflict:{error_code or 'unknown'}"
    )


def evaluate_product_activation(
    adapters: DeviceFirstbootAdapters,
    transaction_root: str | Path,
    candidate_root: str | Path,
    factory_acceptance_path: str | Path,
    *,
    release_id: str,
) -> dict[str, Any]:
    ready = verify_device_ready(
        adapters,
        transaction_root,
        candidate_root,
        release_id=release_id,
    )
    marker = Path(factory_acceptance_path).expanduser()
    if not marker.is_absolute():
        raise DeviceProvisioningRuntimeError("factory_acceptance_path_not_absolute")

    if not marker.exists() and not marker.is_symlink():
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "state": "DEVICE_READY",
            "release_id": release_id,
            "host_instance_id": ready["host_instance_id"],
            "system_id": ready["system_id"],
            "factory_accepted": False,
            "activation_eligible": False,
            "reason": "factory_acceptance_missing",
            "production_service_start": False,
            "board_access": False,
        }

    document = _read_factory_acceptance(marker)
    system_id = ready["system_id"]
    system_id_sha256 = hashlib.sha256(str(system_id).encode()).hexdigest()
    expected = {
        "schema": FACTORY_ACCEPTED_SCHEMA,
        "status": "PASS",
        "factory_accepted": True,
        "release_id": release_id,
        "host_instance_id": ready["host_instance_id"],
        "system_id": system_id,
        "system_id_sha256": system_id_sha256,
    }
    for key, value in expected.items():
        if document.get(key) != value:
            raise DeviceProvisioningRuntimeError(
                f"factory_acceptance_binding_invalid:{key}"
            )

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "state": "FACTORY_ACCEPTED",
        "release_id": release_id,
        "host_instance_id": ready["host_instance_id"],
        "system_id": system_id,
        "factory_accepted": True,
        "activation_eligible": True,
        "production_service_start": False,
        "board_access": False,
    }
