#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "gh.n3w.r10-t1-candidate-upgrade-package/1"
PREDECESSOR_SOURCE = "03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6"
TARGET_SOURCE = "e299c937a7b89bb8a7b9a7432186ba46a416cd44"
PREDECESSOR_MANAGER_IMAGE = "local/greenhouse-manager:fresh-03dab2bd04e7"
TARGET_MANAGER_IMAGE = "local/greenhouse-manager:fresh-e299c937a7b8"
BASE_IMAGE_REF = "python:3.11-slim"
EMERGENCY_RESERVE_BYTES = 2 * 1024 * 1024 * 1024

LIVE_FILES = {
    "compose": {
        "predecessor_source": "infra/n3w-t1/production/docker-compose.fresh.yml",
        "target_source": "infra/n3w-t1/production/docker-compose.fresh.yml",
        "artifact": "runtime/live/etc/n3wfc4/docker-compose.yml",
        "target": "/etc/n3wfc4/docker-compose.yml",
        "mode": 0o644,
        "f4_bound": True,
        "predecessor_present": True,
    },
    "services_unit": {
        "predecessor_source": "infra/n3w-t1/f4/n3wfc4-services-activation.service",
        "target_source": "infra/n3w-t1/f4/n3wfc4-services-activation.service",
        "artifact": (
            "runtime/live/etc/systemd/system/"
            "n3wfc4-services-activation.service"
        ),
        "target": (
            "/etc/systemd/system/n3wfc4-services-activation.service"
        ),
        "mode": 0o644,
        "f4_bound": True,
        "predecessor_present": True,
    },
    "dispatcher": {
        "predecessor_source": (
            "infra/n3w-t1/NetworkManager/dispatcher.d/"
            "90-n3wfc4-broker-ingress-guard"
        ),
        "target_source": (
            "infra/n3w-t1/NetworkManager/dispatcher.d/"
            "90-n3wfc4-broker-ingress-guard"
        ),
        "artifact": (
            "runtime/live/etc/NetworkManager/dispatcher.d/"
            "90-n3wfc4-broker-ingress-guard"
        ),
        "target": (
            "/etc/NetworkManager/dispatcher.d/"
            "90-n3wfc4-broker-ingress-guard"
        ),
        "mode": 0o755,
        "f4_bound": True,
        "predecessor_present": True,
    },
    "registration_unit": {
        "predecessor_source": None,
        "target_source": (
            "infra/n3w-t1/systemd/"
            "n3wfc4-registration-ingress-guard.service"
        ),
        "artifact": (
            "runtime/live/etc/systemd/system/"
            "n3wfc4-registration-ingress-guard.service"
        ),
        "target": (
            "/etc/systemd/system/"
            "n3wfc4-registration-ingress-guard.service"
        ),
        "mode": 0o644,
        "f4_bound": False,
        "predecessor_present": False,
    },
    "registration_guard": {
        "predecessor_source": None,
        "target_source": "tools/n3w_registration_ingress_guard.py",
        "artifact": (
            "runtime/live/usr/local/sbin/n3w-registration-ingress-guard"
        ),
        "target": "/usr/local/sbin/n3w-registration-ingress-guard",
        "mode": 0o755,
        "f4_bound": False,
        "predecessor_present": False,
    },
    "trusted_lan_authority": {
        "predecessor_source": None,
        "target_source": "tools/n3w_trusted_product_lan_authority.py",
        "artifact": (
            "runtime/live/usr/local/sbin/"
            "n3w-trusted-product-lan-authority"
        ),
        "target": "/usr/local/sbin/n3w-trusted-product-lan-authority",
        "mode": 0o755,
        "f4_bound": False,
        "predecessor_present": False,
    },
}

SOURCE_OVERLAY = {
    "canonical_compose": {
        "predecessor_source": (
            "infra/n3w-t1/production/docker-compose.fresh.yml"
        ),
        "target_source": "infra/n3w-t1/production/docker-compose.fresh.yml",
        "artifact": (
            "runtime/source/infra/n3w-t1/production/docker-compose.yml"
        ),
        "target": (
            "/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.yml"
        ),
        "mode": 0o644,
    },
    "fresh_compose": {
        "predecessor_source": (
            "infra/n3w-t1/production/docker-compose.fresh.yml"
        ),
        "target_source": "infra/n3w-t1/production/docker-compose.fresh.yml",
        "artifact": (
            "runtime/source/infra/n3w-t1/production/"
            "docker-compose.fresh.yml"
        ),
        "target": (
            "/opt/HomeAssistant/infra/n3w-t1/production/"
            "docker-compose.fresh.yml"
        ),
        "mode": 0o644,
    },
    "f4_services_unit": {
        "predecessor_source": (
            "infra/n3w-t1/f4/n3wfc4-services-activation.service"
        ),
        "target_source": (
            "infra/n3w-t1/f4/n3wfc4-services-activation.service"
        ),
        "artifact": (
            "runtime/source/infra/n3w-t1/f4/"
            "n3wfc4-services-activation.service"
        ),
        "target": (
            "/opt/HomeAssistant/infra/n3w-t1/f4/"
            "n3wfc4-services-activation.service"
        ),
        "mode": 0o644,
    },
    "generic_services_unit": {
        "predecessor_source": (
            "infra/n3w-t1/systemd/n3wfc4-services-activation.service"
        ),
        "target_source": (
            "infra/n3w-t1/systemd/n3wfc4-services-activation.service"
        ),
        "artifact": (
            "runtime/source/infra/n3w-t1/systemd/"
            "n3wfc4-services-activation.service"
        ),
        "target": (
            "/opt/HomeAssistant/infra/n3w-t1/systemd/"
            "n3wfc4-services-activation.service"
        ),
        "mode": 0o644,
    },
    "registration_unit": {
        "predecessor_source": None,
        "target_source": (
            "infra/n3w-t1/systemd/"
            "n3wfc4-registration-ingress-guard.service"
        ),
        "artifact": (
            "runtime/source/infra/n3w-t1/systemd/"
            "n3wfc4-registration-ingress-guard.service"
        ),
        "target": (
            "/opt/HomeAssistant/infra/n3w-t1/systemd/"
            "n3wfc4-registration-ingress-guard.service"
        ),
        "mode": 0o644,
    },
    "dispatcher": {
        "predecessor_source": (
            "infra/n3w-t1/NetworkManager/dispatcher.d/"
            "90-n3wfc4-broker-ingress-guard"
        ),
        "target_source": (
            "infra/n3w-t1/NetworkManager/dispatcher.d/"
            "90-n3wfc4-broker-ingress-guard"
        ),
        "artifact": (
            "runtime/source/infra/n3w-t1/NetworkManager/dispatcher.d/"
            "90-n3wfc4-broker-ingress-guard"
        ),
        "target": (
            "/opt/HomeAssistant/infra/n3w-t1/NetworkManager/dispatcher.d/"
            "90-n3wfc4-broker-ingress-guard"
        ),
        "mode": 0o755,
    },
    "registration_guard": {
        "predecessor_source": None,
        "target_source": "tools/n3w_registration_ingress_guard.py",
        "artifact": (
            "runtime/source/tools/n3w_registration_ingress_guard.py"
        ),
        "target": (
            "/opt/HomeAssistant/tools/n3w_registration_ingress_guard.py"
        ),
        "mode": 0o755,
    },
    "trusted_lan_authority": {
        "predecessor_source": None,
        "target_source": "tools/n3w_trusted_product_lan_authority.py",
        "artifact": (
            "runtime/source/tools/"
            "n3w_trusted_product_lan_authority.py"
        ),
        "target": (
            "/opt/HomeAssistant/tools/"
            "n3w_trusted_product_lan_authority.py"
        ),
        "mode": 0o755,
    },
}


class PackageError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _regular(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if (
        pure.is_absolute()
        or not pure.parts
        or any(part in {"", ".", ".."} for part in pure.parts)
        or pure.as_posix() != relative
    ):
        raise PackageError("source_path_invalid")
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise PackageError(f"source_symlink_forbidden:{relative}")
    if not current.is_file():
        raise PackageError(f"source_file_missing:{relative}")
    return current


def _copy_exact(source: Path, target: Path, mode: int) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise PackageError(f"artifact_target_exists:{target}")
    data = source.read_bytes()
    target.write_bytes(data)
    os.chmod(target, mode)
    return {
        "artifact_path": target.as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "mode": mode,
    }


def _source_binding(
    root: Path,
    relative: str | None,
) -> dict[str, Any] | None:
    if relative is None:
        return None
    path = _regular(root, relative)
    return {
        "source_path": relative,
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
    }


def _materialize_group(
    *,
    output: Path,
    predecessor_root: Path,
    target_root: Path,
    records: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, spec in records.items():
        target_source = _regular(target_root, str(spec["target_source"]))
        artifact_rel = str(spec["artifact"])
        artifact_path = output / artifact_rel
        copied = _copy_exact(target_source, artifact_path, int(spec["mode"]))
        copied["artifact_path"] = artifact_rel
        copied["target"] = str(spec["target"])
        copied["predecessor"] = _source_binding(
            predecessor_root,
            spec.get("predecessor_source"),
        )
        copied["target_source"] = str(spec["target_source"])
        if "f4_bound" in spec:
            copied["f4_bound"] = bool(spec["f4_bound"])
            copied["predecessor_present"] = bool(
                spec["predecessor_present"]
            )
        result[name] = copied
    return result


def build(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output).resolve()
    predecessor = Path(args.predecessor_source_root).resolve()
    target = Path(args.target_source_root).resolve()
    manager_tar = Path(args.manager_tar).resolve()
    executor = Path(args.executor).resolve()

    if output.exists() or output.is_symlink():
        raise PackageError("output_must_be_absent")
    for root, label in (
        (predecessor, "predecessor"),
        (target, "target"),
    ):
        if root.is_symlink() or not root.is_dir():
            raise PackageError(f"{label}_root_invalid")
    if manager_tar.is_symlink() or not manager_tar.is_file():
        raise PackageError("manager_tar_invalid")
    if executor.is_symlink() or not executor.is_file():
        raise PackageError("executor_invalid")
    if args.predecessor_source != PREDECESSOR_SOURCE:
        raise PackageError("predecessor_source_invalid")
    if args.target_source != TARGET_SOURCE:
        raise PackageError("target_source_invalid")
    if args.manager_image != TARGET_MANAGER_IMAGE:
        raise PackageError("manager_image_invalid")
    if args.base_image_ref != BASE_IMAGE_REF:
        raise PackageError("base_image_ref_invalid")
    for label, value in (
        ("package_head", args.package_head),
        ("predecessor_source", args.predecessor_source),
        ("target_source", args.target_source),
    ):
        if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
            raise PackageError(f"{label}_invalid")
    for label, value in (
        ("base_arm64_digest", args.base_arm64_digest),
        ("base_image_id", args.base_image_id),
        ("manager_image_id", args.manager_image_id),
    ):
        if not value.startswith("sha256:") or len(value) != 71:
            raise PackageError(f"{label}_invalid")

    output.mkdir(mode=0o755)
    artifact_manager = output / "greenhouse-manager-arm64.tar"
    shutil.copyfile(manager_tar, artifact_manager)
    os.chmod(artifact_manager, 0o644)

    artifact_executor = output / "upgrade-executor.py"
    shutil.copyfile(executor, artifact_executor)
    os.chmod(artifact_executor, 0o755)

    live = _materialize_group(
        output=output,
        predecessor_root=predecessor,
        target_root=target,
        records=LIVE_FILES,
    )
    overlay = _materialize_group(
        output=output,
        predecessor_root=predecessor,
        target_root=target,
        records=SOURCE_OVERLAY,
    )

    runtime_bytes = sum(
        int(record["size"])
        for record in (*live.values(), *overlay.values())
    )
    manager_tar_size = artifact_manager.stat().st_size

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "package_head": args.package_head,
        "predecessor_source": PREDECESSOR_SOURCE,
        "target_source": TARGET_SOURCE,
        "predecessor_manager_image": PREDECESSOR_MANAGER_IMAGE,
        "target_manager_image": TARGET_MANAGER_IMAGE,
        "manager": {
            "artifact_path": artifact_manager.name,
            "tar_sha256": sha256_file(artifact_manager),
            "tar_size_bytes": manager_tar_size,
            "image_id": args.manager_image_id,
            "image_size_bytes": args.manager_image_size_bytes,
            "platform": "linux/arm64",
            "source_dockerfile_git_blob": (
                "6486ff5fbcc23536676a48f36d67e4e0d364900a"
            ),
            "base_image_ref": BASE_IMAGE_REF,
            "base_arm64_manifest_digest": args.base_arm64_digest,
            "base_image_id": args.base_image_id,
            "historical_byte_continuity_claimed": False,
            "candidate_build_authority": (
                "exact_target_source_plus_frozen_arm64_base_digest"
            ),
        },
        "live_files": live,
        "source_overlay": overlay,
        "executor": {
            "artifact_path": artifact_executor.name,
            "sha256": sha256_file(artifact_executor),
            "size": artifact_executor.stat().st_size,
        },
        "capacity": {
            "runtime_bundle_size_bytes": runtime_bytes,
            "upgrade_emergency_reserve_bytes": EMERGENCY_RESERVE_BYTES,
            "dynamic_rollback_measurement_required": True,
        },
        "registration_tls": {
            "included_in_artifact": False,
            "generated_on_target": True,
            "certificate_target": (
                "/etc/n3wfc4/registration-tls/bootstrap.pem"
            ),
            "private_key_target": (
                "/etc/n3wfc4/registration-tls/bootstrap.key"
            ),
        },
        "policy": {
            "homeassistant_image_included": False,
            "broker_image_included": False,
            "compose_override_allowed": False,
            "force_recreate_allowed": False,
            "t1_access": False,
            "t1_mutation": False,
            "service_stop_start": False,
            "board_access": False,
            "secret_values_included": False,
        },
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(manifest_path, 0o644)
    return manifest


def verify(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / "manifest.json"
    if root.is_symlink() or not root.is_dir() or not manifest_path.is_file():
        raise PackageError("package_invalid")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackageError("manifest_invalid") from error
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("target_source") != TARGET_SOURCE
        or manifest.get("predecessor_source") != PREDECESSOR_SOURCE
        or manifest.get("policy", {}).get("secret_values_included") is not False
        or manifest.get("policy", {}).get("t1_access") is not False
        or manifest.get("policy", {}).get("t1_mutation") is not False
        or manifest.get("policy", {}).get("board_access") is not False
    ):
        raise PackageError("manifest_contract_invalid")

    expected_files = {"manifest.json", "greenhouse-manager-arm64.tar", "upgrade-executor.py"}
    for group_name in ("live_files", "source_overlay"):
        group = manifest.get(group_name)
        if not isinstance(group, dict):
            raise PackageError(f"{group_name}_invalid")
        for record in group.values():
            expected_files.add(str(record["artifact_path"]))

    actual_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise PackageError("package_file_set_invalid")

    manager = manifest["manager"]
    manager_path = root / str(manager["artifact_path"])
    if (
        sha256_file(manager_path) != manager["tar_sha256"]
        or manager_path.stat().st_size != manager["tar_size_bytes"]
    ):
        raise PackageError("manager_tar_binding_invalid")

    executor = manifest["executor"]
    executor_path = root / str(executor["artifact_path"])
    if (
        sha256_file(executor_path) != executor["sha256"]
        or executor_path.stat().st_size != executor["size"]
    ):
        raise PackageError("executor_binding_invalid")

    for group_name in ("live_files", "source_overlay"):
        for record in manifest[group_name].values():
            path = root / str(record["artifact_path"])
            if (
                sha256_file(path) != record["sha256"]
                or path.stat().st_size != record["size"]
            ):
                raise PackageError(
                    f"runtime_binding_invalid:{record['artifact_path']}"
                )
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--output", required=True)
    build_parser.add_argument("--predecessor-source-root", required=True)
    build_parser.add_argument("--target-source-root", required=True)
    build_parser.add_argument("--predecessor-source", required=True)
    build_parser.add_argument("--target-source", required=True)
    build_parser.add_argument("--package-head", required=True)
    build_parser.add_argument("--manager-tar", required=True)
    build_parser.add_argument("--manager-image", required=True)
    build_parser.add_argument("--manager-image-id", required=True)
    build_parser.add_argument("--manager-image-size-bytes", type=int, required=True)
    build_parser.add_argument("--base-image-ref", required=True)
    build_parser.add_argument("--base-arm64-digest", required=True)
    build_parser.add_argument("--base-image-id", required=True)
    build_parser.add_argument("--executor", required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("package_root")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "build":
            document = build(args)
        else:
            document = verify(Path(args.package_root))
        print(json.dumps(document, sort_keys=True))
        return 0
    except PackageError as error:
        print(f"STOP={error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
