from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import stat
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from greenhouse_manager.ops.t1_clean_service_credential_bundle import (
    create_clean_service_credential_bundle,
    verify_clean_service_credential_bundle,
)
from greenhouse_manager.runtime.dynsec_api import (
    CONTROL_TOPIC,
    RESPONSE_TOPIC,
    create_client_command,
    create_role_command,
)
from greenhouse_manager.runtime.service_identity_plan import (
    ServiceCredentials,
    ServiceIdentityPlan,
    build_service_identity_plan,
)

AUTHORIZATION_ID = "N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_APPLY_20261010_01"
SCHEMA = "gh.n3w-t1-s20-real-three-service-secret-handoff/1"
SYSTEM_ID = "greenhouse"
GENERATION = 1
SERVICES = ("provisioning", "manager", "homeassistant")
EXPECTED_ACL_COUNTS = {
    "provisioning": 10,
    "manager": 17,
    "homeassistant": 9,
}
EXPECTED_DEFAULTS = {
    "publishClientSend": False,
    "publishClientReceive": False,
    "subscribe": False,
    "unsubscribe": True,
}
EXPECTED_KERNEL = "6.18.26-ophub"
EXPECTED_ARCH = "aarch64"
EXPECTED_DOCKER_VERSION = "29.7.1"
EXPECTED_VOLUME_COUNT = 45
EXPECTED_VOLUME_SET_SHA256 = (
    "20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b"
)
EXPECTED_BROKER_CONFIG_SHA256 = (
    "3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6"
)
EXPECTED_DYNSEC_SHA256 = (
    "94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5"
)
EXPECTED_S18_BACKUP_SHA256 = (
    "93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da"
)
BROKER_SOURCE_TAG = "m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine"
EXPECTED_BROKER_INDEX_DIGEST = (
    "sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408"
)
EXPECTED_BROKER_ARM64_MANIFEST_DIGEST = (
    "sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549"
)
BROKER_IMAGE = BROKER_SOURCE_TAG
BROKER_CONFIG = Path("/etc/n3wfc4/mosquitto.conf")
DYNSEC_PATH = Path("/var/lib/n3wfc4-broker/dynamic-security.json")
DYNSEC_DATA = Path("/var/lib/n3wfc4-broker")
S18_BACKUP = Path("/etc/n3wfc4/private/dynsec-s18-pre-receive-deny.json")
ADMIN_PASSWORD = Path("/etc/n3wfc4/private/dynsec-admin-password")
TLS_DIR = Path("/etc/n3wfc4/tls")
ROLLBACK_SNAPSHOT = Path(
    "/etc/n3wfc4/private/dynsec-s20-pre-three-service.json"
)
SECRET_PARENT = Path("/opt/greenhouse-secrets")
SECRET_ROOT = SECRET_PARENT / "mqtt"
TRANSACTION_DIR = Path("/etc/n3wfc4/private/.s20-three-service-transaction")
CONTAINER_NAME = "n3w-s20-three-service-transaction"
NETWORKS = ("n3wfc4-private", "n3wfc4-services")


class S20ServiceHandoffError(RuntimeError):
    pass


class CommandRunner:
    def run(
        self,
        command: Sequence[str],
        *,
        input_text: str | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, str]:
        completed = subprocess.run(
            tuple(command),
            input=input_text,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return completed.returncode, completed.stdout


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _plans() -> dict[str, ServiceIdentityPlan]:
    result: dict[str, ServiceIdentityPlan] = {}
    for service in SERVICES:
        plan = build_service_identity_plan(
            system_id=SYSTEM_ID,
            service=service,  # type: ignore[arg-type]
            generation=GENERATION,
        )
        if len(plan.acls) != EXPECTED_ACL_COUNTS[service]:
            raise S20ServiceHandoffError("service_acl_count_drift")
        result[service] = plan
    return result


def _run_required(
    runner: CommandRunner,
    command: Sequence[str],
    label: str,
    *,
    input_text: str | None = None,
    timeout: float = 30.0,
) -> str:
    try:
        return_code, output = runner.run(
            command,
            input_text=input_text,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise S20ServiceHandoffError(label) from error
    if return_code != 0:
        raise S20ServiceHandoffError(label)
    return output


def _load_dynsec(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise S20ServiceHandoffError("dynsec_state_unsafe")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise S20ServiceHandoffError("dynsec_state_invalid") from error
    if not isinstance(document, dict):
        raise S20ServiceHandoffError("dynsec_state_invalid")
    return document


def _names(
    document: dict[str, Any],
    collection: str,
    field: str,
) -> set[str]:
    values = document.get(collection)
    if not isinstance(values, list):
        raise S20ServiceHandoffError(f"dynsec_{collection}_invalid")
    result: set[str] = set()
    for value in values:
        if not isinstance(value, dict):
            raise S20ServiceHandoffError(f"dynsec_{collection}_invalid")
        name = value.get(field)
        if not isinstance(name, str) or not name or name in result:
            raise S20ServiceHandoffError(f"dynsec_{collection}_invalid")
        result.add(name)
    return result


def validate_preclaim_dynsec(document: dict[str, Any]) -> dict[str, object]:
    defaults = document.get("defaultACLAccess")
    if defaults != EXPECTED_DEFAULTS:
        raise S20ServiceHandoffError("dynsec_default_acl_drift")
    clients = document.get("clients")
    roles = document.get("roles")
    if not isinstance(clients, list) or not isinstance(roles, list):
        raise S20ServiceHandoffError("dynsec_inventory_invalid")
    usernames = _names(document, "clients", "username")
    role_names = _names(document, "roles", "rolename")
    plans = _plans()
    target_usernames = {plan.username for plan in plans.values()}
    target_roles = {plan.role_name for plan in plans.values()}
    if target_usernames & usernames or target_roles & role_names:
        raise S20ServiceHandoffError("target_service_identity_already_present")
    if usernames != {"admin"}:
        raise S20ServiceHandoffError("preclaim_client_inventory_not_admin_only")
    if any(name.startswith("ghn_") for name in usernames):
        raise S20ServiceHandoffError("node_identity_present")
    return {
        "client_count": len(usernames),
        "target_service_clients_absent": True,
        "target_service_roles_absent": True,
        "node_clients_absent": True,
        "default_acl_baseline": True,
    }


def validate_applied_dynsec(document: dict[str, Any]) -> dict[str, object]:
    if document.get("defaultACLAccess") != EXPECTED_DEFAULTS:
        raise S20ServiceHandoffError("postapply_default_acl_drift")
    clients_raw = document.get("clients")
    roles_raw = document.get("roles")
    if not isinstance(clients_raw, list) or not isinstance(roles_raw, list):
        raise S20ServiceHandoffError("postapply_inventory_invalid")
    clients = {
        item.get("username"): item
        for item in clients_raw
        if isinstance(item, dict) and isinstance(item.get("username"), str)
    }
    roles = {
        item.get("rolename"): item
        for item in roles_raw
        if isinstance(item, dict) and isinstance(item.get("rolename"), str)
    }
    plans = _plans()
    expected_users = {"admin", *(plan.username for plan in plans.values())}
    if set(clients) != expected_users:
        raise S20ServiceHandoffError("postapply_client_set_invalid")
    if any(name.startswith("ghn_") for name in clients):
        raise S20ServiceHandoffError("postapply_node_identity_present")
    for service, plan in plans.items():
        client = clients.get(plan.username)
        role = roles.get(plan.role_name)
        if not isinstance(client, dict) or not isinstance(role, dict):
            raise S20ServiceHandoffError("postapply_service_binding_missing")
        if client.get("clientid") != plan.client_id:
            raise S20ServiceHandoffError("postapply_client_id_drift")
        bindings = client.get("roles")
        if not isinstance(bindings, list) or {
            item.get("rolename")
            for item in bindings
            if isinstance(item, dict)
        } != {plan.role_name}:
            raise S20ServiceHandoffError("postapply_role_binding_drift")
        raw_acls = role.get("acls")
        if not isinstance(raw_acls, list) or len(raw_acls) != EXPECTED_ACL_COUNTS[service]:
            raise S20ServiceHandoffError("postapply_acl_count_drift")
        expected_acls = {
            (acl.acl_type, acl.topic, acl.allow, acl.priority)
            for acl in plan.acls
        }
        actual_acls = {
            (
                item.get("acltype"),
                item.get("topic"),
                item.get("allow"),
                item.get("priority"),
            )
            for item in raw_acls
            if isinstance(item, dict)
        }
        if actual_acls != expected_acls:
            raise S20ServiceHandoffError("postapply_acl_drift")
    return {
        "service_client_count": 3,
        "service_role_count": 3,
        "node_client_created": False,
        "default_acl_baseline_unchanged": True,
        "acl_counts": dict(EXPECTED_ACL_COUNTS),
    }


def _safe_private_file(path: Path, *, uid: int, mode: int) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    info = path.stat()
    return info.st_uid == uid and stat.S_IMODE(info.st_mode) == mode


def _listener_count(output: str, port: int) -> int:
    count = 0
    suffix = f":{port}"
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[3].endswith(suffix):
            count += 1
    return count


def _volume_set(runner: CommandRunner) -> tuple[int, str]:
    output = _run_required(
        runner,
        ("docker", "volume", "ls", "-q"),
        "docker_volume_inventory_failed",
    )
    names = sorted(line.strip() for line in output.splitlines() if line.strip())
    payload = "".join(f"{name}\n" for name in names).encode("utf-8")
    return len(names), _sha256_bytes(payload)


def _network_count(runner: CommandRunner, name: str) -> int:
    output = _run_required(
        runner,
        (
            "docker",
            "network",
            "inspect",
            "-f",
            "{{len .Containers}}",
            name,
        ),
        "docker_network_inventory_failed",
    ).strip()
    if not output.isdigit():
        raise S20ServiceHandoffError("docker_network_inventory_invalid")
    return int(output)


def _guard_contract(runner: CommandRunner) -> dict[str, object]:
    active = _run_required(
        runner,
        ("systemctl", "is-active", "n3wfc4-broker-ingress-guard.service"),
        "guard_not_active",
    ).strip()
    enabled = _run_required(
        runner,
        ("systemctl", "is-enabled", "n3wfc4-broker-ingress-guard.service"),
        "guard_not_enabled",
    ).strip()
    input_rules = _run_required(
        runner,
        ("iptables", "-S", "INPUT"),
        "iptables_input_read_failed",
    ).splitlines()
    docker_rules = _run_required(
        runner,
        ("iptables", "-S", "DOCKER-USER"),
        "iptables_docker_user_read_failed",
    ).splitlines()
    ingress_rules = _run_required(
        runner,
        ("iptables", "-S", "N3WFC4-BROKER-INGRESS"),
        "iptables_ingress_read_failed",
    ).splitlines()
    input_appends = [line for line in input_rules if line.startswith("-A INPUT ")]
    docker_appends = [
        line for line in docker_rules if line.startswith("-A DOCKER-USER ")
    ]
    ingress_appends = [
        line
        for line in ingress_rules
        if line.startswith("-A N3WFC4-BROKER-INGRESS ")
    ]
    if active != "active" or enabled != "enabled":
        raise S20ServiceHandoffError("guard_state_drift")
    if not input_appends or "-j N3WFC4-BROKER-INGRESS" not in input_appends[0]:
        raise S20ServiceHandoffError("input_first_jump_drift")
    if not docker_appends or "-j N3WFC4-BROKER-INGRESS" not in docker_appends[0]:
        raise S20ServiceHandoffError("docker_user_first_jump_drift")
    if sum("-j N3WFC4-BROKER-INGRESS" in line for line in input_appends) != 1:
        raise S20ServiceHandoffError("input_anchor_count_drift")
    if sum("-j N3WFC4-BROKER-INGRESS" in line for line in docker_appends) != 1:
        raise S20ServiceHandoffError("docker_user_anchor_count_drift")
    if not ingress_appends or not ingress_appends[-1].endswith("-j DROP"):
        raise S20ServiceHandoffError("guard_last_drop_drift")
    return {
        "active": True,
        "enabled": True,
        "input_first_jump": True,
        "docker_user_first_jump": True,
        "terminal_drop": True,
    }


def _verify_broker_source_tag(
    runner: CommandRunner,
) -> dict[str, str]:
    image = _run_required(
        runner,
        (
            "docker",
            "image",
            "inspect",
            "--format",
            "{{.Id}}|{{.Os}}|{{.Architecture}}|{{json .RepoDigests}}",
            BROKER_SOURCE_TAG,
        ),
        "exact_broker_image_unavailable",
    ).strip()
    fields = image.split("|", 3)
    if len(fields) != 4:
        raise S20ServiceHandoffError("exact_broker_image_inspect_invalid")
    image_id, image_os, architecture, repo_digests_raw = fields
    if image_os != "linux" or architecture != "arm64":
        raise S20ServiceHandoffError("exact_broker_image_platform_drift")
    try:
        repo_digests = json.loads(repo_digests_raw)
    except json.JSONDecodeError as error:
        raise S20ServiceHandoffError(
            "exact_broker_image_repo_digest_invalid"
        ) from error
    expected_repo_digest = (
        "m.daocloud.io/docker.io/library/eclipse-mosquitto@"
        f"{EXPECTED_BROKER_INDEX_DIGEST}"
    )
    if (
        not isinstance(repo_digests, list)
        or expected_repo_digest not in repo_digests
    ):
        raise S20ServiceHandoffError("exact_broker_image_index_digest_drift")
    if not image_id.startswith("sha256:"):
        raise S20ServiceHandoffError("exact_broker_image_id_invalid")
    return {
        "image_id": image_id,
        "platform": "linux/arm64",
        "index_digest": EXPECTED_BROKER_INDEX_DIGEST,
        "arm64_manifest_digest": EXPECTED_BROKER_ARM64_MANIFEST_DIGEST,
    }


def build_preclaim_report(
    runner: CommandRunner,
    *,
    executor_path: Path | None = None,
    expected_executor_sha256: str | None = None,
) -> dict[str, object]:
    if os.geteuid() != 0:
        raise S20ServiceHandoffError("root_required")
    if (
        expected_executor_sha256 is not None
        and (
            executor_path is None
            or _sha256_path(executor_path) != expected_executor_sha256
        )
    ):
        raise S20ServiceHandoffError("executor_sha256_mismatch")
    if _run_required(runner, ("uname", "-m"), "uname_arch_failed").strip() != EXPECTED_ARCH:
        raise S20ServiceHandoffError("arch_drift")
    if _run_required(runner, ("uname", "-r"), "uname_kernel_failed").strip() != EXPECTED_KERNEL:
        raise S20ServiceHandoffError("kernel_drift")
    docker_version = _run_required(
        runner,
        ("docker", "version", "--format", "{{.Server.Version}}"),
        "docker_version_failed",
    ).strip()
    if docker_version != EXPECTED_DOCKER_VERSION:
        raise S20ServiceHandoffError("docker_version_drift")
    containers = [
        line
        for line in _run_required(
            runner,
            ("docker", "ps", "-aq"),
            "docker_container_inventory_failed",
        ).splitlines()
        if line.strip()
    ]
    if containers:
        raise S20ServiceHandoffError("docker_container_count_drift")
    volume_count, volume_sha = _volume_set(runner)
    if (
        volume_count != EXPECTED_VOLUME_COUNT
        or volume_sha != EXPECTED_VOLUME_SET_SHA256
    ):
        raise S20ServiceHandoffError("docker_volume_set_drift")
    network_counts = {name: _network_count(runner, name) for name in NETWORKS}
    if any(network_counts.values()):
        raise S20ServiceHandoffError("project_network_not_empty")
    guard = _guard_contract(runner)
    listeners = _run_required(
        runner,
        ("ss", "-H", "-ltn"),
        "listener_inventory_failed",
    )
    listener_counts = {
        port: _listener_count(listeners, port)
        for port in (1883, 8883, 18883)
    }
    if any(listener_counts.values()):
        raise S20ServiceHandoffError("mqtt_host_listener_present")
    if _sha256_path(BROKER_CONFIG) != EXPECTED_BROKER_CONFIG_SHA256:
        raise S20ServiceHandoffError("broker_config_sha_drift")
    if _sha256_path(DYNSEC_PATH) != EXPECTED_DYNSEC_SHA256:
        raise S20ServiceHandoffError("dynsec_sha_drift")
    if _sha256_path(S18_BACKUP) != EXPECTED_S18_BACKUP_SHA256:
        raise S20ServiceHandoffError("s18_backup_sha_drift")
    dynsec_info = DYNSEC_PATH.stat()
    if (
        dynsec_info.st_uid != 1883
        or dynsec_info.st_gid != 1883
        or stat.S_IMODE(dynsec_info.st_mode) != 0o600
    ):
        raise S20ServiceHandoffError("dynsec_owner_mode_drift")
    if not _safe_private_file(ADMIN_PASSWORD, uid=0, mode=0o600):
        raise S20ServiceHandoffError("admin_password_file_unsafe")
    if SECRET_ROOT.exists() or SECRET_ROOT.is_symlink():
        raise S20ServiceHandoffError("production_secret_destination_exists")
    secret_parent_state = "absent"
    if SECRET_PARENT.exists() or SECRET_PARENT.is_symlink():
        if SECRET_PARENT.is_symlink() or not SECRET_PARENT.is_dir():
            raise S20ServiceHandoffError("production_secret_parent_unsafe")
        parent_info = SECRET_PARENT.stat()
        if (
            parent_info.st_uid != 0
            or parent_info.st_gid != 0
            or stat.S_IMODE(parent_info.st_mode) != 0o700
        ):
            raise S20ServiceHandoffError("production_secret_parent_unsafe")
        secret_parent_state = "safe_existing"
    if ROLLBACK_SNAPSHOT.exists() or ROLLBACK_SNAPSHOT.is_symlink():
        raise S20ServiceHandoffError("s20_rollback_snapshot_exists")
    if TRANSACTION_DIR.exists() or TRANSACTION_DIR.is_symlink():
        raise S20ServiceHandoffError("transaction_directory_exists")
    dynsec = validate_preclaim_dynsec(_load_dynsec(DYNSEC_PATH))
    broker_image = _verify_broker_source_tag(runner)
    return {
        "schema": SCHEMA,
        "phase": "preclaim",
        "status": "PASS",
        "authorization_id": AUTHORIZATION_ID,
        "executor_bound": expected_executor_sha256 is not None,
        "docker_container_count": 0,
        "docker_volume_count": volume_count,
        "docker_volume_set_sha256": volume_sha,
        "project_network_container_counts": network_counts,
        "guard": guard,
        "host_listener_counts": {
            str(port): count for port, count in listener_counts.items()
        },
        "broker_config_sha_match": True,
        "dynsec_sha_match": True,
        "s18_backup_sha_match": True,
        "dynsec_inventory": dynsec,
        "secret_destination_absent": True,
        "secret_parent_state": secret_parent_state,
        "rollback_snapshot_absent": True,
        "exact_broker_image_local_arm64": True,
        "broker_image": broker_image,
        "live_mutation": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "board_access": False,
    }


def _write_private(path: Path, value: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    os.chmod(path, 0o600)


def _create_snapshot() -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(ROLLBACK_SNAPSHOT, flags, 0o600)
    try:
        with DYNSEC_PATH.open("rb") as source, os.fdopen(
            descriptor, "wb"
        ) as target:
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
    except Exception:
        ROLLBACK_SNAPSHOT.unlink(missing_ok=True)
        raise
    os.chown(ROLLBACK_SNAPSHOT, 0, 0)
    os.chmod(ROLLBACK_SNAPSHOT, 0o600)
    if _sha256_path(ROLLBACK_SNAPSHOT) != EXPECTED_DYNSEC_SHA256:
        raise S20ServiceHandoffError("rollback_snapshot_sha_mismatch")


def _read_password(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise S20ServiceHandoffError("credential_file_unsafe")
    value = path.read_text(encoding="utf-8").rstrip("\r\n")
    if not value:
        raise S20ServiceHandoffError("credential_file_empty")
    return value


def _client_config(
    *,
    username: str,
    password: str,
    client_id: str | None,
) -> str:
    lines = [
        "-h 127.0.0.1",
        "-p 1883",
        f"-u {username}",
        f"-P {password}",
        "-V 5",
    ]
    if client_id is not None:
        lines.append(f"-i {client_id}")
    return "\n".join(lines) + "\n"


def _prepare_transaction_material() -> dict[str, ServiceIdentityPlan]:
    TRANSACTION_DIR.mkdir(mode=0o700)
    os.chown(TRANSACTION_DIR, 0, 0)
    os.chmod(TRANSACTION_DIR, 0o700)
    if SECRET_PARENT.exists() or SECRET_PARENT.is_symlink():
        if SECRET_PARENT.is_symlink() or not SECRET_PARENT.is_dir():
            raise S20ServiceHandoffError("production_secret_parent_unsafe")
        parent_info = SECRET_PARENT.stat()
        if (
            parent_info.st_uid != 0
            or parent_info.st_gid != 0
            or stat.S_IMODE(parent_info.st_mode) != 0o700
        ):
            raise S20ServiceHandoffError("production_secret_parent_unsafe")
        _write_private(TRANSACTION_DIR / "parent-preexisting", "true\n")
    else:
        _write_private(TRANSACTION_DIR / "parent-was-absent", "true\n")
        SECRET_PARENT.mkdir(mode=0o700)
        os.chown(SECRET_PARENT, 0, 0)
        os.chmod(SECRET_PARENT, 0o700)
    create_clean_service_credential_bundle(
        SECRET_ROOT,
        system_id=SYSTEM_ID,
        generation=GENERATION,
    )
    verify_clean_service_credential_bundle(SECRET_ROOT)
    os.chown(SECRET_ROOT / "manager/password", 999, 999)
    os.chown(SECRET_ROOT / "provisioning/password", 999, 999)
    admin_password = _read_password(ADMIN_PASSWORD)
    _write_private(
        TRANSACTION_DIR / "admin.conf",
        _client_config(
            username="admin",
            password=admin_password,
            client_id=None,
        ),
    )
    plans = _plans()
    for service, plan in plans.items():
        password = _read_password(SECRET_ROOT / service / "password")
        _write_private(
            TRANSACTION_DIR / f"{service}.conf",
            _client_config(
                username=plan.username,
                password=password,
                client_id=plan.client_id,
            ),
        )
        _write_private(
            TRANSACTION_DIR / f"{service}-wrong.conf",
            _client_config(
                username=plan.username,
                password=password,
                client_id=f"{plan.client_id}-wrong",
            ),
        )
    return plans


def _docker_mount(source: Path, target: str, *, read_only: bool) -> str:
    suffix = ":ro" if read_only else ""
    return f"{source}:{target}{suffix}"


def _start_broker(runner: CommandRunner) -> None:
    _verify_broker_source_tag(runner)
    command = (
        "docker",
        "run",
        "-d",
        "--rm",
        "--pull",
        "never",
        "--name",
        CONTAINER_NAME,
        "--network",
        "none",
        "--user",
        "1883:1883",
        "-v",
        _docker_mount(
            BROKER_CONFIG,
            "/mosquitto/config/mosquitto.conf",
            read_only=True,
        ),
        "-v",
        _docker_mount(DYNSEC_DATA, "/mosquitto/data", read_only=False),
        "-v",
        _docker_mount(TLS_DIR, "/mosquitto/tls", read_only=True),
        "-v",
        _docker_mount(TRANSACTION_DIR, "/run/n3w-s20", read_only=True),
        BROKER_IMAGE,
    )
    _run_required(runner, command, "transaction_broker_start_failed", timeout=60)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            _rr(
                runner,
                ({"command": "listClients"},),
                "/run/n3w-s20/admin.conf",
                timeout=3,
            )
            return
        except S20ServiceHandoffError:
            time.sleep(0.5)
    raise S20ServiceHandoffError("transaction_broker_not_ready")


def _stop_broker(runner: CommandRunner) -> None:
    return_code, _output = runner.run(
        ("docker", "rm", "-f", CONTAINER_NAME),
        timeout=30,
    )
    if return_code not in (0, 1):
        raise S20ServiceHandoffError("transaction_broker_remove_failed")


def _rr(
    runner: CommandRunner,
    commands: Sequence[dict[str, Any]],
    config_path: str,
    *,
    timeout: float = 10,
) -> tuple[dict[str, Any], ...]:
    payload = json.dumps(
        {"commands": list(commands)},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    output = _run_required(
        runner,
        (
            "docker",
            "exec",
            "-i",
            CONTAINER_NAME,
            "mosquitto_rr",
            "-o",
            config_path,
            "-q",
            "1",
            "-W",
            str(int(timeout)),
            "-t",
            CONTROL_TOPIC,
            "-e",
            RESPONSE_TOPIC,
            "-s",
        ),
        "dynsec_request_failed",
        input_text=payload,
        timeout=timeout + 5,
    )
    try:
        document = json.loads(output)
    except json.JSONDecodeError as error:
        raise S20ServiceHandoffError("dynsec_response_invalid") from error
    responses = document.get("responses") if isinstance(document, dict) else None
    if not isinstance(responses, list) or len(responses) != len(commands):
        raise S20ServiceHandoffError("dynsec_response_invalid")
    for response in responses:
        if not isinstance(response, dict) or response.get("error"):
            raise S20ServiceHandoffError("dynsec_command_rejected")
    return tuple(responses)


def _mqtt_action(
    runner: CommandRunner,
    service: str,
    config_path: str,
) -> bool:
    if service == "provisioning":
        try:
            _rr(
                runner,
                ({"command": "listClients"},),
                config_path,
                timeout=4,
            )
        except S20ServiceHandoffError:
            return False
        return True
    if service == "manager":
        topic = "gh/v1/greenhouse/state/s20-credential-probe/telemetry"
    else:
        topic = "homeassistant/status"
    return_code, _output = runner.run(
        (
            "docker",
            "exec",
            CONTAINER_NAME,
            "mosquitto_pub",
            "-o",
            config_path,
            "-q",
            "1",
            "-t",
            topic,
            "-m",
            f"s20-{service}-probe",
        ),
        timeout=10,
    )
    return return_code == 0


def _verify_authentication(
    runner: CommandRunner,
    plans: dict[str, ServiceIdentityPlan],
) -> None:
    for service in plans:
        if not _mqtt_action(
            runner,
            service,
            f"/run/n3w-s20/{service}.conf",
        ):
            raise S20ServiceHandoffError("service_positive_auth_failed")
        if _mqtt_action(
            runner,
            service,
            f"/run/n3w-s20/{service}-wrong.conf",
        ):
            raise S20ServiceHandoffError("wrong_client_id_accepted")
    return_code, _output = runner.run(
        (
            "docker",
            "exec",
            CONTAINER_NAME,
            "mosquitto_pub",
            "-h",
            "127.0.0.1",
            "-p",
            "1883",
            "-V",
            "5",
            "-q",
            "1",
            "-t",
            "gh/s20/anonymous-probe",
            "-m",
            "anonymous-probe",
        ),
        timeout=10,
    )
    if return_code == 0:
        raise S20ServiceHandoffError("anonymous_connection_accepted")


def _apply_dynsec(
    runner: CommandRunner,
    plans: dict[str, ServiceIdentityPlan],
) -> None:
    document = _load_dynsec(DYNSEC_PATH)
    validate_preclaim_dynsec(document)
    for service in SERVICES:
        plan = plans[service]
        password = _read_password(SECRET_ROOT / service / "password")
        credentials = ServiceCredentials(
            username=plan.username,
            client_id=plan.client_id,
            generation=plan.generation,
            password=password,
        )
        _rr(
            runner,
            (create_role_command(plan),),
            "/run/n3w-s20/admin.conf",
        )
        _rr(
            runner,
            (create_client_command(plan, credentials),),
            "/run/n3w-s20/admin.conf",
        )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            validate_applied_dynsec(_load_dynsec(DYNSEC_PATH))
            return
        except S20ServiceHandoffError:
            time.sleep(0.25)
    raise S20ServiceHandoffError("postapply_dynsec_state_not_stable")


def _restore_snapshot() -> None:
    if not ROLLBACK_SNAPSHOT.is_file() or ROLLBACK_SNAPSHOT.is_symlink():
        raise S20ServiceHandoffError("rollback_snapshot_unavailable")
    temporary = DYNSEC_PATH.with_name(".dynamic-security.s20-rollback.tmp")
    temporary.unlink(missing_ok=True)
    with ROLLBACK_SNAPSHOT.open("rb") as source, temporary.open(
        "xb"
    ) as target:
        shutil.copyfileobj(source, target)
        target.flush()
        os.fsync(target.fileno())
    os.chown(temporary, 1883, 1883)
    os.chmod(temporary, 0o600)
    os.replace(temporary, DYNSEC_PATH)
    descriptor = os.open(DYNSEC_PATH.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if _sha256_path(DYNSEC_PATH) != EXPECTED_DYNSEC_SHA256:
        raise S20ServiceHandoffError("rollback_dynsec_sha_mismatch")


def _cleanup_transaction_material(*, remove_bundle: bool) -> None:
    parent_was_absent = (
        TRANSACTION_DIR / "parent-was-absent"
    ).is_file()
    if remove_bundle:
        shutil.rmtree(SECRET_ROOT, ignore_errors=True)
        if parent_was_absent and SECRET_PARENT.is_dir():
            with contextlib.suppress(OSError):
                SECRET_PARENT.rmdir()
    shutil.rmtree(TRANSACTION_DIR, ignore_errors=True)


def _bundle_owner_mode() -> dict[str, str]:
    expected = {
        "manager": (SECRET_ROOT / "manager/password", 999, 999),
        "provisioning": (
            SECRET_ROOT / "provisioning/password",
            999,
            999,
        ),
        "homeassistant": (
            SECRET_ROOT / "homeassistant/password",
            0,
            0,
        ),
        "homeassistant_bootstrap": (
            SECRET_ROOT / "homeassistant/mqtt-bootstrap.json",
            0,
            0,
        ),
    }
    result: dict[str, str] = {}
    for label, (path, uid, gid) in expected.items():
        info = path.stat()
        mode = stat.S_IMODE(info.st_mode)
        if path.is_symlink() or (info.st_uid, info.st_gid, mode) != (
            uid,
            gid,
            0o600,
        ):
            raise S20ServiceHandoffError("credential_owner_mode_invalid")
        result[label] = f"{uid}:{gid}:600"
    return result


def _postcheck(runner: CommandRunner) -> dict[str, object]:
    containers = [
        line
        for line in _run_required(
            runner,
            ("docker", "ps", "-aq"),
            "postcheck_container_inventory_failed",
        ).splitlines()
        if line.strip()
    ]
    if containers:
        raise S20ServiceHandoffError("postcheck_container_present")
    volume_count, volume_sha = _volume_set(runner)
    if (
        volume_count != EXPECTED_VOLUME_COUNT
        or volume_sha != EXPECTED_VOLUME_SET_SHA256
    ):
        raise S20ServiceHandoffError("postcheck_volume_set_drift")
    network_counts = {name: _network_count(runner, name) for name in NETWORKS}
    if any(network_counts.values()):
        raise S20ServiceHandoffError("postcheck_network_not_empty")
    guard = _guard_contract(runner)
    listeners = _run_required(
        runner,
        ("ss", "-H", "-ltn"),
        "postcheck_listener_inventory_failed",
    )
    counts = {
        port: _listener_count(listeners, port)
        for port in (1883, 8883, 18883)
    }
    if any(counts.values()):
        raise S20ServiceHandoffError("postcheck_mqtt_listener_present")
    dynsec_sha = _sha256_path(DYNSEC_PATH)
    if dynsec_sha == EXPECTED_DYNSEC_SHA256:
        raise S20ServiceHandoffError("postcheck_dynsec_not_changed")
    validate_applied_dynsec(_load_dynsec(DYNSEC_PATH))
    info = DYNSEC_PATH.stat()
    if (
        info.st_uid != 1883
        or info.st_gid != 1883
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise S20ServiceHandoffError("postcheck_dynsec_owner_mode_invalid")
    return {
        "docker_container_count": 0,
        "docker_volume_count": volume_count,
        "docker_volume_set_sha256": volume_sha,
        "project_network_container_counts": network_counts,
        "guard": guard,
        "host_listener_counts": {
            str(port): count for port, count in counts.items()
        },
        "dynsec_sha256": dynsec_sha,
        "credential_owner_mode": _bundle_owner_mode(),
    }


class LocalTransactionRuntime:
    def __init__(
        self,
        runner: CommandRunner,
        *,
        executor_path: Path,
        expected_executor_sha256: str,
    ) -> None:
        self.runner = runner
        self.executor_path = executor_path
        self.expected_executor_sha256 = expected_executor_sha256

    def preclaim(self) -> dict[str, object]:
        return build_preclaim_report(
            self.runner,
            executor_path=self.executor_path,
            expected_executor_sha256=self.expected_executor_sha256,
        )

    def create_snapshot(self) -> None:
        _create_snapshot()

    def create_material(self) -> dict[str, ServiceIdentityPlan]:
        return _prepare_transaction_material()

    def start_broker(self) -> None:
        _start_broker(self.runner)

    def apply_and_verify(
        self,
        plans: dict[str, ServiceIdentityPlan],
    ) -> None:
        _apply_dynsec(self.runner, plans)
        _verify_authentication(self.runner, plans)

    def stop_broker(self) -> None:
        _stop_broker(self.runner)

    def finish(self) -> dict[str, object]:
        _cleanup_transaction_material(remove_bundle=False)
        return _postcheck(self.runner)

    def rollback(self) -> None:
        with contextlib.suppress(S20ServiceHandoffError):
            _stop_broker(self.runner)
        _restore_snapshot()
        _cleanup_transaction_material(remove_bundle=True)


def execute_apply(
    runtime: LocalTransactionRuntime,
    *,
    authorization_id: str,
    emit: Callable[[str], None] = print,
) -> dict[str, object]:
    if authorization_id != AUTHORIZATION_ID:
        raise S20ServiceHandoffError("authorization_id_invalid")
    preclaim = runtime.preclaim()
    if preclaim.get("status") != "PASS":
        raise S20ServiceHandoffError("preclaim_not_pass")
    emit("AUTHORIZATION_CLAIMED=true")
    claimed = True
    try:
        runtime.create_snapshot()
        plans = runtime.create_material()
        runtime.start_broker()
        runtime.apply_and_verify(plans)
        runtime.stop_broker()
        postcheck = runtime.finish()
    except Exception as error:
        try:
            runtime.rollback()
        except Exception as rollback_error:
            raise S20ServiceHandoffError(
                "rollback_incomplete_manual_recovery_required"
            ) from rollback_error
        raise S20ServiceHandoffError(
            f"transaction_failed_rolled_back:{type(error).__name__}"
        ) from error
    result = {
        "schema": SCHEMA,
        "phase": "apply",
        "status": "PASS",
        "authorization_id": AUTHORIZATION_ID,
        "authorization_claimed": claimed,
        "authorization_consumed": True,
        "exact_service_client_count_created": 3,
        "exact_service_role_count_created": 3,
        "node_client_created": False,
        "all_three_exact_credential_auth": True,
        "all_three_wrong_client_id_rejected": True,
        "anonymous_rejected": True,
        "production_broker_started": False,
        "board_access": False,
        "postcheck": postcheck,
    }
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=("preclaim", "apply"),
        required=True,
    )
    parser.add_argument("--expected-executor-sha256", required=True)
    parser.add_argument("--authorization-id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    runner = CommandRunner()
    executor_path = Path(__file__).resolve()
    try:
        runtime = LocalTransactionRuntime(
            runner,
            executor_path=executor_path,
            expected_executor_sha256=args.expected_executor_sha256,
        )
        if args.phase == "preclaim":
            report = runtime.preclaim()
        else:
            if not args.authorization_id:
                raise S20ServiceHandoffError("authorization_id_required")
            report = execute_apply(
                runtime,
                authorization_id=args.authorization_id,
            )
    except S20ServiceHandoffError as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error),
                    "secrets_read_to_output": False,
                    "board_access": False,
                },
                separators=(",", ":"),
            )
        )
        return 2
    except Exception as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": f"unexpected_{type(error).__name__}",
                    "secrets_read_to_output": False,
                    "board_access": False,
                },
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
