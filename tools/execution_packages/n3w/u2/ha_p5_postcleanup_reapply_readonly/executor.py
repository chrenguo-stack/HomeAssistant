#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from n3w_t1_ssh_transport import SSHTransport

SCHEMA = "gh.n3w-t1-core-updater-ha-p5-postcleanup-reapply-readonly/1"
GATE_ID = "N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_POSTCLEANUP_REAPPLY_READONLY_20261106_01"
CONFIRMATION = "READONLY HA P5 POSTCLEANUP REAPPLY PREFLIGHT: YES"

PROJECT = "n3wfc4"
PREDECESSOR_IMAGE = "local/n3w-homeassistant:2026.10.0-0c73235a"
TARGET_IMAGE = "local/n3w-homeassistant:2026.10.4-5881590f"
MANAGER_IMAGE = "local/greenhouse-manager:fresh-5b32e1ae8210"
BROKER_IMAGE = "local/n3w-mosquitto:2.1.2-3184566d"
PREDECESSOR_IMAGE_ID = "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306"
TARGET_IMAGE_ID = "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365"
TARGET_CONFIG_SEMANTICS_SHA256 = "2ceae2ee88683a423315a3faf81cd14af36d8542cd5d948e1747479d4ec749bd"
TARGET_ROOTFS_DIFF_IDS_SHA256 = "971b2515c2e33e9b661f40f87494519dd5d4db945a35384709c694ecc93f60c9"
TARGET_MANIFEST_BLOB = "6966b4fe4d7620ccc436643cc840da9ae95e6010"
CLEANUP_CLOSURE_BLOB = "8ff2bdcd7a321789a13f24111fd20d75faa94a2f"

COMPOSE = "/etc/n3wfc4/docker-compose.yml"
COMPOSE_ENV = "/etc/n3wfc4/docker-compose.env"
SERVICES_UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"
REQUIRED_UNITS = (
    "n3wfc4-provision-resume.service",
    "n3wfc4-broker-ingress-guard.service",
    "n3wfc4-registration-ingress-guard.service",
    BROKER_UNIT,
    SERVICES_UNIT,
    "n3wfc4-broker-certificate-lifecycle.timer",
)
CERT_SERVICE = "n3wfc4-broker-certificate-lifecycle.service"
SHA40 = re.compile(r"^[0-9a-f]{40}$")

class StopExecution(RuntimeError):
    pass

def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def git_text(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode:
        raise StopExecution("git_command_failed")
    return result.stdout.strip()

def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution("json_invalid") from error
    if not isinstance(value, dict):
        raise StopExecution("json_shape_invalid")
    return value

def validate_source(expected_head: str) -> dict[str, str]:
    if SHA40.fullmatch(expected_head) is None:
        raise StopExecution("expected_source_head_invalid")
    if git_text("rev-parse", "HEAD") != expected_head:
        raise StopExecution("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise StopExecution("tracked_worktree_dirty")
    manifest = read_json(MANIFEST_PATH)
    if manifest.get("schema") != "gh.n3w-t1-core-updater-ha-p5-postcleanup-reapply-readonly-package/1":
        raise StopExecution("manifest_schema_invalid")
    if manifest.get("gate_id") != GATE_ID:
        raise StopExecution("manifest_gate_invalid")
    for key in ("t1_mutation", "service_restart", "container_delete", "image_load", "board_access"):
        if manifest.get(key) is not False:
            raise StopExecution("manifest_readonly_invalid")
    bindings = manifest.get("source_binding")
    if not isinstance(bindings, dict):
        raise StopExecution("manifest_source_binding_invalid")
    for relative, expected_blob in bindings.items():
        if git_text("rev-parse", f"{expected_head}:{relative}") != expected_blob:
            raise StopExecution(f"source_blob_mismatch:{Path(relative).name}")
    if bindings.get("infra/n3w-t1/upgrades/homeassistant-2026.10.4.json") != TARGET_MANIFEST_BLOB:
        raise StopExecution("target_manifest_blob_drift")
    if bindings.get("docs/development/N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_ATTEMPT03_RESIDUE_CLEANUP_CLOSURE_20261105.md") != CLEANUP_CLOSURE_BLOB:
        raise StopExecution("cleanup_closure_blob_drift")
    return {"exact_source_head": expected_head, "target_manifest_blob_sha": TARGET_MANIFEST_BLOB}

def prepare_evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    repo = REPO_ROOT.resolve()
    if root == repo or repo in root.parents:
        raise StopExecution("evidence_root_inside_repository")
    if root.exists():
        if root.is_symlink() or not root.is_dir() or root.stat().st_uid != os.geteuid() or stat.S_IMODE(root.stat().st_mode) != 0o700 or any(root.iterdir()):
            raise StopExecution("evidence_root_invalid")
    else:
        root.mkdir(parents=True, mode=0o700)
        os.chmod(root, 0o700)
    return root

def write_private(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, sort_keys=True, indent=2) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.write(fd, payload.encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(path, 0o600)

def run_text(transport: SSHTransport, argv: list[str], timeout: int = 60, check: bool = True) -> str:
    return transport.run_remote(argv, timeout=timeout, check=check).stdout

def parse_json_text(raw: str, reason: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise StopExecution(reason) from error

def container_ids(transport: SSHTransport, service: str) -> list[str]:
    raw = run_text(transport, [
        "docker", "ps", "-aq", "--no-trunc",
        "--filter", f"label=com.docker.compose.project={PROJECT}",
        "--filter", f"label=com.docker.compose.service={service}",
    ])
    return [line.strip() for line in raw.splitlines() if line.strip()]

def inspect_container(transport: SSHTransport, container_id: str) -> dict[str, Any]:
    value = parse_json_text(run_text(transport, ["docker", "inspect", container_id]), "container_inspect_invalid")
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise StopExecution("container_inspect_shape_invalid")
    return value[0]

def inspect_image(transport: SSHTransport, reference: str) -> dict[str, Any]:
    value = parse_json_text(run_text(transport, ["docker", "image", "inspect", reference]), "image_inspect_invalid")
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise StopExecution("image_inspect_shape_invalid")
    return value[0]

def runtime(transport: SSHTransport, service: str, expected_image: str) -> dict[str, Any]:
    ids = container_ids(transport, service)
    if len(ids) != 1:
        raise StopExecution(f"{service}_container_count_invalid")
    item = inspect_container(transport, ids[0])
    state = item.get("State") or {}
    config = item.get("Config") or {}
    host = item.get("HostConfig") or {}
    labels = config.get("Labels") or {}
    if (
        state.get("Running") is not True
        or state.get("Status") != "running"
        or labels.get("com.docker.compose.project") != PROJECT
        or labels.get("com.docker.compose.service") != service
        or config.get("Image") != expected_image
    ):
        raise StopExecution(f"{service}_runtime_invalid")
    return {
        "container_id": item.get("Id"),
        "image_ref": config.get("Image"),
        "image_id": item.get("Image"),
        "started_at": state.get("StartedAt"),
        "network_mode": host.get("NetworkMode"),
        "restart_count": item.get("RestartCount"),
    }

def listener_count(transport: SSHTransport, protocol: str, port: int) -> int:
    flag = "-ltn" if protocol == "tcp" else "-lun"
    raw = run_text(transport, ["ss", "-H", flag, "sport", "=", f":{port}"])
    return len([line for line in raw.splitlines() if line.strip()])

def mqtt_identity(transport: SSHTransport, service: str) -> tuple[str, str]:
    if service == "manager":
        raw = run_text(transport, ["cat", "/opt/greenhouse-secrets/mqtt/manager/runtime.env"])
        values: dict[str, str] = {}
        for line in raw.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key in {"GH_MQTT_CLIENT_ID", "GH_MQTT_USERNAME"}:
                values[key] = value
        client_id = values.get("GH_MQTT_CLIENT_ID")
        username = values.get("GH_MQTT_USERNAME")
    else:
        value = parse_json_text(
            run_text(transport, ["cat", "/opt/greenhouse-secrets/mqtt/homeassistant/mqtt-bootstrap.json"]),
            "homeassistant_mqtt_identity_invalid",
        )
        client_id = value.get("client_id") if isinstance(value, dict) else None
        username = value.get("username") if isinstance(value, dict) else None
    if not all(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]+", value) for value in (client_id, username)):
        raise StopExecution(f"{service}_mqtt_identity_invalid")
    return client_id, username

def mqtt_authenticated(transport: SSHTransport, broker: dict[str, Any], service: str) -> bool:
    client_id, username = mqtt_identity(transport, service)
    raw = run_text(
        transport,
        ["docker", "logs", "--timestamps", "--since", str(broker["started_at"]), "--tail", "10000", str(broker["container_id"])],
        timeout=30,
    )
    lines = raw.splitlines()
    if len(lines) >= 10000:
        raise StopExecution("broker_log_coverage_insufficient")
    connected = re.compile(
        r"New client connected from .+ as " + re.escape(client_id)
        + r" \(p5, c[01], k[0-9]+, u'" + re.escape(username) + r"'\)\."
    )
    any_connection = re.compile(r"New client connected from .+ as " + re.escape(client_id) + r" \(")
    terminal = re.compile(
        r"(?:Client|client) " + re.escape(client_id)
        + r"(?: \[[^\]\r\n]+\] disconnected(?:\.|:)| disconnected\b| closed its connection\b| already connected, closing old connection\b| has exceeded timeout, disconnecting\b)"
    )
    current = False
    for line in lines:
        if any_connection.search(line):
            if connected.search(line) is None:
                raise StopExecution(f"{service}_mqtt_authenticated_identity_mismatch")
            current = True
        elif terminal.search(line):
            current = False
    return current

CONFIG_FIELDS = (
    "Entrypoint", "Cmd", "User", "Env", "WorkingDir", "Labels",
    "Healthcheck", "StopSignal", "Volumes", "ExposedPorts",
)

def normalized_config(config: Any) -> dict[str, Any]:
    raw = config if isinstance(config, dict) else {}
    result: dict[str, Any] = {}
    for field in CONFIG_FIELDS:
        observed = raw.get(field)
        if field in {"Entrypoint", "Cmd", "Env"} and observed is None:
            observed = []
        elif field in {"User", "WorkingDir", "StopSignal"} and observed is None:
            observed = ""
        elif field in {"Labels", "Healthcheck", "Volumes", "ExposedPorts"} and observed is None:
            observed = {}
        result[field] = observed
    return result

def target_fingerprint(document: dict[str, Any]) -> dict[str, str]:
    config = document.get("Config")
    rootfs = document.get("RootFS")
    layers = rootfs.get("Layers") if isinstance(rootfs, dict) else None
    if not isinstance(config, dict) or not isinstance(layers, list) or not layers:
        raise StopExecution("target_image_inspect_invalid")
    return {
        "image_id": str(document.get("Id")),
        "os": str(document.get("Os")),
        "architecture": str(document.get("Architecture")),
        "config_semantics_sha256": sha256_bytes(canonical(normalized_config(config))),
        "rootfs_diff_ids_sha256": sha256_bytes(canonical(layers)),
    }

def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise StopExecution("readonly_confirmation_invalid")
    source = validate_source(args.expected_source_head)
    evidence = prepare_evidence_root(args.evidence_root)
    transport = SSHTransport(
        target=args.target,
        known_hosts=args.known_hosts,
        expected_host_key_sha256=args.expected_host_key_sha256,
    )
    started = False
    try:
        transport.start_epoch()
        started = True

        system_state = run_text(transport, ["systemctl", "is-system-running"], timeout=15, check=False).strip()
        if system_state not in {"running", "degraded"}:
            raise StopExecution("system_state_not_acceptable")
        for unit in REQUIRED_UNITS:
            if run_text(transport, ["systemctl", "is-active", unit], check=False).strip() != "active":
                raise StopExecution(f"unit_active_invalid:{unit}")
            if run_text(transport, ["systemctl", "is-enabled", unit], check=False).strip() != "enabled":
                raise StopExecution(f"unit_enabled_invalid:{unit}")
        if run_text(transport, ["systemctl", "is-active", CERT_SERVICE], check=False).strip() != "inactive":
            raise StopExecution("certificate_service_not_quiescent")

        broker = runtime(transport, "broker", BROKER_IMAGE)
        manager = runtime(transport, "manager", MANAGER_IMAGE)
        homeassistant = runtime(transport, "homeassistant", PREDECESSOR_IMAGE)
        if homeassistant["image_id"] != PREDECESSOR_IMAGE_ID:
            raise StopExecution("predecessor_image_id_drift")
        if manager["network_mode"] != "host" or homeassistant["network_mode"] != "host":
            raise StopExecution("runtime_network_contract_drift")

        compose = parse_json_text(
            run_text(transport, [
                "docker", "compose", "--project-name", PROJECT,
                "--env-file", COMPOSE_ENV, "-f", COMPOSE,
                "--profile", "application", "config", "--format", "json",
            ], timeout=120),
            "compose_render_invalid",
        )
        services = compose.get("services") if isinstance(compose, dict) else None
        if not isinstance(services, dict):
            raise StopExecution("compose_services_invalid")
        expected_images = {"broker": BROKER_IMAGE, "manager": MANAGER_IMAGE, "homeassistant": PREDECESSOR_IMAGE}
        for service, image in expected_images.items():
            value = services.get(service)
            if not isinstance(value, dict) or value.get("image") != image:
                raise StopExecution(f"{service}_compose_binding_invalid")

        listeners = {
            "tcp_8883": listener_count(transport, "tcp", 8883),
            "tcp_47110": listener_count(transport, "tcp", 47110),
            "udp_47111": listener_count(transport, "udp", 47111),
            "tcp_47112": listener_count(transport, "tcp", 47112),
        }
        if listeners != {"tcp_8883": 1, "tcp_47110": 1, "udp_47111": 1, "tcp_47112": 0}:
            raise StopExecution("listener_contract_drift")

        if not mqtt_authenticated(transport, broker, "manager"):
            raise StopExecution("manager_mqtt_authentication_missing")
        if not mqtt_authenticated(transport, broker, "homeassistant"):
            raise StopExecution("homeassistant_mqtt_authentication_missing")

        http_status = run_text(
            transport,
            ["python3", "-c", "import http.client;c=http.client.HTTPConnection('127.0.0.1',8123,timeout=5);c.request('GET','/api/');r=c.getresponse();print(r.status);r.read(1024);c.close()"],
            timeout=15,
        ).strip()
        if http_status not in {"200", "401"}:
            raise StopExecution("homeassistant_http_not_ready")

        target = inspect_image(transport, TARGET_IMAGE)
        fingerprint = target_fingerprint(target)
        if fingerprint != {
            "image_id": TARGET_IMAGE_ID,
            "os": "linux",
            "architecture": "arm64",
            "config_semantics_sha256": TARGET_CONFIG_SEMANTICS_SHA256,
            "rootfs_diff_ids_sha256": TARGET_ROOTFS_DIFF_IDS_SHA256,
        }:
            raise StopExecution("target_portable_fingerprint_mismatch")

        private = {
            "system_state": system_state,
            "runtime": {"broker": broker, "manager": manager, "homeassistant": homeassistant},
            "listeners": listeners,
            "mqtt_authenticated": {"manager": True, "homeassistant": True},
            "homeassistant_http_status": int(http_status),
            "target_fingerprint": fingerprint,
        }
        write_private(evidence / "preflight-private.json", private)

        public = {
            "schema": SCHEMA,
            "gate_id": GATE_ID,
            "status": "PASS",
            "operation": "readonly_postcleanup_reapply_preflight",
            "mutation": False,
            "source_authority": source,
            "classification": "POSTCLEANUP_REAPPLY_PREFLIGHT_PASS",
            "production_runtime_healthy": True,
            "homeassistant_residue_count": 0,
            "running_predecessor_image_ref": PREDECESSOR_IMAGE,
            "target_image_ref": TARGET_IMAGE,
            "target_image_prestate": "PRESENT_AND_EXACT",
            "target_image_id": TARGET_IMAGE_ID,
            "target_config_semantics_sha256": TARGET_CONFIG_SEMANTICS_SHA256,
            "target_rootfs_diff_ids_sha256": TARGET_ROOTFS_DIFF_IDS_SHA256,
            "reapply_candidate": True,
            "board_access": False,
        }
        write_private(evidence / "result.json", public)
        return public
    finally:
        if started:
            transport.close_epoch()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-source-head", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--expected-host-key-sha256", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"schema": SCHEMA, "status": "STOP", "reason": "execute_flag_required"}, sort_keys=True))
        return 2
    try:
        result = execute(args)
    except Exception as error:
        reason = str(error)
        if not reason or len(reason) > 200 or "/" in reason or "\\" in reason or "@" in reason:
            reason = type(error).__name__
        print(json.dumps({"schema": SCHEMA, "status": "STOP", "reason": reason, "mutation": False}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
