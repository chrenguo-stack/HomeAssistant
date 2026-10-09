from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import cold_snapshot as snapshot
import controlled_window as window
import cutover_contract as contract
import fresh_state_contract as fresh

AUTHORIZATION_ID = "N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_LIVE_DEPLOY"
STATE_FILE = "fresh-manager-deploy-state-private.json"
FRESH_BASE = "fresh-manager-runtime-state"
ENV_FILE = "fresh-manager-env-private"
SHADOW_NAME = "greenhouse-manager-p4-shadow"
PARKED_NAME = "greenhouse-manager-p4-rollback"
FAILED_NAME = "greenhouse-manager-p4-failed"
STOP_TIMEOUT_SECONDS = 30
START_TIMEOUT_SECONDS = 45
POSTFLIGHT_TIMEOUT_SECONDS = 60
TCP_PORT = 8883
TRUE_VALUES = {"1", "true", "yes", "on"}


class DeployStop(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise DeployStop(code)


def invoke(args: tuple[str, ...], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def checked(args: tuple[str, ...], code: str, *, timeout: int = 30) -> str:
    result = invoke(args, timeout=timeout)
    require(result.returncode == 0, code)
    return result.stdout


def docker_json(kind: str, target: str) -> dict[str, Any]:
    if kind == "container":
        command = ("docker", "inspect", "--type", "container", target)
    elif kind == "image":
        command = ("docker", "image", "inspect", target)
    else:
        raise DeployStop("DOCKER_INSPECT_KIND_INVALID")
    raw = checked(command, "DOCKER_INSPECT_FAILED")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise DeployStop("DOCKER_INSPECT_JSON_INVALID") from error
    require(isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict),
            "DOCKER_INSPECT_SHAPE_INVALID")
    return value[0]


def container_exists(name: str) -> bool:
    result = invoke(("docker", "inspect", "--type", "container", name), timeout=12)
    if result.returncode == 0:
        return True
    require(result.returncode == 1, "DOCKER_CONTAINER_LOOKUP_UNCERTAIN")
    return False


def _env_map(value: object) -> dict[str, str]:
    require(isinstance(value, list), "MANAGER_ENV_INVALID")
    result: dict[str, str] = {}
    for item in value:
        require(isinstance(item, str) and "=" in item and "\n" not in item and "\x00" not in item,
                "MANAGER_ENV_INVALID")
        key, val = item.split("=", 1)
        require(bool(key) and key not in result, "MANAGER_ENV_DUPLICATE_OR_EMPTY")
        result[key] = val
    return result


def _atomic_json(path: Path, value: dict[str, Any], *, create: bool = False) -> None:
    temp = path.with_name(path.name + ".tmp")
    require(not temp.exists() and not temp.is_symlink(), "TRANSACTION_STATE_TEMP_COLLISION")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(temp, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if create:
            require(not path.exists() and not path.is_symlink(), "TRANSACTION_ALREADY_EXISTS_NO_REPLAY")
        os.replace(temp, path)
        path.chmod(0o600)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        if temp.exists():
            temp.unlink()
        raise


class TransactionState:
    def __init__(self, path: Path, document: dict[str, Any]) -> None:
        self.path = path
        self.document = document

    @classmethod
    def create(cls, private: Path, context: "DeployContext") -> "TransactionState":
        path = private / STATE_FILE
        require(not path.exists() and not path.is_symlink(), "TRANSACTION_ALREADY_EXISTS_NO_REPLAY")
        document = {
            "schema": "gh.n3w.p4.fresh-manager-deploy/1",
            "authorization_id": AUTHORIZATION_ID,
            "committed": False,
            "phase": "STARTED",
            "old_manager_id": context.old_manager["Id"],
            "old_manager_image": context.old_manager["Image"],
            "parked_name": PARKED_NAME,
            "candidate_image_id": context.image["Id"],
            "candidate_id": None,
            "broker_id": context.broker["Id"],
            "broker_started_at": context.broker.get("State", {}).get("StartedAt"),
            "broker_restart_count": context.broker.get("RestartCount"),
            "fresh_sources": {},
            "manager_uid": context.manager_uid,
            "manager_gid": context.manager_gid,
            "rollback_result": None,
        }
        _atomic_json(path, document, create=True)
        return cls(path, document)

    def save(self) -> None:
        _atomic_json(self.path, self.document)

    def phase(self, name: str) -> None:
        require(name in contract.TRANSACTION_PHASES, "TRANSACTION_PHASE_UNKNOWN")
        self.document["phase"] = name
        self.save()

    def update(self, **values: Any) -> None:
        self.document.update(values)
        self.save()

    def commit(self) -> None:
        self.document["phase"] = contract.TRANSACTION_PHASES[-1]
        self.document["committed"] = True
        self.save()


@dataclass(frozen=True)
class DeployContext:
    old_manager: dict[str, Any]
    broker: dict[str, Any]
    image: dict[str, Any]
    manager_uid: int
    manager_gid: int


def verify_r5_rollback_authority(private: Path) -> None:
    required_files = (
        "manager-inspect-private.json",
        "broker-inspect-private.json",
        "old-manager-image.tar",
        "old-manager-image.tar.sha256",
        "cold-snapshot-manifest-private.json",
        "p4-business-restore-evidence-private.json",
    )
    for name in required_files:
        path = private / name
        require(
            path.is_file()
            and not path.is_symlink()
            and stat.S_IMODE(path.stat().st_mode) == 0o600,
            "R5_PRIVATE_ROLLBACK_AUTHORITY_MISSING",
        )
    checked(
        ("sha256sum", "-c", "--status", str(private / "old-manager-image.tar.sha256")),
        "R5_OLD_IMAGE_ARCHIVE_HASH_INVALID",
        timeout=40,
    )


def broker_static_authority(before: dict[str, Any], after: dict[str, Any]) -> None:
    require(after.get("Id") == before.get("Id"), "BROKER_CONTAINER_CHANGED")
    require(after.get("Image") == before.get("Image"), "BROKER_IMAGE_CHANGED")
    require(after.get("State", {}).get("Running") is True, "BROKER_NOT_RUNNING")
    require(
        set(after.get("NetworkSettings", {}).get("Networks", {}))
        == set(before.get("NetworkSettings", {}).get("Networks", {})),
        "BROKER_NETWORK_ATTACHMENTS_CHANGED",
    )
    require(
        after.get("HostConfig", {}).get("PortBindings")
        == before.get("HostConfig", {}).get("PortBindings"),
        "BROKER_PORT_BINDINGS_CHANGED",
    )


def broker_unchanged(before: dict[str, Any], after: dict[str, Any]) -> None:
    broker_static_authority(before, after)
    require(
        after.get("State", {}).get("StartedAt") == before.get("State", {}).get("StartedAt"),
        "BROKER_STARTED_AT_CHANGED",
    )
    require(after.get("RestartCount") == before.get("RestartCount"), "BROKER_RESTART_COUNT_CHANGED")


def _read_numeric(args: tuple[str, ...], code: str) -> int:
    text = checked(args, code, timeout=20).strip()
    require(text.isdecimal(), code)
    return int(text)


def runtime_uid_gid() -> tuple[int, int]:
    return (
        _read_numeric(("docker", "exec", contract.MANAGER_NAME, "id", "-u"), "OLD_MANAGER_UID_UNAVAILABLE"),
        _read_numeric(("docker", "exec", contract.MANAGER_NAME, "id", "-g"), "OLD_MANAGER_GID_UNAVAILABLE"),
    )


def candidate_uid_gid(image_id: str) -> tuple[int, int]:
    base = ("docker", "run", "--rm", "--network", "none", "--read-only", "--entrypoint", "id", image_id)
    uid = _read_numeric((*base, "-u"), "CANDIDATE_UID_UNAVAILABLE")
    gid = _read_numeric((*base, "-g"), "CANDIDATE_GID_UNAVAILABLE")
    return uid, gid


def validate_create_contract(old: dict[str, Any]) -> None:
    config = old.get("Config", {})
    host = old.get("HostConfig", {})
    entrypoint = config.get("Entrypoint")
    require(isinstance(entrypoint, list) and len(entrypoint) == 1
            and isinstance(entrypoint[0], str) and entrypoint[0],
            "UNSUPPORTED_ENTRYPOINT_CONTRACT")
    require(config.get("Cmd") in (None, []) or isinstance(config.get("Cmd"), list),
            "UNSUPPORTED_CMD_CONTRACT")
    require(config.get("OpenStdin") is False and config.get("StdinOnce") is False
            and config.get("Tty") is False, "INTERACTIVE_CONTAINER_FORBIDDEN")
    require(host.get("Privileged") is False, "PRIVILEGED_MANAGER_FORBIDDEN")
    require(host.get("Devices") in (None, []), "DEVICE_MAPPING_UNSUPPORTED")
    require(host.get("DeviceRequests") in (None, []), "DEVICE_REQUEST_UNSUPPORTED")
    require(host.get("PidsLimit") in (None, 0), "PIDS_LIMIT_UNSUPPORTED")
    require(host.get("Memory") in (None, 0), "MEMORY_LIMIT_UNSUPPORTED")
    require(host.get("MemorySwap") in (None, 0), "MEMORY_SWAP_UNSUPPORTED")
    require(host.get("NanoCpus") in (None, 0), "CPU_LIMIT_UNSUPPORTED")
    require(host.get("Ulimits") in (None, []), "ULIMIT_UNSUPPORTED")
    require(host.get("PidMode") in (None, ""), "PID_MODE_UNSUPPORTED")
    require(host.get("Dns") in (None, []), "DNS_OVERRIDE_UNSUPPORTED")
    require(host.get("ExtraHosts") in (None, []), "EXTRA_HOSTS_UNSUPPORTED")
    require(host.get("Init") in (None, False), "INIT_OVERRIDE_UNSUPPORTED")
    require(host.get("OomKillDisable") in (None, False), "OOM_KILL_OVERRIDE_UNSUPPORTED")
    require(host.get("CapAdd") in (None, []), "CAP_ADD_UNSUPPORTED")
    require(host.get("CapDrop") in (None, []), "CAP_DROP_UNSUPPORTED")
    require(host.get("SecurityOpt") in (None, []), "SECURITY_OPT_UNSUPPORTED")
    _logging_contract(host)


def _logging_contract(host: dict[str, Any]) -> tuple[str, dict[str, str]]:
    log = host.get("LogConfig") or {}
    require(isinstance(log, dict), "LOG_CONFIG_INVALID")
    driver = log.get("Type") or ""
    require(driver in ("", "json-file"), "LOG_DRIVER_UNSUPPORTED")
    options = log.get("Config") or {}
    require(isinstance(options, dict), "LOG_OPTIONS_UNSUPPORTED")
    for key, value in options.items():
        require(
            isinstance(key, str)
            and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", key) is not None
            and isinstance(value, str)
            and len(value) <= 1024
            and not any(ord(char) < 32 or ord(char) == 127 for char in value),
            "LOG_OPTIONS_UNSUPPORTED",
        )
    return driver, options


def _write_env_file(private: Path, env: list[str]) -> Path:
    path = private / ENV_FILE
    require(not path.exists() and not path.is_symlink(), "PRIVATE_ENV_FILE_COLLISION")
    _env_map(env)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        for item in env:
            stream.write(item + "\n")
    return path


def _mount_arg(item: dict[str, Any]) -> str:
    pieces = [
        "type=bind",
        "src=" + str(item["Source"]),
        "dst=" + str(item["Destination"]),
        "bind-propagation=rprivate",
    ]
    if not item["RW"]:
        pieces.append("readonly")
    return ",".join(pieces)


def create_command(
    old: dict[str, Any],
    image_id: str,
    name: str,
    fresh_sources: dict[str, str],
    env_file: Path,
) -> tuple[str, ...]:
    validate_create_contract(old)
    planned = contract.plan_isolated_bindings(old, fresh_sources)
    config = old["Config"]
    host = old["HostConfig"]
    args: list[str] = ["docker", "create", "--name", name, "--network", "host"]
    args.extend(("--restart", "no", "--read-only", "--env-file", str(env_file)))
    user = config.get("User")
    if user:
        args.extend(("--user", str(user)))
    working = config.get("WorkingDir")
    if working:
        args.extend(("--workdir", str(working)))
    stop_signal = config.get("StopSignal")
    if stop_signal:
        args.extend(("--stop-signal", str(stop_signal)))
    tmpfs = host.get("Tmpfs") or {}
    require(isinstance(tmpfs, dict), "TMPFS_CONTRACT_INVALID")
    for destination in sorted(tmpfs):
        args.extend(("--tmpfs", destination + ":" + str(tmpfs[destination])))
    labels = dict(config.get("Labels") or {})
    labels.pop("org.opencontainers.image.revision", None)
    for key in sorted(labels):
        args.extend(("--label", str(key) + "=" + str(labels[key])))
    for destination in sorted(planned):
        args.extend(("--mount", _mount_arg(planned[destination])))
    args.extend(("--entrypoint", config["Entrypoint"][0], image_id))
    cmd = config.get("Cmd") or []
    require(all(isinstance(item, str) for item in cmd), "CMD_VALUE_INVALID")
    args.extend(cmd)
    return tuple(args)


def prepare_fresh_sources(
    private: Path,
    old: dict[str, Any],
    uid: int,
    gid: int,
) -> dict[str, str]:
    base = private / FRESH_BASE
    require(not base.exists() and not base.is_symlink(), "FRESH_RUNTIME_BASE_ALREADY_EXISTS")
    base.mkdir(mode=0o700)
    names = {
        "/var/lib/greenhouse-manager-registration": "registration",
        "/var/lib/greenhouse-manager/n3w": "n3w",
        "/var/lib/greenhouse-manager/n3w/relay-keys": "relay-keys",
    }
    sources: dict[str, str] = {}
    for destination, name in names.items():
        path = base / name
        path.mkdir(mode=0o700)
        os.chown(path, uid, gid)
        path.chmod(0o700)
        sources[destination] = str(path)
    fresh.validate_fresh_sources(
        old,
        sources,
        expected_uid=uid,
        expected_gid=gid,
    )
    return sources


def _socket_path(old: dict[str, Any]) -> str:
    env = _env_map(old.get("Config", {}).get("Env", []))
    path = env.get("GH_N3W_PAIRING_SOCKET_PATH", "/run/greenhouse-manager/pairing.sock")
    require(path.startswith("/") and ".." not in Path(path).parts, "PAIRING_SOCKET_PATH_INVALID")
    return path


def _tls_port_contract(old: dict[str, Any]) -> None:
    env = _env_map(old.get("Config", {}).get("Env", []))
    tls = env.get("GH_MQTT_TLS", "0").strip().lower()
    require(tls in TRUE_VALUES, "MANAGER_MQTT_TLS_NOT_ENABLED")
    require(env.get("GH_MQTT_PORT", "1883") == str(TCP_PORT), "MANAGER_MQTT_PORT_NOT_8883")


def manager_tcp_8883_established() -> bool:
    top = invoke(("docker", "top", contract.MANAGER_NAME, "-eo", "pid="), timeout=12)
    require(top.returncode == 0, "MANAGER_PROCESS_LIST_UNAVAILABLE")
    pids = {line.strip() for line in top.stdout.splitlines() if line.strip().isdigit()}
    require(bool(pids), "MANAGER_PROCESS_LIST_EMPTY")
    sockets = invoke(("ss", "-Hntp", "state", "established"), timeout=12)
    require(sockets.returncode == 0, "HOST_SOCKET_TABLE_UNAVAILABLE")
    for line in sockets.stdout.splitlines():
        if ":" + str(TCP_PORT) not in line:
            continue
        if any(("pid=" + pid + ",") in line or ("pid=" + pid + ")") in line for pid in pids):
            return True
    return False


class LiveOps:
    def __init__(self, private: Path) -> None:
        self.private = private
        self.context: DeployContext | None = None
        self.fresh_sources: dict[str, str] = {}

    def preflight(self) -> DeployContext:
        verify_r5_rollback_authority(self.private)
        origin, broker_origin = window.get_private_origin(self.private)
        window.check_old_running(origin, broker_origin)
        old = docker_json("container", contract.MANAGER_NAME)
        broker = docker_json("container", contract.BROKER_NAME)
        image = docker_json("image", contract.CANDIDATE_TAG)
        require(old.get("Id") == origin.get("Id"), "OLD_MANAGER_NOT_R5_ORIGIN")
        require(old.get("Image") == origin.get("Image"), "OLD_MANAGER_IMAGE_DRIFT")
        broker_static_authority(broker_origin, broker)
        contract.validate_source_authority(old, broker, image)
        validate_create_contract(old)
        require(shutil.which("ss") is not None, "SS_TOOL_REQUIRED")
        for name in (SHADOW_NAME, PARKED_NAME, FAILED_NAME):
            require(not container_exists(name), "CUTOVER_CONTAINER_NAME_COLLISION")
        uid, gid = runtime_uid_gid()
        candidate_uid, candidate_gid = candidate_uid_gid(str(image["Id"]))
        require((uid, gid) == (candidate_uid, candidate_gid), "CANDIDATE_RUNTIME_UID_GID_DRIFT")
        _tls_port_contract(old)
        context = DeployContext(old, broker, image, uid, gid)
        self.context = context
        return context

    def prepare_fresh(self) -> dict[str, str]:
        require(self.context is not None, "PREFLIGHT_CONTEXT_MISSING")
        self.fresh_sources = prepare_fresh_sources(
            self.private,
            self.context.old_manager,
            self.context.manager_uid,
            self.context.manager_gid,
        )
        return dict(self.fresh_sources)

    def _create(self, name: str, record_candidate_id: Callable[[str], None] | None = None) -> dict[str, Any]:
        require(self.context is not None and self.fresh_sources, "CREATE_CONTEXT_MISSING")
        env_file = _write_env_file(
            self.private,
            list(self.context.old_manager["Config"]["Env"]),
        )
        try:
            command = create_command(
                self.context.old_manager,
                str(self.context.image["Id"]),
                name,
                self.fresh_sources,
                env_file,
            )
            container_id = checked(command, "CANDIDATE_CREATE_FAILED", timeout=45).strip()
            require(re.fullmatch(r"[a-f0-9]{64}", container_id) is not None,
                    "CANDIDATE_CREATE_ID_UNBOUND")
            if record_candidate_id is not None:
                record_candidate_id(container_id)
        finally:
            if env_file.exists():
                env_file.unlink()
        created = docker_json("container", name)
        require(created.get("Id") == container_id, "CANDIDATE_CREATE_ID_MISMATCH")
        contract.verify_stopped_shadow_matches_origin(
            self.context.old_manager,
            created,
            str(self.context.image["Id"]),
            self.fresh_sources,
        )
        return created

    def shadow_create_and_verify(self) -> None:
        require(not container_exists(SHADOW_NAME), "SHADOW_NAME_COLLISION")
        created = self._create(SHADOW_NAME)
        require(created.get("State", {}).get("Running") is False, "SHADOW_STARTED_UNEXPECTEDLY")
        broker_unchanged(self.context.broker, docker_json("container", contract.BROKER_NAME))
        checked(("docker", "rm", SHADOW_NAME), "SHADOW_REMOVE_FAILED")
        require(not container_exists(SHADOW_NAME), "SHADOW_REMOVE_INCOMPLETE")

    def stop_old(self) -> None:
        require(self.context is not None, "PREFLIGHT_CONTEXT_MISSING")
        checked(
            ("docker", "stop", "--time", str(STOP_TIMEOUT_SECONDS), contract.MANAGER_NAME),
            "OLD_MANAGER_STOP_FAILED",
            timeout=STOP_TIMEOUT_SECONDS + 15,
        )
        stopped = docker_json("container", contract.MANAGER_NAME)
        require(stopped.get("Id") == self.context.old_manager.get("Id"), "OLD_MANAGER_ID_CHANGED_DURING_STOP")
        require(stopped.get("State", {}).get("Running") is False, "OLD_MANAGER_STILL_RUNNING")
        broker_unchanged(self.context.broker, docker_json("container", contract.BROKER_NAME))

    def park_old(self) -> None:
        require(self.context is not None, "PREFLIGHT_CONTEXT_MISSING")
        require(not container_exists(PARKED_NAME), "PARKED_NAME_COLLISION")
        checked(
            ("docker", "rename", contract.MANAGER_NAME, PARKED_NAME),
            "OLD_MANAGER_PARK_FAILED",
        )
        parked = docker_json("container", PARKED_NAME)
        require(parked.get("Id") == self.context.old_manager.get("Id"), "PARKED_OLD_MANAGER_ID_MISMATCH")
        require(parked.get("State", {}).get("Running") is False, "PARKED_OLD_MANAGER_RUNNING")
        require(not container_exists(contract.MANAGER_NAME), "MANAGER_NAME_NOT_RELEASED")
        broker_unchanged(self.context.broker, docker_json("container", contract.BROKER_NAME))

    def create_candidate(self, record_candidate_id: Callable[[str], None]) -> str:
        require(not container_exists(contract.MANAGER_NAME), "CANDIDATE_NAME_COLLISION")
        created = self._create(contract.MANAGER_NAME, record_candidate_id)
        return str(created["Id"])

    def start_candidate(self, candidate_id: str) -> None:
        checked(
            ("docker", "start", contract.MANAGER_NAME),
            "CANDIDATE_START_FAILED",
            timeout=START_TIMEOUT_SECONDS,
        )
        deadline = time.monotonic() + START_TIMEOUT_SECONDS
        consecutive = 0
        while time.monotonic() < deadline:
            current = docker_json("container", contract.MANAGER_NAME)
            require(current.get("Id") == candidate_id, "CANDIDATE_ID_CHANGED_AFTER_START")
            if current.get("State", {}).get("Running") is True:
                consecutive += 1
                if consecutive >= 3:
                    broker_unchanged(self.context.broker, docker_json("container", contract.BROKER_NAME))
                    return
            else:
                consecutive = 0
            time.sleep(1)
        raise DeployStop("CANDIDATE_NOT_STABLY_RUNNING")

    def _postflight_once(self, candidate_id: str) -> None:
        current = docker_json("container", contract.MANAGER_NAME)
        require(current.get("Id") == candidate_id, "CANDIDATE_ID_CHANGED_POSTFLIGHT")
        contract.verify_running_candidate_matches_origin(
            self.context.old_manager,
            current,
            str(self.context.image["Id"]),
            self.fresh_sources,
        )
        require(
            invoke(("docker", "exec", contract.MANAGER_NAME, "greenhouse-manager", "--check-config"), timeout=15).returncode == 0,
            "CANDIDATE_CONFIG_CHECK_FAILED",
        )
        require(
            invoke((
                "docker", "exec", contract.MANAGER_NAME,
                "greenhouse-manager-registration", "p4-pending-readonly", "--help",
            ), timeout=15).returncode == 0,
            "P4_READONLY_CLI_UNAVAILABLE",
        )
        require(
            invoke((
                "docker", "exec", contract.MANAGER_NAME,
                "greenhouse-manager-pairing", "import-payload", "--help",
            ), timeout=15).returncode == 0,
            "P4_IMPORT_PAYLOAD_CLI_UNAVAILABLE",
        )
        require(
            invoke((
                "docker", "exec", contract.MANAGER_NAME,
                "test", "-S", _socket_path(self.context.old_manager),
            ), timeout=12).returncode == 0,
            "PAIRING_SOCKET_NOT_READY",
        )
        fresh.validate_initialized_fresh_state(
            self.fresh_sources,
            expected_uid=self.context.manager_uid,
            expected_gid=self.context.manager_gid,
        )
        require(manager_tcp_8883_established(), "MANAGER_BROKER_TCP_NOT_ESTABLISHED")
        broker_unchanged(self.context.broker, docker_json("container", contract.BROKER_NAME))

    def postflight(self, candidate_id: str) -> None:
        deadline = time.monotonic() + POSTFLIGHT_TIMEOUT_SECONDS
        last: BaseException | None = None
        while time.monotonic() < deadline:
            try:
                self._postflight_once(candidate_id)
                return
            except (DeployStop, contract.CutoverStop, OSError) as error:
                last = error
                time.sleep(1)
        if last is not None:
            raise DeployStop("CANDIDATE_POSTFLIGHT_FAILED") from last
        raise DeployStop("CANDIDATE_POSTFLIGHT_FAILED")

    def commit_restart_policy(self, candidate_id: str) -> None:
        checked(
            ("docker", "update", "--restart", "unless-stopped", contract.MANAGER_NAME),
            "CANDIDATE_RESTART_POLICY_UPDATE_FAILED",
        )
        current = docker_json("container", contract.MANAGER_NAME)
        require(current.get("Id") == candidate_id, "CANDIDATE_ID_CHANGED_AT_COMMIT")
        contract.verify_running_candidate_matches_origin(
            self.context.old_manager,
            current,
            str(self.context.image["Id"]),
            self.fresh_sources,
            restart_policy="unless-stopped",
        )
        broker_unchanged(self.context.broker, docker_json("container", contract.BROKER_NAME))


def execute_transaction(private: Path, ops: LiveOps) -> TransactionState:
    context = ops.preflight()
    state = TransactionState.create(private, context)
    phases: list[str] = []

    def advance(name: str) -> None:
        phases.append(name)
        state.phase(name)

    advance("PRECHECK_OLD_MANAGER_RUNNING")
    fresh_sources = ops.prepare_fresh()
    state.update(fresh_sources=fresh_sources)
    advance("FRESH_SOURCES_PREPARED_EMPTY")
    ops.shadow_create_and_verify()
    advance("SHADOW_CREATE_AND_COMPARE_STOPPED")
    ops.stop_old()
    advance("OLD_MANAGER_STOP")
    ops.park_old()
    advance("OLD_MANAGER_PARKED_NOT_DELETED")
    candidate_id = ops.create_candidate(lambda value: state.update(candidate_id=value))
    require(state.document.get("candidate_id") == candidate_id,
            "CANDIDATE_ID_NOT_DURABLY_BOUND")
    advance("NEW_MANAGER_CREATED_WITH_ONLY_FRESH_RW_STATE")
    ops.start_candidate(candidate_id)
    advance("NEW_MANAGER_STARTED")
    ops.postflight(candidate_id)
    advance("NEW_MANAGER_HOST_POSTFLIGHT_ZERO_BASELINE")
    ops.commit_restart_policy(candidate_id)
    advance("SUCCESS_COMMIT_KEEP_ORIGINAL_FOR_ROLLBACK")
    contract.assert_cutover_sequence(phases)
    state.commit()
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("execute",))
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--permit-live-manager-replacement", action="store_true")
    parser.add_argument("--systemd-supervised", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    require(args.authorization_id == AUTHORIZATION_ID, "AUTHORIZATION_ID_MISMATCH")
    require(args.permit_live_manager_replacement, "LIVE_MANAGER_REPLACEMENT_NOT_AUTHORIZED")
    require(args.systemd_supervised, "DIRECT_UNSUPERVISED_EXECUTION_FORBIDDEN")
    private = snapshot.private_root(args.private_root)
    state = execute_transaction(private, LiveOps(private))
    require(state.document.get("committed") is True, "TRANSACTION_NOT_COMMITTED")
    print("FRESH_MANAGER_DEPLOYMENT=PASS")
    print("FRESH_MANAGER_ZERO_BASELINE=PASS")
    print("BROKER_UNCHANGED=PASS")
    print("OLD_MANAGER_PARKED_FOR_ROLLBACK=PASS")
    print("REAL_NODE_TELEMETRY_CHECK=DEFERRED_NO_POWERED_BOARD")


if __name__ == "__main__":
    try:
        main()
    except (
        DeployStop,
        snapshot.Stop,
        window.WindowStop,
        contract.CutoverStop,
        OSError,
        ValueError,
        KeyError,
        subprocess.TimeoutExpired,
    ) as error:
        if isinstance(error, (DeployStop, snapshot.Stop, window.WindowStop, contract.CutoverStop)):
            code = str(error)
        else:
            code = type(error).__name__
        print("P4_FRESH_MANAGER_DEPLOY=STOP:" + code, file=sys.stderr)
        raise SystemExit(1)
