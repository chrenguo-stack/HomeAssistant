#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "gh.n3w.r10-failed-residue-reconciliation/1"
CONFIRMATION = "ARCHIVE R10 FAILED RESIDUE: YES"
AUTH_PREFIX = "N3W_R10_FAILED_RESIDUE_RECONCILE_"

PROVISION_ROOT = Path("/var/lib/n3w-t1-provisioning")
TRANSACTION = PROVISION_ROOT / "R10_CANDIDATE_UPGRADE_TRANSACTION.json"
WORK_ROOT = Path("/var/lib/n3w-r10-candidate-upgrade")
HISTORY_ROOT = Path("/var/lib/n3w-r10-candidate-upgrade-history")
CLAIMS_ROOT = HISTORY_ROOT / "claims"

FAILED_AUTH = "N3W_R10_T1_CANDIDATE_UPGRADE_R2_20261028_01"
FAILED_HEAD = "4a8c2a62be74ec5c9740d37946e770d9464b6cb3"
FAILED_MANIFEST_SHA256 = (
    "1794a8696663dfaf49a1454cfcf7865ba90cbd8444a508750622d315b5fea64a"
)
FAILED_WORKSPACE_SUFFIX = "00fc1816be40562c"
FAILED_WORKSPACE_PATH = WORK_ROOT / FAILED_WORKSPACE_SUFFIX

PREDECESSOR_MANAGER_IMAGE = "local/greenhouse-manager:fresh-03dab2bd04e7"
TARGET_MANAGER_IMAGE = "local/greenhouse-manager:fresh-e299c937a7b8"
EXPECTED_BROKER_IMAGE = "local/n3w-mosquitto:2.1.2-3184566d"
EXPECTED_HOMEASSISTANT_IMAGE = "local/n3w-homeassistant:2026.10.0-0c73235a"
EXPECTED_F4_SHA256 = (
    "09e0d6a041edff2291d47c8ba2d31f7976d0383e04c7869c4c5379bfa3913fd8"
)

F4_TRANSACTION = PROVISION_ROOT / "F4_ACTIVATION_TRANSACTION.json"
COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")
REGISTRATION_TLS_ROOT = Path("/etc/n3wfc4/registration-tls")
TRUSTED_LAN_RUNTIME = Path("/run/n3wfc4-trusted-lan")
REGISTRATION_CHAIN = "N3WFC4-REGISTRATION-INGRESS"
REGISTRATION_COMMENT = "n3wfc4-registration-ingress-v1"

SERVICES = {
    "n3wfc4-services-activation.service": ("active", "enabled", "loaded"),
    "n3wfc4-broker-activation.service": ("active", "enabled", "loaded"),
    "n3wfc4-broker-ingress-guard.service": ("active", "enabled", "loaded"),
    "n3wfc4-registration-ingress-guard.service": (
        "inactive",
        "not-found",
        "not-found",
    ),
}

EXPECTED_WORKSPACE_FILES = {
    "static/docker-compose.env.bin",
    "static/f4-transaction.bin",
    "static/file-000.bin",
    "static/file-001.bin",
    "static/file-004.bin",
    "static/index.json",
    "static/iptables-filter-prestate.txt",
}


class ReconcileError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def run(
    argv: Iterable[str],
    *,
    timeout: int = 60,
    allowed: frozenset[int] = frozenset({0}),
) -> str:
    command = tuple(str(item) for item in argv)
    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ReconcileError(
            f"command_execution_failed:{Path(command[0]).name}"
        ) from error
    if result.returncode not in allowed:
        raise ReconcileError(
            f"command_failed:{Path(command[0]).name}:{result.returncode}:"
            + (result.stderr.strip() or result.stdout.strip())[:240]
        )
    return result.stdout


def require_root() -> None:
    if os.geteuid() != 0:
        raise ReconcileError("root_required")


def read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReconcileError(f"json_file_invalid:{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReconcileError(f"json_invalid:{path}") from error
    if not isinstance(value, dict):
        raise ReconcileError(f"json_object_required:{path}")
    return value


def fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    payload = (
        json.dumps(value, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb", closefd=True) as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def valid_reconcile_authorization(value: str) -> bool:
    return (
        value.startswith(AUTH_PREFIX)
        and len(value) <= 200
        and value.replace("_", "").replace("-", "").isalnum()
    )


def validate_failed_transaction(document: dict[str, Any]) -> None:
    expected = {
        "schema": "gh.n3w.r10-t1-candidate-upgrade-transaction/1",
        "authorization_id": FAILED_AUTH,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "package_head": FAILED_HEAD,
        "package_manifest_sha256": FAILED_MANIFEST_SHA256,
        "predecessor_source": "03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6",
        "target_source": "e299c937a7b89bb8a7b9a7432186ba46a416cd44",
        "predecessor_f4_transaction_sha256": EXPECTED_F4_SHA256,
        "predecessor_f4_installed_files_sha256": (
            "66f8c89a10363fbf12cbd711f26257dd7cfacdfc178e7f0b4de229ba573f21a5"
        ),
        "current_registration_count": 1,
        "static_backup_complete": True,
        "status": "FAIL",
        "phase": "ROLLBACK_FAILED",
        "committed": False,
        "rollback_completed": False,
        "rollback_error_count": 1,
        "rollback_error_classes": ["firewall:UpgradeError"],
        "predecessor_manager_image": PREDECESSOR_MANAGER_IMAGE,
        "target_manager_image": TARGET_MANAGER_IMAGE,
        "board_access": False,
    }
    for key, wanted in expected.items():
        if document.get(key) != wanted:
            raise ReconcileError(f"failed_transaction_binding_invalid:{key}")
    wanted_workspace_hash = sha256_bytes(
        str(FAILED_WORKSPACE_PATH).encode("utf-8")
    )
    if document.get("workspace_sha256") != wanted_workspace_hash:
        raise ReconcileError("workspace_path_binding_invalid")


def _binding(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReconcileError(f"file_invalid:{path}")
    meta = path.stat()
    return {
        "sha256": sha256_file(path),
        "size": meta.st_size,
        "mode": stat.S_IMODE(meta.st_mode),
        "uid": meta.st_uid,
        "gid": meta.st_gid,
    }


def validate_workspace() -> dict[str, Any]:
    if WORK_ROOT.is_symlink() or not WORK_ROOT.is_dir():
        raise ReconcileError("work_root_invalid")
    root_meta = WORK_ROOT.stat()
    if (
        root_meta.st_uid != 0
        or root_meta.st_gid != 0
        or stat.S_IMODE(root_meta.st_mode) != 0o700
    ):
        raise ReconcileError("work_root_metadata_invalid")
    children = [item.name for item in WORK_ROOT.iterdir()]
    if children != [FAILED_WORKSPACE_SUFFIX]:
        raise ReconcileError("work_root_member_set_invalid")
    if FAILED_WORKSPACE_PATH.is_symlink() or not FAILED_WORKSPACE_PATH.is_dir():
        raise ReconcileError("failed_workspace_invalid")

    files: list[dict[str, Any]] = []
    actual: set[str] = set()
    for root, dirs, names in os.walk(FAILED_WORKSPACE_PATH):
        root_path = Path(root)
        root_stat = root_path.stat()
        if (
            root_stat.st_uid != 0
            or root_stat.st_gid != 0
            or stat.S_IMODE(root_stat.st_mode) != 0o700
        ):
            raise ReconcileError(f"workspace_directory_metadata_invalid:{root_path}")
        for name in dirs:
            item = root_path / name
            if item.is_symlink() or not item.is_dir():
                raise ReconcileError("workspace_special_directory_forbidden")
        for name in names:
            item = root_path / name
            if item.is_symlink() or not item.is_file():
                raise ReconcileError("workspace_special_file_forbidden")
            relative = item.relative_to(FAILED_WORKSPACE_PATH).as_posix()
            actual.add(relative)
            binding = _binding(item)
            if (
                binding["mode"] != 0o600
                or binding["uid"] != 0
                or binding["gid"] != 0
            ):
                raise ReconcileError(
                    f"workspace_file_metadata_invalid:{relative}"
                )
            files.append({"path": relative, **binding})
    if actual != EXPECTED_WORKSPACE_FILES:
        raise ReconcileError("workspace_file_set_invalid")
    files.sort(key=lambda item: str(item["path"]))

    index = read_json(FAILED_WORKSPACE_PATH / "static/index.json")
    for key in ("f4_transaction", "compose_env"):
        record = index.get(key)
        if not isinstance(record, dict) or record.get("present") is not True:
            raise ReconcileError(f"workspace_index_record_invalid:{key}")
        backup = record.get("backup")
        if not isinstance(backup, str):
            raise ReconcileError(f"workspace_index_backup_invalid:{key}")
        path = FAILED_WORKSPACE_PATH / "static" / backup
        binding = record.get("binding")
        if not isinstance(binding, dict) or _binding(path) != binding:
            raise ReconcileError(f"workspace_backup_binding_invalid:{key}")

    if sha256_file(
        FAILED_WORKSPACE_PATH / "static/f4-transaction.bin"
    ) != EXPECTED_F4_SHA256:
        raise ReconcileError("workspace_f4_backup_invalid")

    for key, record in index.items():
        if not str(key).startswith("live_files:"):
            continue
        if not isinstance(record, dict):
            raise ReconcileError("workspace_live_record_invalid")
        target = Path(str(record.get("path", "")))
        if record.get("present") is True:
            backup = record.get("backup")
            binding = record.get("binding")
            if not isinstance(backup, str) or not isinstance(binding, dict):
                raise ReconcileError("workspace_live_binding_invalid")
            backup_path = FAILED_WORKSPACE_PATH / "static" / backup
            backup_binding = _binding(backup_path)
            if (
                backup_binding["sha256"] != binding.get("sha256")
                or backup_binding["size"] != binding.get("size")
                or backup_binding["mode"] != 0o600
                or backup_binding["uid"] != 0
                or backup_binding["gid"] != 0
            ):
                raise ReconcileError(
                    f"workspace_backup_copy_invalid:{target}"
                )
            if _binding(target) != binding:
                raise ReconcileError(
                    f"current_static_not_predecessor_exact:{target}"
                )
        elif target.exists() or target.is_symlink():
            raise ReconcileError(f"new_live_file_residue:{target}")

    return {
        "workspace_file_count": len(files),
        "workspace_inventory_sha256": canonical_sha256(files),
        "workspace_files": files,
        "index_sha256": sha256_file(
            FAILED_WORKSPACE_PATH / "static/index.json"
        ),
        "firewall_prestate_sha256": sha256_file(
            FAILED_WORKSPACE_PATH / "static/iptables-filter-prestate.txt"
        ),
    }


def service_state(unit: str) -> tuple[str, str, str]:
    active = run(
        ("systemctl", "is-active", unit),
        allowed=frozenset({0, 3, 4}),
    ).strip() or "unknown"
    enabled = run(
        ("systemctl", "is-enabled", unit),
        allowed=frozenset({0, 1, 3, 4}),
    ).strip() or "unknown"
    load = run(
        ("systemctl", "show", unit, "-p", "LoadState", "--value"),
        allowed=frozenset({0, 1, 3, 4}),
    ).strip() or "not-found"
    return active, enabled, load


def container_image(name: str) -> str:
    raw = run(
        (
            "docker",
            "inspect",
            name,
            "--format",
            "{{json .}}",
        ),
        timeout=30,
    )
    doc = json.loads(raw)
    if (
        not isinstance(doc, dict)
        or not isinstance(doc.get("Config"), dict)
        or not isinstance(doc.get("State"), dict)
        or doc["State"].get("Running") is not True
    ):
        raise ReconcileError(f"container_state_invalid:{name}")
    image = doc["Config"].get("Image")
    if not isinstance(image, str):
        raise ReconcileError(f"container_image_invalid:{name}")
    return image


def parse_env_image() -> str:
    if COMPOSE_ENV.is_symlink() or not COMPOSE_ENV.is_file():
        raise ReconcileError("compose_env_invalid")
    values = {}
    for raw in COMPOSE_ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    value = values.get("GH_MANAGER_IMAGE")
    if not value:
        raise ReconcileError("compose_manager_image_missing")
    return value


def validate_live_predecessor() -> dict[str, Any]:
    for unit, expected in SERVICES.items():
        observed = service_state(unit)
        if observed != expected:
            raise ReconcileError(
                f"service_state_invalid:{unit}:{observed}"
            )

    images = {
        "manager": container_image("n3wfc4-manager-1"),
        "broker": container_image("n3wfc4-broker-1"),
        "homeassistant": container_image("n3wfc4-homeassistant-1"),
    }
    if images != {
        "manager": PREDECESSOR_MANAGER_IMAGE,
        "broker": EXPECTED_BROKER_IMAGE,
        "homeassistant": EXPECTED_HOMEASSISTANT_IMAGE,
    }:
        raise ReconcileError("container_image_predecessor_invalid")

    if parse_env_image() != PREDECESSOR_MANAGER_IMAGE:
        raise ReconcileError("compose_env_predecessor_invalid")

    target_ids = run(
        (
            "docker",
            "image",
            "ls",
            "--no-trunc",
            "--quiet",
            "--filter",
            f"reference={TARGET_MANAGER_IMAGE}",
        ),
        timeout=30,
    ).strip()
    if target_ids:
        raise ReconcileError("target_manager_image_residue")

    if _binding(F4_TRANSACTION)["sha256"] != EXPECTED_F4_SHA256:
        raise ReconcileError("f4_transaction_not_predecessor_exact")

    if REGISTRATION_TLS_ROOT.exists() or REGISTRATION_TLS_ROOT.is_symlink():
        raise ReconcileError("registration_tls_residue")
    if TRUSTED_LAN_RUNTIME.exists() or TRUSTED_LAN_RUNTIME.is_symlink():
        raise ReconcileError("trusted_lan_residue")

    firewall = run(("iptables-save", "-t", "filter"), timeout=20)
    if REGISTRATION_CHAIN in firewall or REGISTRATION_COMMENT in firewall:
        raise ReconcileError("registration_firewall_residue")
    if (
        "N3WFC4-BROKER-INGRESS" not in firewall
        or "n3wfc4-broker-ingress-v1" not in firewall
    ):
        raise ReconcileError("broker_firewall_predecessor_invalid")

    sockets = run(("ss", "-lntup"), timeout=20)
    if re.search(r":(?:47110|47111|47112)\b", sockets):
        raise ReconcileError("registration_listener_residue")

    pairing_raw = run(
        (
            "docker",
            "exec",
            "n3wfc4-manager-1",
            "greenhouse-manager-pairing",
            "window-status",
        ),
        timeout=30,
    )
    try:
        pairing = json.loads(pairing_raw)
    except json.JSONDecodeError as error:
        raise ReconcileError("pairing_status_invalid") from error
    if (
        not isinstance(pairing, dict)
        or pairing.get("accepted") is not True
        or pairing.get("pairing_window_state") != "CLOSED"
    ):
        raise ReconcileError("pairing_window_not_closed")

    return {
        "containers": images,
        "f4_transaction_sha256": EXPECTED_F4_SHA256,
        "registration_tls_absent": True,
        "trusted_lan_absent": True,
        "registration_firewall_absent": True,
        "registration_ports_absent": True,
        "pairing_window": "CLOSED",
    }


def claim_path(authorization_id: str) -> Path:
    suffix = sha256_bytes(authorization_id.encode("utf-8"))[:16]
    return CLAIMS_ROOT / f"{suffix}.json"


def archive_entry() -> Path:
    return HISTORY_ROOT / f"r2-{FAILED_WORKSPACE_SUFFIX}"


def claim_authorization(
    authorization_id: str,
    *,
    transaction_sha256: str,
    workspace_inventory_sha256: str,
) -> None:
    if HISTORY_ROOT.is_symlink() or CLAIMS_ROOT.is_symlink():
        raise ReconcileError("history_root_symlink_forbidden")
    HISTORY_ROOT.mkdir(mode=0o700, exist_ok=True)
    CLAIMS_ROOT.mkdir(mode=0o700, exist_ok=True)
    for path in (HISTORY_ROOT, CLAIMS_ROOT):
        meta = path.stat()
        if (
            meta.st_uid != 0
            or meta.st_gid != 0
            or stat.S_IMODE(meta.st_mode) != 0o700
        ):
            raise ReconcileError("history_root_metadata_invalid")
    claim = claim_path(authorization_id)
    write_json_exclusive(
        claim,
        {
            "schema": SCHEMA,
            "authorization_id": authorization_id,
            "authorization_consumed": True,
            "replay_allowed": False,
            "failed_authorization_id": FAILED_AUTH,
            "transaction_sha256": transaction_sha256,
            "workspace_inventory_sha256": workspace_inventory_sha256,
        },
    )
    fsync_directory(CLAIMS_ROOT)


def execute_reconcile(
    *,
    authorization_id: str,
    confirmation: str,
) -> dict[str, Any]:
    require_root()
    if confirmation != CONFIRMATION:
        raise ReconcileError("confirmation_invalid")
    if not valid_reconcile_authorization(authorization_id):
        raise ReconcileError("authorization_id_invalid")
    if claim_path(authorization_id).exists():
        raise ReconcileError("authorization_replay_forbidden")

    document = read_json(TRANSACTION)
    validate_failed_transaction(document)
    transaction_bytes = TRANSACTION.read_bytes()
    transaction_sha256 = sha256_bytes(transaction_bytes)
    workspace = validate_workspace()
    live = validate_live_predecessor()

    final = archive_entry()
    if final.exists() or final.is_symlink():
        raise ReconcileError("archive_entry_preexisting")

    claim_authorization(
        authorization_id,
        transaction_sha256=transaction_sha256,
        workspace_inventory_sha256=str(
            workspace["workspace_inventory_sha256"]
        ),
    )

    incoming = HISTORY_ROOT / f".incoming-{FAILED_WORKSPACE_SUFFIX}"
    if incoming.exists() or incoming.is_symlink():
        raise ReconcileError("archive_incoming_preexisting")
    incoming.mkdir(mode=0o700)

    write_json_exclusive(
        incoming / "preflight.json",
        {
            "schema": SCHEMA,
            "status": "PRECHECK_PASS",
            "failed_transaction_sha256": transaction_sha256,
            "workspace_inventory_sha256": workspace[
                "workspace_inventory_sha256"
            ],
            "workspace_file_count": workspace["workspace_file_count"],
            "workspace_index_sha256": workspace["index_sha256"],
            "firewall_prestate_sha256": workspace[
                "firewall_prestate_sha256"
            ],
            "live_predecessor": live,
            "failed_authorization_id": FAILED_AUTH,
            "reconcile_authorization_id": authorization_id,
        },
    )
    fsync_directory(incoming)

    os.replace(WORK_ROOT, incoming / "workspace-root")
    fsync_directory(WORK_ROOT.parent)
    fsync_directory(incoming)
    fsync_directory(HISTORY_ROOT)
    if WORK_ROOT.exists() or WORK_ROOT.is_symlink():
        raise ReconcileError("active_workspace_archive_failed")

    os.replace(incoming, final)
    fsync_directory(HISTORY_ROOT)

    archived_workspace = final / "workspace-root" / FAILED_WORKSPACE_SUFFIX
    if (
        not archived_workspace.is_dir()
        or archived_workspace.is_symlink()
    ):
        raise ReconcileError("archived_workspace_invalid")

    os.replace(TRANSACTION, final / "transaction.json")
    fsync_directory(PROVISION_ROOT)
    fsync_directory(final)

    if (
        TRANSACTION.exists()
        or TRANSACTION.is_symlink()
        or WORK_ROOT.exists()
        or WORK_ROOT.is_symlink()
    ):
        raise ReconcileError("active_residue_still_present")
    if sha256_file(final / "transaction.json") != transaction_sha256:
        raise ReconcileError("archived_transaction_hash_mismatch")

    result = {
        "schema": SCHEMA,
        "status": "PASS",
        "authorization_consumed": True,
        "replay_allowed": False,
        "failed_authorization_id": FAILED_AUTH,
        "archive_path": str(final),
        "transaction_sha256": transaction_sha256,
        "workspace_inventory_sha256": workspace[
            "workspace_inventory_sha256"
        ],
        "active_transaction_absent": True,
        "active_workspace_absent": True,
        "predecessor_runtime_proven": True,
        "board_access": False,
    }
    write_json_exclusive(final / "reconciliation.json", result)
    fsync_directory(final)
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--authorization-id", required=True)
    result.add_argument("--confirm", required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        result = execute_reconcile(
            authorization_id=args.authorization_id,
            confirmation=args.confirm,
        )
    except ReconcileError as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error),
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
