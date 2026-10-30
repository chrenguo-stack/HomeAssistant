#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import copy
import fcntl
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable, Sequence

import n3w_t1_maintenance_transaction as maintenance
import n3w_t1_portable_image_identity as portable
import n3w_t1_production_v2_contract as production_contract

SCHEMA = "gh.n3w-r10-e03-successor-recovery/1"
PLAN_SCHEMA = "gh.n3w-r10-e03-successor-recovery-plan/1"
PREDECESSOR_SCHEMA = "gh.n3w-r10-e03-manager-successor-refresh-transaction/1"
CONFIRMATION = "N3W_T1_R10_E03_SUCCESSOR_RECOVERY_APPLY"

PROJECT = "n3wfc4"
BROKER_UNIT = "n3wfc4-broker-activation.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
REGISTRATION_GUARD_UNIT = "n3wfc4-registration-ingress-guard.service"
BROKER_ENV = Path("/etc/n3wfc4/broker-activation.env")
COMPOSE = Path("/etc/n3wfc4/docker-compose.yml")
COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")
HA_CONFIG_ENTRIES = Path("/var/lib/n3wfc4-homeassistant/.storage/core.config_entries")
PREDECESSOR_TX = Path(
    "/var/lib/n3w-t1-provisioning/R10_E03_MANAGER_SUCCESSOR_REFRESH.json"
)
MAINTENANCE_ROOT = Path("/var/lib/n3w-t1-maintenance")
TRANSACTION_ROOT = MAINTENANCE_ROOT / "transactions"
LOCK_PATH = MAINTENANCE_ROOT / ".maintenance.lock"
GATE_TARGET = Path("/usr/local/sbin/n3w-t1-maintenance-activation-gate")
GATE_DROPIN = Path(
    "/etc/systemd/system/n3wfc4-services-activation.service.d/"
    "90-n3w-maintenance-gate.conf"
)
F4_HOST = Path("/usr/local/sbin/n3w-t1-f4-activation")
F4_REBOOT_VERIFY = Path("/usr/local/sbin/n3w-t1-f4-reboot-verify")
RUNTIME_SNAPSHOT_SCHEMA = "gh.n3w-t1-runtime-snapshot/2"

EXPECTED_EXECSTART = (
    "ExecStart=/usr/bin/docker compose "
    "--project-name ${N3WFC4_COMPOSE_PROJECT_NAME} "
    "--env-file ${N3WFC4_COMPOSE_ENV_FILE} "
    "-f ${N3WFC4_COMPOSE_FILE} --profile application up --no-deps "
    "--no-log-prefix --abort-on-container-exit manager homeassistant"
)
EXPECTED_EXECSTOP = (
    "ExecStop=/usr/bin/docker compose "
    "--project-name ${N3WFC4_COMPOSE_PROJECT_NAME} "
    "--env-file ${N3WFC4_COMPOSE_ENV_FILE} "
    "-f ${N3WFC4_COMPOSE_FILE} stop homeassistant manager"
)
GATE_DROPIN_BYTES = (
    "[Service]\n"
    "ExecCondition=/usr/local/sbin/n3w-t1-maintenance-activation-gate\n"
).encode("utf-8")

OLD_MANAGER_IMAGE = "local/greenhouse-manager:fresh-ff750b3801a2"
OLD_MANAGER_ID = (
    "sha256:5b8150e457a1cc5af3e7e576514dfb3fa33e15f4dfe4801640ec604dd962218f"
)
TARGET_SOURCE_HEAD = "f8876fd87165df731d792690a8288867c3eeef55"
TARGET_MANAGER_IMAGE = "local/greenhouse-manager:fresh-f8876fd87165"
TARGET_MANAGER_TAR_SHA256 = (
    "d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5"
)
TARGET_CONFIG_DIGEST = (
    "sha256:089153fa4bbc823a1357427083f23ef96933a119c6ae150c143b62d7b40859e4"
)
TARGET_ARTIFACT_SHA256 = (
    "c94568f740b911eee0f4238207249b1e98f84748c17a902938ccc35293e4b183"
)
TARGET_ARTIFACT_ID = 12900601779
TARGET_ARTIFACT_RUN_ID = 40880705472

HA_IMAGE = "local/n3w-homeassistant:2026.10.0-0c73235a"
HA_IMAGE_ID = (
    "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306"
)
BROKER_IMAGE = "local/n3w-mosquitto:2.1.2-3184566d"
BROKER_IMAGE_ID = (
    "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563"
)

PAIRING_SHA256 = "9931c366d483abd3af6e1e3d903b82645542346dbd258975acd788998f0404dc"
HARDWARE_SHA256 = "3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55"
PRE_INVENTORY_SHA256 = "2ac5373cc532499154fffdd42e14f6225cc2ebdd90deb0a5bacdda3ec3ccaaed"
EMPTY_INVENTORY_SHA256 = (
    "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
)

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
TXID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,199}$")
MIN_FREE_BYTES = 256 * 1024 * 1024
READINESS_TIMEOUT_SECONDS = 300.0
READINESS_POLL_SECONDS = 2.0
STABILITY_WINDOW_SECONDS = 90.0
_LOCK_DEPTH = 0

SCOPE = (
    "activation_gate_install",
    "service_stop",
    "deployment_inputs_publish",
    "service_start",
    "runtime_acceptance",
    "rollback_service_stop",
    "deployment_inputs_rollback",
    "rollback_service_start",
)

SETTINGS_PROBE = (
    "import json;"
    "from pathlib import Path;"
    "from greenhouse_manager.runtime.config import Settings;"
    "s=Settings.from_env();"
    "print(json.dumps({'pairing':str(Path(s.pairing_db_path).expanduser()),"
    "'credential':str(Path(s.n3w_credential_lifecycle_db_path).expanduser())},"
    "sort_keys=True))"
)

LEDGER_PROBE = r"""
import hashlib,json,sqlite3,sys
p,c=sys.argv[1],sys.argv[2]
db=sqlite3.connect("file:"+p+"?mode=ro",uri=True);db.row_factory=sqlite3.Row;db.execute("PRAGMA query_only=ON")
cr=sqlite3.connect("file:"+c+"?mode=ro",uri=True);cr.row_factory=sqlite3.Row;cr.execute("PRAGMA query_only=ON")
rows=db.execute("SELECT pairing_id,hardware_id_sha256,expires_at,state,phase,cleanup_state,node_id,terminal_at,terminal_reason,CASE WHEN julianday(expires_at)<=julianday('now') THEN 1 ELSE 0 END expired_by_clock FROM first_registration_attempts ORDER BY opened_at,pairing_id").fetchall()
attempts=[]
for r in rows:
    pid=str(r["pairing_id"])
    s=db.execute("SELECT hardware_id,state,reason FROM pairing_sessions WHERE pairing_id=?",(pid,)).fetchone()
    reg=None if s is None else db.execute("SELECT current_pairing_id,node_id FROM registrations WHERE hardware_id=?",(s["hardware_id"],)).fetchone()
    hid=None if s is None else str(s["hardware_id"])
    attempts.append({
      "pairing_id_sha256":hashlib.sha256(pid.encode()).hexdigest(),
      "hardware_id_sha256":str(r["hardware_id_sha256"]),
      "state":str(r["state"]),"phase":str(r["phase"]),"cleanup_state":str(r["cleanup_state"]),
      "node_id_present":r["node_id"] is not None,"terminal_at_present":r["terminal_at"] is not None,
      "terminal_reason":r["terminal_reason"],"expired_by_clock":bool(r["expired_by_clock"]),
      "session_state":None if s is None else str(s["state"]),"session_reason":None if s is None else s["reason"],
      "session_hardware_sha256":None if hid is None else hashlib.sha256(hid.encode()).hexdigest(),
      "registration_match_count":0 if reg is None else int(reg["current_pairing_id"]==pid),
      "current_pairing_matches":bool(reg is not None and reg["current_pairing_id"]==pid),
      "registration_node_id_present":bool(reg is not None and reg["node_id"] is not None),
      "pairing_credential_count":int(cr.execute("SELECT COUNT(*) FROM credential_assignments WHERE pairing_id=?",(pid,)).fetchone()[0]),
      "hardware_credential_history_count":0 if hid is None else int(cr.execute("SELECT COUNT(*) FROM credential_assignments WHERE hardware_id=?",(hid,)).fetchone()[0])
    })
regs=db.execute("SELECT hardware_id,current_pairing_id,pairing_epoch,node_id,logical_location_id,repair_authorized,retired_at,retirement_reason FROM registrations ORDER BY hardware_id").fetchall()
inv=[[x["hardware_id"],x["current_pairing_id"],x["pairing_epoch"],x["node_id"],x["logical_location_id"],x["repair_authorized"],x["retired_at"],x["retirement_reason"]] for x in regs]
unresolved=int(db.execute("SELECT COUNT(*) FROM first_registration_attempts WHERE state='ACTIVE' OR (state IN ('EXPIRED','RESTART_INVALIDATED') AND cleanup_state!='COMPLETE')").fetchone()[0])
db.close();cr.close()
print(json.dumps({"attempt_count":len(attempts),"attempts":attempts,"registration_count":len(regs),"registration_inventory_sha256":hashlib.sha256(json.dumps(inv,sort_keys=True,separators=(',',':')).encode()).hexdigest(),"unresolved_count":unresolved},sort_keys=True))
"""


class SuccessorError(RuntimeError):
    pass


class BlockedError(SuccessorError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_text(value: str) -> str:
    return sha_bytes(value.encode("utf-8"))


def sha_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise SuccessorError("file_invalid")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_bytes(value: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(value)).encode("ascii") + b"\0" + value
    ).hexdigest()


def git_blob(path: Path) -> str:
    return git_blob_bytes(path.read_bytes())


def safe_reason(error: BaseException) -> str:
    raw = str(error).split(":", 1)[0]
    if re.fullmatch(r"[A-Za-z0-9_.-]{3,120}", raw or ""):
        return raw
    return type(error).__name__


def run(
    argv: Sequence[str],
    *,
    timeout: float = 30.0,
    allowed: frozenset[int] = frozenset({0}),
    input_bytes: bytes | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        tuple(argv),
        input=input_bytes,
        stdin=None if input_bytes is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        env=env,
    )
    if result.returncode not in allowed:
        detail = (result.stderr or result.stdout).decode(errors="replace").strip()
        raise SuccessorError(
            f"command_failed:{Path(argv[0]).name}:{result.returncode}:{detail[:240]}"
        )
    return result


def systemctl(operation: str, unit: str) -> str:
    result = run(
        ("systemctl", operation, unit),
        allowed=frozenset({0, 1, 3, 4}),
    )
    return result.stdout.decode().strip() or "unknown"


def _json_bytes(value: bytes, code: str) -> Any:
    try:
        return json.loads(value.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SuccessorError(code) from error


def _transaction_path(transaction_id: str) -> Path:
    if TXID.fullmatch(transaction_id or "") is None:
        raise SuccessorError("transaction_id_invalid")
    return TRANSACTION_ROOT / f"{transaction_id}.json"


def host_binding_sha256() -> str:
    path = Path("/etc/machine-id")
    if path.is_symlink() or not path.is_file():
        raise SuccessorError("machine_id_invalid")
    value = path.read_text(encoding="ascii").strip().lower()
    if re.fullmatch(r"[0-9a-f]{32}", value) is None:
        raise SuccessorError("machine_id_invalid")
    return sha_text("n3w-t1-host-v1:" + value)


def _ensure_private_dir(path: Path) -> None:
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_dir():
            raise SuccessorError("maintenance_directory_invalid")
        meta = path.stat()
        if meta.st_uid != 0 or meta.st_gid != 0 or stat.S_IMODE(meta.st_mode) != 0o700:
            raise SuccessorError("maintenance_directory_metadata_invalid")
        return
    path.mkdir(mode=0o700)
    os.chown(path, 0, 0)
    os.chmod(path, 0o700)
    fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def global_lock():
    global _LOCK_DEPTH
    _ensure_private_dir(MAINTENANCE_ROOT)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(LOCK_PATH, flags, 0o600)
    acquired = False
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, 0, 0)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SuccessorError("maintenance_lock_busy") from error
        acquired = True
        if _LOCK_DEPTH != 0:
            raise SuccessorError("maintenance_lock_reentered")
        _LOCK_DEPTH = 1
        yield
    finally:
        _LOCK_DEPTH = 0
        try:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _require_global_lock() -> None:
    if _LOCK_DEPTH != 1:
        raise SuccessorError("maintenance_lock_not_held")


def runtime_authority() -> dict[str, str]:
    injected_head = globals().get("BUNDLE_SOURCE_HEAD")
    injected_blob = globals().get("BUNDLE_EXECUTOR_BLOB")
    injected_modules = globals().get("BUNDLE_MODULE_SET_SHA256")
    source_head = (
        injected_head
        if isinstance(injected_head, str)
        else os.environ.get("N3W_SUCCESSOR_SOURCE_HEAD")
    )
    if not isinstance(source_head, str) or SHA40.fullmatch(source_head) is None:
        raise SuccessorError("executor_source_head_unbound")

    current = Path(__file__)
    executor_blob = (
        injected_blob
        if isinstance(injected_blob, str)
        else git_blob(current)
    )
    if not isinstance(executor_blob, str) or SHA40.fullmatch(executor_blob) is None:
        raise SuccessorError("executor_blob_invalid")

    if isinstance(injected_modules, str):
        module_set = injected_modules
    else:
        base = current.parent
        paths = (
            base / "n3w_t1_portable_image_identity.py",
            base / "n3w_t1_maintenance_transaction.py",
            base / "n3w_t1_maintenance_activation_gate.py",
            base / "n3w_t1_production_v2_contract.py",
            current,
        )
        if any(path.is_symlink() or not path.is_file() for path in paths):
            raise SuccessorError("executor_module_set_unavailable")
        material = {path.name: git_blob(path) for path in paths}
        module_set = sha_bytes(canonical(material))
    if SHA64.fullmatch(module_set or "") is None:
        raise SuccessorError("executor_module_set_invalid")
    return {
        "source_head": source_head,
        "executor_blob": executor_blob,
        "module_set_sha256": module_set,
    }


def _gate_source_bytes() -> bytes:
    injected = globals().get("BUNDLED_GATE_SOURCE")
    if isinstance(injected, str):
        return injected.encode("utf-8")
    path = Path(__file__).with_name("n3w_t1_maintenance_activation_gate.py")
    if path.is_symlink() or not path.is_file():
        raise SuccessorError("gate_source_unavailable")
    return path.read_bytes()


def _atomic_create_or_exact(path: Path, payload: bytes, mode: int) -> str:
    wanted = sha_bytes(payload)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or sha_file(path) != wanted:
            raise BlockedError("controlled_file_unknown")
        return wanted
    if path.parent.is_symlink():
        raise BlockedError("controlled_parent_symlink")
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        os.fchmod(fd, mode)
        os.fchown(fd, 0, 0)
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    dfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    if sha_file(path) != wanted:
        raise SuccessorError("controlled_file_verify_failed")
    return wanted


def _atomic_replace_exact(path: Path, payload: bytes, expected_sha256: str) -> str:
    if path.is_symlink() or not path.is_file() or sha_file(path) != expected_sha256:
        raise BlockedError("replace_prestate_unknown")
    meta = path.stat()
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(raw)
    try:
        os.fchmod(fd, stat.S_IMODE(meta.st_mode))
        os.fchown(fd, meta.st_uid, meta.st_gid)
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if fd >= 0:
            os.close(fd)
        tmp.unlink(missing_ok=True)
    observed = sha_file(path)
    if observed != sha_bytes(payload):
        raise SuccessorError("replace_verify_failed")
    return observed


def compose_argv(path: str = "-") -> tuple[str, ...]:
    return (
        "docker",
        "compose",
        "--project-name",
        PROJECT,
        "--env-file",
        str(COMPOSE_ENV),
        "-f",
        path,
    )


def render_compose_payload(
    payload: bytes,
    *,
    manager_image_override: str | None = None,
) -> dict[str, Any]:
    environment = dict(os.environ)
    environment.pop("GH_MANAGER_IMAGE", None)
    if manager_image_override is not None:
        environment["GH_MANAGER_IMAGE"] = manager_image_override
    raw = run(
        (*compose_argv("-"), "--profile", "application", "config", "--format", "json"),
        input_bytes=payload,
        timeout=45,
        env=environment,
    ).stdout
    value = _json_bytes(raw, "compose_render_invalid")
    if not isinstance(value, dict):
        raise SuccessorError("compose_render_shape_invalid")
    return value


def _service_record(rendered: dict[str, Any], service: str) -> dict[str, Any]:
    services = rendered.get("services")
    record = services.get(service) if isinstance(services, dict) else None
    if not isinstance(record, dict):
        raise SuccessorError(f"compose_service_missing:{service}")
    return record


def validate_manager_image_indirection(original: bytes) -> None:
    try:
        lines = original.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise SuccessorError("compose_encoding_invalid") from error
    start: int | None = None
    end = len(lines)
    for index, line in enumerate(lines):
        if line == "  manager:":
            if start is not None:
                raise SuccessorError("manager_service_duplicate")
            start = index
            continue
        if (
            start is not None
            and index > start
            and re.fullmatch(r"  [A-Za-z0-9_.-]+:", line)
        ):
            end = index
            break
    if start is None:
        raise SuccessorError("manager_service_missing")
    expected = '    image: "${GH_MANAGER_IMAGE:?GH_MANAGER_IMAGE required}"'
    image_lines = [
        line for line in lines[start + 1 : end]
        if line.lstrip().startswith("image:")
    ]
    if image_lines != [expected]:
        raise SuccessorError("manager_image_indirection_invalid")


def rewrite_manager_image_env(original: bytes) -> bytes:
    try:
        text = original.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SuccessorError("compose_env_encoding_invalid") from error
    lines = text.splitlines(keepends=True)
    candidate_indexes = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^\s*(?:export\s+)?GH_MANAGER_IMAGE\s*=", line)
    ]
    if len(candidate_indexes) != 1:
        raise SuccessorError("compose_env_manager_image_count_invalid")
    index = candidate_indexes[0]
    match = re.fullmatch(
        r"(GH_MANAGER_IMAGE=)([^\r\n]*)(\r?\n)?",
        lines[index],
    )
    if match is None:
        raise SuccessorError("compose_env_manager_image_format_invalid")
    if match.group(2) != OLD_MANAGER_IMAGE:
        raise SuccessorError("compose_env_manager_image_predecessor_drift")
    lines[index] = (
        match.group(1)
        + TARGET_MANAGER_IMAGE
        + (match.group(3) or "")
    )
    return "".join(lines).encode("utf-8")


def deployment_inputs_fingerprint(
    compose_sha256: str,
    compose_env_sha256: str,
) -> str:
    if SHA64.fullmatch(compose_sha256 or "") is None:
        raise SuccessorError("compose_sha256_invalid")
    if SHA64.fullmatch(compose_env_sha256 or "") is None:
        raise SuccessorError("compose_env_sha256_invalid")
    return sha_bytes(
        canonical(
            {
                "compose_sha256": compose_sha256,
                "compose_env_sha256": compose_env_sha256,
            }
        )
    )


def validate_candidate(before: dict[str, Any], after: dict[str, Any]) -> None:
    expected = copy.deepcopy(before)
    services = expected.get("services")
    manager = services.get("manager") if isinstance(services, dict) else None
    if not isinstance(manager, dict) or manager.get("image") != OLD_MANAGER_IMAGE:
        raise SuccessorError("candidate_predecessor_invalid")
    manager["image"] = TARGET_MANAGER_IMAGE
    if expected != after:
        raise SuccessorError("candidate_non_manager_drift")


def verify_service_unit() -> dict[str, str]:
    raw = run(("systemctl", "cat", SERVICES_UNIT)).stdout.decode()
    starts = [
        line.strip()
        for line in raw.splitlines()
        if line.strip().startswith("ExecStart=")
    ]
    stops = [
        line.strip()
        for line in raw.splitlines()
        if line.strip().startswith("ExecStop=")
    ]
    if starts != [EXPECTED_EXECSTART] or stops != [EXPECTED_EXECSTOP]:
        raise SuccessorError("services_unit_command_drift")
    if "--force-recreate" in raw:
        raise SuccessorError("manager_only_recreate_forbidden")
    return {
        "execstart_sha256": sha_text(starts[0]),
        "execstop_sha256": sha_text(stops[0]),
    }


def parse_activation_env() -> None:
    if BROKER_ENV.is_symlink() or not BROKER_ENV.is_file():
        raise SuccessorError("activation_env_invalid")
    values: dict[str, str] = {}
    for raw in BROKER_ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise SuccessorError("activation_env_line_invalid")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
            value = value[1:-1]
        if key in values:
            raise SuccessorError("activation_env_duplicate")
        values[key] = value
    expected = {
        "N3WFC4_COMPOSE_FILE": str(COMPOSE),
        "N3WFC4_COMPOSE_ENV_FILE": str(COMPOSE_ENV),
        "N3WFC4_COMPOSE_PROJECT_NAME": PROJECT,
    }
    if any(values.get(key) != expected[key] for key in expected):
        raise SuccessorError("activation_env_authority_drift")


def _container_ids(service: str) -> list[str]:
    raw = run(
        (
            "docker",
            "ps",
            "-q",
            "--filter",
            f"label=com.docker.compose.project={PROJECT}",
            "--filter",
            f"label=com.docker.compose.service={service}",
        )
    ).stdout.decode()
    return [line.strip() for line in raw.splitlines() if line.strip()]


def container_id(service: str) -> str:
    values = _container_ids(service)
    if len(values) != 1:
        raise SuccessorError(f"{service}_container_count_invalid")
    return values[0]


def inspect_container(reference: str) -> dict[str, Any]:
    value = _json_bytes(
        run(("docker", "inspect", reference)).stdout,
        "docker_inspect_json_invalid",
    )
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise SuccessorError("docker_inspect_shape_invalid")
    return value[0]


def runtime(service: str) -> dict[str, Any]:
    item = inspect_container(container_id(service))
    state = item.get("State")
    config = item.get("Config")
    host = item.get("HostConfig")
    labels = config.get("Labels") if isinstance(config, dict) else None
    if (
        not isinstance(state, dict)
        or state.get("Running") is not True
        or not isinstance(config, dict)
        or not isinstance(host, dict)
        or not isinstance(labels, dict)
        or labels.get("com.docker.compose.project") != PROJECT
        or labels.get("com.docker.compose.service") != service
    ):
        raise SuccessorError(f"{service}_runtime_invalid")
    result = {
        "container_id": item.get("Id"),
        "image_id": item.get("Image"),
        "image_ref": config.get("Image"),
        "started_at": state.get("StartedAt"),
        "restart_count": item.get("RestartCount"),
        "network_mode": host.get("NetworkMode"),
    }
    if (
        not isinstance(result["container_id"], str)
        or not isinstance(result["image_id"], str)
        or IMAGE_ID.fullmatch(result["image_id"]) is None
        or not isinstance(result["image_ref"], str)
        or not isinstance(result["started_at"], str)
        or not isinstance(result["restart_count"], int)
    ):
        raise SuccessorError(f"{service}_runtime_identity_invalid")
    return result


def listener_count(protocol: str, port: int) -> int:
    flag = "-ltn" if protocol == "tcp" else "-lun"
    raw = run(("ss", "-H", flag, "sport", "=", f":{port}")).stdout.decode()
    return len([line for line in raw.splitlines() if line.strip()])


def listener_snapshot() -> dict[str, int]:
    return {
        "tcp_8883": listener_count("tcp", 8883),
        "tcp_47110": listener_count("tcp", 47110),
        "udp_47111": listener_count("udp", 47111),
        "tcp_47112": listener_count("tcp", 47112),
    }


EXPECTED_LISTENERS = {
    "tcp_8883": 1,
    "tcp_47110": 1,
    "udp_47111": 1,
    "tcp_47112": 0,
}


def systemd_nrestarts(unit: str) -> int:
    raw = run(
        ("systemctl", "show", unit, "--property", "NRestarts", "--value")
    ).stdout.decode().strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise SuccessorError("systemd_nrestarts_invalid") from error
    if value < 0:
        raise SuccessorError("systemd_nrestarts_invalid")
    return value


def ha_mqtt_hash(path: Path = HA_CONFIG_ENTRIES) -> str:
    if path.is_symlink() or not path.is_file():
        raise SuccessorError("ha_config_entries_invalid")
    value = _json_bytes(path.read_bytes(), "ha_config_entries_invalid")
    data = value.get("data") if isinstance(value, dict) else None
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise SuccessorError("ha_config_entries_shape_invalid")
    mqtt = [
        item
        for item in entries
        if isinstance(item, dict) and item.get("domain") == "mqtt"
    ]
    return sha_bytes(canonical(mqtt))


def _manager_paths(manager_id: str) -> tuple[dict[str, str], dict[str, str]]:
    inside = _json_bytes(
        run(("docker", "exec", manager_id, "python", "-c", SETTINGS_PROBE)).stdout,
        "manager_settings_invalid",
    )
    if (
        not isinstance(inside, dict)
        or not isinstance(inside.get("pairing"), str)
        or not inside["pairing"].startswith("/")
        or not isinstance(inside.get("credential"), str)
        or not inside["credential"].startswith("/")
    ):
        raise SuccessorError("manager_settings_path_invalid")
    mounts = inspect_container(manager_id).get("Mounts")
    if not isinstance(mounts, list):
        raise SuccessorError("manager_mounts_invalid")

    def translate(value: str) -> str:
        matches: list[tuple[int, str]] = []
        for mount in mounts:
            if not isinstance(mount, dict) or mount.get("Type") != "bind":
                continue
            source, destination = mount.get("Source"), mount.get("Destination")
            if not isinstance(source, str) or not isinstance(destination, str):
                continue
            if value == destination or value.startswith(destination.rstrip("/") + "/"):
                relative = value[len(destination):].lstrip("/")
                matches.append(
                    (
                        len(destination),
                        str(Path(source) / relative) if relative else source,
                    )
                )
        if not matches:
            raise SuccessorError("state_path_translation_missing")
        matches.sort(reverse=True)
        if len(matches) > 1 and matches[0][0] == matches[1][0]:
            raise SuccessorError("state_path_translation_ambiguous")
        return matches[0][1]

    return inside, {
        "pairing": translate(inside["pairing"]),
        "credential": translate(inside["credential"]),
    }


def ledger_in_manager(manager_id: str) -> tuple[dict[str, Any], dict[str, str]]:
    inside, host = _manager_paths(manager_id)
    value = _json_bytes(
        run(
            (
                "docker",
                "exec",
                manager_id,
                "python",
                "-c",
                LEDGER_PROBE,
                inside["pairing"],
                inside["credential"],
            ),
            timeout=60,
        ).stdout,
        "ledger_invalid",
    )
    if not isinstance(value, dict):
        raise SuccessorError("ledger_shape_invalid")
    return value, host


def validate_pre_ledger(document: dict[str, Any]) -> None:
    if (
        document.get("attempt_count") != 1
        or document.get("registration_count") != 1
        or document.get("registration_inventory_sha256") != PRE_INVENTORY_SHA256
        or document.get("unresolved_count") != 1
    ):
        raise SuccessorError("pre_ledger_cardinality_drift")
    attempts = document.get("attempts")
    attempt = attempts[0] if isinstance(attempts, list) and len(attempts) == 1 else None
    expected = {
        "pairing_id_sha256": PAIRING_SHA256,
        "hardware_id_sha256": HARDWARE_SHA256,
        "state": "ACTIVE",
        "phase": "BOOTSTRAP_ACCEPTED",
        "cleanup_state": "NONE",
        "node_id_present": False,
        "terminal_at_present": False,
        "terminal_reason": None,
        "expired_by_clock": True,
        "session_state": "pending",
        "session_hardware_sha256": HARDWARE_SHA256,
        "registration_match_count": 1,
        "current_pairing_matches": True,
        "registration_node_id_present": False,
        "pairing_credential_count": 0,
        "hardware_credential_history_count": 0,
    }
    if not isinstance(attempt, dict) or any(
        attempt.get(key) != value for key, value in expected.items()
    ):
        raise SuccessorError("pre_ledger_state_drift")


def validate_post_ledger(document: dict[str, Any]) -> None:
    if (
        document.get("attempt_count") != 1
        or document.get("registration_count") != 0
        or document.get("registration_inventory_sha256") != EMPTY_INVENTORY_SHA256
        or document.get("unresolved_count") != 0
    ):
        raise SuccessorError("post_ledger_cardinality_invalid")
    attempts = document.get("attempts")
    attempt = attempts[0] if isinstance(attempts, list) and len(attempts) == 1 else None
    expected = {
        "pairing_id_sha256": PAIRING_SHA256,
        "hardware_id_sha256": HARDWARE_SHA256,
        "state": "EXPIRED",
        "phase": "TERMINAL",
        "cleanup_state": "COMPLETE",
        "node_id_present": False,
        "terminal_at_present": True,
        "terminal_reason": "expired",
        "expired_by_clock": True,
        "session_state": "expired",
        "session_reason": "expired",
        "session_hardware_sha256": HARDWARE_SHA256,
        "registration_match_count": 0,
        "current_pairing_matches": False,
        "registration_node_id_present": False,
        "pairing_credential_count": 0,
        "hardware_credential_history_count": 0,
    }
    if not isinstance(attempt, dict) or any(
        attempt.get(key) != value for key, value in expected.items()
    ):
        raise SuccessorError("post_ledger_state_invalid")


def predecessor_evidence(expected_sha256: str) -> dict[str, Any]:
    if SHA64.fullmatch(expected_sha256 or "") is None:
        raise SuccessorError("predecessor_sha256_invalid")
    if sha_file(PREDECESSOR_TX) != expected_sha256:
        raise SuccessorError("predecessor_evidence_changed")
    value = _json_bytes(PREDECESSOR_TX.read_bytes(), "predecessor_json_invalid")
    if not isinstance(value, dict):
        raise SuccessorError("predecessor_shape_invalid")
    expected = {
        "schema": PREDECESSOR_SCHEMA,
        "status": "CLAIMED",
        "phase": "AUTHORIZATION_CLAIMED",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "target_source_head": TARGET_SOURCE_HEAD,
        "target_manager_image": TARGET_MANAGER_IMAGE,
        "target_manager_tar_sha256": TARGET_MANAGER_TAR_SHA256,
        "artifact_id": TARGET_ARTIFACT_ID,
        "artifact_digest_sha256": TARGET_ARTIFACT_SHA256,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise SuccessorError(f"predecessor_semantic_drift:{key}")
    for key in (
        "authorization_id_sha256",
        "executor_source_head",
        "executor_blob",
        "compose_sha256",
        "compose_render_sha256",
        "ha_mqtt_sha256",
    ):
        raw = value.get(key)
        pattern = SHA40 if key in {"executor_source_head", "executor_blob"} else SHA64
        if not isinstance(raw, str) or pattern.fullmatch(raw) is None:
            raise SuccessorError(f"predecessor_field_invalid:{key}")
    for key in ("broker_container_id", "manager_predecessor_container_id"):
        raw = value.get(key)
        if not isinstance(raw, str) or re.fullmatch(r"[0-9a-f]{64}", raw) is None:
            raise SuccessorError(f"predecessor_field_invalid:{key}")
    if (
        not isinstance(value.get("broker_image_id"), str)
        or IMAGE_ID.fullmatch(value["broker_image_id"]) is None
        or not isinstance(value.get("broker_started_at"), str)
        or not value["broker_started_at"]
    ):
        raise SuccessorError("predecessor_broker_binding_invalid")
    for key in ("broker_restart_count", "services_nrestarts"):
        raw = value.get(key)
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            raise SuccessorError(f"predecessor_field_invalid:{key}")
    return value


def _runtime_image_exists(reference: str, expected_id: str) -> None:
    result = run(
        ("docker", "image", "inspect", reference),
        allowed=frozenset({0, 1}),
    )
    if result.returncode:
        raise SuccessorError("rollback_predecessor_image_missing")
    value = _json_bytes(result.stdout, "rollback_image_inspect_invalid")
    observed = (
        value[0].get("Id")
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict)
        else None
    )
    if observed != expected_id:
        raise SuccessorError("rollback_predecessor_image_drift")


def _active_maintenance_documents() -> list[dict[str, Any]]:
    if not TRANSACTION_ROOT.exists():
        return []
    if TRANSACTION_ROOT.is_symlink() or not TRANSACTION_ROOT.is_dir():
        raise SuccessorError("transaction_root_invalid")
    meta = TRANSACTION_ROOT.stat()
    if (
        meta.st_uid != 0
        or meta.st_gid != 0
        or stat.S_IMODE(meta.st_mode) != 0o700
    ):
        raise SuccessorError("transaction_root_metadata_invalid")
    documents: list[dict[str, Any]] = []
    for path in sorted(TRANSACTION_ROOT.glob("*.json")):
        try:
            documents.append(maintenance.TransactionStore(path).load())
        except maintenance.MaintenanceTransactionError as error:
            raise SuccessorError("maintenance_transaction_unreadable") from error
    return documents


def _portable_identity_sha256(
    identity: portable.PortableImageIdentity,
) -> str:
    return sha_bytes(canonical(identity.to_dict()))


def _portable_identity_from_b64(
    value: str,
    expected_sha256: str,
) -> portable.PortableImageIdentity:
    if SHA64.fullmatch(expected_sha256 or "") is None:
        raise SuccessorError("portable_identity_sha256_invalid")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise SuccessorError("portable_identity_b64_invalid") from error
    document = _json_bytes(raw, "portable_identity_json_invalid")
    try:
        identity = portable.identity_from_dict(document)
    except portable.PortableImageIdentityError as error:
        raise SuccessorError(f"portable_identity_invalid:{error}") from error
    if _portable_identity_sha256(identity) != expected_sha256:
        raise SuccessorError("portable_identity_sha256_mismatch")
    if identity.archive_sha256 != TARGET_MANAGER_TAR_SHA256:
        raise SuccessorError("portable_identity_archive_drift")
    if identity.config_digest != TARGET_CONFIG_DIGEST:
        raise SuccessorError("portable_identity_config_drift")
    if identity.os != "linux" or identity.architecture != "arm64":
        raise SuccessorError("portable_identity_platform_drift")
    return identity


def _portable_identity_b64(identity: portable.PortableImageIdentity) -> str:
    return base64.b64encode(canonical(identity.to_dict())).decode("ascii")


def _verify_candidate_identity(
    identity: portable.PortableImageIdentity,
) -> portable.VerificationVerdict:
    verdict = portable.verify_docker_image(identity, TARGET_MANAGER_IMAGE)
    if verdict.status != "VERIFIED":
        raise SuccessorError(f"target_portable_identity_{verdict.status.lower()}")
    return verdict


def _service_semantic() -> dict[str, Any]:
    return {
        "active": systemctl("is-active", SERVICES_UNIT),
        "enabled": systemctl("is-enabled", SERVICES_UNIT),
        "manager_count": len(_container_ids("manager")),
        "homeassistant_count": len(_container_ids("homeassistant")),
    }


def _service_fingerprint() -> str:
    return sha_bytes(canonical(_service_semantic()))


def _gate_loaded_state() -> str:
    loaded = run(
        (
            "systemctl",
            "show",
            SERVICES_UNIT,
            "--property",
            "ExecCondition",
            "--value",
        )
    ).stdout.decode()
    return "YES" if str(GATE_TARGET) in loaded else "NO"


def _gate_state() -> dict[str, str]:
    absent = sha_text("ABSENT")
    return {
        "helper": sha_file(GATE_TARGET)
        if GATE_TARGET.exists() and not GATE_TARGET.is_symlink()
        else absent,
        "dropin": sha_file(GATE_DROPIN)
        if GATE_DROPIN.exists() and not GATE_DROPIN.is_symlink()
        else absent,
        "loaded": sha_text(_gate_loaded_state()),
    }


def _gate_fingerprint() -> str:
    return sha_bytes(canonical(_gate_state()))


def _expected_gate_after() -> tuple[str, dict[str, str]]:
    helper = _gate_source_bytes()
    state = {
        "helper": sha_bytes(helper),
        "dropin": sha_bytes(GATE_DROPIN_BYTES),
        "loaded": sha_text("YES"),
    }
    return sha_bytes(canonical(state)), state


def _current_release_id(
    compose_sha256: str,
    compose_env_sha256: str,
    rendered_sha256: str,
    unit: dict[str, str],
) -> str:
    return sha_bytes(
        canonical(
            {
                "schema": "gh.n3w-r10-e03-current-release-binding/2",
                "deployment_inputs": {
                    "compose_sha256": compose_sha256,
                    "compose_env_sha256": compose_env_sha256,
                },
                "compose_render_sha256": rendered_sha256,
                "manager_image": OLD_MANAGER_IMAGE,
                "homeassistant_image": HA_IMAGE,
                "broker_image": BROKER_IMAGE,
                "service_unit": unit,
                "state_contract": {
                    "pre_registration_inventory_sha256": PRE_INVENTORY_SHA256,
                    "post_registration_inventory_sha256": EMPTY_INVENTORY_SHA256,
                    "schema_migration_required": False,
                },
            }
        )
    )


def _target_release_id(
    identity: portable.PortableImageIdentity,
    compose_sha256: str,
    compose_env_sha256: str,
    unit: dict[str, str],
) -> str:
    try:
        return production_contract.portable_deployment_binding_id_v2(
            source_head=TARGET_SOURCE_HEAD,
            artifact_sha256=TARGET_ARTIFACT_SHA256,
            identity=identity,
            deployment_inputs={
                "compose_sha256": compose_sha256,
                "compose_env_sha256": compose_env_sha256,
            },
            service_unit=unit,
            state_contract={
                "pre_registration_inventory_sha256": PRE_INVENTORY_SHA256,
                "post_registration_inventory_sha256": EMPTY_INVENTORY_SHA256,
                "schema_migration_required": False,
            },
        )
    except production_contract.ProductionV2ContractError as error:
        raise SuccessorError("target_release_contract_invalid") from error


def preauthorization(
    *,
    identity: portable.PortableImageIdentity,
    expected_identity_sha256: str,
    predecessor_sha256: str,
    expected_host_binding_sha256: str,
) -> dict[str, Any]:
    if SHA64.fullmatch(expected_identity_sha256 or "") is None:
        raise SuccessorError("portable_identity_sha256_invalid")
    if _portable_identity_sha256(identity) != expected_identity_sha256:
        raise SuccessorError("portable_identity_sha256_mismatch")
    predecessor = predecessor_evidence(predecessor_sha256)
    observed_host = host_binding_sha256()
    if observed_host != expected_host_binding_sha256:
        raise SuccessorError("host_binding_mismatch")
    if systemctl("is-active", BROKER_UNIT) != "active" or systemctl(
        "is-enabled", BROKER_UNIT
    ) != "enabled":
        raise SuccessorError("broker_unit_drift")
    if systemctl("is-active", SERVICES_UNIT) != "active" or systemctl(
        "is-enabled", SERVICES_UNIT
    ) != "enabled":
        raise SuccessorError("services_unit_drift")
    if systemctl("is-active", REGISTRATION_GUARD_UNIT) != "active":
        raise SuccessorError("registration_guard_drift")
    unit = verify_service_unit()
    parse_activation_env()
    if (
        COMPOSE.is_symlink()
        or not COMPOSE.is_file()
        or COMPOSE_ENV.is_symlink()
        or not COMPOSE_ENV.is_file()
    ):
        raise SuccessorError("compose_authority_invalid")

    original = COMPOSE.read_bytes()
    compose_env_original = COMPOSE_ENV.read_bytes()
    validate_manager_image_indirection(original)
    compose_env_candidate = rewrite_manager_image_env(compose_env_original)
    before = render_compose_payload(original)
    services = before.get("services")
    if not isinstance(services, dict):
        raise SuccessorError("compose_services_invalid")
    if _service_record(before, "manager").get("image") != OLD_MANAGER_IMAGE:
        raise SuccessorError("compose_manager_image_drift")
    if _service_record(before, "homeassistant").get("image") != HA_IMAGE:
        raise SuccessorError("compose_homeassistant_image_drift")
    if _service_record(before, "broker").get("image") != BROKER_IMAGE:
        raise SuccessorError("compose_broker_image_drift")

    after = render_compose_payload(
        original,
        manager_image_override=TARGET_MANAGER_IMAGE,
    )
    validate_candidate(before, after)
    compose_sha256 = sha_bytes(original)
    compose_env_before_sha256 = sha_bytes(compose_env_original)
    compose_env_candidate_sha256 = sha_bytes(compose_env_candidate)
    deployment_before_fingerprint = deployment_inputs_fingerprint(
        compose_sha256,
        compose_env_before_sha256,
    )
    deployment_candidate_fingerprint = deployment_inputs_fingerprint(
        compose_sha256,
        compose_env_candidate_sha256,
    )
    if compose_sha256 != predecessor["compose_sha256"]:
        raise SuccessorError("predecessor_compose_binding_drift")
    if sha_bytes(canonical(before)) != predecessor["compose_render_sha256"]:
        raise SuccessorError("predecessor_compose_render_drift")

    manager = runtime("manager")
    ha = runtime("homeassistant")
    broker = runtime("broker")
    if (
        manager["image_ref"] != OLD_MANAGER_IMAGE
        or manager["image_id"] != OLD_MANAGER_ID
        or manager["network_mode"] != "host"
        or manager["restart_count"] != 0
    ):
        raise SuccessorError("manager_runtime_drift")
    if manager["container_id"] != predecessor["manager_predecessor_container_id"]:
        raise SuccessorError("manager_predecessor_continuity_drift")
    if (
        ha["image_ref"] != HA_IMAGE
        or ha["image_id"] != HA_IMAGE_ID
        or ha["network_mode"] != "host"
        or ha["restart_count"] != 0
    ):
        raise SuccessorError("homeassistant_runtime_drift")
    if (
        broker["image_ref"] != BROKER_IMAGE
        or broker["image_id"] != BROKER_IMAGE_ID
        or broker["restart_count"] != 0
    ):
        raise SuccessorError("broker_runtime_drift")
    if any(
        broker[key] != predecessor[predecessor_key]
        for key, predecessor_key in (
            ("container_id", "broker_container_id"),
            ("image_id", "broker_image_id"),
            ("started_at", "broker_started_at"),
            ("restart_count", "broker_restart_count"),
        )
    ):
        raise SuccessorError("broker_predecessor_continuity_drift")
    observed_services_nrestarts = systemd_nrestarts(SERVICES_UNIT)
    if observed_services_nrestarts != predecessor["services_nrestarts"]:
        raise SuccessorError("services_owner_restart_continuity_drift")

    _runtime_image_exists(OLD_MANAGER_ID, OLD_MANAGER_ID)
    _runtime_image_exists(OLD_MANAGER_IMAGE, OLD_MANAGER_ID)
    verdict = _verify_candidate_identity(identity)
    if listener_snapshot() != EXPECTED_LISTENERS:
        raise SuccessorError("listener_drift")
    ledger, host_paths = ledger_in_manager(manager["container_id"])
    validate_pre_ledger(ledger)
    if ha_mqtt_hash() != predecessor["ha_mqtt_sha256"]:
        raise SuccessorError("ha_mqtt_predecessor_drift")
    if shutil.disk_usage("/").free < MIN_FREE_BYTES:
        raise SuccessorError("maintenance_capacity_insufficient")
    active = _active_maintenance_documents()
    if any(doc["state"] in maintenance.ACTIVE_STATES for doc in active):
        raise SuccessorError("other_active_transaction")

    service_before = _service_semantic()
    if service_before != {
        "active": "active",
        "enabled": "enabled",
        "manager_count": 1,
        "homeassistant_count": 1,
    }:
        raise SuccessorError("application_owner_prestate_drift")

    gate_before = _gate_fingerprint()
    gate_after, _ = _expected_gate_after()
    rendered_sha256 = sha_bytes(canonical(before))
    current_release_id = _current_release_id(
        compose_sha256,
        compose_env_before_sha256,
        rendered_sha256,
        unit,
    )
    target_release_id = _target_release_id(
        identity,
        compose_sha256,
        compose_env_candidate_sha256,
        unit,
    )

    return {
        "schema": PLAN_SCHEMA,
        "predecessor_sha256": predecessor_sha256,
        "predecessor_authorization_id_sha256": predecessor[
            "authorization_id_sha256"
        ],
        "predecessor_executor_source_head": predecessor["executor_source_head"],
        "predecessor_executor_blob": predecessor["executor_blob"],
        "predecessor_disposition": "ABORTED_PRECUTOVER_STAGED_IMAGE_RETAINED",
        "host_binding_sha256": observed_host,
        "current_release_id": current_release_id,
        "target_release_id": target_release_id,
        "target_source_head": TARGET_SOURCE_HEAD,
        "artifact_sha256": TARGET_ARTIFACT_SHA256,
        "artifact_run_id": TARGET_ARTIFACT_RUN_ID,
        "artifact_id": TARGET_ARTIFACT_ID,
        "portable_identity": identity.to_dict(),
        "portable_identity_sha256": _portable_identity_sha256(identity),
        "target_runtime_image_id_observed": verdict.runtime_image_id,
        "compose_sha256": compose_sha256,
        "compose_render_sha256": rendered_sha256,
        "compose_env_before_sha256": compose_env_before_sha256,
        "compose_env_candidate_sha256": compose_env_candidate_sha256,
        "compose_env_before_b64": base64.b64encode(
            compose_env_original
        ).decode("ascii"),
        "compose_env_candidate_b64": base64.b64encode(
            compose_env_candidate
        ).decode("ascii"),
        "deployment_before_fingerprint": deployment_before_fingerprint,
        "deployment_candidate_fingerprint": deployment_candidate_fingerprint,
        "service_unit": unit,
        "service_before_fingerprint": sha_bytes(canonical(service_before)),
        "service_stopped_fingerprint": sha_bytes(
            canonical(
                {
                    "active": "inactive",
                    "enabled": "enabled",
                    "manager_count": 0,
                    "homeassistant_count": 0,
                }
            )
        ),
        "service_running_fingerprint": sha_bytes(
            canonical(
                {
                    "active": "active",
                    "enabled": "enabled",
                    "manager_count": 1,
                    "homeassistant_count": 1,
                }
            )
        ),
        "gate_before_fingerprint": gate_before,
        "gate_after_fingerprint": gate_after,
        "broker_baseline": broker,
        "manager_predecessor_container_id": manager["container_id"],
        "services_nrestarts": observed_services_nrestarts,
        "ha_mqtt_sha256": predecessor["ha_mqtt_sha256"],
        "state_paths": host_paths,
        "rollback_policy": "EXACT_CANDIDATE_TO_EXACT_BEFORE_ONLY",
        "resume_policy": [
            "APPLYING_AFTER_PROCESS_OR_SSH_LOSS",
            "APPLYING_AFTER_REBOOT_WITH_GATE",
            "VERIFYING_READINESS_AND_ACCEPTANCE",
        ],
        "schema_migration_required": False,
        "manual_sqlite_edit": False,
        "old_db_restore": False,
        "real_node_telemetry": "NOT_APPLICABLE",
        "no_docker_load": True,
        "no_docker_tag": True,
        "no_docker_rmi": True,
    }


def _execution_session_id(value: str) -> str:
    if TXID.fullmatch(value or "") is None:
        raise SuccessorError("execution_session_id_invalid")
    return value


def _authorization_id(value: str) -> str:
    if (
        not value.startswith("N3W_T1_R10_E03_SUCCESSOR_RECOVERY_")
        or len(value) > 200
        or not value.replace("_", "").replace("-", "").isalnum()
    ):
        raise SuccessorError("authorization_id_invalid")
    return value


def _build_full_plan(
    seed: dict[str, Any],
    *,
    transaction_id: str,
    authorization_id_sha256: str,
    preauth_plan_sha256: str,
    authority: dict[str, str],
) -> dict[str, Any]:
    plan = copy.deepcopy(seed)
    plan.update(
        {
            "transaction_id": transaction_id,
            "authorization_id_sha256": authorization_id_sha256,
            "preauth_plan_sha256": preauth_plan_sha256,
            "executor_source_head": authority["source_head"],
            "executor_blob": authority["executor_blob"],
            "module_set_sha256": authority["module_set_sha256"],
            "scope": list(SCOPE),
        }
    )
    return plan


def claim(
    *,
    identity: portable.PortableImageIdentity,
    expected_identity_sha256: str,
    predecessor_sha256: str,
    expected_host_binding_sha256: str,
    expected_preauth_plan_sha256: str,
    transaction_id: str,
    authorization_id: str,
    execution_session_id: str,
    confirmation: str,
) -> dict[str, Any]:
    if confirmation != CONFIRMATION:
        raise SuccessorError("confirmation_missing")
    if TXID.fullmatch(transaction_id or "") is None:
        raise SuccessorError("transaction_id_invalid")
    aid = _authorization_id(authorization_id)
    session_id = _execution_session_id(execution_session_id)
    if SHA64.fullmatch(expected_preauth_plan_sha256 or "") is None:
        raise SuccessorError("preauth_plan_sha256_invalid")

    with global_lock():
        authority = runtime_authority()
        seed = preauthorization(
            identity=identity,
            expected_identity_sha256=expected_identity_sha256,
            predecessor_sha256=predecessor_sha256,
            expected_host_binding_sha256=expected_host_binding_sha256,
        )
        observed_preauth_plan_sha256 = sha_bytes(canonical(seed))
        if observed_preauth_plan_sha256 != expected_preauth_plan_sha256:
            raise SuccessorError("preauth_plan_sha256_mismatch")

        authorization_hash = sha_text(aid)
        plan = _build_full_plan(
            seed,
            transaction_id=transaction_id,
            authorization_id_sha256=authorization_hash,
            preauth_plan_sha256=expected_preauth_plan_sha256,
            authority=authority,
        )
        plan_sha256 = maintenance.sha256_bytes(
            maintenance.canonical_bytes(plan)
        )
        binding = maintenance.MaintenanceBinding(
            transaction_id=transaction_id,
            authorization_id_sha256=authorization_hash,
            host_binding_sha256=expected_host_binding_sha256,
            current_release_id=seed["current_release_id"],
            target_release_id=seed["target_release_id"],
            artifact_sha256=TARGET_ARTIFACT_SHA256,
            executor_source_head=authority["source_head"],
            executor_blob=authority["executor_blob"],
            module_set_sha256=authority["module_set_sha256"],
            plan_sha256=plan_sha256,
            scope=SCOPE,
        )
        document = maintenance.new_transaction(
            binding,
            predecessor_sha256=predecessor_sha256,
            before={
                "deployment_inputs": seed["deployment_before_fingerprint"]
            },
            intended_after={
                "deployment_inputs": seed["deployment_candidate_fingerprint"]
            },
            plan=plan,
        )
        document = maintenance.mark_ready(document)
        document = maintenance.claim_authorization(document)
        document = maintenance.record_execution_session(
            document,
            session_id,
            action="claim",
        )

        _ensure_private_dir(TRANSACTION_ROOT)
        existing = _active_maintenance_documents()
        maintenance.ensure_no_other_active(
            existing,
            transaction_id=transaction_id,
        )
        store = maintenance.TransactionStore(
            _transaction_path(transaction_id)
        )
        store.create(document)

    return public_result(
        document,
        operation="claim",
        reason_code="SUCCESSOR_AUTHORIZATION_CLAIMED",
        last_proven_state="PREAUTH_EXACT_BEFORE",
        mutation_observed=False,
        recovery_class="APPLY_REQUIRED",
    )

def _binding(document: dict[str, Any]) -> maintenance.MaintenanceBinding:
    return maintenance.binding_from_transaction(document)


def _runtime_rebind(
    document: dict[str, Any],
    *,
    action: str,
    allowed_states: Iterable[str],
) -> maintenance.MaintenanceBinding:
    _require_global_lock()
    binding = _binding(document)
    maintenance.require_mutation_binding(
        document,
        binding,
        action=action,
        allowed_states=allowed_states,
    )
    authority = runtime_authority()
    if (
        authority["source_head"] != binding.executor_source_head
        or authority["executor_blob"] != binding.executor_blob
        or authority["module_set_sha256"] != binding.module_set_sha256
    ):
        raise SuccessorError("executor_authority_drift")
    if host_binding_sha256() != binding.host_binding_sha256:
        raise SuccessorError("host_binding_drift")
    maintenance.assert_predecessor_immutable(
        PREDECESSOR_TX,
        document["predecessor_sha256"],
    )
    predecessor_evidence(document["predecessor_sha256"])
    plan = document["plan"]
    identity = portable.identity_from_dict(plan["portable_identity"])
    if (
        plan.get("portable_identity_sha256") != _portable_identity_sha256(identity)
    ):
        raise SuccessorError("portable_identity_transaction_binding_drift")
    _verify_candidate_identity(identity)
    unit = verify_service_unit()
    source_release_id = _current_release_id(
        plan["compose_sha256"],
        plan["compose_env_before_sha256"],
        plan["compose_render_sha256"],
        unit,
    )
    target_release_id = _target_release_id(
        identity,
        plan["compose_sha256"],
        plan["compose_env_candidate_sha256"],
        unit,
    )
    if (
        plan["current_release_id"] != binding.current_release_id
        or plan["target_release_id"] != binding.target_release_id
        or plan["artifact_sha256"] != binding.artifact_sha256
        or source_release_id != binding.current_release_id
        or target_release_id != binding.target_release_id
    ):
        raise SuccessorError("release_binding_drift")
    return binding


def _save(
    store: maintenance.TransactionStore,
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    store.save(after, expected_generation=before["generation"])
    return store.load()


def _block(
    store: maintenance.TransactionStore,
    document: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    if document["state"] in {"READY", "APPLYING", "VERIFYING", "ROLLING_BACK"}:
        blocked = maintenance.transition(
            document,
            "BLOCKED",
            operation="blocked",
            reason=reason,
        )
        return _save(store, document, blocked)
    return document


def _operation(
    store: maintenance.TransactionStore,
    document: dict[str, Any],
    *,
    binding: maintenance.MaintenanceBinding,
    action: str,
    operation_type: str,
    before_fingerprint: str,
    after_fingerprint: str,
    reality: Callable[[], str],
    execute: Callable[[], None],
    allowed_states: Iterable[str],
    accept_after_without_intent: bool = False,
) -> dict[str, Any]:
    _require_global_lock()
    maintenance.require_mutation_binding(
        document,
        binding,
        action=action,
        allowed_states=allowed_states,
    )
    pending = maintenance.pending_operation(document)
    observed = reality()
    last_record = document["operations"][-1] if document["operations"] else None
    if (
        pending is None
        and isinstance(last_record, dict)
        and last_record.get("operation_type") == operation_type
        and last_record.get("status") == "COMPLETE"
        and last_record.get("intended_after_fingerprint") == after_fingerprint
        and last_record.get("observed_after_fingerprint") == after_fingerprint
        and observed == after_fingerprint
    ):
        return document
    if pending is not None:
        if pending["operation_type"] != operation_type:
            raise BlockedError("pending_operation_unexpected")
        if (
            pending["before_fingerprint"] != before_fingerprint
            or pending["intended_after_fingerprint"] != after_fingerprint
        ):
            raise BlockedError("pending_operation_binding_drift")
        if observed == after_fingerprint:
            finished = maintenance.finish_operation(
                document,
                observed_after_fingerprint=observed,
            )
            return _save(store, document, finished)
        if observed != before_fingerprint:
            raise BlockedError("operation_reality_unknown")
    else:
        if observed == after_fingerprint and accept_after_without_intent:
            intent = maintenance.begin_operation(
                document,
                operation_type=operation_type,
                before_fingerprint=before_fingerprint,
                intended_after_fingerprint=after_fingerprint,
                allowed_states=allowed_states,
            )
            document = _save(store, document, intent)
            finished = maintenance.finish_operation(
                document,
                observed_after_fingerprint=observed,
            )
            return _save(store, document, finished)
        if observed != before_fingerprint:
            raise BlockedError("operation_prestate_unknown")
        intent = maintenance.begin_operation(
            document,
            operation_type=operation_type,
            before_fingerprint=before_fingerprint,
            intended_after_fingerprint=after_fingerprint,
            allowed_states=allowed_states,
        )
        document = _save(store, document, intent)

    execute()
    observed = reality()
    if observed != after_fingerprint:
        raise BlockedError("operation_poststate_unproven")
    finished = maintenance.finish_operation(
        document,
        observed_after_fingerprint=observed,
    )
    return _save(store, document, finished)


def _install_gate() -> None:
    _atomic_create_or_exact(GATE_TARGET, _gate_source_bytes(), 0o755)
    _atomic_create_or_exact(GATE_DROPIN, GATE_DROPIN_BYTES, 0o644)
    run(("systemctl", "daemon-reload"), timeout=60)
    raw = run(("systemctl", "cat", SERVICES_UNIT)).stdout.decode()
    expected = GATE_DROPIN_BYTES.decode().strip()
    if expected not in raw:
        raise SuccessorError("activation_gate_dropin_unproven")
    loaded = run(
        (
            "systemctl",
            "show",
            SERVICES_UNIT,
            "--property",
            "ExecCondition",
            "--value",
        )
    ).stdout.decode()
    if str(GATE_TARGET) not in loaded:
        raise SuccessorError("activation_gate_not_loaded")
    result = run((str(GATE_TARGET),), allowed=frozenset({0, 1}))
    if result.returncode != 0:
        raise SuccessorError("activation_gate_ready_phase_invalid")


def _assert_gate_blocking() -> None:
    result = run((str(GATE_TARGET),), allowed=frozenset({0, 1}))
    if result.returncode != 1 or b"MAINTENANCE_BLOCKING" not in result.stderr:
        raise SuccessorError("activation_gate_not_blocking")


def _assert_gate_rollback_restored() -> None:
    result = run((str(GATE_TARGET),), allowed=frozenset({0, 1}))
    if result.returncode != 0:
        raise SuccessorError("activation_gate_rollback_restore_not_proven")


def _stop_services() -> None:
    run(("systemctl", "stop", SERVICES_UNIT), timeout=120)
    semantic = _service_semantic()
    if semantic != {
        "active": "inactive",
        "enabled": "enabled",
        "manager_count": 0,
        "homeassistant_count": 0,
    }:
        raise SuccessorError("application_owner_not_stopped")


def _start_services() -> None:
    run(("systemctl", "start", SERVICES_UNIT), timeout=180)


def _broker_continuity(plan: dict[str, Any]) -> dict[str, Any]:
    expected = plan["broker_baseline"]
    observed = runtime("broker")
    for key in ("container_id", "image_id", "started_at", "restart_count"):
        if observed.get(key) != expected.get(key):
            raise SuccessorError("broker_continuity_failed")
    if listener_count("tcp", 8883) != 1:
        raise SuccessorError("broker_listener_continuity_failed")
    return observed


def _deployment_reality(plan: dict[str, Any]) -> str:
    if (
        COMPOSE.is_symlink()
        or not COMPOSE.is_file()
        or COMPOSE_ENV.is_symlink()
        or not COMPOSE_ENV.is_file()
    ):
        raise BlockedError("deployment_inputs_authority_invalid")
    return deployment_inputs_fingerprint(
        sha_file(COMPOSE),
        sha_file(COMPOSE_ENV),
    )


def _publish_candidate_env(plan: dict[str, Any]) -> None:
    if _service_fingerprint() != plan["service_stopped_fingerprint"]:
        raise BlockedError("candidate_owner_not_controlled")
    current = _deployment_reality(plan)
    state = maintenance.require_compose_publishable(
        plan["deployment_before_fingerprint"],
        plan["deployment_candidate_fingerprint"],
        current,
    )
    if state == "AFTER":
        return
    if sha_file(COMPOSE) != plan["compose_sha256"]:
        raise BlockedError("compose_authority_drift")
    payload = base64.b64decode(
        plan["compose_env_candidate_b64"],
        validate=True,
    )
    _atomic_replace_exact(
        COMPOSE_ENV,
        payload,
        plan["compose_env_before_sha256"],
    )


def _completed_deployment_publish(
    document: dict[str, Any],
    plan: dict[str, Any],
) -> bool:
    return any(
        isinstance(record, dict)
        and record.get("operation_type") == "deployment_inputs_publish"
        and record.get("status") == "COMPLETE"
        and record.get("intended_after_fingerprint")
        == plan["deployment_candidate_fingerprint"]
        and record.get("observed_after_fingerprint")
        == plan["deployment_candidate_fingerprint"]
        for record in document.get("operations", [])
    )


def _restore_deployment_env(plan: dict[str, Any]) -> None:
    current = _deployment_reality(plan)
    state = maintenance.require_compose_rollbackable(
        plan["deployment_before_fingerprint"],
        plan["deployment_candidate_fingerprint"],
        current,
    )
    if state == "BEFORE":
        return
    if sha_file(COMPOSE) != plan["compose_sha256"]:
        raise BlockedError("rollback_compose_authority_drift")
    payload = base64.b64decode(
        plan["compose_env_before_b64"],
        validate=True,
    )
    _atomic_replace_exact(
        COMPOSE_ENV,
        payload,
        plan["compose_env_candidate_sha256"],
    )


def _load_f4() -> ModuleType:
    if F4_HOST.is_symlink() or not F4_HOST.is_file():
        raise SuccessorError("f4_authority_unavailable")
    loader = importlib.machinery.SourceFileLoader("n3w_e03_f4_authority", str(F4_HOST))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise SuccessorError("f4_authority_import_invalid")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    for name in (
        "_compose_service_inspect",
        "_container_established_socket_count",
        "_homeassistant_http_readiness",
        "_broker_auth_negative_and_provisioning_probe",
    ):
        if not callable(getattr(module, name, None)):
            raise SuccessorError("f4_authority_contract_missing")
    return module


def _load_f4_reboot_verify() -> ModuleType:
    if F4_REBOOT_VERIFY.is_symlink() or not F4_REBOOT_VERIFY.is_file():
        raise SuccessorError("f4_reboot_verify_authority_unavailable")
    loader = importlib.machinery.SourceFileLoader(
        "n3w_e03_f4_reboot_verify_authority",
        str(F4_REBOOT_VERIFY),
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise SuccessorError("f4_reboot_verify_authority_import_invalid")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    if not callable(getattr(module, "runtime_snapshot", None)):
        raise SuccessorError("f4_reboot_verify_contract_missing")
    return module


def _runtime_identity_sha256(item: dict[str, Any]) -> str:
    return sha_bytes(
        canonical([item["container_id"], item["started_at"]])
    )


def _validate_auth_probe(document: Any) -> dict[str, Any]:
    expected = {
        "manager_wrong_client_id_rejected",
        "provisioning_wrong_client_id_rejected",
        "homeassistant_wrong_client_id_rejected",
        "anonymous_rejected",
        "provisioning_exact_credential_auth",
    }
    if (
        not isinstance(document, dict)
        or set(document) != expected
        or any(document.get(key) is not True for key in expected)
    ):
        raise SuccessorError("broker_auth_probe_contract_invalid")
    return dict(document)


def _application_owner_acceptance(plan: dict[str, Any]) -> dict[str, Any]:
    semantic = _service_semantic()
    expected = {
        "active": "active",
        "enabled": "enabled",
        "manager_count": 1,
        "homeassistant_count": 1,
    }
    if semantic != expected:
        raise SuccessorError("application_owner_acceptance_drift")
    nrestarts = systemd_nrestarts(SERVICES_UNIT)
    if nrestarts != plan["services_nrestarts"]:
        raise SuccessorError("services_automatic_restart_observed")
    return {**semantic, "nrestarts": nrestarts}


def _authenticated_runtime_snapshot() -> dict[str, Any]:
    module = _load_f4_reboot_verify()
    try:
        document = module.runtime_snapshot()
    except Exception as error:
        raise SuccessorError(
            "authenticated_runtime_snapshot_failed"
        ) from error
    if (
        not isinstance(document, dict)
        or document.get("schema") != RUNTIME_SNAPSHOT_SCHEMA
        or document.get("status") != "PASS"
        or document.get("homeassistant_http_ready") is not True
    ):
        raise SuccessorError("authenticated_runtime_snapshot_invalid")
    for key in (
        "boot_id_sha256",
        "control_manifest_sha256",
        "systemd_state_sha256",
        "critical_errors_sha256",
    ):
        value = document.get(key)
        if not isinstance(value, str) or SHA64.fullmatch(value) is None:
            raise SuccessorError("authenticated_runtime_snapshot_digest_invalid")
    source_head = document.get("source_head")
    if not isinstance(source_head, str) or SHA40.fullmatch(source_head) is None:
        raise SuccessorError("authenticated_runtime_snapshot_source_invalid")

    containers = document.get("containers")
    if (
        not isinstance(containers, dict)
        or set(containers) != {"broker", "manager", "homeassistant"}
    ):
        raise SuccessorError("authenticated_runtime_container_set_invalid")
    observed_runtimes = {
        service: runtime(service)
        for service in ("broker", "manager", "homeassistant")
    }
    for service, observed in observed_runtimes.items():
        record = containers.get(service)
        if (
            not isinstance(record, dict)
            or record.get("running") is not True
            or record.get("restart_count") != observed["restart_count"]
            or record.get("identity_sha256")
            != _runtime_identity_sha256(observed)
        ):
            raise SuccessorError(
                f"authenticated_runtime_container_invalid:{service}"
            )

    auth = document.get("runtime_service_auth")
    if not isinstance(auth, dict) or set(auth) != {"manager", "homeassistant"}:
        raise SuccessorError("authenticated_runtime_auth_set_invalid")
    for service, port in (("manager", 8883), ("homeassistant", 1883)):
        record = auth.get(service)
        count = record.get("owned_socket_count") if isinstance(record, dict) else None
        if (
            not isinstance(record, dict)
            or record.get("authenticated") is not True
            or record.get("endpoint_port") != port
            or isinstance(count, bool)
            or not isinstance(count, int)
            or (service == "manager" and count != 1)
            or (service == "homeassistant" and count < 1)
        ):
            raise SuccessorError(
                f"authenticated_runtime_service_invalid:{service}"
            )
        for key in (
            "identity_sha256",
            "owned_socket_sha256",
            "authenticated_connection_sha256",
        ):
            value = record.get(key)
            if not isinstance(value, str) or SHA64.fullmatch(value) is None:
                raise SuccessorError(
                    f"authenticated_runtime_service_digest_invalid:{service}"
                )
    return copy.deepcopy(document)


def mqtt_readiness_sample(
    module: ModuleType,
    *,
    identity: portable.PortableImageIdentity,
) -> dict[str, Any]:
    if systemctl("is-enabled", SERVICES_UNIT) != "enabled":
        raise SuccessorError("services_owner_enablement_drift")
    if systemctl("is-active", SERVICES_UNIT) != "active":
        return {"state": "WAIT", "reason": "services_not_active"}
    try:
        manager_runtime = runtime("manager")
        ha_runtime = runtime("homeassistant")
    except SuccessorError:
        return {"state": "WAIT", "reason": "application_containers_not_ready"}
    if manager_runtime["image_ref"] != TARGET_MANAGER_IMAGE:
        raise SuccessorError("manager_target_ref_invalid")
    _verify_candidate_identity(identity)
    running_verdict = portable.verify_docker_image(
        identity,
        manager_runtime["image_id"],
    )
    if running_verdict.status != "VERIFIED":
        raise SuccessorError(
            "manager_running_portable_identity_"
            + running_verdict.status.lower()
        )
    if (
        manager_runtime["network_mode"] != "host"
        or manager_runtime["restart_count"] != 0
        or ha_runtime["image_ref"] != HA_IMAGE
        or ha_runtime["image_id"] != HA_IMAGE_ID
        or ha_runtime["network_mode"] != "host"
        or ha_runtime["restart_count"] != 0
    ):
        raise SuccessorError("application_runtime_contract_invalid")
    manager_inspect = module._compose_service_inspect("manager")
    ha_inspect = module._compose_service_inspect("homeassistant")
    manager_name = str(manager_inspect.get("Name", "")).lstrip("/")
    ha_name = str(ha_inspect.get("Name", "")).lstrip("/")
    if not manager_name or not ha_name:
        raise SuccessorError("runtime_container_name_invalid")
    manager_count = module._container_established_socket_count(
        manager_name,
        8883,
    )
    ha_count = module._container_established_socket_count(ha_name, 1883)
    if manager_count > 1:
        raise SuccessorError("manager_mqtt_socket_count_invalid")
    if manager_count == 0:
        return {"state": "WAIT", "reason": "manager_mqtt_socket_not_ready"}
    if ha_count == 0:
        return {"state": "WAIT", "reason": "homeassistant_mqtt_socket_not_ready"}
    if listener_snapshot() != EXPECTED_LISTENERS:
        return {"state": "WAIT", "reason": "listeners_not_ready"}
    return {
        "state": "READY",
        "manager_mqtt_socket_count": manager_count,
        "homeassistant_mqtt_socket_count": ha_count,
        "manager_container_id": manager_runtime["container_id"],
        "homeassistant_container_id": ha_runtime["container_id"],
        "manager_started_at": manager_runtime["started_at"],
        "homeassistant_started_at": ha_runtime["started_at"],
    }


def wait_readiness(
    *,
    identity: portable.PortableImageIdentity,
    timeout: float = READINESS_TIMEOUT_SECONDS,
    poll: float = READINESS_POLL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    module = _load_f4()
    deadline = clock() + timeout
    last: dict[str, Any] = {"state": "WAIT", "reason": "not_sampled"}
    while True:
        last = mqtt_readiness_sample(module, identity=identity)
        if last["state"] == "READY":
            return {**last, "f4_authority": True}
        if clock() >= deadline:
            raise SuccessorError(f"mqtt_readiness_timeout:{last.get('reason')}")
        sleep(poll)


def strict_acceptance(
    plan: dict[str, Any],
    *,
    identity: portable.PortableImageIdentity,
    stability_seconds: float = STABILITY_WINDOW_SECONDS,
    poll: float = READINESS_POLL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    module = _load_f4()
    first = mqtt_readiness_sample(module, identity=identity)
    if first.get("state") != "READY":
        raise SuccessorError("acceptance_mqtt_not_ready")

    owner_baseline = _application_owner_acceptance(plan)
    manager = runtime("manager")
    ha = runtime("homeassistant")
    broker = _broker_continuity(plan)
    if manager["container_id"] == plan["manager_predecessor_container_id"]:
        raise SuccessorError("manager_container_not_recreated")
    if ha_mqtt_hash() != plan["ha_mqtt_sha256"]:
        raise SuccessorError("ha_mqtt_continuity_changed")

    post, _paths = ledger_in_manager(manager["container_id"])
    validate_post_ledger(post)
    module._homeassistant_http_readiness()
    auth_probe = _validate_auth_probe(
        module._broker_auth_negative_and_provisioning_probe(
            TARGET_MANAGER_IMAGE
        )
    )
    authenticated_baseline = _authenticated_runtime_snapshot()

    baseline = {
        "manager_container_id": manager["container_id"],
        "manager_started_at": manager["started_at"],
        "manager_restart_count": manager["restart_count"],
        "ha_container_id": ha["container_id"],
        "ha_started_at": ha["started_at"],
        "ha_restart_count": ha["restart_count"],
        "broker_container_id": broker["container_id"],
        "broker_started_at": broker["started_at"],
        "broker_restart_count": broker["restart_count"],
    }
    samples = 1
    deadline = clock() + stability_seconds
    while clock() < deadline:
        sleep(poll)
        sample = mqtt_readiness_sample(module, identity=identity)
        if sample.get("state") != "READY":
            raise SuccessorError("acceptance_stability_mqtt_lost")
        if _application_owner_acceptance(plan) != owner_baseline:
            raise SuccessorError("acceptance_owner_identity_changed")
        now_manager = runtime("manager")
        now_ha = runtime("homeassistant")
        now_broker = _broker_continuity(plan)
        observed = {
            "manager_container_id": now_manager["container_id"],
            "manager_started_at": now_manager["started_at"],
            "manager_restart_count": now_manager["restart_count"],
            "ha_container_id": now_ha["container_id"],
            "ha_started_at": now_ha["started_at"],
            "ha_restart_count": now_ha["restart_count"],
            "broker_container_id": now_broker["container_id"],
            "broker_started_at": now_broker["started_at"],
            "broker_restart_count": now_broker["restart_count"],
        }
        if observed != baseline:
            raise SuccessorError("acceptance_runtime_identity_changed")
        samples += 1

    if ha_mqtt_hash() != plan["ha_mqtt_sha256"]:
        raise SuccessorError("ha_mqtt_stability_changed")
    module._homeassistant_http_readiness()
    authenticated_final = _authenticated_runtime_snapshot()
    if authenticated_final != authenticated_baseline:
        raise SuccessorError("authenticated_runtime_evidence_changed")

    post_final, _ = ledger_in_manager(manager["container_id"])
    validate_post_ledger(post_final)
    return {
        "status": "PASS",
        "manager_exact_release_binding": True,
        "homeassistant_expected_release_binding": True,
        "broker_continuity": True,
        "application_owner_stable": True,
        "expected_listeners": True,
        "manager_authenticated_mqtt_session": True,
        "homeassistant_authenticated_mqtt_session": True,
        "process_socket_ownership": True,
        "auth_probe": auth_probe,
        "authenticated_runtime_snapshot_sha256": sha_bytes(
            canonical(authenticated_final)
        ),
        "stability_window_seconds": stability_seconds,
        "stability_samples": samples,
        "registration_count": post_final["registration_count"],
        "unresolved_count": post_final["unresolved_count"],
        "registration_inventory_sha256": post_final[
            "registration_inventory_sha256"
        ],
        "real_node_telemetry": "NOT_APPLICABLE",
    }

def apply(transaction_id: str, execution_session_id: str) -> dict[str, Any]:
    session_id = _execution_session_id(execution_session_id)
    with global_lock():
        store = maintenance.TransactionStore(_transaction_path(transaction_id))
        document = store.load()
        if document["state"] in maintenance.ACTIVE_STATES or document["state"] == "ROLLED_BACK":
            session_document = maintenance.record_execution_session(
                document,
                session_id,
                action="apply",
            )
            document = _save(store, document, session_document)
        plan = document["plan"]
        identity = portable.identity_from_dict(plan["portable_identity"])
        if document["state"] == "COMMITTED":
            return public_result(
                document,
                operation="apply",
                reason_code="ALREADY_COMMITTED",
                last_proven_state="TARGET_RUNTIME_ACCEPTED",
                mutation_observed=document["operation_seq"] > 0,
                recovery_class="COMMITTED",
            )
        if document["state"] == "BLOCKED":
            return public_result(
                document,
                operation="apply",
                reason_code=document.get("last_reason") or "BLOCKED",
                last_proven_state="BLOCKED",
                mutation_observed=document["operation_seq"] > 0,
                recovery_class="BLOCKED_NO_REPLAY",
            )
        if document["state"] in {"ROLLING_BACK", "ROLLED_BACK"}:
            return rollback(
                transaction_id,
                reason=document.get("last_reason") or "resume_rollback",
                execution_session_id=None,
                _store=store,
                _document=document,
            )
        try:
            if document["state"] == "READY":
                binding = _runtime_rebind(
                    document,
                    action="activation_gate_install",
                    allowed_states={"READY"},
                )
                document = _operation(
                    store,
                    document,
                    binding=binding,
                    action="activation_gate_install",
                    operation_type="activation_gate_install",
                    before_fingerprint=plan["gate_before_fingerprint"],
                    after_fingerprint=plan["gate_after_fingerprint"],
                    reality=_gate_fingerprint,
                    execute=_install_gate,
                    allowed_states={"READY"},
                    accept_after_without_intent=True,
                )
                applying = maintenance.begin_apply(document)
                document = _save(store, document, applying)
                _assert_gate_blocking()

            if document["state"] == "APPLYING":
                binding = _runtime_rebind(
                    document,
                    action="service_stop",
                    allowed_states={"APPLYING"},
                )
                _broker_continuity(plan)
                document = _operation(
                    store,
                    document,
                    binding=binding,
                    action="service_stop",
                    operation_type="service_stop",
                    before_fingerprint=plan["service_before_fingerprint"],
                    after_fingerprint=plan["service_stopped_fingerprint"],
                    reality=_service_fingerprint,
                    execute=_stop_services,
                    allowed_states={"APPLYING"},
                )
                _broker_continuity(plan)

                binding = _runtime_rebind(
                    document,
                    action="deployment_inputs_publish",
                    allowed_states={"APPLYING"},
                )
                document = _operation(
                    store,
                    document,
                    binding=binding,
                    action="deployment_inputs_publish",
                    operation_type="deployment_inputs_publish",
                    before_fingerprint=plan["deployment_before_fingerprint"],
                    after_fingerprint=plan["deployment_candidate_fingerprint"],
                    reality=lambda: _deployment_reality(plan),
                    execute=lambda: _publish_candidate_env(plan),
                    allowed_states={"APPLYING"},
                )
                if _deployment_reality(plan) != plan[
                    "deployment_candidate_fingerprint"
                ]:
                    raise BlockedError("candidate_deployment_reality_unknown")
                rendered = render_compose_payload(COMPOSE.read_bytes())
                if _service_record(rendered, "manager").get("image") != TARGET_MANAGER_IMAGE:
                    raise SuccessorError("candidate_readback_invalid")
                _verify_candidate_identity(identity)
                _broker_continuity(plan)

                verifying = maintenance.transition(
                    document,
                    "VERIFYING",
                    operation="candidate_published_owner_controlled",
                    observed_after={
                        "deployment_inputs": plan[
                            "deployment_candidate_fingerprint"
                        ]
                    },
                )
                document = _save(store, document, verifying)

            if document["state"] != "VERIFYING":
                raise SuccessorError("apply_state_not_resumable")

            binding = _runtime_rebind(
                document,
                action="service_start",
                allowed_states={"VERIFYING"},
            )
            _runtime_image_exists(HA_IMAGE, HA_IMAGE_ID)
            document = _operation(
                store,
                document,
                binding=binding,
                action="service_start",
                operation_type="service_start",
                before_fingerprint=plan["service_stopped_fingerprint"],
                after_fingerprint=plan["service_running_fingerprint"],
                reality=_service_fingerprint,
                execute=_start_services,
                allowed_states={"VERIFYING"},
                accept_after_without_intent=True,
            )

            wait_readiness(identity=identity)
            _runtime_rebind(
                document,
                action="runtime_acceptance",
                allowed_states={"VERIFYING"},
            )
            acceptance = strict_acceptance(plan, identity=identity)
            committed = maintenance.transition(
                document,
                "COMMITTED",
                operation="runtime_acceptance_pass",
                reason=None,
                observed_after={
                    "deployment_inputs": plan[
                        "deployment_candidate_fingerprint"
                    ]
                },
            )
            document = _save(store, document, committed)
            return public_result(
                document,
                operation="apply",
                reason_code="SUCCESSOR_COMMITTED",
                last_proven_state="TARGET_RUNTIME_ACCEPTED",
                mutation_observed=True,
                recovery_class="COMMITTED",
                extra={
                    "registration_count": acceptance["registration_count"],
                    "unresolved_count": acceptance["unresolved_count"],
                    "registration_inventory_sha256": acceptance[
                        "registration_inventory_sha256"
                    ],
                    "real_node_telemetry": "NOT_APPLICABLE",
                },
            )
        except BlockedError as error:
            document = _block(store, store.load(), reason=safe_reason(error))
            return public_result(
                document,
                operation="apply",
                reason_code=safe_reason(error),
                last_proven_state="BLOCKED_UNKNOWN_REALITY",
                mutation_observed=document["operation_seq"] > 0,
                recovery_class="BLOCKED_NO_WRITE",
            )
        except Exception as error:
            current = store.load()
            if current["state"] == "VERIFYING":
                try:
                    return rollback(
                        transaction_id,
                        reason=safe_reason(error),
                        execution_session_id=None,
                        _store=store,
                        _document=current,
                    )
                except Exception as rollback_error:
                    blocked = _block(
                        store,
                        store.load(),
                        reason="rollback_failed_" + safe_reason(rollback_error),
                    )
                    return public_result(
                        blocked,
                        operation="apply",
                        reason_code=safe_reason(error),
                        last_proven_state="ROLLBACK_UNPROVEN",
                        mutation_observed=True,
                        recovery_class="BLOCKED_ROLLBACK_UNPROVEN",
                    )
            blocked = _block(store, current, reason=safe_reason(error))
            return public_result(
                blocked,
                operation="apply",
                reason_code=safe_reason(error),
                last_proven_state="APPLY_INCOMPLETE",
                mutation_observed=blocked["operation_seq"] > 0,
                recovery_class="BLOCKED_REVIEW_REQUIRED",
            )


def rollback(
    transaction_id: str,
    *,
    reason: str,
    execution_session_id: str | None,
    _store: maintenance.TransactionStore | None = None,
    _document: dict[str, Any] | None = None,
) -> dict[str, Any]:
    owned_lock = _store is None
    if owned_lock:
        lock = global_lock()
        lock.__enter__()
    else:
        lock = None
    store: maintenance.TransactionStore | None = _store
    try:
        store = store or maintenance.TransactionStore(
            _transaction_path(transaction_id)
        )
        document = _document or store.load()
        if execution_session_id is not None:
            session_id = _execution_session_id(execution_session_id)
            session_document = maintenance.record_execution_session(
                document,
                session_id,
                action="rollback",
            )
            document = _save(store, document, session_document)
        plan = document["plan"]

        if document["state"] == "ROLLED_BACK":
            return public_result(
                document,
                operation="rollback",
                reason_code="ALREADY_ROLLED_BACK",
                last_proven_state="EXACT_PREDECESSOR_RESTORED",
                mutation_observed=document["operation_seq"] > 0,
                recovery_class="ROLLED_BACK",
            )
        if document["state"] == "VERIFYING":
            rolling = maintenance.transition(
                document,
                "ROLLING_BACK",
                operation="rollback_begin",
                reason=reason,
            )
            document = _save(store, document, rolling)
        if document["state"] != "ROLLING_BACK":
            raise SuccessorError("rollback_state_invalid")

        binding = _runtime_rebind(
            document,
            action="rollback_service_stop",
            allowed_states={"ROLLING_BACK"},
        )
        current_service = _service_fingerprint()
        if current_service == plan["service_running_fingerprint"]:
            before_service = plan["service_running_fingerprint"]
        elif current_service == plan["service_stopped_fingerprint"]:
            before_service = plan["service_stopped_fingerprint"]
        else:
            raise BlockedError("rollback_service_reality_unknown")
        document = _operation(
            store,
            document,
            binding=binding,
            action="rollback_service_stop",
            operation_type="rollback_service_stop",
            before_fingerprint=before_service,
            after_fingerprint=plan["service_stopped_fingerprint"],
            reality=_service_fingerprint,
            execute=_stop_services,
            allowed_states={"ROLLING_BACK"},
            accept_after_without_intent=True,
        )
        _broker_continuity(plan)

        if not _completed_deployment_publish(document, plan):
            raise BlockedError("rollback_candidate_write_unproven")
        binding = _runtime_rebind(
            document,
            action="deployment_inputs_rollback",
            allowed_states={"ROLLING_BACK"},
        )
        document = _operation(
            store,
            document,
            binding=binding,
            action="deployment_inputs_rollback",
            operation_type="deployment_inputs_rollback",
            before_fingerprint=plan["deployment_candidate_fingerprint"],
            after_fingerprint=plan["deployment_before_fingerprint"],
            reality=lambda: _deployment_reality(plan),
            execute=lambda: _restore_deployment_env(plan),
            allowed_states={"ROLLING_BACK"},
            accept_after_without_intent=True,
        )

        _assert_gate_rollback_restored()
        _runtime_image_exists(OLD_MANAGER_IMAGE, OLD_MANAGER_ID)
        _runtime_image_exists(HA_IMAGE, HA_IMAGE_ID)
        binding = _runtime_rebind(
            document,
            action="rollback_service_start",
            allowed_states={"ROLLING_BACK"},
        )
        document = _operation(
            store,
            document,
            binding=binding,
            action="rollback_service_start",
            operation_type="rollback_service_start",
            before_fingerprint=plan["service_stopped_fingerprint"],
            after_fingerprint=plan["service_running_fingerprint"],
            reality=_service_fingerprint,
            execute=_start_services,
            allowed_states={"ROLLING_BACK"},
            accept_after_without_intent=True,
        )

        manager = runtime("manager")
        if (
            manager["image_ref"] != OLD_MANAGER_IMAGE
            or manager["image_id"] != OLD_MANAGER_ID
            or manager["network_mode"] != "host"
            or manager["restart_count"] != 0
        ):
            raise SuccessorError("rollback_manager_predecessor_not_restored")
        ha = runtime("homeassistant")
        if (
            ha["image_ref"] != HA_IMAGE
            or ha["image_id"] != HA_IMAGE_ID
            or ha["network_mode"] != "host"
            or ha["restart_count"] != 0
        ):
            raise SuccessorError("rollback_homeassistant_not_restored")
        _broker_continuity(plan)
        if _deployment_reality(plan) != plan["deployment_before_fingerprint"]:
            raise BlockedError("rollback_deployment_poststart_drift")

        rolled = maintenance.transition(
            document,
            "ROLLED_BACK",
            operation="rollback_runtime_restored",
            reason=reason,
            observed_after={
                "deployment_inputs": plan["deployment_before_fingerprint"]
            },
        )
        document = _save(store, document, rolled)
        return public_result(
            document,
            operation="rollback",
            reason_code=reason,
            last_proven_state="EXACT_PREDECESSOR_RESTORED",
            mutation_observed=True,
            recovery_class="ROLLED_BACK",
        )
    except Exception as error:
        if store is not None:
            current = store.load()
            if current["state"] in {
                "READY",
                "APPLYING",
                "VERIFYING",
                "ROLLING_BACK",
            }:
                blocked = _block(
                    store,
                    current,
                    reason=safe_reason(error),
                )
                return public_result(
                    blocked,
                    operation="rollback",
                    reason_code=safe_reason(error),
                    last_proven_state="ROLLBACK_BLOCKED",
                    mutation_observed=blocked["operation_seq"] > 0,
                    recovery_class="BLOCKED_ROLLBACK_UNPROVEN",
                )
        raise
    finally:
        if lock is not None:
            lock.__exit__(None, None, None)

def public_result(
    document: dict[str, Any],
    *,
    operation: str,
    reason_code: str,
    last_proven_state: str,
    mutation_observed: bool,
    recovery_class: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": (
            "PASS"
            if document["state"] in {"COMMITTED", "ROLLED_BACK"}
            else "STOP"
            if document["state"] == "BLOCKED"
            else "PASS"
        ),
        "transaction_id_sha256": sha_text(document["transaction_id"]),
        "execution_session_id_sha256": (
            document["execution_sessions"][-1]["session_id_sha256"]
            if document["execution_sessions"]
            else None
        ),
        "stage": document["state"],
        "operation": operation,
        "reason_code": reason_code,
        "last_proven_state": last_proven_state,
        "authorization_consumed": document["authorization_consumed"],
        "replay_allowed": document["replay_allowed"],
        "mutation_observed": mutation_observed,
        "recovery_class": recovery_class,
        "predecessor_sha256": document["predecessor_sha256"],
        "target_release_id": document["target_release_id"],
        "artifact_sha256": document["artifact_sha256"],
        "board_access": False,
    }
    if extra:
        result.update(extra)
    return result


def status(transaction_id: str) -> dict[str, Any]:
    store = maintenance.TransactionStore(_transaction_path(transaction_id))
    document = store.load()
    maintenance.assert_predecessor_immutable(
        PREDECESSOR_TX,
        document["predecessor_sha256"],
    )
    deployment = _deployment_reality(document["plan"])
    disposition = maintenance.recovery_disposition(
        document,
        {"deployment_inputs": deployment},
    )
    return public_result(
        document,
        operation="status",
        reason_code="READ_ONLY_STATUS",
        last_proven_state=f"COMPOSE_{disposition}",
        mutation_observed=document["operation_seq"] > 0,
        recovery_class=disposition,
    )


def build_identity(
    path: Path,
    *,
    expected_archive_size_bytes: int,
) -> dict[str, Any]:
    if (
        isinstance(expected_archive_size_bytes, bool)
        or not isinstance(expected_archive_size_bytes, int)
        or expected_archive_size_bytes <= 0
    ):
        raise SuccessorError("artifact_tar_size_authority_invalid")
    identity = portable.parse_image_archive(
        path,
        expected_archive_sha256=TARGET_MANAGER_TAR_SHA256,
        expected_archive_size_bytes=expected_archive_size_bytes,
        expected_tag=TARGET_MANAGER_IMAGE,
        platform_os="linux",
        platform_architecture="arm64",
    )
    if identity.config_digest != TARGET_CONFIG_DIGEST:
        raise SuccessorError("artifact_config_digest_drift")
    identity_sha256 = _portable_identity_sha256(identity)
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "build-identity",
        "portable_identity_b64": _portable_identity_b64(identity),
        "portable_identity_sha256": identity_sha256,
        "archive_sha256": identity.archive_sha256,
        "archive_size_bytes": identity.archive_size_bytes,
        "config_digest": identity.config_digest,
        "board_access": False,
        "t1_access": False,
    }


def _emit(document: dict[str, Any], *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    stream.write(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="operation", required=True)

    build = sub.add_parser("build-identity")
    build.add_argument("--manager-tar", required=True)
    build.add_argument(
        "--manager-tar-size-bytes",
        required=True,
        type=int,
    )

    pre = sub.add_parser("preauth")
    pre.add_argument("--portable-identity-b64", required=True)
    pre.add_argument("--portable-identity-sha256", required=True)
    pre.add_argument("--predecessor-sha256", required=True)
    pre.add_argument("--host-binding-sha256", required=True)

    claim_parser = sub.add_parser("claim")
    claim_parser.add_argument("--portable-identity-b64", required=True)
    claim_parser.add_argument("--portable-identity-sha256", required=True)
    claim_parser.add_argument("--preauth-plan-sha256", required=True)
    claim_parser.add_argument("--predecessor-sha256", required=True)
    claim_parser.add_argument("--host-binding-sha256", required=True)
    claim_parser.add_argument("--transaction-id", required=True)
    claim_parser.add_argument("--authorization-id", required=True)
    claim_parser.add_argument("--execution-session-id", required=True)
    claim_parser.add_argument("--confirmation", required=True)

    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--transaction-id", required=True)
    apply_parser.add_argument("--execution-session-id", required=True)

    rollback_parser = sub.add_parser("rollback")
    rollback_parser.add_argument("--transaction-id", required=True)
    rollback_parser.add_argument("--execution-session-id", required=True)
    rollback_parser.add_argument("--reason", required=True)

    status_parser = sub.add_parser("status")
    status_parser.add_argument("--transaction-id", required=True)

    args = parser.parse_args()
    try:
        if args.operation == "build-identity":
            result = build_identity(
                Path(args.manager_tar),
                expected_archive_size_bytes=args.manager_tar_size_bytes,
            )
        elif args.operation == "preauth":
            identity = _portable_identity_from_b64(
                args.portable_identity_b64,
                args.portable_identity_sha256,
            )
            plan = preauthorization(
                identity=identity,
                expected_identity_sha256=args.portable_identity_sha256,
                predecessor_sha256=args.predecessor_sha256,
                expected_host_binding_sha256=args.host_binding_sha256,
            )
            preauth_plan_sha256 = sha_bytes(canonical(plan))
            result = {
                "schema": SCHEMA,
                "status": "PASS",
                "operation": "preauth",
                "portable_identity_sha256": plan["portable_identity_sha256"],
                "preauth_plan_sha256": preauth_plan_sha256,
                "predecessor_sha256": plan["predecessor_sha256"],
                "current_release_id": plan["current_release_id"],
                "target_release_id": plan["target_release_id"],
                "target_runtime_image_id_observed": plan[
                    "target_runtime_image_id_observed"
                ],
                "candidate_portable_identity": "VERIFIED",
                "compose_prestate": "EXACT_PREDECESSOR",
                "old_authorization": "CONSUMED_NO_REPLAY",
                "no_other_active_transaction": True,
                "t1_mutation": False,
                "board_access": False,
            }
        elif args.operation == "claim":
            identity = _portable_identity_from_b64(
                args.portable_identity_b64,
                args.portable_identity_sha256,
            )
            result = claim(
                identity=identity,
                expected_identity_sha256=args.portable_identity_sha256,
                predecessor_sha256=args.predecessor_sha256,
                expected_host_binding_sha256=args.host_binding_sha256,
                expected_preauth_plan_sha256=args.preauth_plan_sha256,
                transaction_id=args.transaction_id,
                authorization_id=args.authorization_id,
                execution_session_id=args.execution_session_id,
                confirmation=args.confirmation,
            )
        elif args.operation == "apply":
            result = apply(args.transaction_id, args.execution_session_id)
        elif args.operation == "rollback":
            result = rollback(
                args.transaction_id,
                reason=args.reason,
                execution_session_id=args.execution_session_id,
            )
        elif args.operation == "status":
            result = status(args.transaction_id)
        else:
            raise SuccessorError("operation_invalid")
        _emit(result)
        return 0 if result.get("status") == "PASS" else 3
    except Exception as error:
        _emit(
            {
                "schema": SCHEMA,
                "status": "STOP",
                "operation": args.operation,
                "reason_code": safe_reason(error),
                "authorization_replay": False,
                "board_access": False,
            },
            error=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
