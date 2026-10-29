from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import tarfile
import time
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "gh.n3w.r10-manager-successor-refresh-execution/1"
PACKAGE_SCHEMA = "gh.n3w.r10-manager-successor-refresh-package/1"

PREDECESSOR_SOURCE = "e299c937a7b89bb8a7b9a7432186ba46a416cd44"
TARGET_SOURCE = "ff750b3801a282af1667b5fa63481e2333e301b3"
TARGET_TREE = "ee6ee5e362628fa725d57fbdf50c6608e9032b17"

PREDECESSOR_MANAGER_IMAGE = "local/greenhouse-manager:fresh-e299c937a7b8"
TARGET_MANAGER_IMAGE = "local/greenhouse-manager:fresh-ff750b3801a2"
EXPECTED_BROKER_IMAGE = "local/n3w-mosquitto:2.1.2-3184566d"
EXPECTED_HOMEASSISTANT_IMAGE = "local/n3w-homeassistant:2026.10.0-0c73235a"
PREDECESSOR_CANDIDATE_TTL_SECONDS = 30
EXPECTED_CANDIDATE_TTL_SECONDS = 60

CONFIRMATION = "APPLY R10 MANAGER SUCCESSOR REFRESH: YES"
AUTHORIZATION_PATTERN = re.compile(
    r"^N3W_R10_MANAGER_SUCCESSOR_REFRESH_[0-9]{8}_[0-9]{2}$"
)

PROVISION_ROOT = Path("/var/lib/n3w-t1-provisioning")
TRANSACTION = PROVISION_ROOT / "R10_MANAGER_SUCCESSOR_REFRESH_TRANSACTION.json"
F4_TRANSACTION = PROVISION_ROOT / "F4_ACTIVATION_TRANSACTION.json"
PREDECESSOR_UPGRADE_TRANSACTION = (
    PROVISION_ROOT / "R10_CANDIDATE_UPGRADE_TRANSACTION.json"
)
WORK_ROOT = Path("/var/lib/n3w-r10-manager-successor-refresh")

COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")
COMPOSE_FILE = Path("/etc/n3wfc4/docker-compose.yml")
MANAGER_DB = Path("/var/lib/greenhouse-manager/manager/manager-state.sqlite3")
BROKER_DYNSEC = Path("/var/lib/n3wfc4-broker/dynamic-security.json")
REGISTRATION_CERT = Path("/etc/n3wfc4/registration-tls/bootstrap.pem")
REGISTRATION_KEY = Path("/etc/n3wfc4/registration-tls/bootstrap.key")

SERVICES_UNIT = "n3wfc4-services-activation.service"
REGISTRATION_UNIT = "n3wfc4-registration-ingress-guard.service"

POSTCHECK_TIMEOUT_SECONDS = 180
POSTCHECK_POLL_SECONDS = 2


class RefreshError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256_bytes(payload)


def image_config_contract(config: object) -> dict[str, object]:
    value = config if isinstance(config, dict) else {}
    result: dict[str, object] = {}
    sequence_fields = {"Entrypoint", "Cmd", "Env"}
    string_fields = {"User", "WorkingDir", "StopSignal"}
    mapping_fields = {
        "Labels",
        "Healthcheck",
        "Volumes",
        "ExposedPorts",
    }
    for key in sorted(sequence_fields | string_fields | mapping_fields):
        observed = value.get(key)
        if key in sequence_fields and observed is None:
            observed = []
        elif key in string_fields and observed is None:
            observed = ""
        elif key in mapping_fields and observed is None:
            observed = {}
        result[key] = observed
    return result


def run(
    argv: Iterable[str],
    *,
    timeout: int = 180,
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
        raise RefreshError(
            f"command_execution_failed:{Path(command[0]).name}"
        ) from error
    if result.returncode not in allowed:
        detail = (result.stderr.strip() or result.stdout.strip())[:240]
        raise RefreshError(
            f"command_failed:{Path(command[0]).name}:{result.returncode}:{detail}"
        )
    return result.stdout


def require_root() -> None:
    if os.geteuid() != 0:
        raise RefreshError("root_required")


def file_binding(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RefreshError(f"file_invalid:{path}")
    metadata = path.stat()
    return {
        "sha256": sha256_file(path),
        "size": metadata.st_size,
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
    }


def atomic_write_bytes(
    path: Path,
    payload: bytes,
    *,
    mode: int,
    uid: int,
    gid: int,
    exclusive: bool = False,
) -> None:
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise RefreshError(f"parent_invalid:{parent}")
    if exclusive:
        target = path
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
    else:
        target = parent / f".{path.name}.r10-manager-refresh-{os.getpid()}"
        if target.exists() or target.is_symlink():
            raise RefreshError("temporary_path_collision")
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
    descriptor = os.open(target, flags, mode)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(target, mode)
        os.chown(target, uid, gid)
        if not exclusive:
            os.replace(target, path)
        directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        try:
            if not exclusive and target.exists():
                target.unlink()
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, value: dict[str, Any], *, exclusive: bool = False) -> None:
    payload = (
        json.dumps(value, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    atomic_write_bytes(
        path,
        payload,
        mode=0o600,
        uid=0,
        gid=0,
        exclusive=exclusive,
    )


def read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RefreshError(f"json_file_invalid:{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RefreshError(f"json_file_unreadable:{path.name}") from error
    if not isinstance(value, dict):
        raise RefreshError(f"json_document_invalid:{path.name}")
    return value


def parse_env(path: Path) -> tuple[list[str], dict[str, str]]:
    if path.is_symlink() or not path.is_file():
        raise RefreshError("compose_env_invalid")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise RefreshError("compose_env_read_failed") from error
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in line:
            raise RefreshError("compose_env_line_invalid")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise RefreshError("compose_env_key_invalid")
        values[key] = value
    return lines, values


def manager_env_payload(lines: list[str], expected: str, target: str) -> bytes:
    values = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in line:
            raise RefreshError("compose_env_line_invalid")
        key, value = line.split("=", 1)
        if key in values:
            raise RefreshError("compose_env_key_invalid")
        values[key] = value
    if values.get("GH_MANAGER_IMAGE") != expected:
        raise RefreshError("compose_env_manager_image_drift")
    if sum(line.startswith("GH_MANAGER_IMAGE=") for line in lines) != 1:
        raise RefreshError("compose_env_manager_image_count_invalid")
    replaced = [
        f"GH_MANAGER_IMAGE={target}"
        if line.startswith("GH_MANAGER_IMAGE=")
        else line
        for line in lines
    ]
    return ("\n".join(replaced) + "\n").encode("utf-8")


def service_state(unit: str) -> dict[str, str]:
    active = run(
        ("systemctl", "is-active", unit),
        timeout=20,
        allowed=frozenset({0, 3, 4}),
    ).strip()
    enabled = run(
        ("systemctl", "is-enabled", unit),
        timeout=20,
        allowed=frozenset({0, 1, 3, 4}),
    ).strip()
    load = run(
        ("systemctl", "show", unit, "-p", "LoadState", "--value"),
        timeout=20,
        allowed=frozenset({0, 1}),
    ).strip()
    return {
        "active": active or "inactive",
        "enabled": enabled or "unknown",
        "load": load or "unknown",
    }


def container(service: str, *, running_only: bool = True) -> dict[str, Any]:
    command = ["docker", "ps"]
    if not running_only:
        command.append("-a")
    command.extend(
        [
            "--filter",
            "label=com.docker.compose.project=n3wfc4",
            "--filter",
            f"label=com.docker.compose.service={service}",
            "-q",
        ]
    )
    identifiers = [
        line.strip()
        for line in run(command, timeout=30).splitlines()
        if line.strip()
    ]
    if len(identifiers) != 1:
        raise RefreshError(f"container_not_unique:{service}")
    try:
        docs = json.loads(
            run(("docker", "inspect", identifiers[0]), timeout=30)
        )
    except json.JSONDecodeError as error:
        raise RefreshError(f"container_inspect_invalid:{service}") from error
    if (
        not isinstance(docs, list)
        or len(docs) != 1
        or not isinstance(docs[0], dict)
    ):
        raise RefreshError(f"container_inspect_invalid:{service}")
    return docs[0]


def container_snapshot(document: dict[str, Any]) -> dict[str, Any]:
    config = document.get("Config")
    state = document.get("State")
    if not isinstance(config, dict) or not isinstance(state, dict):
        raise RefreshError("container_snapshot_invalid")
    return {
        "id": str(document.get("Id") or ""),
        "image_id": str(document.get("Image") or ""),
        "image": str(config.get("Image") or ""),
        "started_at": str(state.get("StartedAt") or ""),
        "restart_count": int(document.get("RestartCount") or 0),
        "running": state.get("Running") is True,
    }


def listener_count(protocol: str, port: int) -> int:
    flag = "-lnt" if protocol == "tcp" else "-lnu"
    output = run(("ss", "-H", flag), timeout=20)
    suffix = f":{port}"
    return sum(
        1
        for line in output.splitlines()
        if len(line.split()) >= 4 and line.split()[3].endswith(suffix)
    )


def _db_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"bytes_sha256": sha256_bytes(value)}
    if value is None or isinstance(value, (str, int, float)):
        return value
    return str(value)


def database_state() -> dict[str, Any]:
    if MANAGER_DB.is_symlink() or not MANAGER_DB.is_file():
        raise RefreshError("manager_database_invalid")
    try:
        con = sqlite3.connect(
            "file:" + str(MANAGER_DB) + "?mode=ro",
            uri=True,
            timeout=5,
        )
        con.execute("PRAGMA query_only=ON")
        integrity_row = con.execute("PRAGMA integrity_check").fetchone()
        integrity = str(integrity_row[0]) if integrity_row else "invalid"
        tables = {
            str(row[0])
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        current = int(
            con.execute(
                "SELECT COUNT(*) FROM registrations WHERE retired_at IS NULL"
            ).fetchone()[0]
        )
        attempt_count = 0
        unresolved = 0
        if "first_registration_attempts" in tables:
            attempt_count = int(
                con.execute(
                    "SELECT COUNT(*) FROM first_registration_attempts"
                ).fetchone()[0]
            )
            unresolved = int(
                con.execute(
                    "SELECT COUNT(*) FROM first_registration_attempts "
                    "WHERE state='ACTIVE' OR "
                    "(state IN ('EXPIRED','RESTART_INVALIDATED') "
                    "AND cleanup_state!='COMPLETE')"
                ).fetchone()[0]
            )

        fingerprint: dict[str, Any] = {}
        for table in ("registrations", "first_registration_attempts"):
            if table not in tables:
                fingerprint[table] = None
                continue
            columns = [
                str(row[1])
                for row in con.execute(f"PRAGMA table_info({table})")
            ]
            rows = [
                [_db_value(value) for value in row]
                for row in con.execute(f"SELECT * FROM {table} ORDER BY rowid")
            ]
            fingerprint[table] = {"columns": columns, "rows": rows}
        con.close()
    except sqlite3.Error as error:
        raise RefreshError("manager_database_read_failed") from error
    return {
        "integrity": integrity,
        "current_registration_count": current,
        "attempt_count": attempt_count,
        "unresolved_first_registration": unresolved,
        "business_fingerprint_sha256": canonical_sha256(fingerprint),
    }


def pairing_window_closed(manager_id: str) -> bool:
    output = run(
        (
            "docker",
            "exec",
            manager_id,
            "greenhouse-manager-pairing",
            "window-status",
        ),
        timeout=30,
    )
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        return False
    return (
        isinstance(value, dict)
        and value.get("accepted") is True
        and value.get("pairing_window_state") == "CLOSED"
        and value.get("raw_locator_in_output") is False
    )


def manager_candidate_ttl(manager_id: str) -> int:
    code = (
        "from greenhouse_manager.runtime.n3w_registration_discovery "
        "import RegistrationCandidate;"
        "c=RegistrationCandidate("
        "manager_id='m',system_id='s',system_id_hint='S',host='127.0.0.1',"
        "bootstrap_tls_sha256='0'*64);"
        "print(c.ttl_s)"
    )
    output = run(
        ("docker", "exec", manager_id, "python", "-c", code),
        timeout=30,
    ).strip()
    try:
        return int(output)
    except ValueError as error:
        raise RefreshError("manager_candidate_ttl_invalid") from error


def docker_image_ids(reference: str) -> list[str]:
    output = run(
        (
            "docker",
            "image",
            "ls",
            "--no-trunc",
            "--quiet",
            "--filter",
            f"reference={reference}",
        ),
        timeout=30,
    )
    return list(
        dict.fromkeys(
            line.strip()
            for line in output.splitlines()
            if line.strip()
        )
    )


def archive_identity(path: Path) -> dict[str, Any]:
    try:
        with tarfile.open(path, "r:*") as archive:
            docker_stream = archive.extractfile("manifest.json")
            index_stream = archive.extractfile("index.json")
            if docker_stream is None or index_stream is None:
                raise RefreshError("manager_archive_identity_missing")
            docker_manifest = json.loads(docker_stream.read().decode("utf-8"))
            index = json.loads(index_stream.read().decode("utf-8"))
            if (
                not isinstance(docker_manifest, list)
                or len(docker_manifest) != 1
                or not isinstance(docker_manifest[0], dict)
                or not isinstance(index, dict)
                or not isinstance(index.get("manifests"), list)
                or len(index["manifests"]) != 1
            ):
                raise RefreshError("manager_archive_identity_invalid")
            config_path = str(docker_manifest[0].get("Config", ""))
            descriptor = str(index["manifests"][0].get("digest", ""))
            if (
                not config_path.startswith("blobs/sha256/")
                or not descriptor.startswith("sha256:")
            ):
                raise RefreshError("manager_archive_identity_invalid")
            config_hex = config_path.removeprefix("blobs/sha256/")
            manifest_hex = descriptor.removeprefix("sha256:")
            if len(config_hex) != 64 or len(manifest_hex) != 64:
                raise RefreshError("manager_archive_identity_invalid")
            config_stream = archive.extractfile(config_path)
            manifest_stream = archive.extractfile(f"blobs/sha256/{manifest_hex}")
            if config_stream is None or manifest_stream is None:
                raise RefreshError("manager_archive_identity_missing")
            config_bytes = config_stream.read()
            manifest_bytes = manifest_stream.read()
            if (
                hashlib.sha256(config_bytes).hexdigest() != config_hex
                or hashlib.sha256(manifest_bytes).hexdigest()
                != manifest_hex
            ):
                raise RefreshError("manager_archive_identity_binding_invalid")
            try:
                config_document = json.loads(config_bytes.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as error:
                raise RefreshError("manager_archive_config_invalid") from error
            if not isinstance(config_document, dict):
                raise RefreshError("manager_archive_config_invalid")
            rootfs = config_document.get("rootfs")
            diff_ids = rootfs.get("diff_ids") if isinstance(rootfs, dict) else None
            if (
                not isinstance(diff_ids, list)
                or not diff_ids
                or not all(
                    isinstance(item, str)
                    and re.fullmatch(r"sha256:[0-9a-f]{64}", item) is not None
                    for item in diff_ids
                )
            ):
                raise RefreshError("manager_archive_rootfs_invalid")
            config_contract = image_config_contract(
                config_document.get("config")
            )
            tags = docker_manifest[0].get("RepoTags")
            if (
                not isinstance(tags, list)
                or TARGET_MANAGER_IMAGE not in tags
            ):
                raise RefreshError("manager_archive_tag_binding_invalid")
            return {
                "config_digest": f"sha256:{config_hex}",
                "manifest_digest": descriptor,
                "rootfs_layers_sha256": canonical_sha256(diff_ids),
                "config_contract_sha256": canonical_sha256(config_contract),
            }
    except (OSError, UnicodeError, json.JSONDecodeError, tarfile.TarError) as error:
        raise RefreshError("manager_archive_identity_unreadable") from error


def manifest_file_set(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def validate_package(root: Path, expected_manifest_sha256: str) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / "manifest.json"
    if (
        root.is_symlink()
        or not root.is_dir()
        or manifest_path.is_symlink()
        or not manifest_path.is_file()
        or sha256_file(manifest_path) != expected_manifest_sha256
    ):
        raise RefreshError("package_manifest_binding_invalid")
    if manifest_file_set(root) != {
        "manifest.json",
        "greenhouse-manager-arm64.tar",
        "refresh-executor.py",
        "manager-python-distributions.json",
    }:
        raise RefreshError("package_file_set_invalid")
    manifest = read_json(manifest_path)
    authority = manifest.get("product_authority")
    policy = manifest.get("policy")
    if (
        manifest.get("schema") != PACKAGE_SCHEMA
        or not isinstance(authority, dict)
        or authority.get("predecessor_source") != PREDECESSOR_SOURCE
        or authority.get("target_source") != TARGET_SOURCE
        or authority.get("target_tree") != TARGET_TREE
        or authority.get("manager_discovery_blob")
        != "ac6e3f70879f980ee9a2d37938879dc6345a511e"
        or authority.get("dockerfile_blob")
        != "6486ff5fbcc23536676a48f36d67e4e0d364900a"
        or authority.get("compose_blob")
        != "c9038251d9ba1b05a472edda14b287470690815a"
        or authority.get("predecessor_candidate_ttl_seconds")
        != PREDECESSOR_CANDIDATE_TTL_SECONDS
        or authority.get("candidate_ttl_seconds")
        != EXPECTED_CANDIDATE_TTL_SECONDS
        or manifest.get("predecessor_manager_image")
        != PREDECESSOR_MANAGER_IMAGE
        or manifest.get("target_manager_image") != TARGET_MANAGER_IMAGE
        or not isinstance(policy, dict)
        or policy.get("secret_values_included") is not False
        or policy.get("registration_tls_included") is not False
        or policy.get("broker_image_included") is not False
        or policy.get("homeassistant_image_included") is not False
        or policy.get("live_authorization_granted") is not False
    ):
        raise RefreshError("package_contract_invalid")

    manager = manifest.get("manager")
    if not isinstance(manager, dict):
        raise RefreshError("manager_manifest_invalid")
    tar_path = root / str(manager.get("artifact_path", ""))
    if (
        tar_path.is_symlink()
        or not tar_path.is_file()
        or sha256_file(tar_path) != manager.get("sha256")
        or tar_path.stat().st_size != manager.get("size")
    ):
        raise RefreshError("manager_tar_binding_invalid")
    identity = archive_identity(tar_path)
    if (
        identity["config_digest"] != manager.get("archive_config_digest")
        or identity["manifest_digest"] != manager.get("archive_manifest_digest")
        or identity["rootfs_layers_sha256"]
        != manager.get("rootfs_layers_sha256")
        or identity["config_contract_sha256"]
        != manager.get("config_contract_sha256")
        or manager.get("platform") != "linux/arm64"
    ):
        raise RefreshError("manager_archive_binding_invalid")

    inventory = manager.get("python_distributions")
    if not isinstance(inventory, dict):
        raise RefreshError("python_distributions_manifest_invalid")
    inventory_path = root / str(inventory.get("artifact_path", ""))
    if (
        inventory_path.is_symlink()
        or not inventory_path.is_file()
        or sha256_file(inventory_path) != inventory.get("sha256")
        or inventory_path.stat().st_size != inventory.get("size")
    ):
        raise RefreshError("python_distributions_binding_invalid")
    try:
        distribution_document = json.loads(
            inventory_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RefreshError("python_distributions_json_invalid") from error
    if (
        not isinstance(distribution_document, list)
        or not distribution_document
        or len(distribution_document) != inventory.get("count")
        or not all(
            isinstance(item, dict)
            and set(item) == {"name", "version"}
            and isinstance(item["name"], str)
            and bool(item["name"])
            and isinstance(item["version"], str)
            and bool(item["version"])
            for item in distribution_document
        )
    ):
        raise RefreshError("python_distributions_contract_invalid")

    executor = manifest.get("executor")
    if not isinstance(executor, dict):
        raise RefreshError("executor_manifest_invalid")
    packaged_executor = root / str(executor.get("artifact_path", ""))
    if (
        packaged_executor.is_symlink()
        or not packaged_executor.is_file()
        or sha256_file(packaged_executor) != executor.get("sha256")
        or packaged_executor.stat().st_size != executor.get("size")
        or sha256_file(Path(__file__).resolve()) != executor.get("sha256")
    ):
        raise RefreshError("running_executor_binding_invalid")
    return manifest


def runtime_image_binding(manifest: dict[str, Any]) -> dict[str, str]:
    try:
        docs = json.loads(
            run(("docker", "image", "inspect", TARGET_MANAGER_IMAGE), timeout=30)
        )
    except json.JSONDecodeError as error:
        raise RefreshError("target_image_inspect_invalid") from error
    if (
        not isinstance(docs, list)
        or len(docs) != 1
        or not isinstance(docs[0], dict)
    ):
        raise RefreshError("target_image_inspect_invalid")
    item = docs[0]
    runtime_id = item.get("Id")
    if (
        not isinstance(runtime_id, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", runtime_id) is None
    ):
        raise RefreshError("target_image_runtime_id_invalid")
    if item.get("Architecture") != "arm64" or item.get("Os") != "linux":
        raise RefreshError("target_image_platform_invalid")
    rootfs = item.get("RootFS")
    layers = rootfs.get("Layers") if isinstance(rootfs, dict) else None
    if (
        not isinstance(layers, list)
        or not layers
        or not all(
            isinstance(layer, str)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", layer) is not None
            for layer in layers
        )
    ):
        raise RefreshError("target_image_rootfs_invalid")
    rootfs_hash = canonical_sha256(layers)
    config_hash = canonical_sha256(
        image_config_contract(item.get("Config"))
    )
    manager = manifest["manager"]
    if rootfs_hash != manager.get("rootfs_layers_sha256"):
        raise RefreshError("target_image_rootfs_binding_invalid")
    if config_hash != manager.get("config_contract_sha256"):
        raise RefreshError("target_image_config_binding_invalid")
    return {
        "runtime_id": runtime_id,
        "rootfs_layers_sha256": rootfs_hash,
        "config_contract_sha256": config_hash,
    }


def protected_runtime_snapshot() -> dict[str, Any]:
    return {
        "compose_file": file_binding(COMPOSE_FILE),
        "registration_cert": file_binding(REGISTRATION_CERT),
        "registration_key": file_binding(REGISTRATION_KEY),
        "broker_dynsec": file_binding(BROKER_DYNSEC),
        "f4_transaction": file_binding(F4_TRANSACTION),
        "predecessor_upgrade_transaction": file_binding(
            PREDECESSOR_UPGRADE_TRANSACTION
        ),
        "database": database_state(),
    }


def verify_prestate(manifest: dict[str, Any]) -> dict[str, Any]:
    if TRANSACTION.exists() or TRANSACTION.is_symlink():
        raise RefreshError("refresh_transaction_preexisting")
    if WORK_ROOT.exists() or WORK_ROOT.is_symlink():
        raise RefreshError("refresh_workspace_preexisting")

    services = service_state(SERVICES_UNIT)
    registration = service_state(REGISTRATION_UNIT)
    if (
        services["active"] != "active"
        or services["load"] != "loaded"
        or registration["active"] != "active"
        or registration["enabled"] != "enabled"
        or registration["load"] != "loaded"
    ):
        raise RefreshError("service_prestate_invalid")

    broker_doc = container("broker")
    manager_doc = container("manager")
    ha_doc = container("homeassistant")
    broker = container_snapshot(broker_doc)
    manager = container_snapshot(manager_doc)
    homeassistant = container_snapshot(ha_doc)

    if (
        broker["image"] != EXPECTED_BROKER_IMAGE
        or manager["image"] != PREDECESSOR_MANAGER_IMAGE
        or homeassistant["image"] != EXPECTED_HOMEASSISTANT_IMAGE
        or not broker["running"]
        or not manager["running"]
        or not homeassistant["running"]
    ):
        raise RefreshError("container_prestate_invalid")

    if docker_image_ids(TARGET_MANAGER_IMAGE):
        raise RefreshError("target_manager_image_preexisting")

    lines, env = parse_env(COMPOSE_ENV)
    if env.get("GH_MANAGER_IMAGE") != PREDECESSOR_MANAGER_IMAGE:
        raise RefreshError("compose_env_predecessor_drift")
    expected_target_env = manager_env_payload(
        lines,
        PREDECESSOR_MANAGER_IMAGE,
        TARGET_MANAGER_IMAGE,
    )

    protected = protected_runtime_snapshot()

    f4 = read_json(F4_TRANSACTION)
    if (
        f4.get("r10_candidate_upgrade_target_source") != PREDECESSOR_SOURCE
        or f4.get("r10_candidate_upgrade_authorization_claimed") is not True
        or f4.get("r10_candidate_upgrade_authorization_consumed") is not True
        or f4.get("r10_candidate_upgrade_replay_allowed") is not False
        or f4.get("r10_candidate_upgrade_committed") is not True
    ):
        raise RefreshError("f4_predecessor_authority_invalid")

    predecessor_upgrade = read_json(PREDECESSOR_UPGRADE_TRANSACTION)
    if (
        predecessor_upgrade.get("target_source") != PREDECESSOR_SOURCE
        or predecessor_upgrade.get("phase") != "COMMITTED"
        or predecessor_upgrade.get("status") != "PASS"
        or predecessor_upgrade.get("authorization_claimed") is not True
        or predecessor_upgrade.get("authorization_consumed") is not True
        or predecessor_upgrade.get("replay_allowed") is not False
        or predecessor_upgrade.get("committed") is not True
    ):
        raise RefreshError("candidate_upgrade_predecessor_authority_invalid")

    database = protected["database"]
    if (
        database["integrity"] != "ok"
        or database["current_registration_count"] != 1
        or database["attempt_count"] != 0
        or database["unresolved_first_registration"] != 0
    ):
        raise RefreshError("database_prestate_invalid")
    if (
        listener_count("tcp", 47110) != 1
        or listener_count("udp", 47111) != 1
        or listener_count("tcp", 47112) != 0
        or not pairing_window_closed(str(manager_doc["Id"]))
    ):
        raise RefreshError("registration_prestate_invalid")

    candidate_ttl_before = manager_candidate_ttl(str(manager_doc["Id"]))
    if candidate_ttl_before != PREDECESSOR_CANDIDATE_TTL_SECONDS:
        raise RefreshError("predecessor_candidate_ttl_not_30")

    return {
        "broker": broker,
        "manager": manager,
        "homeassistant": homeassistant,
        "protected": protected,
        "compose_env": file_binding(COMPOSE_ENV),
        "expected_target_env_sha256": sha256_bytes(expected_target_env),
        "candidate_ttl_before": candidate_ttl_before,
        "predecessor_f4_transaction_sha256": (
            protected["f4_transaction"]["sha256"]
        ),
        "predecessor_candidate_upgrade_transaction_sha256": (
            protected["predecessor_upgrade_transaction"]["sha256"]
        ),
    }


def create_workspace(authorization_id: str) -> Path:
    WORK_ROOT.mkdir(mode=0o700)
    workspace = WORK_ROOT / sha256_bytes(authorization_id.encode("utf-8"))[:16]
    workspace.mkdir(mode=0o700)
    return workspace


def claim_refresh(
    *,
    authorization_id: str,
    manifest_sha256: str,
    package_head: str,
    prestate: dict[str, Any],
) -> dict[str, Any]:
    if AUTHORIZATION_PATTERN.fullmatch(authorization_id) is None:
        raise RefreshError("authorization_id_invalid")
    document = {
        "schema": "gh.n3w.r10-manager-successor-refresh-transaction/1",
        "authorization_id": authorization_id,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "manifest_sha256": manifest_sha256,
        "package_head": package_head,
        "predecessor_source": PREDECESSOR_SOURCE,
        "target_source": TARGET_SOURCE,
        "predecessor_manager_image": PREDECESSOR_MANAGER_IMAGE,
        "target_manager_image": TARGET_MANAGER_IMAGE,
        "phase": "CLAIMED",
        "status": "CLAIMED",
        "prestate_fingerprint_sha256": canonical_sha256(prestate),
        "predecessor_f4_transaction_sha256": (
            prestate["predecessor_f4_transaction_sha256"]
        ),
        "predecessor_candidate_upgrade_transaction_sha256": (
            prestate["predecessor_candidate_upgrade_transaction_sha256"]
        ),
        "committed": False,
        "rollback_completed": False,
    }
    atomic_write_json(TRANSACTION, document, exclusive=True)
    return document


def advance(phase: str, **fields: Any) -> dict[str, Any]:
    document = read_json(TRANSACTION)
    document.update(fields)
    document["phase"] = phase
    document["status"] = (
        "PASS"
        if phase == "COMMITTED"
        else "ROLLED_BACK"
        if phase == "ROLLED_BACK"
        else "FAIL"
        if phase == "ROLLBACK_FAILED"
        else "CLAIMED"
    )
    atomic_write_json(TRANSACTION, document)
    return document


def load_target_manager(
    root: Path,
    manifest: dict[str, Any],
) -> dict[str, str]:
    manager = manifest["manager"]
    tar_path = root / str(manager["artifact_path"])
    run(("docker", "load", "-i", str(tar_path)), timeout=600)
    ids = docker_image_ids(TARGET_MANAGER_IMAGE)
    if len(ids) != 1:
        raise RefreshError("target_image_tag_count_invalid")
    binding = runtime_image_binding(manifest)
    if ids[0] != binding["runtime_id"]:
        raise RefreshError("target_image_local_store_binding_invalid")
    return binding


def assert_protected_unchanged(prestate: dict[str, Any]) -> dict[str, Any]:
    current = protected_runtime_snapshot()
    before = prestate["protected"]
    for key in (
        "compose_file",
        "registration_cert",
        "registration_key",
        "broker_dynsec",
        "f4_transaction",
        "predecessor_upgrade_transaction",
    ):
        if current[key] != before[key]:
            raise RefreshError(f"protected_runtime_changed:{key}")
    if current["database"] != before["database"]:
        raise RefreshError("manager_database_business_state_changed")
    return current


def strict_target_postcheck(
    prestate: dict[str, Any],
    manifest: dict[str, Any],
    *,
    expected_target_env_sha256: str,
) -> dict[str, Any]:
    if service_state(SERVICES_UNIT)["active"] != "active":
        raise RefreshError("services_not_active")
    broker_doc = container("broker")
    manager_doc = container("manager")
    ha_doc = container("homeassistant")
    broker = container_snapshot(broker_doc)
    manager = container_snapshot(manager_doc)
    homeassistant = container_snapshot(ha_doc)

    if broker != prestate["broker"]:
        raise RefreshError("broker_continuity_failed")
    if (
        homeassistant["id"] != prestate["homeassistant"]["id"]
        or homeassistant["image_id"] != prestate["homeassistant"]["image_id"]
        or homeassistant["image"] != prestate["homeassistant"]["image"]
        or not homeassistant["running"]
    ):
        raise RefreshError("homeassistant_continuity_failed")
    runtime_binding = runtime_image_binding(manifest)
    if (
        manager["image"] != TARGET_MANAGER_IMAGE
        or manager["image_id"] != runtime_binding["runtime_id"]
        or not manager["running"]
    ):
        raise RefreshError("target_manager_not_running")
    if sha256_file(COMPOSE_ENV) != expected_target_env_sha256:
        raise RefreshError("compose_env_target_binding_invalid")
    assert_protected_unchanged(prestate)
    if (
        listener_count("tcp", 47110) != 1
        or listener_count("udp", 47111) != 1
        or listener_count("tcp", 47112) != 0
        or not pairing_window_closed(str(manager_doc["Id"]))
    ):
        raise RefreshError("registration_postcheck_failed")
    ttl = manager_candidate_ttl(str(manager_doc["Id"]))
    if ttl != EXPECTED_CANDIDATE_TTL_SECONDS:
        raise RefreshError("manager_candidate_ttl_not_60")
    return {
        "broker": broker,
        "manager": manager,
        "homeassistant": homeassistant,
        "candidate_ttl": ttl,
    }


def wait_target_postcheck(
    prestate: dict[str, Any],
    manifest: dict[str, Any],
    *,
    expected_target_env_sha256: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + POSTCHECK_TIMEOUT_SECONDS
    last = "not_started"
    while True:
        try:
            return strict_target_postcheck(
                prestate,
                manifest,
                expected_target_env_sha256=expected_target_env_sha256,
            )
        except RefreshError as error:
            last = str(error)
            if last.startswith("protected_runtime_changed:") or last in {
                "manager_database_business_state_changed",
                "broker_continuity_failed",
                "homeassistant_continuity_failed",
                "compose_env_target_binding_invalid",
                "manager_candidate_ttl_not_60",
            }:
                raise
            if time.monotonic() >= deadline:
                raise RefreshError(
                    "target_postcheck_timeout:" + last
                ) from error
            time.sleep(POSTCHECK_POLL_SECONDS)


def strict_predecessor_postcheck(prestate: dict[str, Any]) -> None:
    if service_state(SERVICES_UNIT)["active"] != "active":
        raise RefreshError("rollback_services_not_active")
    broker_doc = container("broker")
    manager_doc = container("manager")
    ha_doc = container("homeassistant")
    broker = container_snapshot(broker_doc)
    manager = container_snapshot(manager_doc)
    homeassistant = container_snapshot(ha_doc)
    if broker != prestate["broker"]:
        raise RefreshError("rollback_broker_continuity_failed")
    if (
        homeassistant["id"] != prestate["homeassistant"]["id"]
        or homeassistant["image_id"] != prestate["homeassistant"]["image_id"]
        or homeassistant["image"] != prestate["homeassistant"]["image"]
        or not homeassistant["running"]
    ):
        raise RefreshError("rollback_homeassistant_continuity_failed")
    if (
        manager["image"] != PREDECESSOR_MANAGER_IMAGE
        or not manager["running"]
    ):
        raise RefreshError("rollback_manager_not_predecessor")
    assert_protected_unchanged(prestate)
    if (
        listener_count("tcp", 47110) != 1
        or listener_count("udp", 47111) != 1
        or listener_count("tcp", 47112) != 0
        or not pairing_window_closed(str(manager_doc["Id"]))
    ):
        raise RefreshError("rollback_registration_not_ready")
    if (
        manager_candidate_ttl(str(manager_doc["Id"]))
        != PREDECESSOR_CANDIDATE_TTL_SECONDS
    ):
        raise RefreshError("rollback_candidate_ttl_not_30")


def wait_predecessor_postcheck(prestate: dict[str, Any]) -> None:
    deadline = time.monotonic() + POSTCHECK_TIMEOUT_SECONDS
    last = "not_started"
    while True:
        try:
            strict_predecessor_postcheck(prestate)
            return
        except RefreshError as error:
            last = str(error)
            if last.startswith("protected_runtime_changed:") or last in {
                "manager_database_business_state_changed",
                "rollback_broker_continuity_failed",
                "rollback_homeassistant_continuity_failed",
            }:
                raise
            if time.monotonic() >= deadline:
                raise RefreshError(
                    "rollback_postcheck_timeout:" + last
                ) from error
            time.sleep(POSTCHECK_POLL_SECONDS)


def rollback(
    *,
    workspace: Path,
    prestate: dict[str, Any],
) -> None:
    errors: list[str] = []
    try:
        run(
            ("systemctl", "stop", SERVICES_UNIT),
            timeout=180,
            allowed=frozenset({0, 5}),
        )
    except Exception as error:
        errors.append("stop_services:" + type(error).__name__)
    try:
        backup = workspace / "docker-compose.env.pre"
        meta = prestate["compose_env"]
        atomic_write_bytes(
            COMPOSE_ENV,
            backup.read_bytes(),
            mode=int(meta["mode"]),
            uid=int(meta["uid"]),
            gid=int(meta["gid"]),
        )
    except Exception as error:
        errors.append("restore_env:" + type(error).__name__)
    try:
        run(("systemctl", "start", SERVICES_UNIT), timeout=240)
        wait_predecessor_postcheck(prestate)
    except Exception as error:
        errors.append("predecessor_runtime:" + type(error).__name__)
    try:
        run(
            ("docker", "image", "rm", TARGET_MANAGER_IMAGE),
            timeout=120,
            allowed=frozenset({0, 1}),
        )
    except Exception as error:
        errors.append("target_image_cleanup:" + type(error).__name__)
    if errors:
        advance(
            "ROLLBACK_FAILED",
            rollback_completed=False,
            rollback_error_classes=errors,
        )
        raise RefreshError("rollback_unproven")
    advance(
        "ROLLED_BACK",
        rollback_completed=True,
        committed=False,
    )


def execute_apply(
    *,
    package_root: Path,
    expected_manifest_sha256: str,
    authorization_id: str,
    confirmation: str,
) -> dict[str, Any]:
    require_root()
    if confirmation != CONFIRMATION:
        raise RefreshError("confirmation_invalid")
    manifest = validate_package(package_root, expected_manifest_sha256)
    prestate = verify_prestate(manifest)
    claim_refresh(
        authorization_id=authorization_id,
        manifest_sha256=expected_manifest_sha256,
        package_head=str(manifest["package_head"]),
        prestate=prestate,
    )

    workspace: Path | None = None
    rollback_required = True
    try:
        workspace = create_workspace(authorization_id)
        env_bytes = COMPOSE_ENV.read_bytes()
        env_meta = prestate["compose_env"]
        atomic_write_bytes(
            workspace / "docker-compose.env.pre",
            env_bytes,
            mode=0o600,
            uid=0,
            gid=0,
            exclusive=True,
        )
        advance("BACKUP_COMPLETE", env_backup_sha256=sha256_bytes(env_bytes))

        target_image_binding = load_target_manager(package_root, manifest)
        advance(
            "TARGET_IMAGE_LOADED",
            target_image_loaded=True,
            target_runtime_image_id=target_image_binding["runtime_id"],
            target_rootfs_layers_sha256=(
                target_image_binding["rootfs_layers_sha256"]
            ),
            target_config_contract_sha256=(
                target_image_binding["config_contract_sha256"]
            ),
        )

        run(("systemctl", "stop", SERVICES_UNIT), timeout=240)
        broker_after_stop = container_snapshot(container("broker"))
        if broker_after_stop != prestate["broker"]:
            raise RefreshError("broker_changed_during_services_stop")
        quiescent_db = database_state()
        if quiescent_db != prestate["protected"]["database"]:
            raise RefreshError("database_changed_before_refresh")
        advance("APPLICATION_STOPPED", application_stopped=True)

        lines, _env = parse_env(COMPOSE_ENV)
        target_env = manager_env_payload(
            lines,
            PREDECESSOR_MANAGER_IMAGE,
            TARGET_MANAGER_IMAGE,
        )
        atomic_write_bytes(
            COMPOSE_ENV,
            target_env,
            mode=int(env_meta["mode"]),
            uid=int(env_meta["uid"]),
            gid=int(env_meta["gid"]),
        )
        advance(
            "MANAGER_IMAGE_BOUND",
            compose_env_target_sha256=sha256_bytes(target_env),
        )

        run(("systemctl", "start", SERVICES_UNIT), timeout=240)
        post = wait_target_postcheck(
            prestate,
            manifest,
            expected_target_env_sha256=sha256_bytes(target_env),
        )
        advance(
            "COMMITTED",
            committed=True,
            rollback_completed=False,
            candidate_ttl_seconds=post["candidate_ttl"],
            broker_continuity=True,
            homeassistant_continuity=True,
            registration_tls_continuity=True,
            broker_dynsec_continuity=True,
            manager_database_business_state_continuity=True,
            pairing_window="CLOSED",
            tcp_47112_closed=True,
        )
        rollback_required = False
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "phase": "COMMITTED",
            "predecessor_source": PREDECESSOR_SOURCE,
            "target_source": TARGET_SOURCE,
            "target_manager_image": TARGET_MANAGER_IMAGE,
            "candidate_ttl_seconds": EXPECTED_CANDIDATE_TTL_SECONDS,
            "authorization_consumed": True,
            "board_access": False,
        }
    except Exception as apply_error:
        if TRANSACTION.exists() and not TRANSACTION.is_symlink():
            try:
                advance(
                    "ROLLBACK_STARTED",
                    apply_error_class=type(apply_error).__name__,
                    apply_error_reason=(
                        str(apply_error)[:240] or type(apply_error).__name__
                    ),
                )
            except Exception:
                pass
        if rollback_required and workspace is not None:
            try:
                rollback(workspace=workspace, prestate=prestate)
            except Exception as rollback_error:
                raise RefreshError(
                    "apply_failed:"
                    + (str(apply_error) or type(apply_error).__name__)
                    + ";rollback_failed:"
                    + (str(rollback_error) or type(rollback_error).__name__)
                ) from apply_error
        raise


def public_preflight(
    *,
    package_root: Path,
    expected_manifest_sha256: str,
) -> dict[str, Any]:
    require_root()
    manifest = validate_package(package_root, expected_manifest_sha256)
    prestate = verify_prestate(manifest)
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "mode": "READONLY_PREFLIGHT",
        "predecessor_source": PREDECESSOR_SOURCE,
        "target_source": TARGET_SOURCE,
        "predecessor_manager_image": PREDECESSOR_MANAGER_IMAGE,
        "target_manager_image": TARGET_MANAGER_IMAGE,
        "broker_continuity_eligible": True,
        "homeassistant_continuity_eligible": True,
        "database_integrity": prestate["protected"]["database"]["integrity"],
        "current_registration_count": (
            prestate["protected"]["database"]["current_registration_count"]
        ),
        "unresolved_first_registration": (
            prestate["protected"]["database"]["unresolved_first_registration"]
        ),
        "candidate_ttl_before": prestate["candidate_ttl_before"],
        "target_candidate_ttl": EXPECTED_CANDIDATE_TTL_SECONDS,
        "pairing_window": "CLOSED",
        "tcp_47112_closed": True,
        "live_authorization_claimed": False,
        "board_access": False,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--package-root", required=True)
    preflight.add_argument("--manifest-sha256", required=True)

    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--package-root", required=True)
    apply_parser.add_argument("--manifest-sha256", required=True)
    apply_parser.add_argument("--authorization-id", required=True)
    apply_parser.add_argument("--confirmation", required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "preflight":
            value = public_preflight(
                package_root=Path(args.package_root),
                expected_manifest_sha256=args.manifest_sha256,
            )
        else:
            value = execute_apply(
                package_root=Path(args.package_root),
                expected_manifest_sha256=args.manifest_sha256,
                authorization_id=args.authorization_id,
                confirmation=args.confirmation,
            )
        print(json.dumps(value, sort_keys=True))
        return 0
    except RefreshError as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error),
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
