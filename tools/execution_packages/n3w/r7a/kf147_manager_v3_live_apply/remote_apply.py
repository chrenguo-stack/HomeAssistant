#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

GATE_ID = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_MANAGER_IPC_V3_IMAGE_ONLY_LIVE_APPLY_20261110_01"
CONFIRMATION = "EXECUTE KF147 MANAGER IPC V3 IMAGE ONLY LIVE APPLY: YES"
PREDECESSOR = "local/greenhouse-manager:fresh-7807271e4c48"
PREDECESSOR_IMAGE_ID = "sha256:7e3f09ed47010a18de215faa426113b7faba4e220b41bb9dcafd8ee1d4acf20b"
TARGET = "local/greenhouse-manager:fresh-44e7d7472714"
TARGET_IMAGE_ID = "sha256:fd5104d610645347fe47137dbb24121851fa8a48530df3e3c905704607c5e3d4"
TARGET_TAR_SHA256 = "9316817590c4fe74498629d0451a4897c2e11bef7bc4b423b66e47bb846099c5"
TARGET_TAR_SIZE = 62957568
HOMEASSISTANT = "local/n3w-homeassistant:2026.10.0-0c73235a"
HOMEASSISTANT_IMAGE_ID = "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306"
BROKER = "local/n3w-mosquitto:2.1.2-3184566d"
BROKER_IMAGE_ID = "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563"
TARGET_ARCHIVE_SIZE = 835309535
TARGET_ARCHIVE_SHA256 = "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"
EXPECTED_TRANSACTION_SHA256 = "6e1f0b5d262e346674b62ac79bf2ffbc1c63a8dd22379a0a82c952f0e3626b49"
EXPECTED_CANDIDATE_FINGERPRINT = "e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93"
USB_MODEL = "Extreme"
USB_SIZE = 32017047552
SERVICES_UNIT = "n3wfc4-services-activation.service"
OTA_UNIT = "n3w-t1-ha-ota.service"
COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")
TX = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
PREPARE = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-prepare.json")
STATE_ROOT = Path("/var/lib/n3w-t1-core-updater/kf147-manager-v3-live-20261110-01")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class Stop(RuntimeError):
    pass


def run(argv: list[str], *, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and p.returncode != 0:
        raise Stop(f"command_failed:{Path(argv[0]).name}:{p.returncode}")
    return p


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise Stop(f"invalid_file:{path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Stop(f"invalid_json:{path.name}") from error
    if not isinstance(value, dict):
        raise Stop(f"invalid_json_shape:{path.name}")
    return value


def atomic_replace(path: Path, payload: bytes) -> None:
    if path.is_symlink() or not path.is_file():
        raise Stop("compose_env_invalid")
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
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        tmp.unlink(missing_ok=True)


def rewrite_manager(payload: bytes, old: str, new: str) -> bytes:
    text = payload.decode("utf-8")
    lines = text.splitlines(keepends=True)
    indexes = [i for i, line in enumerate(lines) if line.startswith("GH_MANAGER_IMAGE=")]
    if len(indexes) != 1:
        raise Stop("manager_binding_line_count_invalid")
    i = indexes[0]
    ending = "\n" if lines[i].endswith("\n") else ""
    current = lines[i].rstrip("\r\n").split("=", 1)[1]
    if current != old:
        raise Stop("manager_binding_predecessor_drift")
    lines[i] = f"GH_MANAGER_IMAGE={new}{ending}"
    return "".join(lines).encode("utf-8")


def compose_container(service: str) -> dict[str, Any]:
    ids = run([
        "docker", "ps", "-q",
        "--filter", "label=com.docker.compose.project=n3wfc4",
        "--filter", f"label=com.docker.compose.service={service}",
    ]).stdout.split()
    if len(ids) != 1:
        raise Stop(f"{service}_container_count_invalid")
    value = json.loads(run(["docker", "inspect", ids[0]]).stdout)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise Stop(f"{service}_inspect_invalid")
    return value[0]


def service_active(name: str) -> bool:
    return run(["systemctl", "is-active", name], check=False).stdout.strip() == "active"


def manager_v3_support(container_id: str) -> bool:
    probe = run([
        "docker", "exec", "--user", "999:999", container_id,
        "python", "-c",
        "from greenhouse_manager.runtime import t1_ota_ipc as m;"
        "print(str(hasattr(m,'RESPONSE_SCHEMA_V3')).lower())",
    ], check=False)
    return probe.returncode == 0 and probe.stdout.strip() == "true"


def usb_inventory() -> list[dict[str, Any]]:
    value = json.loads(run([
        "lsblk", "--json", "--bytes",
        "--output", "TYPE,TRAN,RM,RO,SIZE,MODEL,MOUNTPOINTS",
    ]).stdout)
    devices = value.get("blockdevices")
    if not isinstance(devices, list):
        raise Stop("lsblk_invalid")
    return [
        item for item in devices
        if isinstance(item, dict)
        and item.get("type") == "disk"
        and (str(item.get("tran") or "").lower() == "usb" or bool(item.get("rm")))
    ]


def prepare_semantics(doc: dict[str, Any]) -> dict[str, Any]:
    candidate = doc.get("candidate")
    if not isinstance(candidate, dict):
        raise Stop("prepare_candidate_missing")
    fp = candidate.get("public_fingerprint")
    if not isinstance(fp, str) or SHA256_RE.fullmatch(fp) is None:
        raise Stop("prepare_candidate_fingerprint_invalid")
    return {
        "schema": doc.get("schema"),
        "transaction_id_sha256": doc.get("transaction_id_sha256"),
        "release_identity": doc.get("release_identity"),
        "baseline_public_fingerprints": doc.get("baseline_public_fingerprints"),
        "candidate_public_fingerprint": fp,
        "candidate_model": candidate.get("display_model"),
        "candidate_capacity_bytes": candidate.get("display_capacity_bytes"),
        "confirmation_required": doc.get("confirmation_required"),
        "confirmation_consumed": doc.get("confirmation_consumed"),
        "capacity_snapshot_present": isinstance(doc.get("capacity_snapshot"), dict),
        "error_code": doc.get("error_code"),
    }


def collect_preflight() -> dict[str, Any]:
    if os.geteuid() != 0:
        raise Stop("root_required")
    if run(["uname", "-m"]).stdout.strip() != "aarch64":
        raise Stop("architecture_invalid")
    if run(["systemctl", "is-system-running"], check=False).stdout.strip() != "running":
        raise Stop("system_state_invalid")
    if not service_active(SERVICES_UNIT) or not service_active(OTA_UNIT):
        raise Stop("required_service_inactive")

    manager = compose_container("manager")
    ha = compose_container("homeassistant")
    broker = compose_container("broker")
    if manager.get("Config", {}).get("Image") != PREDECESSOR or manager.get("Image") != PREDECESSOR_IMAGE_ID:
        raise Stop("manager_predecessor_invalid")
    if manager.get("Config", {}).get("User") != "999:999":
        raise Stop("manager_user_invalid")
    if manager.get("RestartCount") != 0 or manager.get("State", {}).get("Running") is not True:
        raise Stop("manager_runtime_invalid")
    if manager_v3_support(str(manager.get("Id"))):
        raise Stop("manager_v3_already_present")

    if ha.get("Config", {}).get("Image") != HOMEASSISTANT or ha.get("Image") != HOMEASSISTANT_IMAGE_ID:
        raise Stop("homeassistant_identity_invalid")
    if broker.get("Config", {}).get("Image") != BROKER or broker.get("Image") != BROKER_IMAGE_ID:
        raise Stop("broker_identity_invalid")

    tx = read_json(TX)
    if sha_file(TX) != EXPECTED_TRANSACTION_SHA256:
        raise Stop("u1_transaction_sha256_drift")
    if (
        tx.get("schema") != "gh.n3w-t1-core-updater-homeassistant-usb-transaction/1"
        or tx.get("phase") != "U1_PREPARE_REQUESTED"
        or tx.get("status") != "ACTIVE"
        or tx.get("target_archive_size") != TARGET_ARCHIVE_SIZE
        or tx.get("target_archive_sha256") != TARGET_ARCHIVE_SHA256
        or tx.get("authorization_claimed") is not False
        or tx.get("authorization_consumed") is not False
    ):
        raise Stop("u1_transaction_invalid")

    prepare = prepare_semantics(read_json(PREPARE))
    if (
        prepare["schema"] != "gh.n3w-t1-ha-usb-prepare-state/1"
        or prepare["candidate_public_fingerprint"] != EXPECTED_CANDIDATE_FINGERPRINT
        or prepare["candidate_model"] != USB_MODEL
        or prepare["candidate_capacity_bytes"] != USB_SIZE
        or prepare["confirmation_required"] is not True
        or prepare["confirmation_consumed"] is not False
        or prepare["capacity_snapshot_present"] is not False
        or prepare["error_code"] is not None
    ):
        raise Stop("prepare_state_invalid")

    usb = usb_inventory()
    if len(usb) != 1:
        raise Stop("usb_cardinality_invalid")
    item = usb[0]
    if (
        str(item.get("model") or "").strip() != USB_MODEL
        or item.get("size") != USB_SIZE
        or bool(item.get("ro"))
        or any(v for v in (item.get("mountpoints") or []))
    ):
        raise Stop("usb_candidate_runtime_invalid")

    if COMPOSE_ENV.is_symlink() or not COMPOSE_ENV.is_file():
        raise Stop("compose_env_invalid")
    env = COMPOSE_ENV.read_bytes()
    if rewrite_manager(env, PREDECESSOR, TARGET) == env:
        raise Stop("compose_env_rewrite_noop")

    return {
        "manager_container_id": manager.get("Id"),
        "manager_started_at": manager.get("State", {}).get("StartedAt"),
        "homeassistant_container_id": ha.get("Id"),
        "homeassistant_started_at": ha.get("State", {}).get("StartedAt"),
        "broker_container_id": broker.get("Id"),
        "broker_started_at": broker.get("State", {}).get("StartedAt"),
        "compose_env_sha256": hashlib.sha256(env).hexdigest(),
        "transaction_sha256": sha_file(TX),
        "prepare_semantics": prepare,
        "candidate_fingerprint": prepare["candidate_public_fingerprint"],
    }


def wait_services(timeout: int = 180) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if service_active(SERVICES_UNIT):
            try:
                manager = compose_container("manager")
                ha = compose_container("homeassistant")
                if (
                    manager.get("State", {}).get("Running") is True
                    and ha.get("State", {}).get("Running") is True
                ):
                    return
            except Exception:
                pass
        time.sleep(2)
    raise Stop("services_restart_timeout")


def post_validate(pre: dict[str, Any]) -> dict[str, Any]:
    manager = compose_container("manager")
    ha = compose_container("homeassistant")
    broker = compose_container("broker")
    if manager.get("Config", {}).get("Image") != TARGET or manager.get("Image") != TARGET_IMAGE_ID:
        raise Stop("post_manager_identity_invalid")
    if manager.get("RestartCount") != 0 or manager.get("State", {}).get("Running") is not True:
        raise Stop("post_manager_runtime_invalid")
    if not manager_v3_support(str(manager.get("Id"))):
        raise Stop("post_manager_v3_support_missing")
    if str(manager.get("Id")) == pre["manager_container_id"]:
        raise Stop("manager_container_not_recreated")

    if (
        ha.get("Config", {}).get("Image") != HOMEASSISTANT
        or ha.get("Image") != HOMEASSISTANT_IMAGE_ID
        or ha.get("Id") != pre["homeassistant_container_id"]
    ):
        raise Stop("homeassistant_continuity_failed")
    if (
        broker.get("Config", {}).get("Image") != BROKER
        or broker.get("Image") != BROKER_IMAGE_ID
        or broker.get("Id") != pre["broker_container_id"]
        or broker.get("State", {}).get("StartedAt") != pre["broker_started_at"]
    ):
        raise Stop("broker_continuity_failed")

    if sha_file(TX) != pre["transaction_sha256"]:
        raise Stop("u1_transaction_drift")
    prepare = prepare_semantics(read_json(PREPARE))
    before = pre["prepare_semantics"]
    for key in (
        "schema",
        "transaction_id_sha256",
        "release_identity",
        "baseline_public_fingerprints",
        "candidate_public_fingerprint",
        "candidate_model",
        "candidate_capacity_bytes",
        "confirmation_required",
        "confirmation_consumed",
        "capacity_snapshot_present",
        "error_code",
    ):
        if prepare.get(key) != before.get(key):
            raise Stop(f"prepare_semantic_drift:{key}")

    usb = usb_inventory()
    if len(usb) != 1:
        raise Stop("post_usb_cardinality_invalid")
    item = usb[0]
    if (
        str(item.get("model") or "").strip() != USB_MODEL
        or item.get("size") != USB_SIZE
        or bool(item.get("ro"))
        or any(v for v in (item.get("mountpoints") or []))
    ):
        raise Stop("post_usb_candidate_invalid")

    return {
        "manager_image": TARGET,
        "manager_image_id": TARGET_IMAGE_ID,
        "manager_ipc_v3_support": True,
        "manager_container_recreated": True,
        "homeassistant_image_mutation": False,
        "homeassistant_container_recreated": False,
        "broker_mutation": False,
        "u1_transaction_preserved": True,
        "prepare_candidate_preserved": True,
        "usb_mutation": False,
    }


def rollback(pre: dict[str, Any], snapshot_env: Path) -> None:
    run(["systemctl", "stop", SERVICES_UNIT], timeout=180)
    atomic_replace(COMPOSE_ENV, snapshot_env.read_bytes())
    run(["systemctl", "start", SERVICES_UNIT], timeout=180)
    wait_services()
    manager = compose_container("manager")
    ha = compose_container("homeassistant")
    broker = compose_container("broker")
    if manager.get("Config", {}).get("Image") != PREDECESSOR or manager.get("Image") != PREDECESSOR_IMAGE_ID:
        raise Stop("rollback_manager_identity_invalid")
    if (
        ha.get("Config", {}).get("Image") != HOMEASSISTANT
        or ha.get("Image") != HOMEASSISTANT_IMAGE_ID
        or ha.get("Id") != pre["homeassistant_container_id"]
    ):
        raise Stop("rollback_homeassistant_continuity_failed")
    if (
        broker.get("Config", {}).get("Image") != BROKER
        or broker.get("Image") != BROKER_IMAGE_ID
        or broker.get("Id") != pre["broker_container_id"]
        or broker.get("State", {}).get("StartedAt") != pre["broker_started_at"]
    ):
        raise Stop("rollback_broker_continuity_failed")
    if sha_file(TX) != pre["transaction_sha256"]:
        raise Stop("rollback_u1_transaction_drift")
    current = prepare_semantics(read_json(PREPARE))
    before = pre["prepare_semantics"]
    for key in (
        "transaction_id_sha256",
        "release_identity",
        "candidate_public_fingerprint",
        "candidate_model",
        "candidate_capacity_bytes",
        "confirmation_required",
        "confirmation_consumed",
        "capacity_snapshot_present",
        "error_code",
    ):
        if current.get(key) != before.get(key):
            raise Stop(f"rollback_prepare_semantic_drift:{key}")


def durable_write(path: Path, value: Any) -> None:
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=True) as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
    finally:
        if fd >= 0:
            pass
    directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def execute(tar: Path, authorization: str, confirm: str) -> dict[str, Any]:
    if authorization != GATE_ID:
        raise Stop("authorization_mismatch")
    if confirm != CONFIRMATION:
        raise Stop("confirmation_mismatch")
    if tar.is_symlink() or not tar.is_file() or tar.stat().st_size != TARGET_TAR_SIZE or sha_file(tar) != TARGET_TAR_SHA256:
        raise Stop("target_tar_invalid")
    if STATE_ROOT.exists():
        raise Stop("execution_state_already_exists")

    pre = collect_preflight()
    STATE_ROOT.mkdir(mode=0o700)
    if STATE_ROOT.stat().st_uid != 0 or stat.S_IMODE(STATE_ROOT.stat().st_mode) != 0o700:
        raise Stop("execution_state_metadata_invalid")
    snapshot_env = STATE_ROOT / "docker-compose.env.before"
    snapshot_env.write_bytes(COMPOSE_ENV.read_bytes())
    os.chmod(snapshot_env, 0o600)
    durable_write(STATE_ROOT / "preflight.json", pre)
    durable_write(STATE_ROOT / "authorization_claim.json", {
        "authorization_id": GATE_ID,
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
    })

    rollback_needed = False
    try:
        run(["docker", "load", "-i", str(tar)], timeout=1800)
        image = json.loads(run(["docker", "image", "inspect", TARGET]).stdout)
        if (
            not isinstance(image, list)
            or len(image) != 1
            or image[0].get("Id") != TARGET_IMAGE_ID
            or image[0].get("Os") != "linux"
            or image[0].get("Architecture") != "arm64"
        ):
            raise Stop("loaded_target_identity_invalid")

        rollback_needed = True
        run(["systemctl", "stop", SERVICES_UNIT], timeout=180)
        updated = rewrite_manager(COMPOSE_ENV.read_bytes(), PREDECESSOR, TARGET)
        atomic_replace(COMPOSE_ENV, updated)
        run(["systemctl", "start", SERVICES_UNIT], timeout=180)
        wait_services()
        post = post_validate(pre)
        durable_write(STATE_ROOT / "post.json", post)
        return {
            "status": "PASS",
            "authorization_claimed": True,
            "authorization_consumed": True,
            "replay_permitted": False,
            "rollback_required": False,
            **post,
        }
    except Exception as error:
        result = {
            "status": "STOP",
            "authorization_claimed": True,
            "authorization_consumed": True,
            "replay_permitted": False,
            "first_failed_operation": str(error),
        }
        if rollback_needed:
            try:
                rollback(pre, snapshot_env)
                result["rollback"] = "PASS"
            except Exception as rollback_error:
                result["rollback"] = "FAIL"
                result["rollback_error"] = str(rollback_error)
        else:
            result["rollback"] = "NOT_REQUIRED"
        try:
            durable_write(STATE_ROOT / "failure.json", result)
        except Exception:
            pass
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--manager-tar", type=Path)
    parser.add_argument("--authorization-id")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    try:
        if args.preflight:
            print(json.dumps({"status": "PASS", **collect_preflight()}, sort_keys=True))
            return 0
        if args.execute and args.manager_tar and args.authorization_id:
            result = execute(args.manager_tar, args.authorization_id, args.confirm)
            print(json.dumps(result, sort_keys=True))
            return 0 if result.get("status") == "PASS" else 2
        raise Stop("arguments_invalid")
    except Exception as error:
        print(json.dumps({"status": "STOP", "reason": str(error)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
