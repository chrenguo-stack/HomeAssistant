#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence

SCHEMA = "gh.n3w-t1-fresh-product-bootstrap/1"
PAYLOAD_SCHEMA = "gh.n3w-t1-fresh-bootstrap-payload/1"
AUTHORIZATION_ID = "N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_04"
CLAIM_MARKER_NAME = ".authorization-claimed"
DEFAULT_NETWORKS = frozenset(("bridge", "host", "none"))
PRODUCT_NETWORKS = ("n3wfc4-private", "n3wfc4-services")
TARGET_PORTS = frozenset((1883, 8883, 18883, 8123, 47110, 47111, 47112))
MIN_ROOT_FREE_BYTES = 5 * 1024 * 1024 * 1024
MANAGER_UID = 999
MANAGER_GID = 999
BROKER_UID = 1883
BROKER_GID = 1883
PRODUCT_UNITS = (
    "n3wfc4-broker-ingress-guard.service",
    "n3wfc4-broker-activation.service",
    "n3wfc4-services-activation.service",
    "n3wfc4-broker-certificate-lifecycle.service",
    "n3wfc4-broker-certificate-lifecycle.timer",
)

FINAL_DIRS = {
    "/var/lib/greenhouse-manager": "stage/var-lib-greenhouse-manager",
    "/var/lib/n3wfc4-broker": "stage/var-lib-n3wfc4-broker",
    "/var/lib/n3wfc4-homeassistant": "stage/var-lib-n3wfc4-homeassistant",
    "/opt/greenhouse-secrets": "stage/opt-greenhouse-secrets",
    "/opt/HomeAssistant": "stage/opt-HomeAssistant",
    "/etc/n3wfc4": "stage/etc-n3wfc4",
}
FINAL_FILES = {
    "/usr/local/sbin/n3w-broker-ingress-guard": "stage/n3w-broker-ingress-guard",
    "/etc/systemd/system/n3wfc4-broker-ingress-guard.service": "stage/n3wfc4-broker-ingress-guard.service",
}
EXTRA_ABSENT = (
    "/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard",
    "/usr/local/sbin/n3w-t1-broker-authenticated-readiness",
    "/usr/local/sbin/n3w-broker-certificate-lifecycle",
    "/etc/systemd/system/n3wfc4-broker-activation.service",
    "/etc/systemd/system/n3wfc4-services-activation.service",
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service",
    "/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer",
)


class BootstrapError(RuntimeError):
    pass


class Runner:
    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float = 120.0,
        allowed: frozenset[int] = frozenset({0}),
        input_text: str | None = None,
    ) -> str:
        completed = subprocess.run(
            tuple(argv),
            input=input_text,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if completed.returncode not in allowed:
            reason = completed.stderr.strip() or completed.stdout.strip()
            raise BootstrapError(
                f"command_failed:{Path(argv[0]).name}:{completed.returncode}:{reason[:400]}"
            )
        return completed.stdout


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalized_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / "payload-manifest.json"
    if not path.is_file() or path.is_symlink():
        raise BootstrapError("payload_manifest_missing")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BootstrapError("payload_manifest_invalid") from error
    if not isinstance(document, dict) or document.get("schema") != PAYLOAD_SCHEMA:
        raise BootstrapError("payload_manifest_schema_invalid")
    if document.get("authorization_id") != AUTHORIZATION_ID:
        raise BootstrapError("payload_authorization_invalid")
    source_head = document.get("source_head")
    if not isinstance(source_head, str) or re.fullmatch(r"[0-9a-f]{40}", source_head) is None:
        raise BootstrapError("payload_source_head_invalid")
    records = document.get("files")
    if not isinstance(records, list):
        raise BootstrapError("payload_file_inventory_invalid")
    expected: dict[str, tuple[str, int]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise BootstrapError("payload_file_inventory_invalid")
        relative = record.get("path")
        digest = record.get("sha256")
        size = record.get("size")
        if (
            not isinstance(relative, str)
            or not relative
            or relative.startswith("/")
            or ".." in Path(relative).parts
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
        ):
            raise BootstrapError("payload_file_record_invalid")
        expected[relative] = (digest, size)
    actual = {
        item.relative_to(root).as_posix(): item
        for item in root.rglob("*")
        if item.is_file() and item.name != "payload-manifest.json"
    }
    if set(actual) != set(expected):
        raise BootstrapError("payload_file_set_invalid")
    for relative, item in actual.items():
        digest, size = expected[relative]
        if item.is_symlink() or item.stat().st_size != size or _sha256_file(item) != digest:
            raise BootstrapError(f"payload_file_binding_invalid:{relative}")
    images = document.get("images")
    if not isinstance(images, dict) or set(images) != {"manager", "homeassistant", "broker"}:
        raise BootstrapError("payload_image_inventory_invalid")
    for label, record in images.items():
        if not isinstance(record, dict):
            raise BootstrapError(f"payload_image_record_invalid:{label}")
        if (
            not isinstance(record.get("image"), str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", str(record.get("image_id"))) is None
            or record.get("platform") != "linux/arm64"
            or re.fullmatch(
                r"[0-9a-f]{64}",
                str(record.get("rootfs_layers_sha256")),
            )
            is None
            or not isinstance(record.get("path"), str)
            or re.fullmatch(r"[0-9a-f]{64}", str(record.get("tar_sha256"))) is None
        ):
            raise BootstrapError(f"payload_image_record_invalid:{label}")
        image_path = root / str(record["path"])
        if (
            not image_path.is_file()
            or image_path.is_symlink()
            or _sha256_file(image_path) != record["tar_sha256"]
        ):
            raise BootstrapError(f"payload_image_tar_binding_invalid:{label}")
    lock = document.get("image_lock")
    if not isinstance(lock, dict) or lock.get("schema") != "gh.n3w-t1-fresh-production-image-lock/1":
        raise BootstrapError("payload_image_lock_invalid")
    return document


def _systemctl(runner: Runner, operation: str, unit: str) -> str:
    return runner.run(
        ("systemctl", operation, unit),
        allowed=frozenset({0, 1, 3, 4}),
    ).strip()


def _listeners(runner: Runner) -> int:
    output = runner.run(("ss", "-H", "-lntu"))
    count = 0
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        try:
            port = int(fields[4].rsplit(":", 1)[1].rstrip("]"))
        except (IndexError, ValueError):
            continue
        if port in TARGET_PORTS:
            count += 1
    return count


def _unit_load_state(runner: Runner, unit: str) -> str:
    return runner.run(
        ("systemctl", "show", "-p", "LoadState", "--value", unit),
        allowed=frozenset({0, 1}),
    ).strip()


def _preflight(runner: Runner) -> dict[str, object]:
    architecture = runner.run(("uname", "-m")).strip()
    docker_active = _systemctl(runner, "is-active", "docker")
    ssh_active = _systemctl(runner, "is-active", "ssh")
    nm_active = _systemctl(runner, "is-active", "NetworkManager")
    compose = runner.run(("docker", "compose", "version", "--short")).strip()
    route = runner.run(("ip", "-4", "route", "show", "default")).strip()
    dns = runner.run(
        ("sh", "-c", "grep -Ev '^[[:space:]]*(#|$)' /etc/resolv.conf | head -n 8")
    ).strip()
    ntp = runner.run(
        ("timedatectl", "show", "-p", "NTPSynchronized", "--value")
    ).strip()
    containers = tuple(
        value
        for value in runner.run(("docker", "ps", "-aq")).splitlines()
        if value
    )
    images = tuple(
        value
        for value in runner.run(("docker", "image", "ls", "-q")).splitlines()
        if value
    )
    volumes = tuple(
        value
        for value in runner.run(("docker", "volume", "ls", "-q")).splitlines()
        if value
    )
    networks = frozenset(
        value
        for value in runner.run(
            ("docker", "network", "ls", "--format", "{{.Name}}")
        ).splitlines()
        if value
    )
    product_paths = tuple(
        path
        for path in (*FINAL_DIRS.keys(), *FINAL_FILES.keys(), *EXTRA_ABSENT)
        if Path(path).exists() or Path(path).is_symlink()
    )
    product_units_absent = all(
        _unit_load_state(runner, unit) in {"", "not-found"}
        for unit in PRODUCT_UNITS
    )
    firewall = runner.run(("iptables-save", "-t", "filter"))
    firewall_clean = (
        "N3WFC4-BROKER-INGRESS" not in firewall
        and "n3wfc4-broker-ingress-v1" not in firewall
        and ":DOCKER-USER " in firewall
        and "-A FORWARD -j DOCKER-USER" in firewall
    )
    staging_device = os.stat("/var/tmp").st_dev
    target_parents = {
        Path(path).parent
        for path in (*FINAL_DIRS.keys(), *FINAL_FILES.keys())
    }
    same_filesystem_commit = all(
        parent.is_dir() and os.stat(parent).st_dev == staging_device
        for parent in target_parents
    )
    result = {
        "status": "PASS",
        "arch": architecture,
        "docker_ready": docker_active == "active",
        "compose_ready": bool(compose),
        "network_ready": nm_active == "active" and bool(dns),
        "default_route": bool(route),
        "time_sync": ntp == "yes",
        "root_capacity": shutil.disk_usage("/").free >= MIN_ROOT_FREE_BYTES,
        "product_containers": len(containers),
        "product_images": len(set(images)),
        "product_volumes": len(volumes),
        "product_networks": len(networks - DEFAULT_NETWORKS),
        "product_listeners": _listeners(runner),
        "product_paths_absent": not product_paths,
        "product_units_absent": product_units_absent,
        "product_dispatcher_absent": not Path(EXTRA_ABSENT[0]).exists(),
        "product_firewall_absent": firewall_clean,
        "production_service_start": False,
        "ssh_preserved": ssh_active == "active",
        "default_networks_exact": networks == DEFAULT_NETWORKS,
        "same_filesystem_commit": same_filesystem_commit,
    }
    required = (
        result["arch"] == "aarch64"
        and result["docker_ready"] is True
        and result["compose_ready"] is True
        and result["network_ready"] is True
        and result["default_route"] is True
        and result["time_sync"] is True
        and result["root_capacity"] is True
        and result["product_containers"] == 0
        and result["product_images"] == 0
        and result["product_volumes"] == 0
        and result["product_networks"] == 0
        and result["product_listeners"] == 0
        and result["product_paths_absent"] is True
        and result["product_units_absent"] is True
        and result["product_dispatcher_absent"] is True
        and result["product_firewall_absent"] is True
        and result["ssh_preserved"] is True
        and result["default_networks_exact"] is True
        and result["same_filesystem_commit"] is True
    )
    if not required:
        raise BootstrapError("minimal_host_preflight_drift")
    return result

def _load_contract(payload_root: Path):
    path = payload_root / "contract/fresh_installer.py"
    spec = importlib.util.spec_from_file_location("n3w_fresh_installer_contract", path)
    if spec is None or spec.loader is None:
        raise BootstrapError("fresh_installer_contract_invalid")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _inspect_runtime_image(
    runner: Runner,
    image: str,
    label: str,
) -> dict[str, Any]:
    raw = runner.run(("docker", "image", "inspect", image))
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise BootstrapError(f"image_inspect_invalid:{label}") from error
    if (
        not isinstance(value, list)
        or len(value) != 1
        or not isinstance(value[0], dict)
    ):
        raise BootstrapError(f"image_inspect_invalid:{label}")
    return value[0]


def _verify_runtime_image(
    runner: Runner,
    label: str,
    record: dict[str, Any],
) -> dict[str, str]:
    image = str(record["image"])
    item = _inspect_runtime_image(runner, image, label)
    runtime_id = item.get("Id")
    if (
        not isinstance(runtime_id, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", runtime_id) is None
    ):
        raise BootstrapError(f"image_runtime_id_invalid:{label}")
    if item.get("Architecture") != "arm64" or item.get("Os") != "linux":
        raise BootstrapError(f"image_platform_invalid:{label}")
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
        raise BootstrapError(f"image_rootfs_invalid:{label}")
    rootfs_hash = _normalized_hash(layers)
    if rootfs_hash != record["rootfs_layers_sha256"]:
        raise BootstrapError(f"image_rootfs_binding_invalid:{label}")
    return {
        "runtime_id": runtime_id,
        "rootfs_layers_sha256": rootfs_hash,
    }


class LiveFreshInstallerAdapters:
    def __init__(
        self,
        payload_root: Path,
        manifest: dict[str, Any],
        runner: Runner,
    ) -> None:
        self.payload_root = payload_root
        self.manifest = manifest
        self.runner = runner
        self.created_images: list[str] = []
        self.created_networks: list[str] = []
        self.created_paths: list[Path] = []
        self.candidate_containers: list[str] = []
        self.loaded_image_bindings: dict[str, dict[str, str]] = {}

    @property
    def manager_image(self) -> str:
        return str(self.manifest["images"]["manager"]["image"])

    @property
    def broker_image(self) -> str:
        return str(self.manifest["images"]["broker"]["image"])

    def preflight(self):
        return _preflight(self.runner)

    def load_images(self):
        for label in ("homeassistant", "manager", "broker"):
            record = self.manifest["images"][label]
            image = str(record["image"])
            self.created_images.append(image)
            self.runner.run(
                (
                    "docker",
                    "load",
                    "--input",
                    str(self.payload_root / str(record["path"])),
                ),
                timeout=1800,
            )
            self.loaded_image_bindings[label] = _verify_runtime_image(
                self.runner,
                label,
                record,
            )
            tar_path = self.payload_root / str(record["path"])
            tar_path.unlink()
        return {
            "status": "PASS",
            "image_count": 3,
            "offline": True,
            "registry_pull": False,
            "platform": "linux/arm64",
            "production_service_start": False,
        }

    def _manager_json(
        self,
        candidate: Path,
        source: str,
        *,
        timeout: float = 240.0,
    ) -> dict[str, Any]:
        candidate.mkdir(mode=0o700, exist_ok=True)
        name = f"n3w-fresh-manager-{secrets.token_hex(6)}"
        self.candidate_containers.append(name)
        try:
            output = self.runner.run(
                (
                    "docker",
                    "run",
                    "--rm",
                    "--name",
                    name,
                    "--network",
                    "none",
                    "--user",
                    "0:0",
                    "--mount",
                    f"type=bind,src={candidate},dst=/work",
                    "--entrypoint",
                    "python",
                    self.manager_image,
                    "-c",
                    source,
                ),
                timeout=timeout,
            ).strip()
        finally:
            self.runner.run(
                ("docker", "rm", "-f", "-v", name),
                allowed=frozenset({0, 1}),
            )
            if name in self.candidate_containers:
                self.candidate_containers.remove(name)
        try:
            value = json.loads(output)
        except (UnboundLocalError, json.JSONDecodeError) as error:
            raise BootstrapError("manager_constructor_output_invalid") from error
        if not isinstance(value, dict):
            raise BootstrapError("manager_constructor_output_invalid")
        return value

    def create_identity(self, candidate_root: Path):
        if candidate_root.exists() or candidate_root.is_symlink():
            raise BootstrapError("candidate_root_already_exists")
        candidate_root.mkdir(mode=0o700)
        return self._manager_json(
            candidate_root,
            "import json;from pathlib import Path;"
            "from greenhouse_manager.bootstrap.system_init import initialize_system,INITIALIZATION_CONFIRMATION;"
            "r=initialize_system(Path('/work/identity'),enable=True,confirmation=INITIALIZATION_CONFIRMATION);"
            "print(json.dumps(r.to_dict(),sort_keys=True))",
        )

    def create_state(self, candidate_root: Path, system_id_sha256: str):
        return self._manager_json(
            candidate_root,
            "import json;from pathlib import Path;"
            "from greenhouse_manager.bootstrap.fresh_product_state import create_fresh_state;"
            "m=Path('/work/manager');n=Path('/work/n3w');"
            "m.mkdir(mode=0o700);n.mkdir(mode=0o700);"
            f"r=create_fresh_state(m,n,expected_system_id_sha256={system_id_sha256!r});"
            "print(json.dumps(r,sort_keys=True))",
        )

    def create_broker(self, candidate_root: Path, system_id: str):
        return self._manager_json(
            candidate_root,
            "import json;from pathlib import Path;"
            "from greenhouse_manager.bootstrap.fresh_broker import create_fresh_broker_materials;"
            f"r=create_fresh_broker_materials(Path('/work/broker'),system_id={system_id!r});"
            "print(json.dumps(r.to_dict(),sort_keys=True))",
        )

    def _dynsec_request(
        self,
        container: str,
        config_path: str,
        command: dict[str, Any],
    ) -> None:
        payload = json.dumps(
            {"commands": [command]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        output = self.runner.run(
            (
                "docker",
                "exec",
                "-i",
                container,
                "mosquitto_rr",
                "-o",
                config_path,
                "-q",
                "1",
                "-W",
                "8",
                "-t",
                "$CONTROL/dynamic-security/v1",
                "-e",
                "$CONTROL/dynamic-security/v1/response",
                "-s",
            ),
            input_text=payload,
            timeout=15,
        )
        try:
            document = json.loads(output)
        except json.JSONDecodeError as error:
            raise BootstrapError("dynsec_response_invalid") from error
        responses = document.get("responses") if isinstance(document, dict) else None
        if not isinstance(responses, list) or len(responses) != 1:
            raise BootstrapError("dynsec_response_invalid")
        response = responses[0]
        if (
            not isinstance(response, dict)
            or response.get("command") != command.get("command")
            or response.get("error")
        ):
            raise BootstrapError(
                f"dynsec_command_failed:{command.get('command','unknown')}"
            )

    def initialize_dynsec(self, candidate_root: Path, system_id: str):
        broker_data = candidate_root / "broker-data"
        config = candidate_root / "dynsec-config"
        broker_data.mkdir(mode=0o700)
        config.mkdir(mode=0o700)
        admin_password = (
            candidate_root / "broker/private/dynsec-admin-password"
        ).read_text(encoding="utf-8").strip()
        if not admin_password:
            raise BootstrapError("dynsec_admin_password_missing")

        init_path = config / "dynsec-password-init"
        init_path.write_text(admin_password + "\n", encoding="utf-8")
        os.chmod(init_path, 0o600)
        config_path = config / "mosquitto.conf"
        config_path.write_text(
            "listener 1883 127.0.0.1\n"
            "allow_anonymous false\n"
            "persistence false\n"
            "global_plugin /usr/lib/mosquitto_dynamic_security.so\n"
            "plugin_opt_config_file /mosquitto/data/dynamic-security.json\n"
            "plugin_opt_password_init_file /mosquitto/config/dynsec-password-init\n"
            "log_dest stdout\n",
            encoding="utf-8",
        )
        os.chmod(config_path, 0o644)
        os.chown(config, BROKER_UID, BROKER_GID)
        os.chown(init_path, BROKER_UID, BROKER_GID)
        os.chown(config_path, BROKER_UID, BROKER_GID)
        os.chown(broker_data, BROKER_UID, BROKER_GID)

        name = f"n3w-fresh-dynsec-{secrets.token_hex(6)}"
        self.runner.run(
            (
                "docker",
                "create",
                "--network",
                "none",
                "--name",
                name,
                "--mount",
                f"type=bind,src={config},dst=/mosquitto/config",
                "--mount",
                f"type=bind,src={broker_data},dst=/mosquitto/data",
                "--tmpfs",
                "/mosquitto/log",
                self.broker_image,
            )
        )
        self.candidate_containers.append(name)
        try:
            self.runner.run(("docker", "start", name))
            dynsec = broker_data / "dynamic-security.json"
            deadline = time.monotonic() + 12.0
            while time.monotonic() < deadline and not dynsec.is_file():
                time.sleep(0.2)
            if not dynsec.is_file():
                raise BootstrapError("dynsec_init_timeout")
            init_path.unlink(missing_ok=True)

            admin_host = candidate_root / "dynsec-admin.conf"
            admin_host.write_text(
                "-h 127.0.0.1\n"
                "-u admin\n"
                f"-P {admin_password}\n"
                "-i n3w-fresh-bootstrap-admin\n"
                "-V 5\n",
                encoding="utf-8",
            )
            os.chmod(admin_host, 0o600)
            admin_container = "/tmp/n3w-fresh-admin.conf"
            self.runner.run(
                (
                    "docker",
                    "cp",
                    "--archive",
                    str(admin_host),
                    f"{name}:{admin_container}",
                )
            )

            source = """
import json
from pathlib import Path
from greenhouse_manager.bootstrap.fresh_broker import provision_fresh_service_identities

class RecordingTransport:
    def __init__(self):
        self.commands = []
    def execute(self, commands):
        self.commands.extend(dict(command) for command in commands)
        return tuple({"command": command["command"]} for command in commands)

transport = RecordingTransport()
provision_fresh_service_identities(
    transport,
    Path("/work/broker/service-credentials"),
    system_id=%r,
)
Path("/work/dynsec-commands.json").write_text(
    json.dumps({"commands": transport.commands}, separators=(",", ":")),
    encoding="utf-8",
)
print(json.dumps({"status": "PASS"}))
""" % system_id
            self._manager_json(candidate_root, source)
            command_document = json.loads(
                (candidate_root / "dynsec-commands.json").read_text(
                    encoding="utf-8"
                )
            )
            commands = (
                command_document.get("commands")
                if isinstance(command_document, dict)
                else None
            )
            if not isinstance(commands, list) or len(commands) != 7:
                raise BootstrapError("dynsec_command_set_invalid")
            for command in commands:
                if not isinstance(command, dict):
                    raise BootstrapError("dynsec_command_set_invalid")
                self._dynsec_request(name, admin_container, command)
        finally:
            self.runner.run(
                ("docker", "rm", "-f", "-v", name),
                allowed=frozenset({0, 1}),
            )
            if name in self.candidate_containers:
                self.candidate_containers.remove(name)

        dynsec = broker_data / "dynamic-security.json"
        if not dynsec.is_file() or dynsec.is_symlink():
            raise BootstrapError("dynsec_state_missing")
        os.chmod(dynsec, 0o600)
        os.chown(dynsec, BROKER_UID, BROKER_GID)
        audit = self._manager_json(
            candidate_root,
            "import json;from pathlib import Path;"
            "from greenhouse_manager.bootstrap.fresh_broker import audit_fresh_dynsec_document;"
            f"r=audit_fresh_dynsec_document(Path('/work/broker-data/dynamic-security.json'),system_id={system_id!r});"
            "print(json.dumps(r,sort_keys=True))",
        )
        return {
            **audit,
            "production_service_start": False,
        }

    @staticmethod
    def _chown_tree(path: Path, uid: int, gid: int) -> None:
        if path.is_symlink():
            raise BootstrapError("staged_symlink_forbidden")
        for child in path.rglob("*"):
            if child.is_symlink():
                raise BootstrapError("staged_symlink_forbidden")
            os.chown(child, uid, gid)
        os.chown(path, uid, gid)

    def stage_runtime(self, candidate_root: Path, system_id: str):
        stage = candidate_root / "stage"
        if stage.exists() or stage.is_symlink():
            raise BootstrapError("stage_root_already_exists")
        stage.mkdir(mode=0o700)

        manager_root = stage / "var-lib-greenhouse-manager"
        manager_root.mkdir(mode=0o700)
        for name in ("identity", "manager", "n3w"):
            shutil.copytree(candidate_root / name, manager_root / name)
        self._chown_tree(manager_root / "manager", MANAGER_UID, MANAGER_GID)
        self._chown_tree(manager_root / "n3w", MANAGER_UID, MANAGER_GID)

        broker_data = stage / "var-lib-n3wfc4-broker"
        broker_data.mkdir(mode=0o700)
        shutil.copy2(
            candidate_root / "broker-data/dynamic-security.json",
            broker_data / "dynamic-security.json",
        )
        os.chmod(broker_data / "dynamic-security.json", 0o600)
        self._chown_tree(broker_data, BROKER_UID, BROKER_GID)

        ha_root = stage / "var-lib-n3wfc4-homeassistant"
        ha_root.mkdir(mode=0o755)

        secrets_root = stage / "opt-greenhouse-secrets"
        secrets_root.mkdir(mode=0o700)
        shutil.copytree(
            candidate_root / "broker/service-credentials",
            secrets_root / "mqtt",
        )
        for service in ("manager", "provisioning"):
            self._chown_tree(
                secrets_root / f"mqtt/{service}",
                MANAGER_UID,
                MANAGER_GID,
            )
        runtime_env = secrets_root / "mqtt/manager/runtime.env"
        os.chmod(runtime_env, 0o600)

        broker_secret = secrets_root / "broker"
        broker_secret.mkdir(mode=0o700)
        shutil.copy2(
            candidate_root / "broker/private/dynsec-admin-password",
            broker_secret / "dynsec-admin-password",
        )
        os.chmod(broker_secret / "dynsec-admin-password", 0o600)

        ca_private = secrets_root / "broker-ca"
        ca_private.mkdir(mode=0o700)
        shutil.copy2(
            candidate_root / "broker/tls/ca.key",
            ca_private / "ca.key",
        )
        os.chmod(ca_private / "ca.key", 0o600)

        etc = stage / "etc-n3wfc4"
        tls = etc / "tls"
        tls.mkdir(parents=True, mode=0o755)
        compose_env = etc / "docker-compose.env"
        compose_env.write_text(
            runtime_env.read_text(encoding="utf-8")
            + f"GH_MANAGER_IMAGE={self.manager_image}\n",
            encoding="utf-8",
        )
        os.chmod(compose_env, 0o600)
        for name in ("ca.pem", "server.pem", "server.key"):
            shutil.copy2(candidate_root / f"broker/tls/{name}", tls / name)
        os.chmod(tls / "ca.pem", 0o644)
        os.chmod(tls / "server.pem", 0o644)
        os.chmod(tls / "server.key", 0o600)
        os.chown(tls / "server.key", BROKER_UID, BROKER_GID)

        source_root = self.payload_root / "runtime-source/opt/HomeAssistant"
        product_source = stage / "opt-HomeAssistant"
        shutil.copytree(source_root, product_source)
        production = product_source / "infra/n3w-t1/production"
        fresh_compose = production / "docker-compose.fresh.yml"
        canonical_compose = production / "docker-compose.yml"
        fresh_compose.replace(canonical_compose)
        (production / "image-lock.json").write_text(
            json.dumps(
                self.manifest["image_lock"],
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        guard = stage / "n3w-broker-ingress-guard"
        shutil.copy2(
            self.payload_root
            / "runtime-source/usr/local/sbin/n3w-broker-ingress-guard",
            guard,
        )
        os.chmod(guard, 0o755)
        unit = stage / "n3wfc4-broker-ingress-guard.service"
        shutil.copy2(
            self.payload_root
            / "runtime-source/etc/systemd/system/n3wfc4-broker-ingress-guard.service",
            unit,
        )
        os.chmod(unit, 0o644)

        return {
            "status": "PASS",
            "source_files_staged": True,
            "network_count": 2,
            "guard_ready": True,
            "services_stopped": True,
            "production_service_start": False,
        }

    def commit_candidate(self, candidate_root: Path, system_id: str):
        for target in (*FINAL_DIRS.keys(), *FINAL_FILES.keys()):
            path = Path(target)
            if path.exists() or path.is_symlink():
                raise BootstrapError(f"commit_target_exists:{target}")

        for target, relative in FINAL_DIRS.items():
            source = candidate_root / relative
            if not source.is_dir() or source.is_symlink():
                raise BootstrapError(f"commit_source_invalid:{relative}")
            os.rename(source, target)
            self.created_paths.append(Path(target))

        for target, relative in FINAL_FILES.items():
            source = candidate_root / relative
            if not source.is_file() or source.is_symlink():
                raise BootstrapError(f"commit_source_invalid:{relative}")
            os.rename(source, target)
            self.created_paths.append(Path(target))

        self.runner.run(("systemctl", "daemon-reload"))
        shutil.rmtree(candidate_root, ignore_errors=True)
        return {
            "status": "PASS",
            "committed": True,
            "transaction_owned_only": True,
            "production_service_start": False,
        }

    def stopped_postcheck(self, system_id: str):
        if self.runner.run(("docker", "ps", "-aq")).strip():
            raise BootstrapError("postcheck_container_present")
        image_ids = {
            value
            for value in self.runner.run(("docker", "image", "ls", "--no-trunc", "-q")).splitlines()
            if value
        }
        if len(image_ids) != 3:
            raise BootstrapError("postcheck_image_count_invalid")
        for label in ("homeassistant", "manager", "broker"):
            record = self.manifest["images"][label]
            binding = _verify_runtime_image(self.runner, label, record)
            loaded = self.loaded_image_bindings.get(label)
            if loaded is None or binding != loaded:
                raise BootstrapError(f"postcheck_image_binding_drift:{label}")
        if self.runner.run(("docker", "volume", "ls", "-q")).strip():
            raise BootstrapError("postcheck_volume_present")

        networks = frozenset(
            value
            for value in self.runner.run(
                ("docker", "network", "ls", "--format", "{{.Name}}")
            ).splitlines()
            if value
        )
        if networks != DEFAULT_NETWORKS:
            raise BootstrapError("postcheck_network_set_invalid")
        if _listeners(self.runner):
            raise BootstrapError("postcheck_listener_present")

        firewall = self.runner.run(("iptables-save", "-t", "filter"))
        if (
            "N3WFC4-BROKER-INGRESS" in firewall
            or "n3wfc4-broker-ingress-v1" in firewall
        ):
            raise BootstrapError("postcheck_firewall_started")

        unit = "n3wfc4-broker-ingress-guard.service"
        if _unit_load_state(self.runner, unit) != "loaded":
            raise BootstrapError("postcheck_guard_unit_missing")
        if _systemctl(self.runner, "is-active", unit) not in {"inactive", "unknown"}:
            raise BootstrapError("postcheck_guard_active")
        if _systemctl(self.runner, "is-enabled", unit) not in {"disabled", "static", "indirect"}:
            raise BootstrapError("postcheck_guard_enabled")

        for target in (*FINAL_DIRS.keys(), *FINAL_FILES.keys()):
            path = Path(target)
            if not path.exists() or path.is_symlink():
                raise BootstrapError(f"postcheck_product_path_missing:{target}")
        if any(Path(path).exists() or Path(path).is_symlink() for path in EXTRA_ABSENT):
            raise BootstrapError("postcheck_forbidden_product_path_present")

        env_file = "/etc/n3wfc4/docker-compose.env"
        compose = "/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.yml"
        compose_json = self.runner.run(
            (
                "docker",
                "compose",
                "--env-file",
                env_file,
                "-f",
                compose,
                "--profile",
                "*",
                "config",
                "--format",
                "json",
            )
        )
        gate = self.runner.run(
            (
                "python3",
                "/opt/HomeAssistant/tools/n3w_t1_clean_product_deployment_gate.py",
                "--compose-json",
                "-",
                "--image-lock-json",
                "/opt/HomeAssistant/infra/n3w-t1/production/image-lock.json",
            ),
            input_text=compose_json,
        )
        if json.loads(gate).get("status") != "PASS":
            raise BootstrapError("postcheck_deployment_gate_invalid")

        audit_source = """
import hashlib
import json
from pathlib import Path
from greenhouse_manager.bootstrap.system_init import verify_initialization
from greenhouse_manager.bootstrap.fresh_product_state import audit_fresh_state
from greenhouse_manager.bootstrap.fresh_broker import audit_fresh_dynsec_document
from greenhouse_manager.ops.t1_clean_service_credential_bundle import verify_clean_service_credential_bundle

system_id = %r
identity = verify_initialization(Path("/state/identity"))
if identity.system_id != system_id:
    raise RuntimeError("system_identity_drift")
state = audit_fresh_state(
    Path("/state/manager"),
    Path("/state/n3w"),
    expected_system_id_sha256=hashlib.sha256(system_id.encode()).hexdigest(),
)
dynsec = audit_fresh_dynsec_document(
    Path("/broker/dynamic-security.json"),
    system_id=system_id,
)
credentials = verify_clean_service_credential_bundle(Path("/secrets/mqtt"))
print(json.dumps({
    "state_node_count": state["node_credential_count"],
    "dynsec_node_count": dynsec["node_client_count"],
    "credential_node_count": credentials["node_credential_count"],
}, sort_keys=True))
""" % system_id
        name = f"n3w-fresh-audit-{secrets.token_hex(6)}"
        self.candidate_containers.append(name)
        try:
            output = self.runner.run(
                (
                    "docker",
                    "run",
                    "--rm",
                    "--name",
                    name,
                    "--network",
                    "none",
                    "--user",
                    "0:0",
                    "--mount",
                    "type=bind,src=/var/lib/greenhouse-manager,dst=/state,readonly",
                    "--mount",
                    "type=bind,src=/var/lib/n3wfc4-broker,dst=/broker,readonly",
                    "--mount",
                    "type=bind,src=/opt/greenhouse-secrets,dst=/secrets,readonly",
                    "--entrypoint",
                    "python",
                    self.manager_image,
                    "-c",
                    audit_source,
                ),
                timeout=240,
            )
        finally:
            self.runner.run(
                ("docker", "rm", "-f", "-v", name),
                allowed=frozenset({0, 1}),
            )
            if name in self.candidate_containers:
                self.candidate_containers.remove(name)
        audit = json.loads(output)
        if any(
            int(audit[key]) != 0
            for key in (
                "state_node_count",
                "dynsec_node_count",
                "credential_node_count",
            )
        ):
            raise BootstrapError("postcheck_node_credential_present")

        return {
            "status": "PASS",
            "fresh_product_staged": True,
            "node_credential_count": 0,
            "product_listener_count": 0,
            "production_service_start": False,
        }

    def cleanup(self, candidate_root: Path):
        errors: list[str] = []
        for name in tuple(self.candidate_containers):
            try:
                self.runner.run(
                    ("docker", "rm", "-f", "-v", name),
                    allowed=frozenset({0, 1}),
                )
            except Exception as error:
                errors.append(type(error).__name__)
        for network in reversed(self.created_networks):
            try:
                self.runner.run(
                    ("docker", "network", "rm", network),
                    allowed=frozenset({0, 1}),
                )
            except Exception as error:
                errors.append(type(error).__name__)
        for path in reversed(self.created_paths):
            try:
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
            except Exception as error:
                errors.append(type(error).__name__)
        for image in reversed(self.created_images):
            try:
                self.runner.run(
                    ("docker", "image", "rm", image),
                    allowed=frozenset({0, 1}),
                )
            except Exception as error:
                errors.append(type(error).__name__)
        shutil.rmtree(candidate_root, ignore_errors=True)
        try:
            self.runner.run(("systemctl", "daemon-reload"))
        except Exception as error:
            errors.append(type(error).__name__)
        if errors:
            raise BootstrapError("cleanup_incomplete")
        _preflight(self.runner)
        return {
            "status": "PASS",
            "transaction_owned_only": True,
            "production_service_start": False,
        }

def execute_preflight(payload_root: Path, runner: Runner | None = None) -> dict[str, object]:
    manifest = _load_manifest(payload_root)
    report = _preflight(runner or Runner())
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "phase": "preflight",
        "source_head": manifest["source_head"],
        "host_baseline": "PASS",
        "container_count": report["product_containers"],
        "image_count": report["product_images"],
        "volume_count": report["product_volumes"],
        "product_network_count": report["product_networks"],
        "production_listener_count": report["product_listeners"],
        "payload_exact": True,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "live_mutation": False,
        "production_service_start": False,
        "board_access": False,
    }


def execute_apply(payload_root: Path, authorization_id: str, runner: Runner | None = None) -> dict[str, object]:
    if authorization_id != AUTHORIZATION_ID:
        raise BootstrapError("authorization_id_mismatch")
    if os.geteuid() != 0:
        raise BootstrapError("root_required")
    manifest = _load_manifest(payload_root)
    active = runner or Runner()
    adapters = LiveFreshInstallerAdapters(payload_root, manifest, active)
    contract = _load_contract(payload_root)

    def claim() -> None:
        marker = payload_root / CLAIM_MARKER_NAME
        descriptor = os.open(
            marker,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(AUTHORIZATION_ID + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "event": "authorization_claimed",
                    "authorization_id": AUTHORIZATION_ID,
                    "authorization_claimed": True,
                    "authorization_consumed": True,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            flush=True,
        )

    candidate = Path("/var/tmp") / f"n3w-fresh-bootstrap-{secrets.token_hex(8)}"
    claimed = False

    def claim_once() -> None:
        nonlocal claimed
        claim()
        claimed = True

    try:
        report = contract.run_fresh_staging(
            adapters,
            candidate,
            before_mutation=claim_once,
        )
    except Exception as error:
        if claimed:
            print(
                json.dumps(
                    {
                        "schema": SCHEMA,
                        "status": "STOP_PARTIAL",
                        "reason": str(error)[:400],
                        "authorization_claimed": True,
                        "authorization_consumed": True,
                        "replay_allowed": False,
                        "automatic_retry": False,
                        "production_service_start": False,
                        "board_access": False,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                flush=True,
            )
        raise
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "source_head": manifest["source_head"],
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "fresh_product_staged": report["fresh_product_staged"],
        "node_credential_count": report["node_credential_count"],
        "production_service_start": False,
        "activation_authorized": False,
        "board_access": False,
    }


def self_check(payload_root: Path) -> dict[str, object]:
    manifest = _load_manifest(payload_root)
    source = Path(__file__).read_text(encoding="utf-8")
    forbidden = (
        "docker system prune",
        "docker volume prune",
        "docker network prune",
        "systemctl enable n3wfc4",
        "systemctl start n3wfc4",
        "docker compose up",
    )
    executable = source.split("\ndef self_check(", 1)[0]
    found = [value for value in forbidden if value in executable]
    return {
        "schema": SCHEMA,
        "status": "PASS" if not found else "STOP",
        "source_head": manifest["source_head"],
        "authorization_id": AUTHORIZATION_ID,
        "forbidden_operations": found,
        "live_mutation_executed": False,
        "production_service_start": False,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-root", type=Path, required=True)
    parser.add_argument("--phase", choices=("self-check", "preflight", "apply"), required=True)
    parser.add_argument("--authorization-id")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        root = args.payload_root.resolve()
        if args.phase == "self-check":
            result = self_check(root)
        elif args.phase == "preflight":
            result = execute_preflight(root)
        else:
            if not args.authorization_id:
                raise BootstrapError("authorization_id_required")
            result = execute_apply(root, args.authorization_id)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)
        return 0 if result.get("status") == "PASS" else 2
    except Exception as error:
        root = args.payload_root.resolve()
        claimed = (root / CLAIM_MARKER_NAME).is_file()
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP_PARTIAL" if claimed else "STOP",
                    "reason": str(error)[:400],
                    "authorization_claimed": claimed,
                    "authorization_consumed": claimed,
                    "replay_allowed": False if claimed else None,
                    "production_service_start": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
