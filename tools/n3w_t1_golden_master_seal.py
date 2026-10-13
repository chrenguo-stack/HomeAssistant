#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Sequence

from n3w_t1_golden_master_common import public_tree_sha256, sha256_file

SCHEMA = "gh.n3w.t1-golden-master-seal-host/1"
RELEASE_SCHEMA = "gh.n3w.t1-golden-master-release/1"
AUTHORIZATION_ID = "N3W_T1_GOLDEN_MASTER_R2_FINAL_SEAL_LIVE_APPLY_20261013_01"
RELEASE_RELATIVE_PATH = Path(
    "infra/n3w-t1/production/golden-master-release.json"
)
IMAGE_LOCK_RELATIVE_PATH = Path("infra/n3w-t1/production/image-lock.json")
_SHA40 = re.compile(r"[0-9a-f]{40}")
_SHA64 = re.compile(r"[0-9a-f]{64}")


class GoldenMasterSealHostError(RuntimeError):
    pass


class Runner:
    def run(self, argv: Sequence[str]) -> str:
        completed = subprocess.run(
            tuple(argv),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if completed.returncode != 0:
            raise GoldenMasterSealHostError(
                f"command_failed:{Path(argv[0]).name}:{completed.returncode}"
            )
        return completed.stdout


def _load_release(source_root: Path) -> dict[str, Any]:
    path = source_root / RELEASE_RELATIVE_PATH
    if path.is_symlink() or not path.is_file():
        raise GoldenMasterSealHostError("release_manifest_missing")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GoldenMasterSealHostError("release_manifest_invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("schema") != RELEASE_SCHEMA
        or not isinstance(document.get("release_id"), str)
        or not document["release_id"]
        or _SHA40.fullmatch(str(document.get("source_head"))) is None
        or _SHA64.fullmatch(str(document.get("payload_manifest_sha256"))) is None
        or _SHA64.fullmatch(str(document.get("image_lock_sha256"))) is None
        or _SHA64.fullmatch(str(document.get("public_source_tree_sha256"))) is None
        or document.get("architecture") != "linux/arm64"
        or document.get("instance_material_absent") is not True
        or document.get("secret_values_included") is not False
        or document.get("seal_state") != "UNSEALED"
        or document.get("production_service_start") is not False
    ):
        raise GoldenMasterSealHostError("release_manifest_contract_invalid")
    images = document.get("images")
    if not isinstance(images, dict) or set(images) != {
        "homeassistant",
        "manager",
        "broker",
    }:
        raise GoldenMasterSealHostError("release_manifest_images_invalid")
    return document


def _normalized_hash(value: object) -> str:
    import hashlib

    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _image_config_contract(config: object) -> dict[str, object]:
    value = config if isinstance(config, dict) else {}
    result: dict[str, object] = {}
    sequence_fields = {"Entrypoint", "Cmd", "Env"}
    string_fields = {"User", "WorkingDir", "StopSignal"}
    mapping_fields = {
        "Labels",
        "Healthcheck",
        "Volumes",
        "ExposedPorts",
    }
    for key in (
        "Entrypoint",
        "Cmd",
        "User",
        "Env",
        "WorkingDir",
        "Labels",
        "Healthcheck",
        "StopSignal",
        "Volumes",
        "ExposedPorts",
    ):
        observed = value.get(key)
        if key in sequence_fields and observed is None:
            observed = []
        elif key in string_fields and observed is None:
            observed = ""
        elif key in mapping_fields and observed is None:
            observed = {}
        result[key] = observed
    return result


def _verify_images(
    runner: Runner,
    release: dict[str, Any],
) -> None:
    for label, record in release["images"].items():
        raw = runner.run(("docker", "image", "inspect", str(record["image"])))
        try:
            values = json.loads(raw)
        except json.JSONDecodeError as error:
            raise GoldenMasterSealHostError(
                f"image_inspect_invalid:{label}"
            ) from error
        if (
            not isinstance(values, list)
            or len(values) != 1
            or not isinstance(values[0], dict)
        ):
            raise GoldenMasterSealHostError(
                f"image_inspect_invalid:{label}"
            )
        item = values[0]
        if item.get("Architecture") != "arm64" or item.get("Os") != "linux":
            raise GoldenMasterSealHostError(
                f"image_platform_invalid:{label}"
            )
        rootfs = item.get("RootFS")
        layers = rootfs.get("Layers") if isinstance(rootfs, dict) else None
        if (
            not isinstance(layers, list)
            or _normalized_hash(layers) != record["rootfs_layers_sha256"]
        ):
            raise GoldenMasterSealHostError(
                f"image_rootfs_binding_invalid:{label}"
            )
        if (
            _normalized_hash(_image_config_contract(item.get("Config")))
            != record["config_contract_sha256"]
        ):
            raise GoldenMasterSealHostError(
                f"image_config_binding_invalid:{label}"
            )


def audit_public_master(
    source_root: Path,
    *,
    runner: Runner | None = None,
) -> dict[str, object]:
    root = source_root.resolve()
    release = _load_release(root)
    excluded = frozenset({RELEASE_RELATIVE_PATH.as_posix()})
    if (
        public_tree_sha256(root, excluded=excluded)
        != release["public_source_tree_sha256"]
    ):
        raise GoldenMasterSealHostError("public_source_tree_binding_invalid")

    image_lock = root / IMAGE_LOCK_RELATIVE_PATH
    if image_lock.is_symlink() or not image_lock.is_file():
        raise GoldenMasterSealHostError("image_lock_missing")
    if sha256_file(image_lock) != release["image_lock_sha256"]:
        raise GoldenMasterSealHostError("image_lock_binding_invalid")

    active = runner or Runner()
    _verify_images(active, release)
    if active.run(("docker", "ps", "-aq")).strip():
        raise GoldenMasterSealHostError("product_container_present")
    if active.run(("docker", "volume", "ls", "-q")).strip():
        raise GoldenMasterSealHostError("product_volume_present")

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "phase": "public-audit",
        "release_id": release["release_id"],
        "source_head": release["source_head"],
        "exact_release_binding": True,
        "instance_material_absent": True,
        "public_source_tree_exact": True,
        "image_lock_exact": True,
        "image_binding_exact": True,
        "target_identity_adapter_ready": False,
        "disk_capture_ready": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "secret_values_included": False,
        "production_service_start": False,
        "board_access": False,
    }


def execute_seal(_source_root: Path, authorization_id: str) -> dict[str, object]:
    if authorization_id != AUTHORIZATION_ID:
        raise GoldenMasterSealHostError("authorization_id_mismatch")
    raise GoldenMasterSealHostError("target_identity_adapter_required")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n3w-t1-golden-master-seal")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("/opt/HomeAssistant"),
    )
    parser.add_argument(
        "--phase",
        choices=("public-audit", "seal"),
        required=True,
    )
    parser.add_argument("--authorization-id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.phase == "public-audit":
            result = audit_public_master(args.source_root)
        else:
            if not args.authorization_id:
                raise GoldenMasterSealHostError("authorization_id_required")
            result = execute_seal(args.source_root, args.authorization_id)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error)[:400],
                    "authorization_claimed": False,
                    "authorization_consumed": False,
                    "replay_allowed": None,
                    "production_service_start": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
