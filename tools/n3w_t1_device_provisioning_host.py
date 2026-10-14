#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from types import ModuleType

SCHEMA = "gh.n3w-t1-device-provisioning-host/1"
RELEASE_SCHEMA = "gh.n3w-t1-fresh-release/1"
RELEASE_PATH = Path(
    "/opt/HomeAssistant/infra/n3w-t1/production/fresh-release.json"
)
FRESH_TOOL_PATH = Path(
    "/opt/HomeAssistant/tools/n3w_t1_fresh_product_bootstrap.py"
)
FIRSTBOOT_TOOL_PATH = Path(
    "/opt/HomeAssistant/tools/n3w_t1_device_firstboot.py"
)
TRANSACTION_ROOT = Path("/var/lib/n3w-t1-provisioning")
CANDIDATE_ROOT = Path("/var/tmp/n3w-t1-provisioning-candidate")
MACHINE_ID_PATH = Path("/etc/machine-id")
SSH_HOST_PUBLIC_KEY = Path("/etc/ssh/ssh_host_ed25519_key.pub")
CONFIRMATION = "START DEVICE PROVISIONING: YES"


class ProvisionHostError(RuntimeError):
    pass


def _load_module(path: Path, name: str) -> ModuleType:
    if path.is_symlink() or not path.is_file():
        raise ProvisionHostError(f"module_source_invalid:{path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ProvisionHostError(f"module_spec_invalid:{path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _read_release(path: Path = RELEASE_PATH) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ProvisionHostError("fresh_release_missing")
    metadata = path.stat()
    if (
        metadata.st_uid != os.geteuid()
        or metadata.st_mode & 0o777 != 0o644
        or metadata.st_nlink != 1
    ):
        raise ProvisionHostError("fresh_release_metadata_invalid")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProvisionHostError("fresh_release_invalid") from error
    if not isinstance(document, dict) or document.get("schema") != RELEASE_SCHEMA:
        raise ProvisionHostError("fresh_release_schema_invalid")
    source_head = document.get("source_head")
    release_id = document.get("release_id")
    if (
        not isinstance(source_head, str)
        or re.fullmatch(r"[0-9a-f]{40}", source_head) is None
        or release_id != source_head
        or document.get("instance_material_absent") is not True
        or document.get("explicit_provisioning_required") is not True
    ):
        raise ProvisionHostError("fresh_release_binding_invalid")
    images = document.get("images")
    image_lock = document.get("image_lock")
    if not isinstance(images, dict) or set(images) != {
        "homeassistant",
        "manager",
        "broker",
    }:
        raise ProvisionHostError("fresh_release_images_invalid")
    if (
        not isinstance(image_lock, dict)
        or image_lock.get("source_head") != source_head
    ):
        raise ProvisionHostError("fresh_release_image_lock_invalid")
    for label in ("homeassistant", "manager", "broker"):
        record = images.get(label)
        locked = image_lock.get(label)
        if (
            not isinstance(record, dict)
            or not isinstance(locked, dict)
            or record.get("image") != locked.get("image")
            or record.get("image_id") != locked.get("image_id")
            or record.get("platform") != "linux/arm64"
        ):
            raise ProvisionHostError(f"fresh_release_image_binding_invalid:{label}")
    return document


def _host_identity() -> dict[str, object]:
    if (
        MACHINE_ID_PATH.is_symlink()
        or not MACHINE_ID_PATH.is_file()
        or SSH_HOST_PUBLIC_KEY.is_symlink()
        or not SSH_HOST_PUBLIC_KEY.is_file()
    ):
        raise ProvisionHostError("os_identity_material_missing")
    machine_id = MACHINE_ID_PATH.read_text(encoding="utf-8").strip()
    if re.fullmatch(r"[0-9a-f]{32}", machine_id) is None:
        raise ProvisionHostError("machine_id_invalid")
    ssh_public = SSH_HOST_PUBLIC_KEY.read_bytes().strip()
    if not ssh_public:
        raise ProvisionHostError("ssh_host_identity_invalid")
    digest = hashlib.sha256(
        machine_id.encode("ascii") + b"\0" + ssh_public
    ).hexdigest()
    return {
        "status": "PASS",
        "host_instance_id": f"t1h-{digest[:24]}",
        "machine_id_ready": True,
        "ssh_host_identity_ready": True,
        "production_service_start": False,
        "network_operation": False,
    }


class HostAdapters:
    def __init__(self, release: dict[str, object]) -> None:
        self.release = release
        self.fresh = _load_module(FRESH_TOOL_PATH, "n3w_installed_fresh_bootstrap")
        manifest = {
            "images": release["images"],
            "image_lock": release["image_lock"],
            "source_head": release["source_head"],
        }
        self.live = self.fresh.LiveFreshInstallerAdapters(
            Path("/opt/HomeAssistant"),
            manifest,
            self.fresh.Runner(),
        )
        for label in ("homeassistant", "manager", "broker"):
            record = release["images"][label]
            self.live.loaded_image_bindings[label] = self.fresh._verify_runtime_image(
                self.live.runner,
                label,
                record,
            )

    def preflight_fresh_host(self):
        report = self.live.master_postcheck(
            require_instance_absent=True,
            staged_units_enabled=True,
        )
        return {
            "status": "PASS",
            "fresh_host_ready": True,
            "release_id": self.release["release_id"],
            "release_binding_verified": True,
            "product_state_absent": report["instance_material_absent"],
            "production_service_start": False,
        }

    def ensure_os_identity(self):
        return _host_identity()

    def verify_os_identity(self):
        return _host_identity()

    def create_identity(self, candidate_root: Path):
        return self.live.create_identity(candidate_root)

    def create_state(self, candidate_root: Path, system_id_sha256: str):
        return self.live.create_state(candidate_root, system_id_sha256)

    def create_broker(self, candidate_root: Path, system_id: str):
        return self.live.create_broker(candidate_root, system_id)

    def initialize_dynsec(self, candidate_root: Path, system_id: str):
        return self.live.initialize_dynsec(candidate_root, system_id)

    def stage_instance_runtime(self, candidate_root: Path, system_id: str):
        return self.live.stage_instance_runtime(candidate_root, system_id)

    def commit_instance_candidate(self, candidate_root: Path, system_id: str):
        return self.live.commit_instance_candidate(candidate_root, system_id)

    def instance_stopped_postcheck(self, system_id: str):
        return self.live.instance_stopped_postcheck(system_id)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n3w-t1-provision")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    start = subparsers.add_parser("start")
    start.add_argument("--confirm", required=True)
    subparsers.add_parser("resume-if-needed")
    subparsers.add_parser("verify")
    return parser


def _emit(document: dict[str, object], *, error: bool = False) -> None:
    destination = sys.stderr if error else sys.stdout
    destination.write(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    )


def _reconcile(firstboot: ModuleType, adapters: HostAdapters, release_id: str):
    observed = firstboot.inspect_device_provisioning(
        adapters,
        TRANSACTION_ROOT,
        CANDIDATE_ROOT,
        release_id=release_id,
    )
    state = observed.get("state")
    if state == "UNPROVISIONED":
        return {
            **observed,
            "boot_action": "NOOP",
            "production_service_start": False,
        }
    if state == "INITIALIZING":
        report = firstboot.resume_device_provisioning(
            adapters,
            TRANSACTION_ROOT,
            CANDIDATE_ROOT,
            release_id=release_id,
        )
        return {
            **report,
            "boot_action": "RESUME_EXISTING",
            "production_service_start": False,
        }
    if state == "DEVICE_READY":
        report = firstboot.verify_device_ready(
            adapters,
            TRANSACTION_ROOT,
            CANDIDATE_ROOT,
            release_id=release_id,
        )
        return {
            **report,
            "boot_action": "VERIFY_ONLY",
            "production_service_start": False,
        }
    raise ProvisionHostError(
        f"provisioning_state_conflict:{observed.get('error_code') or 'unknown'}"
    )


def main() -> int:
    args = _parser().parse_args()
    try:
        if os.geteuid() != 0:
            raise ProvisionHostError("root_required")
        release = _read_release()
        release_id = str(release["release_id"])
        firstboot = _load_module(
            FIRSTBOOT_TOOL_PATH,
            "n3w_installed_device_firstboot",
        )
        adapters = HostAdapters(release)

        if args.command == "status":
            report = firstboot.inspect_device_provisioning(
                adapters,
                TRANSACTION_ROOT,
                CANDIDATE_ROOT,
                release_id=release_id,
            )
        elif args.command == "start":
            if args.confirm != CONFIRMATION:
                raise ProvisionHostError("provisioning_confirmation_invalid")
            report = firstboot.start_device_provisioning(
                adapters,
                TRANSACTION_ROOT,
                CANDIDATE_ROOT,
                release_id=release_id,
                confirmation=args.confirm,
            )
        elif args.command == "resume-if-needed":
            report = _reconcile(firstboot, adapters, release_id)
        else:
            report = firstboot.verify_device_ready(
                adapters,
                TRANSACTION_ROOT,
                CANDIDATE_ROOT,
                release_id=release_id,
            )

        _emit(
            {
                **report,
                "schema": SCHEMA,
                "release_id": release_id,
                "production_service_start": False,
                "board_access": False,
            }
        )
        return 0
    except (
        ImportError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        _emit(
            {
                "schema": SCHEMA,
                "status": "FAIL",
                "error_code": str(error)[:400] or type(error).__name__,
                "production_service_start": False,
                "board_access": False,
            },
            error=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
