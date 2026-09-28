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
SHADOW_OLD_OVERLAY = STAGE_ROOT / "manager-kf098-shadow-old-overlay.yml"
SHADOW_NEW_OVERLAY = STAGE_ROOT / "manager-kf098-shadow-new-overlay.yml"
SHADOW_OLD_NAME = "greenhouse-manager-kf098-shadow-old"
SHADOW_NEW_NAME = "greenhouse-manager-kf098-shadow-new"
STALE_SHADOW_OLD_OVERLAY_SHA256 = "aeab3dafd4edceca69bd3e17964d7fc670c7ef50ee079d80e984f8dd2cabeff8"

PAIRING_KEY = "GH_N3W_PAIRING_ADVERTISED_HOST"
SOURCE_SHA = "575ce642e372961e21de14a36eba5877082de3cf"
SOURCE_TREE = "7f1641827b75668aa220832b7663bf81d98633ba"
ARTIFACT_ID = 10935052471
NEW_IMAGE_CONFIG_DIGEST = "sha256:49c9fcc0a17d47678b0667c48a06f9a9475609a757e510ca148983b53ed537e3"
NEW_IMAGE_MANIFEST_DIGEST = "sha256:b806e7c8b97cc757965161a989f954df09427aa7d2700a6503e56e49cc8f9e4f"
NEW_IMAGE_ID = NEW_IMAGE_CONFIG_DIGEST
NEW_IMAGE_TAG = "local/greenhouse-manager:kf098-575ce642"
NEW_IMAGE_TAR_SHA256 = "6392b8c9bb87d95404346583d6f44967bd4e20fcc092be393c45f75a4ca7a5b2"
EXPECTED_NEW_ROOTFS_LAYERS_SHA256 = "97dd9fb029f1678a4589148d1874c95cd1d26439efa89ee833d5d734b70d42d6"
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


def image_inspect(reference: str) -> dict[str, Any]:
    raw = require_ok(
        run(["docker", "image", "inspect", reference]),
        f"docker image inspect failed for {reference}",
    )
    value = json.loads(raw)
    if not isinstance(value, list) or len(value) != 1:
        raise StopExecution(
            f"docker image inspect shape invalid for {reference}"
        )
    item = value[0]
    if not isinstance(item, dict):
        raise StopExecution(
            f"docker image inspect item invalid for {reference}"
        )
    return item


def accepted_new_runtime_image_ids() -> set[str]:
    return {
        NEW_IMAGE_CONFIG_DIGEST,
        NEW_IMAGE_MANIFEST_DIGEST,
    }


def rootfs_layers_fingerprint(item: dict[str, Any]) -> str:
    rootfs = item.get("RootFS")
    rootfs = rootfs if isinstance(rootfs, dict) else {}
    layers = rootfs.get("Layers")
    layers = layers if isinstance(layers, list) else []
    return normalized_hash(layers)


def verify_loaded_exact_image() -> dict[str, Any]:
    item = image_inspect(NEW_IMAGE_TAG)
    runtime_id = item.get("Id")
    if runtime_id not in accepted_new_runtime_image_ids():
        raise StopExecution(
            "loaded Manager runtime image identity is not artifact-owned"
        )
    if item.get("Architecture") != "arm64":
        raise StopExecution("loaded Manager architecture mismatch")
    if item.get("Os") != "linux":
        raise StopExecution("loaded Manager OS mismatch")
    config = item.get("Config")
    config = config if isinstance(config, dict) else {}
    if config.get("Entrypoint") != ["greenhouse-manager"]:
        raise StopExecution("loaded Manager entrypoint mismatch")
    if config.get("User") != "greenhouse":
        raise StopExecution("loaded Manager user mismatch")
    rootfs_hash = rootfs_layers_fingerprint(item)
    if rootfs_hash != EXPECTED_NEW_ROOTFS_LAYERS_SHA256:
        raise StopExecution("loaded Manager RootFS layer binding mismatch")
    return {
        "runtime_image_id": runtime_id,
        "config_digest": NEW_IMAGE_CONFIG_DIGEST,
        "manifest_digest": NEW_IMAGE_MANIFEST_DIGEST,
        "rootfs_layers_sha256": rootfs_hash,
    }


def ensure_loaded_exact_image() -> dict[str, Any]:
    existing = run(
        ["docker", "image", "inspect", NEW_IMAGE_TAG],
    )
    if existing.returncode == 0:
        result = verify_loaded_exact_image()
        result["load_action"] = "reused_existing_exact_tag"
        return result
    require_ok(
        run(["docker", "load", "-i", str(IMAGE_TAR)], timeout=180),
        "exact Manager image load failed",
    )
    result = verify_loaded_exact_image()
    result["load_action"] = "loaded_exact_tar"
    return result


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


def all_env_fingerprint_excluding_pairing(
    item: dict[str, Any],
) -> str:
    config = item.get("Config")
    config = config if isinstance(config, dict) else {}
    env = config.get("Env")
    env = env if isinstance(env, list) else []
    selected = sorted(
        value
        for value in env
        if isinstance(value, str)
        and not value.startswith(PAIRING_KEY + "=")
    )
    return normalized_hash(selected)


def manager_recreate_contract(
    item: dict[str, Any],
) -> dict[str, Any]:
    config = item.get("Config")
    config = config if isinstance(config, dict) else {}
    host = item.get("HostConfig")
    host = host if isinstance(host, dict) else {}
    env = config.get("Env")
    env = env if isinstance(env, list) else []
    if not all(isinstance(value, str) and "=" in value for value in env):
        raise StopExecution("Manager environment shape is unsupported")
    mounts = []
    for entry in item.get("Mounts", []):
        if not isinstance(entry, dict):
            raise StopExecution("Manager mount entry is invalid")
        if entry.get("Type") != "bind":
            raise StopExecution("Manager non-bind mount is unsupported")
        source = entry.get("Source")
        destination = entry.get("Destination")
        if not isinstance(source, str) or not source:
            raise StopExecution("Manager mount source is invalid")
        if not isinstance(destination, str) or not destination:
            raise StopExecution("Manager mount destination is invalid")
        mounts.append(
            {
                "Type": "bind",
                "Source": source,
                "Destination": destination,
                "RW": entry.get("RW") is True,
                "Propagation": entry.get("Propagation") or "rprivate",
            }
        )
    mounts.sort(
        key=lambda value: (
            value["Destination"],
            value["Source"],
        )
    )
    labels = config.get("Labels")
    if labels is None:
        labels = {}
    if not isinstance(labels, dict):
        raise StopExecution("Manager labels shape is unsupported")
    return {
        "env": list(env),
        "mounts": mounts,
        "labels": dict(sorted(labels.items())),
        "entrypoint": config.get("Entrypoint"),
        "cmd": config.get("Cmd"),
        "user": config.get("User"),
        "working_dir": config.get("WorkingDir"),
        "healthcheck": config.get("Healthcheck"),
        "stop_signal": config.get("StopSignal"),
        "stop_timeout": config.get("StopTimeout"),
        "open_stdin": config.get("OpenStdin"),
        "stdin_once": config.get("StdinOnce"),
        "tty": config.get("Tty"),
        "host": {
            key: host.get(key)
            for key in (
                "AutoRemove",
                "CapAdd",
                "CapDrop",
                "CgroupnsMode",
                "DeviceRequests",
                "Devices",
                "Dns",
                "ExtraHosts",
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
        },
    }


def manager_runtime_security_fingerprint(
    item: dict[str, Any],
) -> str:
    config = item.get("Config")
    config = config if isinstance(config, dict) else {}
    host = item.get("HostConfig")
    host = host if isinstance(host, dict) else {}
    config_keys = (
        "Cmd",
        "Healthcheck",
        "Labels",
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
        "Dns",
        "ExtraHosts",
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
    if image.get("id") != NEW_IMAGE_CONFIG_DIGEST:
        raise StopExecution("manifest image config digest mismatch")
    if image.get("architecture") != "arm64":
        raise StopExecution("manifest image architecture mismatch")
    if image.get("entrypoint") != ["greenhouse-manager"]:
        raise StopExecution("manifest entrypoint mismatch")
    return {
        "artifact_id": ARTIFACT_ID,
        "source_sha": SOURCE_SHA,
        "image_config_digest": NEW_IMAGE_CONFIG_DIGEST,
        "image_manifest_digest": NEW_IMAGE_MANIFEST_DIGEST,
        "image_tar_sha256": NEW_IMAGE_TAR_SHA256,
    }


def base_preflight() -> dict[str, Any]:
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
        "manager_all_env_hash":
            all_env_fingerprint_excluding_pairing(manager),
        "manager_runtime_security_hash":
            manager_runtime_security_fingerprint(manager),
        "manager_recreate_contract":
            manager_recreate_contract(manager),
        "broker_id": broker.get("Id"),
        "broker_restart_count": broker.get("RestartCount"),
        "firewall": firewall,
        "current_eth0_ipv4_sha256": sha256_bytes(current_ip.encode()),
    }


def pairing_replaced_env(
    values: list[str],
    pairing_value: str,
) -> list[str]:
    result = []
    replaced = 0
    for value in values:
        if "\n" in value or "\r" in value or "\x00" in value:
            raise StopExecution("Manager environment contains unsupported bytes")
        name, current = value.split("=", 1)
        if name == PAIRING_KEY:
            result.append(f"{PAIRING_KEY}={pairing_value}")
            replaced += 1
        else:
            result.append(value)
    if replaced != 1:
        raise StopExecution(
            f"runtime pairing environment count={replaced}, expected 1"
        )
    return result


def validate_recreate_contract(
    contract: dict[str, Any],
) -> None:
    host = contract.get("host")
    host = host if isinstance(host, dict) else {}
    if contract.get("entrypoint") != ["greenhouse-manager"]:
        raise StopExecution("recreate entrypoint contract unsupported")
    if contract.get("cmd") not in (None, []):
        raise StopExecution("recreate command contract unsupported")
    if contract.get("user") != "greenhouse":
        raise StopExecution("recreate user contract unsupported")
    if contract.get("working_dir") != "/app":
        raise StopExecution("recreate working directory unsupported")
    if contract.get("healthcheck") not in (None, {}):
        raise StopExecution("recreate healthcheck contract unsupported")
    if contract.get("stop_signal") is not None:
        raise StopExecution("recreate stop signal contract unsupported")
    if contract.get("stop_timeout") is not None:
        raise StopExecution("recreate stop timeout contract unsupported")
    if contract.get("open_stdin") not in (False, None):
        raise StopExecution("recreate stdin contract unsupported")
    if contract.get("stdin_once") not in (False, None):
        raise StopExecution("recreate stdin-once contract unsupported")
    if contract.get("tty") not in (False, None):
        raise StopExecution("recreate TTY contract unsupported")
    if host.get("NetworkMode") != "host":
        raise StopExecution("recreate network mode unsupported")
    restart = host.get("RestartPolicy")
    if restart != {
        "Name": "unless-stopped",
        "MaximumRetryCount": 0,
    }:
        raise StopExecution("recreate restart policy unsupported")
    if host.get("ReadonlyRootfs") is not True:
        raise StopExecution("recreate read-only-rootfs contract unsupported")
    if host.get("Privileged") is not False:
        raise StopExecution("recreate privileged contract unsupported")
    if host.get("PortBindings") not in ({}, None):
        raise StopExecution("recreate port binding contract unsupported")
    if host.get("DeviceRequests") not in (None, []):
        raise StopExecution("recreate device-request contract unsupported")
    if host.get("Devices") not in (None, []):
        raise StopExecution("recreate device contract unsupported")
    if host.get("Ulimits") not in (None, []):
        raise StopExecution("recreate ulimit contract unsupported")
    if host.get("NanoCpus") not in (None, 0):
        raise StopExecution("recreate CPU limit contract unsupported")


def write_runtime_env_file(
    path: Path,
    values: list[str],
) -> None:
    path.write_text("\n".join(values) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def manager_create_argv(
    contract: dict[str, Any],
    *,
    image: str,
    name: str,
    env_file: Path,
) -> list[str]:
    validate_recreate_contract(contract)
    host = contract["host"]
    argv = [
        "docker",
        "create",
        "--name",
        name,
        "--network",
        "host",
        "--restart",
        "unless-stopped",
        "--read-only",
        "--user",
        "greenhouse",
        "--workdir",
        "/app",
        "--entrypoint",
        "greenhouse-manager",
        "--env-file",
        str(env_file),
    ]
    shm_size = host.get("ShmSize")
    if isinstance(shm_size, int) and shm_size > 0:
        argv.extend(["--shm-size", str(shm_size)])
    tmpfs = host.get("Tmpfs")
    if isinstance(tmpfs, dict):
        for destination, options in sorted(tmpfs.items()):
            value = destination
            if options:
                value += ":" + str(options)
            argv.extend(["--tmpfs", value])
    log_config = host.get("LogConfig")
    if isinstance(log_config, dict):
        driver = log_config.get("Type")
        if driver:
            argv.extend(["--log-driver", str(driver)])
        options = log_config.get("Config")
        if isinstance(options, dict):
            for key, value in sorted(options.items()):
                argv.extend(["--log-opt", f"{key}={value}"])
    cap_add = host.get("CapAdd")
    if isinstance(cap_add, list):
        for value in cap_add:
            argv.extend(["--cap-add", str(value)])
    cap_drop = host.get("CapDrop")
    if isinstance(cap_drop, list):
        for value in cap_drop:
            argv.extend(["--cap-drop", str(value)])
    security_opt = host.get("SecurityOpt")
    if isinstance(security_opt, list):
        for value in security_opt:
            argv.extend(["--security-opt", str(value)])
    if host.get("Init") is True:
        argv.append("--init")
    memory = host.get("Memory")
    if isinstance(memory, int) and memory > 0:
        argv.extend(["--memory", str(memory)])
    memory_swap = host.get("MemorySwap")
    if isinstance(memory_swap, int) and memory_swap != 0:
        argv.extend(["--memory-swap", str(memory_swap)])
    pids_limit = host.get("PidsLimit")
    if isinstance(pids_limit, int):
        argv.extend(["--pids-limit", str(pids_limit)])
    if host.get("OomKillDisable") is True:
        argv.append("--oom-kill-disable")
    ipc_mode = host.get("IpcMode")
    if ipc_mode not in (None, "", "private"):
        argv.extend(["--ipc", str(ipc_mode)])
    pid_mode = host.get("PidMode")
    if pid_mode not in (None, ""):
        argv.extend(["--pid", str(pid_mode)])
    dns = host.get("Dns")
    if isinstance(dns, list):
        for value in dns:
            argv.extend(["--dns", str(value)])
    extra_hosts = host.get("ExtraHosts")
    if isinstance(extra_hosts, list):
        for value in extra_hosts:
            argv.extend(["--add-host", str(value)])
    labels = contract.get("labels")
    if isinstance(labels, dict):
        for key, value in sorted(labels.items()):
            if value is None:
                argv.extend(["--label", str(key)])
            else:
                argv.extend(["--label", f"{key}={value}"])
    mounts = contract.get("mounts")
    if not isinstance(mounts, list) or len(mounts) != 6:
        raise StopExecution("recreate mount contract count mismatch")
    for mount in mounts:
        source = mount["Source"]
        destination = mount["Destination"]
        propagation = mount.get("Propagation") or "rprivate"
        spec = (
            f"type=bind,src={source},dst={destination},"
            f"bind-propagation={propagation}"
        )
        if mount.get("RW") is not True:
            spec += ",readonly"
        argv.extend(["--mount", spec])
    argv.append(image)
    return argv


def create_manager_from_contract(
    prestate: dict[str, Any],
    *,
    image: str,
    name: str,
    pairing_value: str,
) -> dict[str, Any]:
    contract = prestate.get("manager_recreate_contract")
    if not isinstance(contract, dict):
        raise StopExecution("Manager recreate contract is missing")
    env = contract.get("env")
    if not isinstance(env, list):
        raise StopExecution("Manager recreate environment is missing")
    values = pairing_replaced_env(env, pairing_value)
    env_file = STAGE_ROOT / f".{name}.env"
    if env_file.exists():
        raise StopExecution(f"private runtime env file already exists: {name}")
    try:
        write_runtime_env_file(env_file, values)
        require_ok(
            run(
                manager_create_argv(
                    contract,
                    image=image,
                    name=name,
                    env_file=env_file,
                ),
                timeout=120,
            ),
            f"cannot create Manager container {name}",
        )
        return docker_inspect(name)
    finally:
        if env_file.exists():
            env_file.unlink()


def validate_shadow_manager(
    item: dict[str, Any],
    prestate: dict[str, Any],
    *,
    expected_image: str | set[str],
    expected_pairing: list[str],
    label: str,
) -> None:
    state = item.get("State")
    state = state if isinstance(state, dict) else {}
    config = item.get("Config")
    config = config if isinstance(config, dict) else {}
    host = item.get("HostConfig")
    host = host if isinstance(host, dict) else {}
    if state.get("Running") is True:
        raise StopExecution(f"{label} shadow unexpectedly running")
    expected_images = (
        {expected_image}
        if isinstance(expected_image, str)
        else expected_image
    )
    if item.get("Image") not in expected_images:
        raise StopExecution(f"{label} shadow image mismatch")
    if host.get("NetworkMode") != "host":
        raise StopExecution(f"{label} shadow network mode mismatch")
    if config.get("Entrypoint") != ["greenhouse-manager"]:
        raise StopExecution(f"{label} shadow entrypoint mismatch")
    if config.get("User") != "greenhouse":
        raise StopExecution(f"{label} shadow user mismatch")
    mount_count, mount_hash = manager_mount_fingerprint(item)
    if mount_count != prestate["manager_mount_count"]:
        raise StopExecution(f"{label} shadow mount count mismatch")
    if mount_hash != prestate["manager_mount_hash"]:
        raise StopExecution(f"{label} shadow mount binding mismatch")
    if gh_env_fingerprint(item) != prestate["manager_gh_env_hash"]:
        raise StopExecution(f"{label} shadow non-target GH env drift")
    if (
        all_env_fingerprint_excluding_pairing(item)
        != prestate["manager_all_env_hash"]
    ):
        raise StopExecution(f"{label} shadow non-target env drift")
    if (
        manager_runtime_security_fingerprint(item)
        != prestate["manager_runtime_security_hash"]
    ):
        raise StopExecution(f"{label} shadow runtime/security contract drift")
    if runtime_pairing_values(item) != expected_pairing:
        raise StopExecution(f"{label} shadow pairing environment mismatch")


def direct_shadow(
    prestate: dict[str, Any],
    *,
    image: str,
    container_name: str,
    pairing_value: str,
) -> dict[str, Any]:
    if run(["docker", "inspect", container_name]).returncode == 0:
        raise StopExecution(f"shadow container already exists: {container_name}")
    primary_error: Exception | None = None
    shadow: dict[str, Any] | None = None
    try:
        shadow = create_manager_from_contract(
            prestate,
            image=image,
            name=container_name,
            pairing_value=pairing_value,
        )
    except Exception as exc:
        primary_error = exc
    cleanup = run(
        ["docker", "rm", "-f", container_name],
        timeout=60,
    )
    if cleanup.returncode not in (0, 1):
        detail = cleanup.stderr.strip() or cleanup.stdout.strip()
        raise StopExecution(
            f"shadow cleanup failed for {container_name}: {detail[:800]}"
        ) from primary_error
    if run(["docker", "inspect", container_name]).returncode == 0:
        raise StopExecution(
            f"shadow container remains after cleanup: {container_name}"
        )
    if primary_error is not None:
        raise primary_error
    if shadow is None:
        raise StopExecution(f"shadow Manager result missing: {container_name}")
    return shadow


def shadow_preflight(
    prestate: dict[str, Any],
) -> dict[str, bool]:
    stale_pairing = env_values(MANAGER_ENV, PAIRING_KEY)
    if len(stale_pairing) != 1:
        raise StopExecution("shadow preflight stale pairing authority invalid")
    old_shadow = direct_shadow(
        prestate,
        image=ROLLBACK_IMAGE_TAG,
        container_name=SHADOW_OLD_NAME,
        pairing_value=stale_pairing[0],
    )
    validate_shadow_manager(
        old_shadow,
        prestate,
        expected_image=OLD_IMAGE_ID,
        expected_pairing=stale_pairing,
        label="old",
    )
    new_shadow = direct_shadow(
        prestate,
        image=NEW_IMAGE_TAG,
        container_name=SHADOW_NEW_NAME,
        pairing_value="auto",
    )
    validate_shadow_manager(
        new_shadow,
        prestate,
        expected_image=accepted_new_runtime_image_ids(),
        expected_pairing=["auto"],
        label="new",
    )
    return {
        "old_live_contract_reproduction": True,
        "new_candidate_contract": True,
    }


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


def rollback_preconditions() -> None:
    if sha256_file(SERVICE_ENV) != EXPECTED_SERVICE_ENV_SHA256:
        raise StopExecution("rollback service-identities authority drift")
    if env_without_target_hash(MANAGER_ENV) != EXPECTED_MANAGER_ENV_EXCLUDING_PAIRING_SHA256:
        raise StopExecution("rollback manager.env non-target drift")
    manager_env_sha = sha256_file(MANAGER_ENV)
    pairing = env_values(MANAGER_ENV, PAIRING_KEY)
    known_old = (
        manager_env_sha == EXPECTED_MANAGER_ENV_SHA256
        and len(pairing) == 1
        and sha256_bytes(pairing[0].encode()) == EXPECTED_STALE_PAIRING_SHA256
    )
    known_candidate = pairing == ["auto"]
    if not known_old and not known_candidate:
        raise StopExecution("rollback manager.env state is not transaction-owned")
    current = run(["docker", "inspect", MANAGER_NAME])
    if current.returncode == 0:
        value = json.loads(current.stdout)
        if not isinstance(value, list) or len(value) != 1:
            raise StopExecution("rollback current Manager inspect shape invalid")
        image_id = value[0].get("Image")
        if (
            image_id != OLD_IMAGE_ID
            and image_id not in accepted_new_runtime_image_ids()
        ):
            raise StopExecution(
                "rollback current Manager image is not transaction-owned"
            )


def rollback(prestate: dict[str, Any]) -> dict[str, Any]:
    rollback_preconditions()
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
    stale_pairing = env_values(MANAGER_ENV, PAIRING_KEY)
    if len(stale_pairing) != 1:
        raise StopExecution("rollback pairing env count mismatch before create")
    create_manager_from_contract(
        prestate,
        image=ROLLBACK_IMAGE_TAG,
        name=MANAGER_NAME,
        pairing_value=stale_pairing[0],
    )
    require_ok(
        run(["docker", "start", MANAGER_NAME], timeout=60),
        "cannot start rollback Manager",
    )
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
        all_env_fingerprint_excluding_pairing(manager)
        != prestate["manager_all_env_hash"]
    ):
        raise StopExecution("rollback Manager non-target env drift")
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


def postcheck(
    prestate: dict[str, Any],
) -> dict[str, Any]:
    manager = docker_inspect(MANAGER_NAME)
    state = manager.get("State")
    state = state if isinstance(state, dict) else {}
    config = manager.get("Config")
    config = config if isinstance(config, dict) else {}
    host = manager.get("HostConfig")
    host = host if isinstance(host, dict) else {}
    if state.get("Running") is not True:
        raise StopExecution("new Manager is not running")
    observed_image = manager.get("Image")
    if observed_image not in accepted_new_runtime_image_ids():
        raise StopExecution("new Manager runtime image mismatch")
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
        all_env_fingerprint_excluding_pairing(manager)
        != prestate["manager_all_env_hash"]
    ):
        raise StopExecution("new Manager non-target env drift")
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
        "manager_runtime_image_id": observed_image,
        "manager_pairing_auto": True,
        "manager_mounts_preserved": True,
        "manager_health": "PASS",
        "broker_preserved": True,
        "r5_preserved": True,
    }


LEGACY_PRESTATE_KEYS = {
    "manager_started_at",
    "manager_restart_count",
    "manager_image_id",
    "manager_mount_count",
    "manager_mount_hash",
    "manager_gh_env_hash",
    "manager_runtime_security_hash",
    "broker_id",
    "broker_restart_count",
    "firewall",
}


def cleanup_known_pretransaction_residual() -> str:
    for name in (SHADOW_OLD_NAME, SHADOW_NEW_NAME):
        if run(["docker", "inspect", name]).returncode == 0:
            raise StopExecution(
                f"unexpected residual shadow container: {name}"
            )
    for path in (
        OVERLAY,
        ROLLBACK_OVERLAY,
        SHADOW_NEW_OVERLAY,
    ):
        if path.exists():
            raise StopExecution(
                f"unexpected transaction overlay: {path.name}"
            )
    if not SHADOW_OLD_OVERLAY.exists():
        return "none"
    if (
        sha256_file(SHADOW_OLD_OVERLAY)
        != STALE_SHADOW_OLD_OVERLAY_SHA256
    ):
        raise StopExecution(
            "stale shadow-old overlay does not match known failed attempt"
        )
    SHADOW_OLD_OVERLAY.unlink()
    return "known_failed_shadow_old_overlay_removed"


def prepare_transaction_snapshot(
    prestate: dict[str, Any],
) -> dict[str, Any]:
    residual = cleanup_known_pretransaction_residual()
    if not ROLLBACK_ROOT.exists():
        ROLLBACK_ROOT.mkdir(mode=0o700)
        shutil.copy2(MANAGER_ENV, MANAGER_ENV_BACKUP)
        os.chmod(MANAGER_ENV_BACKUP, 0o600)
        if sha256_file(MANAGER_ENV_BACKUP) != EXPECTED_MANAGER_ENV_SHA256:
            raise StopExecution("manager.env snapshot mismatch")
        write_private_json(PRESTATE_JSON, prestate)
        return {
            "snapshot": "created",
            "residual_cleanup": residual,
        }

    if ROLLBACK_ROOT.stat().st_mode & 0o777 != 0o700:
        raise StopExecution("existing rollback root mode mismatch")
    if ROLLBACK_ROOT.stat().st_uid != 0:
        raise StopExecution("existing rollback root owner mismatch")
    children = {path.name for path in ROLLBACK_ROOT.iterdir()}
    if children != {"manager.env.before", "manager-prestate.json"}:
        raise StopExecution("existing rollback snapshot shape is not pretransaction")
    if not MANAGER_ENV_BACKUP.is_file() or not PRESTATE_JSON.is_file():
        raise StopExecution("existing rollback snapshot is incomplete")
    if sha256_file(MANAGER_ENV_BACKUP) != EXPECTED_MANAGER_ENV_SHA256:
        raise StopExecution("existing manager.env backup mismatch")
    try:
        saved = json.loads(PRESTATE_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        raise StopExecution("existing prestate JSON is invalid") from exc
    if not isinstance(saved, dict):
        raise StopExecution("existing prestate JSON shape is invalid")

    if saved == prestate:
        return {
            "snapshot": "reused_verified_pretransaction",
            "residual_cleanup": residual,
        }

    if set(saved) == LEGACY_PRESTATE_KEYS:
        projection = {
            key: prestate.get(key)
            for key in LEGACY_PRESTATE_KEYS
        }
        if saved != projection:
            raise StopExecution(
                "legacy pretransaction snapshot no longer matches live prestate"
            )
        write_private_json(PRESTATE_JSON, prestate)
        return {
            "snapshot": "upgraded_verified_pretransaction",
            "residual_cleanup": residual,
        }

    raise StopExecution(
        "existing pretransaction snapshot no longer matches live prestate"
    )


def apply() -> dict[str, Any]:
    artifact = verify_stage_artifact()
    prestate = base_preflight()
    snapshot = prepare_transaction_snapshot(prestate)
    mutation_started = False
    try:
        loaded = ensure_loaded_exact_image()
        require_ok(
            run(["docker", "tag", OLD_IMAGE_ID, ROLLBACK_IMAGE_TAG]),
            "cannot bind rollback image tag",
        )
        shadow = shadow_preflight(prestate)
        mutation_started = True
        rewrite_pairing_env_to_auto(MANAGER_ENV)
        if env_values(MANAGER_ENV, PAIRING_KEY) != ["auto"]:
            raise StopExecution("manager.env auto rewrite failed")
        if env_without_target_hash(MANAGER_ENV) != EXPECTED_MANAGER_ENV_EXCLUDING_PAIRING_SHA256:
            raise StopExecution("manager.env non-target drift after rewrite")
        require_ok(
            run(["docker", "stop", "-t", "20", MANAGER_NAME], timeout=40),
            "cannot stop old Manager",
        )
        require_ok(
            run(["docker", "rm", MANAGER_NAME]),
            "cannot remove old Manager",
        )
        create_manager_from_contract(
            prestate,
            image=NEW_IMAGE_TAG,
            name=MANAGER_NAME,
            pairing_value="auto",
        )
        require_ok(
            run(["docker", "start", MANAGER_NAME], timeout=60),
            "cannot start new Manager",
        )
        post = postcheck(prestate)
        return {
            "result": "PASS",
            "artifact": artifact,
            "loaded_image": loaded,
            "transaction_snapshot": snapshot,
            "shadow_preflight": shadow,
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
        return {
            "result": status,
            "failure": f"{type(exc).__name__}:{exc}",
            "rollback": rollback_result,
            "rollback_error": rollback_error,
        }


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
                "manager_all_env_hash",
                "manager_runtime_security_hash",
                "manager_recreate_contract",
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
