#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

COMPOSE = Path("/opt/greenhouse-fc4-95c42fa5/runtime/docker-compose.yml")
MANAGER_ENV = Path("/opt/greenhouse-fc4-95c42fa5/runtime/manager/manager.env")
SERVICE_ENV = Path("/opt/greenhouse-fc4-95c42fa5/runtime/service-identities.env")
STAGE_ROOT = Path("/root/n3w-kf098-manager-cutover-20260928-01")
IMAGE_TAR = STAGE_ROOT / "greenhouse-manager-arm64.tar"
MANIFEST = STAGE_ROOT / "manifest.json"
MANIFEST_SHA = STAGE_ROOT / "manifest.sha256"
ROLLBACK_ROOT = STAGE_ROOT / "rollback"
MANAGER_ENV_BACKUP = ROLLBACK_ROOT / "manager.env.before"
PRESTATE_JSON = ROLLBACK_ROOT / "manager-prestate.json"
OVERLAY = STAGE_ROOT / "manager-kf098-overlay.yml"
ROLLBACK_OVERLAY = STAGE_ROOT / "manager-kf098-rollback-overlay.yml"

PAIRING_KEY = "GH_N3W_PAIRING_ADVERTISED_HOST"
SOURCE_SHA = "575ce642e372961e21de14a36eba5877082de3cf"
SOURCE_TREE = "7f1641827b75668aa220832b7663bf81d98633ba"
ARTIFACT_ID = 10935052471
NEW_IMAGE_ID = "sha256:49c9fcc0a17d47678b0667c48a06f9a9475609a757e510ca148983b53ed537e3"
NEW_IMAGE_TAG = "local/greenhouse-manager:kf098-575ce642"
NEW_IMAGE_TAR_SHA256 = "6392b8c9bb87d95404346583d6f44967bd4e20fcc092be393c45f75a4ca7a5b2"
OLD_IMAGE_ID = "sha256:271cd87c88c041f0ef7fa55f6c223615edf42388b8e05a7445862e2b700cdfb5"
ROLLBACK_IMAGE_TAG = "local/greenhouse-manager:kf098-precutover-271cd87c"
EXPECTED_COMPOSE_SHA256 = "2c9c28c582a9c01e18a2e54a4c0b2bbddc75192ed377a701ed2f661f15cd5a8a"
EXPECTED_MANAGER_ENV_SHA256 = "f454c6e886ee286192a3c3683a87c33d98e79428de0a6d0c9d2a6e0a19a9d6a6"
EXPECTED_MANAGER_ENV_EXCLUDING_PAIRING_SHA256 = "568c4302f2986e5f52b030ccd9cd96862213bfdfa65f31f5da54a20296bce89e"
EXPECTED_SERVICE_ENV_SHA256 = "1b4e4ecb44505aa8a8ede0159c173df9478dda2532caa5b7c202330dde18bf7c"
EXPECTED_STALE_PAIRING_SHA256 = "fd81bc85606fef9be0fef1ebeda6c00dcab38fe80440939ec413442894216534"
EXPECTED_MANAGER_MOUNT_SHA256 = "6cb94ab6b78e0a68df458e5dc4d9240cc91c225a1b44bc7eba9454325821bffc"
EXPECTED_GUARD_BLOB = "795903b06c7ee93a0602649e478bc070723ab8c0"
EXPECTED_GUARD_UNIT_BLOB = "b68d7d71ee43b26cb0481f0b278cf5739f3a2911"
EXPECTED_ACTIVATION_UNIT_BLOB = "5033b7475f4fafb1409ed277425197a93fd0d5a5"
EXPECTED_DISPATCHER_BLOB = "f733f5a1cfc936f77d1fabc383ccf262264e33d2"
MANAGER_NAME = "greenhouse-manager"
BROKER_PROJECT = "n3wfc4"


class StopExecution(RuntimeError):
    pass


def run(args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def require_ok(result: subprocess.CompletedProcess[str], message: str) -> str:
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise StopExecution(f"{message}: {detail[:800]}")
    return result.stdout


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise StopExecution(f"missing file: {path}")
    return sha256_bytes(path.read_bytes())


def git_blob_hash(path: Path) -> str:
    if not path.is_file():
        raise StopExecution(f"missing file: {path}")
    data = path.read_bytes()
    header = b"blob " + str(len(data)).encode() + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def normalized_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return sha256_bytes(payload)


def ip_kind(value: str) -> str:
    if value == "auto":
        return "auto"
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return "hostname_or_other"
    return "ipv4_literal" if address.version == 4 else "ipv6_literal"


def env_values(path: Path, key: str) -> list[str]:
    result: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        candidate = line[7:].lstrip() if line.startswith("export ") else line
        if "=" not in candidate:
            continue
        name, value = candidate.split("=", 1)
        if name.strip() != key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        result.append(value)
    return result


def env_without_target_hash(path: Path) -> str:
    kept: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        candidate = line[7:].lstrip() if line.startswith("export ") else line
        if candidate.startswith(PAIRING_KEY + "="):
            continue
        kept.append(raw)
    return sha256_bytes(("\n".join(kept) + "\n").encode())


def rewrite_pairing_env_to_auto(path: Path) -> None:
    original = path.stat()
    pattern = re.compile(
        r"^(?P<prefix>\s*(?:export\s+)?"
        + re.escape(PAIRING_KEY)
        + r"\s*=).*$"
    )
    output: list[str] = []
    replaced = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(raw)
        if match:
            output.append(match.group("prefix") + "auto")
            replaced += 1
        else:
            output.append(raw)
    if replaced != 1:
        raise StopExecution(f"pairing env key count={replaced}, expected 1")
    tmp = path.with_name(path.name + ".kf098.tmp")
    if tmp.exists():
        tmp.unlink()
    tmp.write_text("\n".join(output) + "\n", encoding="utf-8")
    os.chmod(tmp, original.st_mode & 0o777)
    os.chown(tmp, original.st_uid, original.st_gid)
    os.replace(tmp, path)


def restore_file(source: Path, destination: Path) -> None:
    tmp = destination.with_name(destination.name + ".kf098.rollback.tmp")
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(source, tmp)
    os.replace(tmp, destination)


def docker_inspect(name: str) -> dict[str, Any]:
    raw = require_ok(
        run(["docker", "inspect", name]),
        f"docker inspect failed for {name}",
    )
    value = json.loads(raw)
    if not isinstance(value, list) or len(value) != 1:
        raise StopExecution(f"docker inspect shape invalid for {name}")
    item = value[0]
    if not isinstance(item, dict):
        raise StopExecution(f"docker inspect item invalid for {name}")
    return item


def manager_mount_fingerprint(item: dict[str, Any]) -> tuple[int, str]:
    mounts = [
        {
            "Type": entry.get("Type"),
            "Source": entry.get("Source"),
            "Destination": entry.get("Destination"),
            "RW": entry.get("RW"),
            "Propagation": entry.get("Propagation"),
        }
        for entry in item.get("Mounts", [])
        if isinstance(entry, dict)
    ]
    mounts = sorted(
        mounts,
        key=lambda value: (
            str(value["Destination"]),
            str(value["Source"]),
        ),
    )
    return len(mounts), normalized_hash(mounts)


def gh_env_fingerprint(item: dict[str, Any]) -> str:
    config = item.get("Config")
    config = config if isinstance(config, dict) else {}
    env = config.get("Env")
    env = env if isinstance(env, list) else []
    selected = sorted(
        value
        for value in env
        if isinstance(value, str)
        and value.startswith("GH_")
        and not value.startswith(PAIRING_KEY + "=")
    )
    return normalized_hash(selected)


def manager_runtime_security_fingerprint(
    item: dict[str, Any],
) -> str:
    config = item.get("Config")
    config = config if isinstance(config, dict) else {}
    host = item.get("HostConfig")
    host = host if isinstance(host, dict) else {}
    config_keys = (
        "Healthcheck",
        "OpenStdin",
        "StdinOnce",
        "StopSignal",
        "StopTimeout",
        "Tty",
        "WorkingDir",
    )
    host_keys = (
        "AutoRemove",
        "CapAdd",
        "CapDrop",
        "CgroupnsMode",
        "DeviceRequests",
        "Devices",
        "Init",
        "IpcMode",
        "LogConfig",
        "Memory",
        "MemorySwap",
        "NanoCpus",
        "NetworkMode",
        "OomKillDisable",
        "PidMode",
        "PidsLimit",
        "PortBindings",
        "Privileged",
        "ReadonlyRootfs",
        "RestartPolicy",
        "SecurityOpt",
        "ShmSize",
        "Tmpfs",
        "Ulimits",
    )
    contract = {
        "config": {
            key: config.get(key)
            for key in config_keys
        },
        "host": {
            key: host.get(key)
            for key in host_keys
        },
    }
    return normalized_hash(contract)


def runtime_pairing_values(item: dict[str, Any]) -> list[str]:
    config = item.get("Config")
    config = config if isinstance(config, dict) else {}
    env = config.get("Env")
    env = env if isinstance(env, list) else []
    return [
        value.split("=", 1)[1]
        for value in env
        if isinstance(value, str)
        and value.startswith(PAIRING_KEY + "=")
    ]


def socket_port_count(proto: str, port: int) -> int:
    args = ["ss", "-H", "-lnt"] if proto == "tcp" else ["ss", "-H", "-lnu"]
    raw = require_ok(run(args), f"cannot inspect {proto} sockets")
    count = 0
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        match = re.search(r":(\d+)$", fields[3])
        if match and int(match.group(1)) == port:
            count += 1
    return count


def eth0_ipv4() -> str:
    raw = require_ok(
        run([
            "ip",
            "-4",
            "-o",
            "addr",
            "show",
            "dev",
            "eth0",
            "scope",
            "global",
        ]),
        "cannot inspect eth0 IPv4",
    )
    values = []
    for line in raw.splitlines():
        match = re.search(r"\binet\s+([0-9.]+)/", line)
        if match:
            values.append(match.group(1))
    if len(values) != 1:
        raise StopExecution(
            f"eth0 global IPv4 count={len(values)}, expected 1"
        )
    return values[0]


def firewall_state() -> dict[str, Any]:
    lines = require_ok(
        run(["iptables-save", "-t", "filter"]),
        "cannot inspect filter table",
    ).splitlines()

    def positions(chain: str) -> list[int]:
        rules = [
            line
            for line in lines
            if line.startswith(f"-A {chain} ")
        ]
        return [
            index + 1
            for index, line in enumerate(rules)
            if "-j N3WFC4-BROKER-INGRESS" in line
        ]

    owned = [
        line
        for line in lines
        if line.startswith("-A N3WFC4-BROKER-INGRESS ")
    ]
    return {
        "docker_user_anchor_positions": positions("DOCKER-USER"),
        "input_anchor_positions": positions("INPUT"),
        "owned_chain_rule_count": len(owned),
        "owned_chain_sha256": sha256_bytes("\n".join(owned).encode()),
    }


def broker_inspect() -> dict[str, Any]:
    raw = require_ok(
        run(["docker", "ps", "-q", "--filter", "label=com.docker.compose.project=n3wfc4",
             "--filter", "label=com.docker.compose.service=broker"]),
        "cannot locate Broker",
    )
    values = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(values) != 1:
        raise StopExecution(f"Broker count={len(values)}, expected 1")
    return docker_inspect(values[0])


def verify_stage_artifact() -> dict[str, Any]:
    if sha256_file(IMAGE_TAR) != NEW_IMAGE_TAR_SHA256:
        raise StopExecution("staged image tar SHA256 mismatch")
    if not MANIFEST.is_file() or not MANIFEST_SHA.is_file():
        raise StopExecution("manifest files are missing")
    expected = f"{sha256_file(MANIFEST)}  manifest.json"
    if MANIFEST_SHA.read_text(encoding="utf-8").strip() != expected:
        raise StopExecution("portable manifest checksum mismatch")
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source = document.get("source")
    image = document.get("image")
    if document.get("schema") != "gh.n3w-manager-exact-source-artifact/1":
        raise StopExecution("manifest schema mismatch")
    if not isinstance(source, dict) or not isinstance(image, dict):
        raise StopExecution("manifest source/image binding missing")
    if source.get("commit") != SOURCE_SHA or source.get("tree") != SOURCE_TREE:
        raise StopExecution("manifest source binding mismatch")
    if image.get("id") != NEW_IMAGE_ID:
        raise StopExecution("manifest image ID mismatch")
    if image.get("architecture") != "arm64":
        raise StopExecution("manifest image architecture mismatch")
    if image.get("entrypoint") != ["greenhouse-manager"]:
        raise StopExecution("manifest entrypoint mismatch")
    return {
        "artifact_id": ARTIFACT_ID,
        "source_sha": SOURCE_SHA,
        "image_id": NEW_IMAGE_ID,
        "image_tar_sha256": NEW_IMAGE_TAR_SHA256,
    }


def base_preflight() -> dict[str, Any]:
    if sha256_file(COMPOSE) != EXPECTED_COMPOSE_SHA256:
        raise StopExecution("live Compose SHA256 drift")
    if sha256_file(MANAGER_ENV) != EXPECTED_MANAGER_ENV_SHA256:
        raise StopExecution("manager.env SHA256 drift")
    if env_without_target_hash(MANAGER_ENV) != EXPECTED_MANAGER_ENV_EXCLUDING_PAIRING_SHA256:
        raise StopExecution("manager.env non-target content drift")
    if sha256_file(SERVICE_ENV) != EXPECTED_SERVICE_ENV_SHA256:
        raise StopExecution("service-identities.env SHA256 drift")

    pairing = env_values(MANAGER_ENV, PAIRING_KEY)
    if len(pairing) != 1:
        raise StopExecution("manager.env pairing key is not unique")
    if ip_kind(pairing[0]) != "ipv4_literal":
        raise StopExecution("manager.env pairing value is not IPv4 literal")
    if sha256_bytes(pairing[0].encode()) != EXPECTED_STALE_PAIRING_SHA256:
        raise StopExecution("manager.env stale pairing hash drift")
    current_ip = eth0_ipv4()
    if pairing[0] == current_ip:
        raise StopExecution("manager.env pairing IPv4 is no longer stale")

    manager = docker_inspect(MANAGER_NAME)
    state = manager.get("State")
    state = state if isinstance(state, dict) else {}
    config = manager.get("Config")
    config = config if isinstance(config, dict) else {}
    host = manager.get("HostConfig")
    host = host if isinstance(host, dict) else {}
    if state.get("Running") is not True:
        raise StopExecution("Manager is not running")
    if manager.get("Image") != OLD_IMAGE_ID:
        raise StopExecution("Manager image ID drift")
    if manager.get("RestartCount") != 1:
        raise StopExecution("Manager restart count drift")
    if host.get("NetworkMode") != "host":
        raise StopExecution("Manager network mode drift")
    if config.get("Entrypoint") != ["greenhouse-manager"]:
        raise StopExecution("Manager entrypoint drift")
    if config.get("User") != "greenhouse":
        raise StopExecution("Manager user drift")
    mount_count, mount_hash = manager_mount_fingerprint(manager)
    if mount_count != 6 or mount_hash != EXPECTED_MANAGER_MOUNT_SHA256:
        raise StopExecution("Manager mount binding drift")
    if runtime_pairing_values(manager) != pairing:
        raise StopExecution("Manager runtime pairing value drift")

    broker = broker_inspect()
    broker_state = broker.get("State")
    broker_state = broker_state if isinstance(broker_state, dict) else {}
    if broker_state.get("Running") is not True:
        raise StopExecution("Broker is not running")
    if broker.get("RestartCount") != 0:
        raise StopExecution("Broker restart count drift")
    if socket_port_count("tcp", 8883) != 1:
        raise StopExecution("TCP 8883 listener count drift")
    if socket_port_count("tcp", 47112) != 1:
        raise StopExecution("TCP 47112 listener count drift")
    if socket_port_count("udp", 47111) != 1:
        raise StopExecution("UDP 47111 listener count drift")

    units = [
        ("n3wfc4-broker-ingress-guard.service", EXPECTED_GUARD_UNIT_BLOB),
        ("n3wfc4-broker-activation.service", EXPECTED_ACTIVATION_UNIT_BLOB),
    ]
    for unit, expected_blob in units:
        active = require_ok(
            run(["systemctl", "is-active", unit]),
            f"{unit} active check failed",
        ).strip()
        enabled = require_ok(
            run(["systemctl", "is-enabled", unit]),
            f"{unit} enabled check failed",
        ).strip()
        if active != "active" or enabled != "enabled":
            raise StopExecution(f"{unit} lifecycle drift")
        path = Path("/etc/systemd/system") / unit
        if git_blob_hash(path) != expected_blob:
            raise StopExecution(f"{unit} blob drift")

    if git_blob_hash(Path("/usr/local/sbin/n3w-broker-ingress-guard")) != EXPECTED_GUARD_BLOB:
        raise StopExecution("R5 guard blob drift")
    dispatcher = Path(
        "/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard"
    )
    if git_blob_hash(dispatcher) != EXPECTED_DISPATCHER_BLOB:
        raise StopExecution("R5 dispatcher blob drift")

    firewall = firewall_state()
    if firewall["docker_user_anchor_positions"] != [1]:
        raise StopExecution("R5 DOCKER-USER anchor drift")
    if firewall["input_anchor_positions"] != [1]:
        raise StopExecution("R5 INPUT anchor drift")
    if firewall["owned_chain_rule_count"] != 3:
        raise StopExecution("R5 owned chain rule count drift")

    return {
        "manager_started_at": state.get("StartedAt"),
        "manager_restart_count": manager.get("RestartCount"),
        "manager_image_id": manager.get("Image"),
        "manager_mount_count": mount_count,
        "manager_mount_hash": mount_hash,
        "manager_gh_env_hash": gh_env_fingerprint(manager),
        "manager_runtime_security_hash": manager_runtime_security_fingerprint(manager),
        "broker_id": broker.get("Id"),
        "broker_restart_count": broker.get("RestartCount"),
        "firewall": firewall,
        "current_eth0_ipv4_sha256": sha256_bytes(current_ip.encode()),
    }


def make_overlay(path: Path, image: str) -> None:
    payload = (
        "services:\n"
        "  manager:\n"
        f"    image: {image}\n"
        "    container_name: greenhouse-manager\n"
        "    pull_policy: never\n"
    )
    path.write_text(payload, encoding="utf-8")
    os.chmod(path, 0o600)


def compose_up(overlay: Path) -> None:
    require_ok(
        run(
            [
                "docker",
                "compose",
                "--project-name",
                BROKER_PROJECT,
                "-f",
                str(COMPOSE),
                "-f",
                str(overlay),
                "up",
                "-d",
                "--no-deps",
                "--force-recreate",
                "manager",
            ],
            timeout=120,
        ),
        "Manager compose recreate failed",
    )


def wait_health(timeout_seconds: int = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:47112/healthz",
                timeout=2,
            ) as response:
                document = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and document == {
                    "schema": "gh.pair.simple-health/1",
                    "status": "ok",
                }:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise StopExecution("Manager simplified health did not recover")


def write_private_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)


def restore_manager_env() -> None:
    if sha256_file(MANAGER_ENV_BACKUP) != EXPECTED_MANAGER_ENV_SHA256:
        raise StopExecution("rollback manager.env authority mismatch")
    tmp = MANAGER_ENV.with_name(MANAGER_ENV.name + ".kf098.rollback.tmp")
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(MANAGER_ENV_BACKUP, tmp)
    os.replace(tmp, MANAGER_ENV)
    if sha256_file(MANAGER_ENV) != EXPECTED_MANAGER_ENV_SHA256:
        raise StopExecution("manager.env rollback verification failed")


def rollback(prestate: dict[str, Any]) -> dict[str, Any]:
    require_ok(
        run(["docker", "image", "inspect", OLD_IMAGE_ID]),
        "old Manager image is unavailable",
    )
    require_ok(
        run(["docker", "tag", OLD_IMAGE_ID, ROLLBACK_IMAGE_TAG]),
        "cannot bind rollback image tag",
    )
    if run(["docker", "inspect", MANAGER_NAME]).returncode == 0:
        require_ok(
            run(["docker", "rm", "-f", MANAGER_NAME], timeout=60),
            "cannot remove candidate Manager",
        )
    restore_manager_env()
    make_overlay(ROLLBACK_OVERLAY, ROLLBACK_IMAGE_TAG)
    compose_up(ROLLBACK_OVERLAY)
    wait_health()
    manager = docker_inspect(MANAGER_NAME)
    state = manager.get("State")
    state = state if isinstance(state, dict) else {}
    config = manager.get("Config")
    config = config if isinstance(config, dict) else {}
    host = manager.get("HostConfig")
    host = host if isinstance(host, dict) else {}
    mount_count, mount_hash = manager_mount_fingerprint(manager)
    if state.get("Running") is not True:
        raise StopExecution("rollback Manager is not running")
    if manager.get("Image") != OLD_IMAGE_ID:
        raise StopExecution("rollback Manager image mismatch")
    if host.get("NetworkMode") != "host":
        raise StopExecution("rollback Manager network mode mismatch")
    if config.get("Entrypoint") != ["greenhouse-manager"]:
        raise StopExecution("rollback Manager entrypoint mismatch")
    if config.get("User") != "greenhouse":
        raise StopExecution("rollback Manager user mismatch")
    if mount_count != prestate["manager_mount_count"]:
        raise StopExecution("rollback Manager mount count mismatch")
    if mount_hash != prestate["manager_mount_hash"]:
        raise StopExecution("rollback Manager mount binding mismatch")
    if gh_env_fingerprint(manager) != prestate["manager_gh_env_hash"]:
        raise StopExecution("rollback Manager non-target GH env drift")
    if (
        manager_runtime_security_fingerprint(manager)
        != prestate["manager_runtime_security_hash"]
    ):
        raise StopExecution("rollback Manager runtime/security contract drift")
    stale_pairing = env_values(MANAGER_ENV, PAIRING_KEY)
    if len(stale_pairing) != 1:
        raise StopExecution("rollback pairing env count mismatch")
    if sha256_file(MANAGER_ENV) != EXPECTED_MANAGER_ENV_SHA256:
        raise StopExecution("rollback manager.env SHA256 mismatch")
    if runtime_pairing_values(manager) != stale_pairing:
        raise StopExecution("rollback Manager pairing runtime mismatch")
    if socket_port_count("tcp", 47112) != 1:
        raise StopExecution("rollback TCP 47112 listener mismatch")
    if socket_port_count("udp", 47111) != 1:
        raise StopExecution("rollback UDP 47111 listener mismatch")
    broker = broker_inspect()
    if broker.get("Id") != prestate["broker_id"]:
        raise StopExecution("Broker identity changed during rollback")
    if broker.get("RestartCount") != prestate["broker_restart_count"]:
        raise StopExecution("Broker restart count changed during rollback")
    if socket_port_count("tcp", 8883) != 1:
        raise StopExecution("rollback TCP 8883 listener mismatch")
    if firewall_state() != prestate["firewall"]:
        raise StopExecution("R5 firewall state changed during rollback")
    return {
        "rollback_result": "PASS",
        "manager_env_restored": True,
        "manager_image_restored": True,
        "manager_runtime_security_restored": True,
        "manager_pairing_runtime_restored": True,
        "broker_preserved": True,
        "r5_preserved": True,
    }


def postcheck(prestate: dict[str, Any]) -> dict[str, Any]:
    manager = docker_inspect(MANAGER_NAME)
    state = manager.get("State")
    state = state if isinstance(state, dict) else {}
    config = manager.get("Config")
    config = config if isinstance(config, dict) else {}
    host = manager.get("HostConfig")
    host = host if isinstance(host, dict) else {}
    if state.get("Running") is not True:
        raise StopExecution("new Manager is not running")
    if manager.get("Image") != NEW_IMAGE_ID:
        raise StopExecution("new Manager image mismatch")
    if host.get("NetworkMode") != "host":
        raise StopExecution("new Manager network mode mismatch")
    if config.get("Entrypoint") != ["greenhouse-manager"]:
        raise StopExecution("new Manager entrypoint mismatch")
    if config.get("User") != "greenhouse":
        raise StopExecution("new Manager user mismatch")
    mount_count, mount_hash = manager_mount_fingerprint(manager)
    if mount_count != prestate["manager_mount_count"]:
        raise StopExecution("new Manager mount count mismatch")
    if mount_hash != prestate["manager_mount_hash"]:
        raise StopExecution("new Manager mount binding mismatch")
    if gh_env_fingerprint(manager) != prestate["manager_gh_env_hash"]:
        raise StopExecution("new Manager non-target GH env drift")
    if (
        manager_runtime_security_fingerprint(manager)
        != prestate["manager_runtime_security_hash"]
    ):
        raise StopExecution("new Manager runtime/security contract drift")
    if runtime_pairing_values(manager) != ["auto"]:
        raise StopExecution("new Manager runtime pairing host is not auto")
    if env_values(MANAGER_ENV, PAIRING_KEY) != ["auto"]:
        raise StopExecution("manager.env pairing host is not auto")
    if env_without_target_hash(MANAGER_ENV) != EXPECTED_MANAGER_ENV_EXCLUDING_PAIRING_SHA256:
        raise StopExecution("manager.env non-target content changed")
    if socket_port_count("tcp", 47112) != 1:
        raise StopExecution("TCP 47112 listener did not recover")
    if socket_port_count("udp", 47111) != 1:
        raise StopExecution("UDP 47111 listener did not recover")
    wait_health()
    broker = broker_inspect()
    if broker.get("Id") != prestate["broker_id"]:
        raise StopExecution("Broker identity changed")
    if broker.get("RestartCount") != prestate["broker_restart_count"]:
        raise StopExecution("Broker restart count changed")
    if socket_port_count("tcp", 8883) != 1:
        raise StopExecution("TCP 8883 listener changed")
    if firewall_state() != prestate["firewall"]:
        raise StopExecution("R5 firewall state changed")
    return {
        "manager_exact_image": True,
        "manager_pairing_auto": True,
        "manager_mounts_preserved": True,
        "manager_health": "PASS",
        "broker_preserved": True,
        "r5_preserved": True,
    }


def apply() -> dict[str, Any]:
    artifact = verify_stage_artifact()
    prestate = base_preflight()
    if ROLLBACK_ROOT.exists():
        raise StopExecution("rollback root already exists")
    ROLLBACK_ROOT.mkdir(mode=0o700)
    shutil.copy2(MANAGER_ENV, MANAGER_ENV_BACKUP)
    os.chmod(MANAGER_ENV_BACKUP, 0o600)
    if sha256_file(MANAGER_ENV_BACKUP) != EXPECTED_MANAGER_ENV_SHA256:
        raise StopExecution("manager.env snapshot mismatch")
    write_private_json(PRESTATE_JSON, prestate)
    mutation_started = False
    try:
        require_ok(
            run(["docker", "load", "-i", str(IMAGE_TAR)], timeout=180),
            "exact Manager image load failed",
        )
        require_ok(
            run(["docker", "image", "inspect", NEW_IMAGE_ID]),
            "exact Manager image ID unavailable after load",
        )
        require_ok(
            run(["docker", "tag", OLD_IMAGE_ID, ROLLBACK_IMAGE_TAG]),
            "cannot bind rollback image tag",
        )
        mutation_started = True
        rewrite_pairing_env_to_auto(MANAGER_ENV)
        if env_values(MANAGER_ENV, PAIRING_KEY) != ["auto"]:
            raise StopExecution("manager.env auto rewrite failed")
        if env_without_target_hash(MANAGER_ENV) != EXPECTED_MANAGER_ENV_EXCLUDING_PAIRING_SHA256:
            raise StopExecution("manager.env non-target drift after rewrite")
        make_overlay(OVERLAY, NEW_IMAGE_TAG)
        require_ok(
            run(["docker", "stop", "-t", "20", MANAGER_NAME], timeout=40),
            "cannot stop old Manager",
        )
        require_ok(
            run(["docker", "rm", MANAGER_NAME]),
            "cannot remove old Manager",
        )
        compose_up(OVERLAY)
        post = postcheck(prestate)
        return {
            "result": "PASS",
            "artifact": artifact,
            "poststate": post,
            "rollback_attempted": False,
        }
    except Exception as exc:
        if not mutation_started:
            raise
        rollback_result = None
        rollback_error = None
        try:
            rollback_result = rollback(prestate)
        except Exception as rollback_exc:
            rollback_error = f"{type(rollback_exc).__name__}:{rollback_exc}"
        status = (
            "FAIL_ROLLED_BACK"
            if rollback_error is None
            else "FAIL_ROLLBACK_INCOMPLETE"
        )
        raise StopExecution(
            json.dumps(
                {
                    "result": status,
                    "failure": f"{type(exc).__name__}:{exc}",
                    "rollback": rollback_result,
                    "rollback_error": rollback_error,
                },
                sort_keys=True,
            )
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase",
        choices=("preflight", "apply", "rollback"),
    )
    args = parser.parse_args()
    try:
        stage_mode = STAGE_ROOT.stat().st_mode & 0o777
        if stage_mode != 0o700 or STAGE_ROOT.stat().st_uid != 0:
            raise StopExecution("stage root authority invalid")
        if args.phase == "preflight":
            prestate = base_preflight()
            result = {
                "result": "PASS",
                "phase": "preflight",
                "artifact": verify_stage_artifact(),
                "manager_image_id": prestate["manager_image_id"],
                "manager_restart_count": prestate["manager_restart_count"],
                "manager_mount_count": prestate["manager_mount_count"],
                "manager_mount_hash": prestate["manager_mount_hash"],
                "broker_restart_count": prestate["broker_restart_count"],
                "r5_firewall": prestate["firewall"],
                "t1_mutation": False,
            }
        elif args.phase == "apply":
            result = apply()
        else:
            if not PRESTATE_JSON.is_file():
                raise StopExecution("rollback prestate authority is missing")
            value = json.loads(PRESTATE_JSON.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise StopExecution("rollback prestate authority is invalid")
            required = {
                "manager_mount_count",
                "manager_mount_hash",
                "manager_gh_env_hash",
                "manager_runtime_security_hash",
                "broker_id",
                "broker_restart_count",
                "firewall",
            }
            if not required.issubset(value):
                raise StopExecution("rollback prestate authority is incomplete")
            result = rollback(value)
        result.pop("manager_id", None)
        result.pop("broker_id", None)
        print(json.dumps(result, sort_keys=True))
        return 0
    except StopExecution as exc:
        print(
            json.dumps(
                {
                    "result": "STOP",
                    "phase": args.phase,
                    "reason": str(exc)[:1600],
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
