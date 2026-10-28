#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import tarfile
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
        "target_authority": "package_head",
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


class PackageError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manager_archive_identity(path: Path) -> dict[str, str]:
    try:
        with tarfile.open(path, "r:*") as archive:
            docker_stream = archive.extractfile("manifest.json")
            index_stream = archive.extractfile("index.json")
            if docker_stream is None or index_stream is None:
                raise PackageError("manager_archive_identity_missing")
            docker_manifest = json.loads(
                docker_stream.read().decode("utf-8")
            )
            index = json.loads(index_stream.read().decode("utf-8"))
            if (
                not isinstance(docker_manifest, list)
                or len(docker_manifest) != 1
                or not isinstance(docker_manifest[0], dict)
                or not isinstance(index, dict)
                or not isinstance(index.get("manifests"), list)
                or len(index["manifests"]) != 1
                or not isinstance(index["manifests"][0], dict)
            ):
                raise PackageError("manager_archive_identity_invalid")
            config_path = str(docker_manifest[0].get("Config", ""))
            config_prefix = "blobs/sha256/"
            if not config_path.startswith(config_prefix):
                raise PackageError("manager_archive_config_path_invalid")
            config_hex = config_path[len(config_prefix):]
            descriptor_digest = str(
                index["manifests"][0].get("digest", "")
            )
            if (
                len(config_hex) != 64
                or any(c not in "0123456789abcdef" for c in config_hex)
                or not descriptor_digest.startswith("sha256:")
                or len(descriptor_digest) != 71
            ):
                raise PackageError("manager_archive_digest_invalid")
            manifest_hex = descriptor_digest.removeprefix("sha256:")
            if any(c not in "0123456789abcdef" for c in manifest_hex):
                raise PackageError("manager_archive_digest_invalid")
            config_stream = archive.extractfile(config_path)
            manifest_path = f"blobs/sha256/{manifest_hex}"
            manifest_stream = archive.extractfile(manifest_path)
            if config_stream is None or manifest_stream is None:
                raise PackageError("manager_archive_digest_member_missing")
            config_bytes = config_stream.read()
            manifest_bytes = manifest_stream.read()
            if (
                hashlib.sha256(config_bytes).hexdigest() != config_hex
                or hashlib.sha256(manifest_bytes).hexdigest()
                != manifest_hex
            ):
                raise PackageError("manager_archive_digest_binding_invalid")
            tags = docker_manifest[0].get("RepoTags")
            if (
                not isinstance(tags, list)
                or TARGET_MANAGER_IMAGE not in tags
            ):
                raise PackageError("manager_archive_tag_binding_invalid")
            return {
                "config_digest": f"sha256:{config_hex}",
                "manifest_digest": descriptor_digest,
            }
    except (OSError, UnicodeError, json.JSONDecodeError, tarfile.TarError) as error:
        raise PackageError("manager_archive_identity_unreadable") from error


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
    package_root: Path,
    package_head: str,
    records: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, spec in records.items():
        target_authority = str(spec.get("target_authority", "target_source"))
        source_root = (
            package_root
            if target_authority == "package_head"
            else target_root
        )
        if target_authority not in {"target_source", "package_head"}:
            raise PackageError("target_authority_invalid")
        target_source = _regular(source_root, str(spec["target_source"]))
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
        copied["target_source_authority"] = target_authority
        copied["target_source_commit"] = (
            package_head
            if target_authority == "package_head"
            else TARGET_SOURCE
        )
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
    package_source = Path(args.package_source_root).resolve()
    manager_tar = Path(args.manager_tar).resolve()
    executor = Path(args.executor).resolve()
    distributions = Path(args.python_distributions).resolve()

    if output.exists() or output.is_symlink():
        raise PackageError("output_must_be_absent")
    for root, label in (
        (predecessor, "predecessor"),
        (target, "target"),
        (package_source, "package"),
    ):
        if root.is_symlink() or not root.is_dir():
            raise PackageError(f"{label}_root_invalid")
    if manager_tar.is_symlink() or not manager_tar.is_file():
        raise PackageError("manager_tar_invalid")
    if executor.is_symlink() or not executor.is_file():
        raise PackageError("executor_invalid")
    if distributions.is_symlink() or not distributions.is_file():
        raise PackageError("python_distributions_invalid")
    try:
        distribution_document = json.loads(
            distributions.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackageError("python_distributions_json_invalid") from error
    if (
        not isinstance(distribution_document, list)
        or not distribution_document
        or not all(
            isinstance(item, dict)
            and set(item) == {"name", "version"}
            and isinstance(item["name"], str)
            and bool(item["name"])
            and isinstance(item["version"], str)
            and bool(item["version"])
            for item in distribution_document
        )
    ):
        raise PackageError("python_distributions_contract_invalid")
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
    manager_archive_identity = _manager_archive_identity(artifact_manager)

    artifact_executor = output / "upgrade-executor.py"
    shutil.copyfile(executor, artifact_executor)
    os.chmod(artifact_executor, 0o755)

    artifact_distributions = output / "manager-python-distributions.json"
    shutil.copyfile(distributions, artifact_distributions)
    os.chmod(artifact_distributions, 0o644)

    live = _materialize_group(
        output=output,
        predecessor_root=predecessor,
        target_root=target,
        package_root=package_source,
        package_head=args.package_head,
        records=LIVE_FILES,
    )
    runtime_bytes = sum(
        int(record["size"])
        for record in live.values()
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
            "image_id_portable_authority": False,
            "archive_config_digest": (
                manager_archive_identity["config_digest"]
            ),
            "archive_manifest_digest": (
                manager_archive_identity["manifest_digest"]
            ),
            "image_size_bytes": args.manager_image_size_bytes,
            "platform": "linux/arm64",
            "source_dockerfile_git_blob": (
                "6486ff5fbcc23536676a48f36d67e4e0d364900a"
            ),
            "base_image_ref": BASE_IMAGE_REF,
            "base_arm64_manifest_digest": args.base_arm64_digest,
            "base_image_id": args.base_image_id,
            "historical_byte_continuity_claimed": False,
            "future_rebuild_byte_identity_claimed": False,
            "candidate_build_authority": (
                "exact_target_source_plus_frozen_arm64_base_digest"
                "_plus_installed_distribution_inventory_plus_output_identity"
            ),
            "python_distributions": {
                "artifact_path": artifact_distributions.name,
                "sha256": sha256_file(artifact_distributions),
                "size": artifact_distributions.stat().st_size,
                "count": len(distribution_document),
            },
        },
        "live_files": live,
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

    expected_files = {
        "manifest.json",
        "greenhouse-manager-arm64.tar",
        "upgrade-executor.py",
        "manager-python-distributions.json",
    }
    group = manifest.get("live_files")
    if not isinstance(group, dict):
        raise PackageError("live_files_invalid")
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
    manager_archive_identity = _manager_archive_identity(manager_path)
    if (
        manager.get("image_id_portable_authority") is not False
        or manager.get("archive_config_digest")
        != manager_archive_identity["config_digest"]
        or manager.get("archive_manifest_digest")
        != manager_archive_identity["manifest_digest"]
    ):
        raise PackageError("manager_archive_identity_binding_invalid")

    distributions = manager.get("python_distributions")
    if not isinstance(distributions, dict):
        raise PackageError("python_distributions_manifest_invalid")
    distributions_path = root / str(distributions.get("artifact_path", ""))
    if (
        distributions_path.is_symlink()
        or not distributions_path.is_file()
        or sha256_file(distributions_path) != distributions.get("sha256")
        or distributions_path.stat().st_size != distributions.get("size")
    ):
        raise PackageError("python_distributions_binding_invalid")
    try:
        distribution_document = json.loads(
            distributions_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackageError("python_distributions_json_invalid") from error
    if (
        not isinstance(distribution_document, list)
        or len(distribution_document) != distributions.get("count")
    ):
        raise PackageError("python_distributions_count_invalid")

    executor = manifest["executor"]
    executor_path = root / str(executor["artifact_path"])
    if (
        sha256_file(executor_path) != executor["sha256"]
        or executor_path.stat().st_size != executor["size"]
    ):
        raise PackageError("executor_binding_invalid")

    for name, record in manifest["live_files"].items():
        path = root / str(record["artifact_path"])
        expected_authority = (
            "package_head" if name == "dispatcher" else "target_source"
        )
        expected_commit = (
            str(manifest["package_head"])
            if expected_authority == "package_head"
            else TARGET_SOURCE
        )
        if (
            record.get("target_source_authority") != expected_authority
            or record.get("target_source_commit") != expected_commit
        ):
            raise PackageError(
                f"runtime_source_authority_invalid:{record['artifact_path']}"
            )
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
    build_parser.add_argument("--package-source-root", required=True)
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
    build_parser.add_argument("--python-distributions", required=True)
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
