#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import copy
import fcntl
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Sequence

SCHEMA = "gh.n3w-r10-e03-manager-successor-refresh-live/1"
TX_SCHEMA = "gh.n3w-r10-e03-manager-successor-refresh-transaction/1"
CONFIRMATION = "N3W_R10_E03_MANAGER_SUCCESSOR_REFRESH_LIVE_APPLY"

PROJECT = "n3wfc4"
BROKER_UNIT = "n3wfc4-broker-activation.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
REGISTRATION_GUARD_UNIT = "n3wfc4-registration-ingress-guard.service"
BROKER_ENV = Path("/etc/n3wfc4/broker-activation.env")
COMPOSE = Path("/etc/n3wfc4/docker-compose.yml")
COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")
TX_PATH = Path("/var/lib/n3w-t1-provisioning/R10_E03_MANAGER_SUCCESSOR_REFRESH.json")
HA_CONFIG_ENTRIES = Path("/var/lib/n3wfc4-homeassistant/.storage/core.config_entries")

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

OLD_MANAGER_IMAGE = "local/greenhouse-manager:fresh-ff750b3801a2"
OLD_MANAGER_ID = "sha256:5b8150e457a1cc5af3e7e576514dfb3fa33e15f4dfe4801640ec604dd962218f"
TARGET_SOURCE_HEAD = "f8876fd87165df731d792690a8288867c3eeef55"
TARGET_MANAGER_IMAGE = "local/greenhouse-manager:fresh-f8876fd87165"
TARGET_MANAGER_ID = "sha256:089153fa4bbc823a1357427083f23ef96933a119c6ae150c143b62d7b40859e4"
TARGET_MANAGER_TAR_SHA256 = "d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5"
TARGET_ARTIFACT_RUN_ID = 40880705472
TARGET_ARTIFACT_ID = 12900601779
TARGET_ARTIFACT_DIGEST = "c94568f740b911eee0f4238207249b1e98f84748c17a902938ccc35293e4b183"
TARGET_ARTIFACT_NAME = (
    "n3w-t1-fresh-exact-arm64-"
    "f8876fd87165df731d792690a8288867c3eeef55"
)

HA_IMAGE = "local/n3w-homeassistant:2026.10.0-0c73235a"
HA_IMAGE_ID = "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306"
BROKER_IMAGE = "local/n3w-mosquitto:2.1.2-3184566d"
BROKER_IMAGE_ID = "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563"

PAIRING_SHA256 = "9931c366d483abd3af6e1e3d903b82645542346dbd258975acd788998f0404dc"
HARDWARE_SHA256 = "3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55"
PRE_INVENTORY_SHA256 = "2ac5373cc532499154fffdd42e14f6225cc2ebdd90deb0a5bacdda3ec3ccaaed"
EMPTY_INVENTORY_SHA256 = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


class RefreshError(RuntimeError):
    pass


class AuthorizationConsumedError(RefreshError):
    pass


class AuthorizationUnknownError(RefreshError):
    pass


def safe_error_code(error: BaseException) -> str:
    if isinstance(error, RefreshError):
        raw = str(error)
        code = raw.split(":", 1)[0]
        if re.fullmatch(r"[A-Za-z0-9_]{3,100}", code):
            return code
    return type(error).__name__


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_text(value: str) -> str:
    return sha_bytes(value.encode())


def sha_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise RefreshError("file_invalid")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def run(
    argv: Sequence[str],
    *,
    timeout: int = 30,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        tuple(argv),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout).decode(errors="replace").strip()
        raise RefreshError(f"command_failed:{argv[0]}:{detail[:300]}")
    return result


def systemctl(mode: str, unit: str) -> str:
    result = run(("systemctl", mode, unit), check=False)
    value = result.stdout.decode().strip()
    if result.returncode and value not in {"inactive", "failed", "disabled", "static", "not-found"}:
        raise RefreshError(f"systemctl_{mode}_failed:{unit}")
    return value


def parse_activation_env() -> dict[str, str]:
    if BROKER_ENV.is_symlink() or not BROKER_ENV.is_file():
        raise RefreshError("activation_env_invalid")
    values: dict[str, str] = {}
    for raw in BROKER_ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise RefreshError("activation_env_line_invalid")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
            value = value[1:-1]
        if key in values:
            raise RefreshError("activation_env_duplicate")
        values[key] = value
    expected = {
        "N3WFC4_COMPOSE_FILE": str(COMPOSE),
        "N3WFC4_COMPOSE_ENV_FILE": str(COMPOSE_ENV),
        "N3WFC4_COMPOSE_PROJECT_NAME": PROJECT,
    }
    if any(values.get(k) != v for k, v in expected.items()):
        raise RefreshError("activation_env_authority_drift")
    return values


def verify_service_unit() -> dict[str, str]:
    raw = run(("systemctl", "cat", SERVICES_UNIT)).stdout.decode()
    starts = [x.strip() for x in raw.splitlines() if x.strip().startswith("ExecStart=")]
    stops = [x.strip() for x in raw.splitlines() if x.strip().startswith("ExecStop=")]
    if len(starts) != 1 or len(stops) != 1:
        raise RefreshError("services_unit_command_count_invalid")
    if starts[0] != EXPECTED_EXECSTART or stops[0] != EXPECTED_EXECSTOP:
        raise RefreshError("services_unit_command_drift")
    if "--force-recreate" in raw:
        raise RefreshError("manager_only_recreate_forbidden")
    return {"execstart_sha256": sha_text(starts[0]), "execstop_sha256": sha_text(stops[0])}


def compose_argv(path: Path = COMPOSE) -> tuple[str, ...]:
    return (
        "docker", "compose", "--project-name", PROJECT,
        "--env-file", str(COMPOSE_ENV), "-f", str(path),
    )


def render_compose(path: Path = COMPOSE) -> dict[str, Any]:
    raw = run((*compose_argv(path), "config", "--format", "json")).stdout
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RefreshError("compose_render_invalid") from error
    if not isinstance(value, dict):
        raise RefreshError("compose_render_shape_invalid")
    return value


def service_image(rendered: dict[str, Any], service: str) -> str:
    services = rendered.get("services")
    record = services.get(service) if isinstance(services, dict) else None
    image = record.get("image") if isinstance(record, dict) else None
    if not isinstance(image, str):
        raise RefreshError(f"compose_image_missing:{service}")
    return image


def container_id(service: str) -> str:
    raw = run(
        (
            "docker", "ps", "-q",
            "--filter", f"label=com.docker.compose.project={PROJECT}",
            "--filter", f"label=com.docker.compose.service={service}",
        )
    ).stdout.decode()
    values = [x.strip() for x in raw.splitlines() if x.strip()]
    if len(values) != 1:
        raise RefreshError(f"{service}_container_count_invalid")
    return values[0]


def inspect_container(value: str) -> dict[str, Any]:
    try:
        doc = json.loads(run(("docker", "inspect", value)).stdout)
    except json.JSONDecodeError as error:
        raise RefreshError("docker_inspect_json_invalid") from error
    if not isinstance(doc, list) or len(doc) != 1 or not isinstance(doc[0], dict):
        raise RefreshError("docker_inspect_shape_invalid")
    return doc[0]


def runtime(service: str) -> dict[str, Any]:
    item = inspect_container(container_id(service))
    state, config, host = item.get("State"), item.get("Config"), item.get("HostConfig")
    labels = config.get("Labels") if isinstance(config, dict) else None
    if (
        not isinstance(state, dict) or state.get("Running") is not True
        or not isinstance(config, dict) or not isinstance(host, dict)
        or not isinstance(labels, dict)
        or labels.get("com.docker.compose.project") != PROJECT
        or labels.get("com.docker.compose.service") != service
    ):
        raise RefreshError(f"{service}_runtime_invalid")
    result = {
        "container_id": item.get("Id"),
        "image_id": item.get("Image"),
        "image_ref": config.get("Image"),
        "started_at": state.get("StartedAt"),
        "restart_count": item.get("RestartCount"),
        "network_mode": host.get("NetworkMode"),
        "mounts": item.get("Mounts"),
    }
    if (
        not isinstance(result["container_id"], str)
        or not isinstance(result["image_id"], str)
        or IMAGE_ID.fullmatch(result["image_id"]) is None
        or not isinstance(result["image_ref"], str)
        or not isinstance(result["started_at"], str)
        or not isinstance(result["restart_count"], int)
    ):
        raise RefreshError(f"{service}_runtime_identity_invalid")
    return result


def image_id(reference: str) -> str | None:
    result = run(("docker", "image", "inspect", reference), check=False)
    if result.returncode:
        return None
    try:
        doc = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RefreshError("image_inspect_json_invalid") from error
    value = doc[0].get("Id") if isinstance(doc, list) and len(doc) == 1 and isinstance(doc[0], dict) else None
    if not isinstance(value, str) or IMAGE_ID.fullmatch(value) is None:
        raise RefreshError("image_id_invalid")
    return value


def listener_count(protocol: str, port: int) -> int:
    flag = "-ltn" if protocol == "tcp" else "-lun"
    raw = run(("ss", "-H", flag, "sport", "=", f":{port}")).stdout.decode()
    return len([x for x in raw.splitlines() if x.strip()])


def listener_snapshot() -> dict[str, int]:
    return {
        "tcp_8883": listener_count("tcp", 8883),
        "tcp_47110": listener_count("tcp", 47110),
        "udp_47111": listener_count("udp", 47111),
        "tcp_47112": listener_count("tcp", 47112),
    }


SETTINGS_PROBE = (
    "import json;"
    "from pathlib import Path;"
    "from greenhouse_manager.runtime.config import Settings;"
    "s=Settings.from_env();"
    "print(json.dumps({'pairing':str(Path(s.pairing_db_path).expanduser()),"
    "'credential':str(Path(s.n3w_credential_lifecycle_db_path).expanduser())},sort_keys=True))"
)

LEDGER_PROBE = r'''
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
'''


def manager_paths(manager_id: str) -> tuple[dict[str, str], dict[str, str]]:
    raw = run(("docker", "exec", manager_id, "python", "-c", SETTINGS_PROBE)).stdout
    try:
        inside = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RefreshError("manager_settings_invalid") from error
    if (
        not isinstance(inside, dict)
        or not isinstance(inside.get("pairing"), str)
        or not inside["pairing"].startswith("/")
        or not isinstance(inside.get("credential"), str)
        or not inside["credential"].startswith("/")
    ):
        raise RefreshError("manager_settings_path_invalid")
    mounts = inspect_container(manager_id).get("Mounts")
    if not isinstance(mounts, list):
        raise RefreshError("manager_mounts_invalid")

    def translate(value: str) -> str:
        matches: list[tuple[int, str]] = []
        for mount in mounts:
            if not isinstance(mount, dict) or mount.get("Type") != "bind":
                continue
            src, dst = mount.get("Source"), mount.get("Destination")
            if not isinstance(src, str) or not isinstance(dst, str):
                continue
            if value == dst or value.startswith(dst.rstrip("/") + "/"):
                rel = value[len(dst):].lstrip("/")
                matches.append((len(dst), str(Path(src) / rel) if rel else src))
        if not matches:
            raise RefreshError("state_path_translation_missing")
        matches.sort(reverse=True)
        if len(matches) > 1 and matches[0][0] == matches[1][0]:
            raise RefreshError("state_path_translation_ambiguous")
        return matches[0][1]

    return inside, {"pairing": translate(inside["pairing"]), "credential": translate(inside["credential"])}


def ledger_in_manager(manager_id: str) -> tuple[dict[str, Any], dict[str, str]]:
    inside, host = manager_paths(manager_id)
    raw = run(
        (
            "docker", "exec", manager_id, "python", "-c", LEDGER_PROBE,
            inside["pairing"], inside["credential"],
        )
    ).stdout
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RefreshError("ledger_invalid") from error
    if not isinstance(doc, dict):
        raise RefreshError("ledger_shape_invalid")
    return doc, host


def ledger_on_host(paths: dict[str, str]) -> dict[str, Any]:
    raw = run((sys.executable, "-B", "-c", LEDGER_PROBE, paths["pairing"], paths["credential"])).stdout
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RefreshError("host_ledger_invalid") from error
    if not isinstance(doc, dict):
        raise RefreshError("host_ledger_shape_invalid")
    return doc


def validate_pre_ledger(doc: dict[str, Any]) -> None:
    if (
        doc.get("attempt_count") != 1
        or doc.get("registration_count") != 1
        or doc.get("registration_inventory_sha256") != PRE_INVENTORY_SHA256
        or doc.get("unresolved_count") != 1
    ):
        raise RefreshError("pre_ledger_cardinality_drift")
    attempts = doc.get("attempts")
    a = attempts[0] if isinstance(attempts, list) and len(attempts) == 1 else None
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
    if not isinstance(a, dict) or any(a.get(k) != v for k, v in expected.items()):
        raise RefreshError("pre_ledger_state_drift")


def validate_post_ledger(doc: dict[str, Any]) -> None:
    if (
        doc.get("attempt_count") != 1
        or doc.get("registration_count") != 0
        or doc.get("registration_inventory_sha256") != EMPTY_INVENTORY_SHA256
        or doc.get("unresolved_count") != 0
    ):
        raise RefreshError("post_ledger_cardinality_invalid")
    attempts = doc.get("attempts")
    a = attempts[0] if isinstance(attempts, list) and len(attempts) == 1 else None
    expected = {
        "pairing_id_sha256": PAIRING_SHA256,
        "hardware_id_sha256": HARDWARE_SHA256,
        "state": "EXPIRED",
        "phase": "TERMINAL",
        "cleanup_state": "COMPLETE",
        "node_id_present": False,
        "terminal_at_present": True,
        "terminal_reason": "expired",
        "session_state": "expired",
        "session_reason": "expired",
        "registration_match_count": 0,
        "current_pairing_matches": False,
        "registration_node_id_present": False,
        "pairing_credential_count": 0,
        "hardware_credential_history_count": 0,
    }
    if not isinstance(a, dict) or any(a.get(k) != v for k, v in expected.items()):
        raise RefreshError("post_ledger_state_invalid")


def rollback_class(doc: dict[str, Any]) -> str:
    try:
        validate_post_ledger(doc)
        return "REPAIR_COMPLETE"
    except RefreshError:
        pass
    try:
        validate_pre_ledger(doc)
        return "ORIGINAL_UNRESOLVED"
    except RefreshError:
        pass
    attempts = doc.get("attempts")
    a = attempts[0] if isinstance(attempts, list) and len(attempts) == 1 else None
    if (
        doc.get("registration_count") == 1
        and doc.get("registration_inventory_sha256") == PRE_INVENTORY_SHA256
        and doc.get("unresolved_count") == 1
        and isinstance(a, dict)
        and a.get("pairing_id_sha256") == PAIRING_SHA256
        and a.get("hardware_id_sha256") == HARDWARE_SHA256
        and a.get("state") == "EXPIRED"
        and a.get("phase") == "TERMINAL"
        and a.get("cleanup_state") == "REQUIRED"
        and a.get("node_id_present") is False
        and a.get("terminal_at_present") is True
        and a.get("terminal_reason") == "expired"
        and a.get("session_state") == "pending"
        and a.get("registration_match_count") == 1
        and a.get("current_pairing_matches") is True
        and a.get("registration_node_id_present") is False
        and a.get("pairing_credential_count") == 0
        and a.get("hardware_credential_history_count") == 0
    ):
        return "RESTARTABLE_REQUIRED"
    return "EMERGENCY_STOP"


def ha_mqtt_hash(path: Path = HA_CONFIG_ENTRIES) -> str:
    if path.is_symlink() or not path.is_file():
        raise RefreshError("ha_config_entries_invalid")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RefreshError("ha_config_entries_invalid") from error
    data = doc.get("data") if isinstance(doc, dict) else None
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise RefreshError("ha_config_entries_shape_invalid")
    mqtt = [x for x in entries if isinstance(x, dict) and x.get("domain") == "mqtt"]
    return sha_bytes(canonical(mqtt))


def preclaim() -> dict[str, Any]:
    if systemctl("is-active", BROKER_UNIT) != "active" or systemctl("is-enabled", BROKER_UNIT) != "enabled":
        raise RefreshError("broker_unit_drift")
    if systemctl("is-active", SERVICES_UNIT) != "active" or systemctl("is-enabled", SERVICES_UNIT) != "enabled":
        raise RefreshError("services_unit_drift")
    if systemctl("is-active", REGISTRATION_GUARD_UNIT) != "active":
        raise RefreshError("registration_guard_drift")
    unit = verify_service_unit()
    parse_activation_env()
    if COMPOSE.is_symlink() or not COMPOSE.is_file() or COMPOSE_ENV.is_symlink() or not COMPOSE_ENV.is_file():
        raise RefreshError("compose_authority_invalid")
    original = COMPOSE.read_bytes()
    rendered = render_compose()
    if service_image(rendered, "manager") != OLD_MANAGER_IMAGE:
        raise RefreshError("compose_manager_image_drift")
    if service_image(rendered, "homeassistant") != HA_IMAGE or service_image(rendered, "broker") != BROKER_IMAGE:
        raise RefreshError("compose_non_manager_image_drift")
    runtimes = {x: runtime(x) for x in ("broker", "manager", "homeassistant")}
    manager, ha, broker = runtimes["manager"], runtimes["homeassistant"], runtimes["broker"]
    if (
        manager["image_ref"] != OLD_MANAGER_IMAGE or manager["image_id"] != OLD_MANAGER_ID
        or manager["network_mode"] != "host" or manager["restart_count"] != 0
    ):
        raise RefreshError("manager_runtime_drift")
    if (
        ha["image_ref"] != HA_IMAGE or ha["image_id"] != HA_IMAGE_ID
        or ha["network_mode"] != "host" or ha["restart_count"] != 0
    ):
        raise RefreshError("ha_runtime_drift")
    if broker["image_ref"] != BROKER_IMAGE or broker["image_id"] != BROKER_IMAGE_ID or broker["restart_count"] != 0:
        raise RefreshError("broker_runtime_drift")
    if image_id(OLD_MANAGER_ID) != OLD_MANAGER_ID:
        raise RefreshError("predecessor_image_missing")
    target_pre = image_id(TARGET_MANAGER_IMAGE)
    if target_pre not in {None, TARGET_MANAGER_ID}:
        raise RefreshError("target_tag_wrong_image")
    listeners = listener_snapshot()
    if listeners != {"tcp_8883": 1, "tcp_47110": 1, "udp_47111": 1, "tcp_47112": 0}:
        raise RefreshError("listener_drift")
    ledger, host_paths = ledger_in_manager(manager["container_id"])
    validate_pre_ledger(ledger)
    return {
        "compose_sha256": sha_bytes(original),
        "compose_render_sha256": sha_bytes(canonical(rendered)),
        "compose_b64": base64.b64encode(original).decode(),
        "unit": unit,
        "runtimes": runtimes,
        "ledger": ledger,
        "host_paths": host_paths,
        "ha_mqtt_sha256": ha_mqtt_hash(),
        "target_image_prestate": "ABSENT" if target_pre is None else "PRESENT_AND_EXACT",
    }


def public_preclaim(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "preclaim",
        "mutation": False,
        "compose_sha256": value["compose_sha256"],
        "compose_render_sha256": value["compose_render_sha256"],
        "target_image_prestate": value["target_image_prestate"],
        "manager_image_id": value["runtimes"]["manager"]["image_id"],
        "broker_container_id_sha256": sha_text(value["runtimes"]["broker"]["container_id"]),
        "ha_mqtt_continuity_sha256": value["ha_mqtt_sha256"],
        "registration_inventory_sha256": value["ledger"]["registration_inventory_sha256"],
        "commit_classification": "DEFINITELY_NOT_COMMITTED",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "t1_mutation": False,
        "board_access": False,
    }


def require_private_parent(path: Path) -> None:
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise RefreshError("transaction_parent_invalid")
    meta = parent.stat()
    if meta.st_uid != 0 or stat.S_IMODE(meta.st_mode) & 0o077:
        raise RefreshError("transaction_parent_not_private")


def write_tx(doc: dict[str, Any], *, exclusive: bool = False) -> None:
    require_private_parent(TX_PATH)
    payload = canonical(doc) + b"\n"
    if exclusive:
        if TX_PATH.exists() or TX_PATH.is_symlink():
            raise RefreshError("authorization_already_claimed")
        fd = os.open(TX_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chown(TX_PATH, 0, 0)
    else:
        fd, raw = tempfile.mkstemp(prefix=f".{TX_PATH.name}.", dir=TX_PATH.parent)
        tmp = Path(raw)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.chown(tmp, 0, 0)
            os.replace(tmp, TX_PATH)
        finally:
            tmp.unlink(missing_ok=True)
    dfd = os.open(TX_PATH.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


@contextmanager
def transaction_lock():
    require_private_parent(TX_PATH)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(TX_PATH.parent, flags)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RefreshError("transaction_busy") from error
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)


def read_tx() -> dict[str, Any]:
    if TX_PATH.is_symlink() or not TX_PATH.is_file():
        raise RefreshError("transaction_missing")
    meta = TX_PATH.stat()
    if meta.st_uid != 0 or stat.S_IMODE(meta.st_mode) != 0o600:
        raise RefreshError("transaction_metadata_invalid")
    try:
        doc = json.loads(TX_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RefreshError("transaction_invalid") from error
    if not isinstance(doc, dict) or doc.get("schema") != TX_SCHEMA:
        raise RefreshError("transaction_schema_invalid")
    return doc


def authorization_id(value: str) -> str:
    if (
        not value.startswith("N3W_R10_E03_MANAGER_SUCCESSOR_REFRESH_")
        or len(value) > 200
        or not value.replace("_", "").replace("-", "").isalnum()
    ):
        raise RefreshError("authorization_id_invalid")
    return value


def remote_claim(args: argparse.Namespace) -> dict[str, Any]:
    aid = authorization_id(args.authorization_id)
    if args.confirmation != CONFIRMATION:
        raise RefreshError("confirmation_missing")
    if SHA40.fullmatch(args.executor_source_head or "") is None or SHA40.fullmatch(args.executor_blob or "") is None:
        raise RefreshError("executor_source_binding_invalid")
    if SHA40.fullmatch(args.pr725_head or "") is None:
        raise RefreshError("pr725_head_invalid")
    if args.pr725_head != args.executor_source_head:
        raise RefreshError("pr725_executor_head_mismatch")
    value = preclaim()
    doc = {
        "schema": TX_SCHEMA,
        "status": "CLAIMED",
        "phase": "AUTHORIZATION_CLAIMED",
        "authorization_id": aid,
        "authorization_id_sha256": sha_text(aid),
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "executor_source_head": args.executor_source_head,
        "executor_blob": args.executor_blob,
        "pr725_head": args.pr725_head,
        "target_source_head": TARGET_SOURCE_HEAD,
        "target_manager_image": TARGET_MANAGER_IMAGE,
        "target_manager_image_id": TARGET_MANAGER_ID,
        "target_manager_tar_sha256": TARGET_MANAGER_TAR_SHA256,
        "artifact_id": TARGET_ARTIFACT_ID,
        "artifact_digest_sha256": TARGET_ARTIFACT_DIGEST,
        "compose_sha256": value["compose_sha256"],
        "compose_render_sha256": value["compose_render_sha256"],
        "compose_b64": value["compose_b64"],
        "host_paths": value["host_paths"],
        "broker_container_id": value["runtimes"]["broker"]["container_id"],
        "broker_image_id": value["runtimes"]["broker"]["image_id"],
        "broker_started_at": value["runtimes"]["broker"]["started_at"],
        "broker_restart_count": value["runtimes"]["broker"]["restart_count"],
        "ha_mqtt_sha256": value["ha_mqtt_sha256"],
        "last_error": None,
        "claimed_at_unix": int(time.time()),
    }
    write_tx(doc, exclusive=True)
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "claim",
        "authorization_id_sha256": doc["authorization_id_sha256"],
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "transaction_sha256": sha_file(TX_PATH),
        "t1_mutation": True,
        "board_access": False,
    }


def rewrite_manager_image(original: bytes) -> bytes:
    lines = original.decode("utf-8").splitlines(keepends=True)
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.rstrip("\r\n") == "  manager:":
            if start is not None:
                raise RefreshError("manager_service_duplicate")
            start = i
            continue
        if start is not None and i > start and re.fullmatch(r"  [A-Za-z0-9_.-]+:", line.rstrip("\r\n")):
            end = i
            break
    if start is None:
        raise RefreshError("manager_service_missing")
    matches: list[tuple[int, re.Match[str]]] = []
    pattern = re.compile(r"^(    image:\s*)(\S+)(\s*)(\r?\n)?$")
    for i in range(start + 1, end):
        match = pattern.match(lines[i])
        if match:
            matches.append((i, match))
    if len(matches) != 1:
        raise RefreshError("manager_image_count_invalid")
    i, match = matches[0]
    if match.group(2) != OLD_MANAGER_IMAGE:
        raise RefreshError("manager_image_predecessor_drift")
    lines[i] = match.group(1) + TARGET_MANAGER_IMAGE + match.group(3) + (match.group(4) or "")
    return "".join(lines).encode()


def validate_candidate(before: dict[str, Any], after: dict[str, Any]) -> None:
    expected = copy.deepcopy(before)
    services = expected.get("services")
    manager = services.get("manager") if isinstance(services, dict) else None
    if not isinstance(manager, dict) or manager.get("image") != OLD_MANAGER_IMAGE:
        raise RefreshError("candidate_predecessor_invalid")
    manager["image"] = TARGET_MANAGER_IMAGE
    if expected != after:
        raise RefreshError("candidate_non_manager_drift")


def atomic_replace(path: Path, payload: bytes, expected_sha: str) -> str:
    if path.is_symlink() or not path.is_file() or sha_file(path) != expected_sha:
        raise RefreshError("replace_binding_drift")
    meta = path.stat()
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(raw)
    try:
        os.fchmod(fd, stat.S_IMODE(meta.st_mode))
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(tmp, meta.st_uid, meta.st_gid)
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        tmp.unlink(missing_ok=True)
    observed = sha_file(path)
    if observed != sha_bytes(payload):
        raise RefreshError("replace_verify_failed")
    return observed


def tx_update(doc: dict[str, Any], phase: str, **extra: Any) -> None:
    doc.update(extra)
    doc["phase"] = phase
    write_tx(doc)


def broker_continuity(doc: dict[str, Any]) -> dict[str, Any]:
    value = runtime("broker")
    if (
        value["container_id"] != doc["broker_container_id"]
        or value["image_id"] != doc["broker_image_id"]
        or value["started_at"] != doc["broker_started_at"]
        or value["restart_count"] != doc["broker_restart_count"]
        or listener_count("tcp", 8883) != 1
    ):
        raise RefreshError("broker_continuity_failed")
    return value


def wait_services(timeout: int = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if systemctl("is-active", SERVICES_UNIT) == "active":
            try:
                container_id("manager")
                container_id("homeassistant")
                return
            except RefreshError:
                pass
        time.sleep(2)
    raise RefreshError("services_start_timeout")


def restore_compose(doc: dict[str, Any], candidate_sha: str | None) -> None:
    original = base64.b64decode(doc["compose_b64"], validate=True)
    current = sha_file(COMPOSE)
    if current == doc["compose_sha256"]:
        return
    if candidate_sha is not None and current != candidate_sha:
        raise RefreshError("rollback_compose_unknown")
    atomic_replace(COMPOSE, original, current)


def rollback(doc: dict[str, Any], candidate_sha: str | None, stopped: bool, reason: str) -> dict[str, str]:
    if not stopped:
        restore_compose(doc, candidate_sha)
        tx_update(doc, "ROLLBACK_PASS", status="FAILED_ROLLED_BACK_PRESTOP", last_error=reason)
        return {"rollback": "PASS_PRESTOP", "durable": "ORIGINAL_UNRESOLVED"}

    run(("systemctl", "stop", SERVICES_UNIT), timeout=120, check=False)
    restore_compose(doc, candidate_sha)
    durable = rollback_class(ledger_on_host(doc["host_paths"]))
    if durable == "EMERGENCY_STOP":
        tx_update(doc, "ROLLBACK_EMERGENCY_STOP", status="FAILED_EMERGENCY", last_error=reason)
        return {"rollback": "EMERGENCY_STOP", "durable": durable}

    run(("systemctl", "start", SERVICES_UNIT), timeout=180)
    wait_services()
    broker_continuity(doc)
    manager = runtime("manager")
    if manager["image_ref"] != OLD_MANAGER_IMAGE or manager["image_id"] != OLD_MANAGER_ID or manager["restart_count"] != 0:
        raise RefreshError("rollback_manager_invalid")
    final, _ = ledger_in_manager(manager["container_id"])
    final_class = rollback_class(final)
    if final_class not in {"ORIGINAL_UNRESOLVED", "REPAIR_COMPLETE"}:
        raise RefreshError("rollback_durable_invalid")
    tx_update(doc, "ROLLBACK_PASS", status="FAILED_ROLLED_BACK", last_error=reason, rollback_durable_state=final_class)
    return {"rollback": "PASS", "durable": final_class}


def _remote_apply_locked() -> dict[str, Any]:
    doc = read_tx()
    if doc.get("status") != "CLAIMED" or doc.get("authorization_consumed") is not True or doc.get("replay_allowed") is not False:
        raise RefreshError("transaction_not_claimed")
    if image_id(TARGET_MANAGER_IMAGE) != TARGET_MANAGER_ID:
        raise RefreshError("target_image_not_exact")
    if image_id(OLD_MANAGER_ID) != OLD_MANAGER_ID:
        raise RefreshError("predecessor_image_missing")

    candidate_sha: str | None = None
    stopped = False
    try:
        fresh = preclaim()
        if fresh["compose_sha256"] != doc["compose_sha256"]:
            raise RefreshError("preapply_compose_drift")
        original = base64.b64decode(doc["compose_b64"], validate=True)
        candidate = rewrite_manager_image(original)
        fd, raw = tempfile.mkstemp(prefix=".r10-e03-candidate.", dir=COMPOSE.parent)
        temp = Path(raw)
        try:
            os.close(fd)
            temp.write_bytes(candidate)
            before, after = render_compose(), render_compose(temp)
            if sha_bytes(canonical(before)) != doc["compose_render_sha256"]:
                raise RefreshError("preapply_render_drift")
            validate_candidate(before, after)
        finally:
            temp.unlink(missing_ok=True)
        candidate_sha = sha_bytes(candidate)
        tx_update(doc, "COMPOSE_CANDIDATE_VALIDATED")
        atomic_replace(COMPOSE, candidate, doc["compose_sha256"])
        tx_update(doc, "COMPOSE_REPLACED", candidate_compose_sha256=candidate_sha)

        stopped = True
        run(("systemctl", "stop", SERVICES_UNIT), timeout=120)
        if systemctl("is-active", SERVICES_UNIT) != "inactive":
            raise RefreshError("services_not_inactive")
        if run(("docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={PROJECT}", "--filter", "label=com.docker.compose.service=manager"), check=False).stdout.strip():
            raise RefreshError("manager_still_running")
        if run(("docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={PROJECT}", "--filter", "label=com.docker.compose.service=homeassistant"), check=False).stdout.strip():
            raise RefreshError("ha_still_running")
        broker_continuity(doc)
        tx_update(doc, "SERVICES_STOPPED")

        run(("systemctl", "start", SERVICES_UNIT), timeout=180)
        wait_services()
        tx_update(doc, "SERVICES_STARTED")
        manager, ha, broker = runtime("manager"), runtime("homeassistant"), broker_continuity(doc)
        if manager["image_ref"] != TARGET_MANAGER_IMAGE or manager["image_id"] != TARGET_MANAGER_ID or manager["network_mode"] != "host" or manager["restart_count"] != 0:
            raise RefreshError("successor_manager_invalid")
        if ha["image_ref"] != HA_IMAGE or ha["image_id"] != HA_IMAGE_ID or ha["network_mode"] != "host" or ha["restart_count"] != 0:
            raise RefreshError("ha_post_runtime_invalid")
        if ha_mqtt_hash() != doc["ha_mqtt_sha256"]:
            raise RefreshError("ha_mqtt_continuity_changed")
        if listener_snapshot() != {"tcp_8883": 1, "tcp_47110": 1, "udp_47111": 1, "tcp_47112": 0}:
            raise RefreshError("post_listener_invalid")
        post, _ = ledger_in_manager(manager["container_id"])
        validate_post_ledger(post)
        tx_update(doc, "COMMITTED", status="PASS", last_error=None, post_registration_inventory_sha256=post["registration_inventory_sha256"])
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "operation": "apply",
            "authorization_claimed": True,
            "authorization_consumed": True,
            "replay_allowed": False,
            "manager_image_id": manager["image_id"],
            "broker_container_id_sha256": sha_text(broker["container_id"]),
            "registration_count": post["registration_count"],
            "registration_inventory_sha256": post["registration_inventory_sha256"],
            "unresolved_count": post["unresolved_count"],
            "t1_mutation": True,
            "board_access": False,
        }
    except Exception as error:
        reason = safe_error_code(error)
        result = rollback(doc, candidate_sha, stopped, reason)
        raise RefreshError(
            f"apply_failed:{reason}:rollback={result['rollback']}:durable={result['durable']}"
        ) from error


def remote_apply() -> dict[str, Any]:
    with transaction_lock():
        return _remote_apply_locked()


def remote_abort_prestop(reason_code: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Z0-9_]{3,80}", reason_code or ""):
        raise RefreshError("abort_reason_invalid")
    with transaction_lock():
        doc = read_tx()
        if (
            doc.get("status") != "CLAIMED"
            or doc.get("phase") != "AUTHORIZATION_CLAIMED"
            or doc.get("authorization_consumed") is not True
            or doc.get("replay_allowed") is not False
        ):
            raise RefreshError("prestop_abort_state_invalid")
        current = preclaim()
        if current["compose_sha256"] != doc.get("compose_sha256"):
            raise RefreshError("prestop_abort_compose_drift")
        tx_update(
            doc,
            "FAILED_PRESTOP",
            status="FAILED_PRESTOP",
            last_error=reason_code,
        )
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "operation": "abort-prestop",
            "transaction_status": "FAILED_PRESTOP",
            "authorization_claimed": True,
            "authorization_consumed": True,
            "replay_allowed": False,
            "t1_mutation": True,
            "board_access": False,
        }


def remote_status() -> dict[str, Any]:
    doc = read_tx()
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "status",
        "transaction_status": doc.get("status"),
        "phase": doc.get("phase"),
        "authorization_id_sha256": doc.get("authorization_id_sha256"),
        "authorization_claimed": doc.get("authorization_claimed"),
        "authorization_consumed": doc.get("authorization_consumed"),
        "replay_allowed": doc.get("replay_allowed"),
        "last_error": doc.get("last_error"),
        "transaction_sha256": sha_file(TX_PATH),
        "t1_mutation": False,
        "board_access": False,
    }


def _gh_json(path: str) -> dict[str, Any]:
    raw = run(
        ("gh", "api", "--method", "GET", path),
        timeout=60,
    ).stdout
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RefreshError("github_metadata_invalid") from error
    if not isinstance(doc, dict):
        raise RefreshError("github_metadata_shape_invalid")
    return doc


def verify_pr725_head(expected_head: str) -> None:
    doc = _gh_json("repos/chrenguo-stack/HomeAssistant/pulls/725")
    head = doc.get("head")
    if (
        doc.get("state") != "open"
        or doc.get("merged_at") is not None
        or not isinstance(head, dict)
        or head.get("sha") != expected_head
    ):
        raise RefreshError("pr725_github_head_drift")


def verify_artifact_metadata() -> None:
    run_doc = _gh_json(
        f"repos/chrenguo-stack/HomeAssistant/actions/runs/{TARGET_ARTIFACT_RUN_ID}"
    )
    if (
        run_doc.get("id") != TARGET_ARTIFACT_RUN_ID
        or run_doc.get("head_sha") != TARGET_SOURCE_HEAD
        or run_doc.get("status") != "completed"
        or run_doc.get("conclusion") != "success"
    ):
        raise RefreshError("artifact_run_binding_mismatch")

    artifacts_doc = _gh_json(
        "repos/chrenguo-stack/HomeAssistant/actions/runs/"
        f"{TARGET_ARTIFACT_RUN_ID}/artifacts?per_page=100"
    )
    artifacts = artifacts_doc.get("artifacts")
    matches = (
        [item for item in artifacts if isinstance(item, dict) and item.get("id") == TARGET_ARTIFACT_ID]
        if isinstance(artifacts, list)
        else []
    )
    if len(matches) != 1:
        raise RefreshError("artifact_cardinality_invalid")
    doc = matches[0]
    if (
        doc.get("name") != TARGET_ARTIFACT_NAME
        or doc.get("digest") != "sha256:" + TARGET_ARTIFACT_DIGEST
        or doc.get("expired") is True
    ):
        raise RefreshError("artifact_metadata_binding_mismatch")


def verify_local_artifact(manager_tar: Path, binding_json: Path) -> None:
    if binding_json.is_symlink() or not binding_json.is_file():
        raise RefreshError("binding_json_invalid")
    try:
        doc = json.loads(binding_json.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RefreshError("binding_json_invalid") from error
    manager = doc.get("manager") if isinstance(doc, dict) else None
    if (
        doc.get("schema") != "gh.n3w.t1-fresh-exact-arm64-binding/1"
        or doc.get("source_head") != TARGET_SOURCE_HEAD
        or not isinstance(manager, dict)
        or manager.get("image") != TARGET_MANAGER_IMAGE
        or manager.get("image_id") != TARGET_MANAGER_ID
        or manager.get("tar_sha256") != TARGET_MANAGER_TAR_SHA256
    ):
        raise RefreshError("binding_json_mismatch")
    if sha_file(manager_tar) != TARGET_MANAGER_TAR_SHA256:
        raise RefreshError("manager_tar_sha256_mismatch")


def verify_source_authority(source_head: str, source_blob: str) -> None:
    if SHA40.fullmatch(source_head or "") is None or SHA40.fullmatch(source_blob or "") is None:
        raise RefreshError("source_authority_invalid")
    root = Path(__file__).resolve().parents[1]
    head = run(("git", "-C", str(root), "rev-parse", "HEAD")).stdout.decode().strip()
    if head != source_head or git_blob(Path(__file__).resolve()) != source_blob:
        raise RefreshError("source_authority_drift")
    dirty = run(("git", "-C", str(root), "status", "--porcelain", "--untracked-files=no")).stdout.decode()
    if dirty.strip():
        raise RefreshError("tracked_worktree_dirty")


def child_ssh_argv(transport: Any, remote: Sequence[str]) -> list[str]:
    transport.assert_master()
    return [
        "ssh", "-F", "/dev/null",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={transport.known_hosts}",
        "-o", "GlobalKnownHostsFile=/dev/null",
        "-o", "HashKnownHosts=no",
        "-o", "IdentitiesOnly=yes",
        "-o", "IdentityAgent=none",
        "-o", "ControlMaster=no",
        "-o", "ControlPersist=no",
        "-o", f"ControlPath={transport.control_path}",
        "-o", "BatchMode=yes",
        "-o", "PubkeyAuthentication=no",
        "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no",
        "-o", "PreferredAuthentications=none",
        "-o", "ProxyCommand=/usr/bin/false",
        transport.target,
        shlex.join(tuple(remote)),
    ]


def stream_file(transport: Any, source: Path, remote: Sequence[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    if source.is_symlink() or not source.is_file():
        raise RefreshError("stream_source_invalid")
    with source.open("rb") as stdin:
        return subprocess.run(
            child_ssh_argv(transport, remote),
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )


def stream_self(transport: Any, args: Sequence[str], timeout: int = 180) -> dict[str, Any]:
    result = stream_file(
        transport,
        Path(__file__).resolve(),
        ("sudo", "-n", "python3", "-B", "-", *args),
        timeout,
    )
    out = result.stdout.decode(errors="replace").strip()
    if result.returncode:
        err = result.stderr.decode(errors="replace").strip()
        raise RefreshError(f"remote_executor_failed:{out or err[:400]}")
    try:
        doc = json.loads(out)
    except json.JSONDecodeError as error:
        raise RefreshError("remote_executor_json_invalid") from error
    if not isinstance(doc, dict):
        raise RefreshError("remote_executor_shape_invalid")
    return doc


def host_apply(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirmation != CONFIRMATION:
        raise RefreshError("confirmation_missing")
    authorization_id(args.authorization_id)
    verify_source_authority(args.executor_source_head, args.executor_blob)
    if args.pr725_head != args.executor_source_head:
        raise RefreshError("pr725_executor_head_mismatch")
    verify_pr725_head(args.pr725_head)
    verify_artifact_metadata()
    verify_local_artifact(args.manager_tar, args.binding_json)
    from n3w_t1_ssh_transport import SSHTransport

    transport = SSHTransport(
        target=args.t1,
        known_hosts=args.known_hosts,
        expected_host_key_sha256=args.host_key_sha256,
    )
    claim_started = False
    claim_observed = False
    result: dict[str, Any] | None = None
    primary: Exception | None = None
    try:
        transport.start_epoch()
        pre = stream_self(transport, ("remote-preclaim",))
        claim_started = True
        claim = stream_self(
            transport,
            (
                "remote-claim",
                "--authorization-id", args.authorization_id,
                "--confirmation", CONFIRMATION,
                "--executor-source-head", args.executor_source_head,
                "--executor-blob", args.executor_blob,
                "--pr725-head", args.pr725_head,
            ),
        )
        claim_observed = claim.get("authorization_consumed") is True
        if not claim_observed:
            raise AuthorizationUnknownError("claim_response_invalid")
        if pre.get("target_image_prestate") == "ABSENT":
            loaded = stream_file(
                transport,
                args.manager_tar,
                ("sudo", "-n", "docker", "load"),
                1800,
            )
            if loaded.returncode:
                try:
                    stream_self(
                        transport,
                        ("remote-abort-prestop", "--reason-code", "DOCKER_LOAD_FAILED"),
                    )
                except Exception:
                    raise AuthorizationUnknownError(
                        "docker_load_failed_abort_state_unknown"
                    )
                raise AuthorizationConsumedError("docker_load_stream_failed")
        applied = stream_self(transport, ("remote-apply",), 360)
        if applied.get("status") != "PASS":
            raise AuthorizationConsumedError("remote_apply_not_pass")
        result = {
            "schema": SCHEMA,
            "status": "PASS",
            "operation": "host-apply",
            "authorization_id_sha256": sha_text(args.authorization_id),
            "authorization_claimed": True,
            "authorization_consumed": True,
            "replay_allowed": False,
            "registration_count": applied["registration_count"],
            "registration_inventory_sha256": applied["registration_inventory_sha256"],
            "unresolved_count": applied["unresolved_count"],
            "t1_mutation": True,
            "board_access": False,
        }
    except Exception as error:
        primary = error
        if claim_started:
            try:
                status = stream_self(transport, ("remote-status",))
            except Exception:
                status = None
            if isinstance(status, dict) and status.get("authorization_consumed") is True and status.get("replay_allowed") is False:
                claim_observed = True
                primary = AuthorizationConsumedError(
                    f"postclaim_failure:{type(error).__name__}:"
                    f"transaction={status.get('transaction_status')}:phase={status.get('phase')}"
                )
            elif not claim_observed:
                primary = AuthorizationUnknownError(f"claim_state_unknown:{type(error).__name__}")
    cleanup: Exception | None = None
    try:
        transport.close_epoch()
    except Exception as error:
        cleanup = error
    if primary is not None:
        raise primary
    if cleanup is not None:
        if claim_observed:
            raise AuthorizationConsumedError(f"postsuccess_ssh_cleanup_failed:{type(cleanup).__name__}") from cleanup
        raise cleanup
    if result is None:
        raise RefreshError("host_result_missing")
    return result


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("remote-preclaim")
    claim = sub.add_parser("remote-claim")
    for name in ("authorization-id", "confirmation", "executor-source-head", "executor-blob", "pr725-head"):
        claim.add_argument("--" + name, required=True)
    sub.add_parser("remote-apply")
    abort = sub.add_parser("remote-abort-prestop")
    abort.add_argument("--reason-code", required=True)
    sub.add_parser("remote-status")
    apply = sub.add_parser("apply")
    apply.add_argument("--t1", required=True)
    apply.add_argument("--known-hosts", type=Path, required=True)
    apply.add_argument("--host-key-sha256", required=True)
    apply.add_argument("--manager-tar", type=Path, required=True)
    apply.add_argument("--binding-json", type=Path, required=True)
    for name in ("authorization-id", "confirmation", "executor-source-head", "executor-blob", "pr725-head"):
        apply.add_argument("--" + name, required=True)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command.startswith("remote-") and os.geteuid() != 0:
            raise RefreshError("remote_root_required")
        if args.command == "remote-preclaim":
            result = public_preclaim(preclaim())
        elif args.command == "remote-claim":
            result = remote_claim(args)
        elif args.command == "remote-apply":
            result = remote_apply()
        elif args.command == "remote-abort-prestop":
            result = remote_abort_prestop(args.reason_code)
        elif args.command == "remote-status":
            result = remote_status()
        elif args.command == "apply":
            result = host_apply(args)
        else:
            raise RefreshError("command_unknown")
    except Exception as error:
        claimed: bool | str = False
        consumed: bool | str = False
        mutation: bool | str = False
        replay = True
        if isinstance(error, AuthorizationConsumedError):
            claimed = consumed = mutation = True
            replay = False
        elif isinstance(error, AuthorizationUnknownError):
            claimed = consumed = mutation = "UNKNOWN"
            replay = False
        elif args.command in {"remote-claim", "remote-apply", "remote-abort-prestop", "remote-status"}:
            try:
                tx = read_tx()
                if tx.get("authorization_consumed") is True:
                    claimed = consumed = mutation = True
                    replay = False
            except Exception:
                pass
        print(json.dumps({
            "schema": SCHEMA,
            "status": "STOP",
            "operation": args.command,
            "reason": safe_error_code(error),
            "authorization_claimed": claimed,
            "authorization_consumed": consumed,
            "replay_allowed": replay,
            "t1_mutation": mutation,
            "board_access": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
