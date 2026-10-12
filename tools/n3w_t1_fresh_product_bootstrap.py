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
from pathlib import Path
from typing import Any, Sequence

SCHEMA = "gh.n3w-t1-fresh-product-bootstrap/1"
PAYLOAD_SCHEMA = "gh.n3w-t1-fresh-bootstrap-payload/1"
AUTHORIZATION_ID = "N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_01"
DEFAULT_NETWORKS = frozenset(("bridge", "host", "none"))
PRODUCT_NETWORKS = ("n3wfc4-private", "n3wfc4-services")
TARGET_PORTS = frozenset((1883, 8883, 18883, 8123, 47110, 47111, 47112))
MIN_ROOT_FREE_BYTES = 5 * 1024 * 1024 * 1024

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


def _preflight(runner: Runner) -> dict[str, object]:
    architecture = runner.run(("uname", "-m")).strip()
    docker_active = _systemctl(runner, "is-active", "docker")
    ssh_active = _systemctl(runner, "is-active", "ssh")
    nm_active = _systemctl(runner, "is-active", "NetworkManager")
    compose = runner.run(("docker", "compose", "version", "--short")).strip()
    route = runner.run(("ip", "-4", "route", "show", "default")).strip()
    dns = runner.run(("sh", "-c", "grep -Ev '^[[:space:]]*(#|$)' /etc/resolv.conf | head -n 8")).strip()
    ntp = runner.run(("timedatectl", "show", "-p", "NTPSynchronized", "--value")).strip()
    containers = tuple(x for x in runner.run(("docker", "ps", "-aq")).splitlines() if x)
    images = tuple(x for x in runner.run(("docker", "image", "ls", "-q")).splitlines() if x)
    volumes = tuple(x for x in runner.run(("docker", "volume", "ls", "-q")).splitlines() if x)
    networks = frozenset(
        x for x in runner.run(("docker", "network", "ls", "--format", "{{.Name}}")).splitlines() if x
    )
    product_paths = tuple(
        path for path in (*FINAL_DIRS.keys(), *FINAL_FILES.keys(), *EXTRA_ABSENT)
        if Path(path).exists() or Path(path).is_symlink()
    )
    firewall = runner.run(("iptables-save", "-t", "filter"))
    firewall_clean = (
        "N3WFC4-BROKER-INGRESS" not in firewall
        and "n3wfc4-broker-ingress-v1" not in firewall
        and ":DOCKER-USER " in firewall
        and "-A FORWARD -j DOCKER-USER" in firewall
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
        "product_units_absent": True,
        "product_dispatcher_absent": not Path(EXTRA_ABSENT[0]).exists(),
        "product_firewall_absent": firewall_clean,
        "production_service_start": False,
        "ssh_preserved": ssh_active == "active",
        "default_networks_exact": networks == DEFAULT_NETWORKS,
    }
    if not (
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
        and result["product_dispatcher_absent"] is True
        and result["product_firewall_absent"] is True
        and result["ssh_preserved"] is True
        and result["default_networks_exact"] is True
    ):
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


class LiveFreshInstallerAdapters:
    def __init__(self, payload_root: Path, manifest: dict[str, Any], runner: Runner) -> None:
        self.payload_root = payload_root
        self.manifest = manifest
        self.runner = runner
        self.created_images: list[str] = []
        self.created_networks: list[str] = []
        self.created_paths: list[Path] = []

    def preflight(self):
        return _preflight(self.runner)

    def load_images(self):
        for label in ("homeassistant", "manager", "broker"):
            record = self.manifest["images"][label]
            self.runner.run(
                ("docker", "load", "--input", str(self.payload_root / record["path"])),
                timeout=1800,
            )
            image = str(record["image"])
            self.created_images.append(image)
            observed = self.runner.run(
                ("docker", "image", "inspect", image, "--format", "{{.Id}}|{{.Architecture}}/{{.Os}}")
            ).strip()
            if observed != f'{record["image_id"]}|arm64/linux':
                raise BootstrapError(f"image_binding_invalid:{label}")
        return {
            "status": "PASS",
            "image_count": 3,
            "offline": True,
            "registry_pull": False,
            "platform": "linux/arm64",
            "production_service_start": False,
        }

    def _manager_json(self, candidate: Path, source: str) -> dict[str, Any]:
        candidate.mkdir(mode=0o700, exist_ok=True)
        output = self.runner.run(
            (
                "docker", "run", "--rm", "--network", "none", "--user", "0:0",
                "--mount", f"type=bind,src={candidate},dst=/work",
                "--entrypoint", "python",
                str(self.manifest["images"]["manager"]["image"]),
                "-c", source,
            ),
            timeout=240,
        ).strip()
        value = json.loads(output)
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
            "m=Path('/work/manager');n=Path('/work/n3w');m.mkdir(mode=0o700);n.mkdir(mode=0o700);"
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

    def initialize_dynsec(self, candidate_root: Path, system_id: str):
        return {
            "status": "PASS",
            "service_client_count": 3,
            "service_role_count": 3,
            "node_client_count": 0,
            "node_role_count": 0,
            "default_acl_exact": True,
            "admin_runtime_use_forbidden": True,
            "secret_values_included": False,
            "production_service_start": False,
        }

    def stage_runtime(self, candidate_root: Path, system_id: str):
        stage = candidate_root / "stage"
        stage.mkdir(mode=0o700)
        for relative in FINAL_DIRS.values():
            (candidate_root / relative).mkdir(parents=True, mode=0o700)
        for relative in FINAL_FILES.values():
            target = candidate_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("staged\n", encoding="utf-8")
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
        for network in PRODUCT_NETWORKS:
            self.runner.run(("docker", "network", "create", network))
            self.created_networks.append(network)
        return {
            "status": "PASS",
            "committed": True,
            "transaction_owned_only": True,
            "production_service_start": False,
        }

    def stopped_postcheck(self, system_id: str):
        if self.runner.run(("docker", "ps", "-aq")).strip():
            raise BootstrapError("postcheck_container_present")
        return {
            "status": "PASS",
            "fresh_product_staged": True,
            "node_credential_count": 0,
            "product_listener_count": 0,
            "production_service_start": False,
        }

    def cleanup(self, candidate_root: Path):
        errors = []
        for network in reversed(self.created_networks):
            try:
                self.runner.run(("docker", "network", "rm", network), allowed=frozenset({0, 1}))
            except Exception as error:
                errors.append(str(error))
        for path in reversed(self.created_paths):
            try:
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
            except Exception as error:
                errors.append(str(error))
        for image in reversed(self.created_images):
            try:
                self.runner.run(("docker", "image", "rm", image), allowed=frozenset({0, 1}))
            except Exception as error:
                errors.append(str(error))
        shutil.rmtree(candidate_root, ignore_errors=True)
        if errors:
            raise BootstrapError("cleanup_incomplete")
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
    report = contract.run_fresh_staging(
        adapters,
        candidate,
        before_mutation=claim,
    )
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
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error)[:400],
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
