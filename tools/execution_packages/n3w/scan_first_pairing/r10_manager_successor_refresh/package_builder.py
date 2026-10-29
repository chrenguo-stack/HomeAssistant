from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w.r10-manager-successor-refresh-package/1"
PREDECESSOR_SOURCE = "e299c937a7b89bb8a7b9a7432186ba46a416cd44"
TARGET_SOURCE = "ff750b3801a282af1667b5fa63481e2333e301b3"
TARGET_TREE = "ee6ee5e362628fa725d57fbdf50c6608e9032b17"
PREDECESSOR_MANAGER_IMAGE = "local/greenhouse-manager:fresh-e299c937a7b8"
TARGET_MANAGER_IMAGE = "local/greenhouse-manager:fresh-ff750b3801a2"
BASE_IMAGE_REF = "python:3.11-slim"
TARGET_DOCKERFILE_BLOB = "6486ff5fbcc23536676a48f36d67e4e0d364900a"
TARGET_COMPOSE_BLOB = "c9038251d9ba1b05a472edda14b287470690815a"
TARGET_DISCOVERY_BLOB = "ac6e3f70879f980ee9a2d37938879dc6345a511e"
PREDECESSOR_CANDIDATE_TTL_SECONDS = 30
EXPECTED_CANDIDATE_TTL_SECONDS = 60


class PackageError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_id(value: str) -> bool:
    return (
        value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _git_sha(value: str) -> bool:
    return (
        len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _normalized_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
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
    for key in sorted(sequence_fields | string_fields | mapping_fields):
        observed = value.get(key)
        if key in sequence_fields and observed is None:
            observed = []
        elif key in string_fields and observed is None:
            observed = ""
        elif key in mapping_fields and observed is None:
            observed = {}
        result[key] = observed
    return result


def _manager_archive_identity(path: Path) -> dict[str, Any]:
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
            if not config_path.startswith("blobs/sha256/"):
                raise PackageError("manager_archive_config_path_invalid")
            config_hex = config_path.removeprefix("blobs/sha256/")
            descriptor_digest = str(index["manifests"][0].get("digest", ""))
            if (
                len(config_hex) != 64
                or any(c not in "0123456789abcdef" for c in config_hex)
                or not _sha256_id(descriptor_digest)
            ):
                raise PackageError("manager_archive_digest_invalid")
            manifest_hex = descriptor_digest.removeprefix("sha256:")
            config_stream = archive.extractfile(config_path)
            manifest_path = f"blobs/sha256/{manifest_hex}"
            manifest_stream = archive.extractfile(manifest_path)
            if config_stream is None or manifest_stream is None:
                raise PackageError("manager_archive_digest_member_missing")
            config_bytes = config_stream.read()
            manifest_bytes = manifest_stream.read()
            if (
                hashlib.sha256(config_bytes).hexdigest() != config_hex
                or hashlib.sha256(manifest_bytes).hexdigest() != manifest_hex
            ):
                raise PackageError("manager_archive_digest_binding_invalid")
            try:
                config_document = json.loads(config_bytes.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as error:
                raise PackageError("manager_archive_config_invalid") from error
            if not isinstance(config_document, dict):
                raise PackageError("manager_archive_config_invalid")
            rootfs = config_document.get("rootfs")
            diff_ids = rootfs.get("diff_ids") if isinstance(rootfs, dict) else None
            if (
                not isinstance(diff_ids, list)
                or not diff_ids
                or not all(
                    isinstance(item, str)
                    and _sha256_id(item)
                    for item in diff_ids
                )
            ):
                raise PackageError("manager_archive_rootfs_invalid")
            config_contract = _image_config_contract(
                config_document.get("config")
            )
            tags = docker_manifest[0].get("RepoTags")
            if (
                not isinstance(tags, list)
                or TARGET_MANAGER_IMAGE not in tags
            ):
                raise PackageError("manager_archive_tag_binding_invalid")
            return {
                "config_digest": f"sha256:{config_hex}",
                "manifest_digest": descriptor_digest,
                "rootfs_layers_sha256": _normalized_hash(diff_ids),
                "config_contract_sha256": _normalized_hash(config_contract),
            }
    except (OSError, UnicodeError, json.JSONDecodeError, tarfile.TarError) as error:
        raise PackageError("manager_archive_identity_unreadable") from error


def _copy_exact(source: Path, target: Path, mode: int) -> dict[str, Any]:
    if source.is_symlink() or not source.is_file():
        raise PackageError(f"source_invalid:{source.name}")
    if target.exists() or target.is_symlink():
        raise PackageError(f"artifact_exists:{target.name}")
    shutil.copyfile(source, target)
    os.chmod(target, mode)
    return {
        "artifact_path": target.name,
        "sha256": sha256_file(target),
        "size": target.stat().st_size,
        "mode": mode,
    }


def _load_distributions(path: Path) -> list[dict[str, str]]:
    if path.is_symlink() or not path.is_file():
        raise PackageError("python_distributions_invalid")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackageError("python_distributions_json_invalid") from error
    if (
        not isinstance(value, list)
        or not value
        or not all(
            isinstance(item, dict)
            and set(item) == {"name", "version"}
            and isinstance(item["name"], str)
            and bool(item["name"])
            and isinstance(item["version"], str)
            and bool(item["version"])
            for item in value
        )
    ):
        raise PackageError("python_distributions_contract_invalid")
    return value


def build(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output).resolve()
    manager_tar = Path(args.manager_tar).resolve()
    executor = Path(args.executor).resolve()
    distributions = Path(args.python_distributions).resolve()

    if output.exists() or output.is_symlink():
        raise PackageError("output_must_be_absent")
    if manager_tar.is_symlink() or not manager_tar.is_file():
        raise PackageError("manager_tar_invalid")
    if executor.is_symlink() or not executor.is_file():
        raise PackageError("executor_invalid")
    distribution_document = _load_distributions(distributions)

    if args.predecessor_source != PREDECESSOR_SOURCE:
        raise PackageError("predecessor_source_invalid")
    if args.target_source != TARGET_SOURCE:
        raise PackageError("target_source_invalid")
    if args.target_tree != TARGET_TREE:
        raise PackageError("target_tree_invalid")
    if args.manager_image != TARGET_MANAGER_IMAGE:
        raise PackageError("manager_image_invalid")
    if args.base_image_ref != BASE_IMAGE_REF:
        raise PackageError("base_image_ref_invalid")
    if args.candidate_ttl_seconds != EXPECTED_CANDIDATE_TTL_SECONDS:
        raise PackageError("candidate_ttl_invalid")
    if not _git_sha(args.package_head):
        raise PackageError("package_head_invalid")
    for label, value in (
        ("base_arm64_digest", args.base_arm64_digest),
        ("base_image_id", args.base_image_id),
        ("manager_image_id", args.manager_image_id),
    ):
        if not _sha256_id(value):
            raise PackageError(f"{label}_invalid")

    output.mkdir(mode=0o755)

    manager = output / "greenhouse-manager-arm64.tar"
    manager_binding = _copy_exact(manager_tar, manager, 0o644)
    archive_identity = _manager_archive_identity(manager)

    refresh = output / "refresh-executor.py"
    refresh_binding = _copy_exact(executor, refresh, 0o755)

    inventory = output / "manager-python-distributions.json"
    inventory_binding = _copy_exact(distributions, inventory, 0o644)

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "package_head": args.package_head,
        "product_authority": {
            "predecessor_source": PREDECESSOR_SOURCE,
            "target_source": TARGET_SOURCE,
            "target_tree": TARGET_TREE,
            "manager_discovery_blob": TARGET_DISCOVERY_BLOB,
            "dockerfile_blob": TARGET_DOCKERFILE_BLOB,
            "compose_blob": TARGET_COMPOSE_BLOB,
            "predecessor_candidate_ttl_seconds": PREDECESSOR_CANDIDATE_TTL_SECONDS,
            "candidate_ttl_seconds": EXPECTED_CANDIDATE_TTL_SECONDS,
        },
        "predecessor_manager_image": PREDECESSOR_MANAGER_IMAGE,
        "target_manager_image": TARGET_MANAGER_IMAGE,
        "manager": {
            **manager_binding,
            "image_id": args.manager_image_id,
            "image_id_portable_authority": False,
            "archive_config_digest": archive_identity["config_digest"],
            "archive_manifest_digest": archive_identity["manifest_digest"],
            "rootfs_layers_sha256": archive_identity["rootfs_layers_sha256"],
            "config_contract_sha256": archive_identity["config_contract_sha256"],
            "image_size_bytes": args.manager_image_size_bytes,
            "platform": "linux/arm64",
            "base_image_ref": BASE_IMAGE_REF,
            "base_arm64_manifest_digest": args.base_arm64_digest,
            "base_image_id": args.base_image_id,
            "python_distributions": {
                **inventory_binding,
                "count": len(distribution_document),
            },
            "candidate_build_authority": (
                "exact_integrated_product_source_plus_pinned_arm64_base_digest"
                "_plus_installed_distribution_inventory_plus_archive_identity"
            ),
        },
        "executor": refresh_binding,
        "protected_runtime": {
            "compose_file_must_remain_unchanged": True,
            "registration_tls_must_remain_unchanged": True,
            "broker_dynsec_must_remain_unchanged": True,
            "broker_container_must_remain_continuous": True,
            "homeassistant_image_and_data_must_remain_unchanged": True,
            "manager_database_business_state_must_remain_unchanged": True,
            "pairing_window_must_remain_closed": True,
            "tcp_47112_must_remain_closed": True,
        },
        "policy": {
            "secret_values_included": False,
            "broker_image_included": False,
            "homeassistant_image_included": False,
            "registration_tls_included": False,
            "compose_file_included": False,
            "t1_access": False,
            "t1_mutation": False,
            "board_access": False,
            "live_authorization_granted": False,
            "old_candidate_upgrade_authorization_reusable": False,
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

    if manifest.get("schema") != SCHEMA:
        raise PackageError("manifest_schema_invalid")
    authority = manifest.get("product_authority")
    if (
        not isinstance(authority, dict)
        or authority.get("predecessor_source") != PREDECESSOR_SOURCE
        or authority.get("target_source") != TARGET_SOURCE
        or authority.get("target_tree") != TARGET_TREE
        or authority.get("manager_discovery_blob") != TARGET_DISCOVERY_BLOB
        or authority.get("dockerfile_blob") != TARGET_DOCKERFILE_BLOB
        or authority.get("compose_blob") != TARGET_COMPOSE_BLOB
        or authority.get("predecessor_candidate_ttl_seconds")
        != PREDECESSOR_CANDIDATE_TTL_SECONDS
        or authority.get("candidate_ttl_seconds")
        != EXPECTED_CANDIDATE_TTL_SECONDS
    ):
        raise PackageError("product_authority_invalid")
    if (
        manifest.get("predecessor_manager_image") != PREDECESSOR_MANAGER_IMAGE
        or manifest.get("target_manager_image") != TARGET_MANAGER_IMAGE
    ):
        raise PackageError("manager_image_contract_invalid")

    policy = manifest.get("policy")
    if (
        not isinstance(policy, dict)
        or policy.get("secret_values_included") is not False
        or policy.get("broker_image_included") is not False
        or policy.get("homeassistant_image_included") is not False
        or policy.get("registration_tls_included") is not False
        or policy.get("compose_file_included") is not False
        or policy.get("t1_access") is not False
        or policy.get("t1_mutation") is not False
        or policy.get("board_access") is not False
        or policy.get("live_authorization_granted") is not False
        or policy.get("old_candidate_upgrade_authorization_reusable") is not False
    ):
        raise PackageError("package_policy_invalid")

    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    expected = {
        "manifest.json",
        "greenhouse-manager-arm64.tar",
        "refresh-executor.py",
        "manager-python-distributions.json",
    }
    if actual != expected:
        raise PackageError("package_file_set_invalid")

    manager_record = manifest.get("manager")
    if not isinstance(manager_record, dict):
        raise PackageError("manager_manifest_invalid")
    manager_path = root / str(manager_record.get("artifact_path", ""))
    if (
        manager_path.is_symlink()
        or not manager_path.is_file()
        or sha256_file(manager_path) != manager_record.get("sha256")
        or manager_path.stat().st_size != manager_record.get("size")
    ):
        raise PackageError("manager_tar_binding_invalid")
    archive_identity = _manager_archive_identity(manager_path)
    if (
        manager_record.get("image_id_portable_authority") is not False
        or manager_record.get("archive_config_digest")
        != archive_identity["config_digest"]
        or manager_record.get("archive_manifest_digest")
        != archive_identity["manifest_digest"]
        or manager_record.get("rootfs_layers_sha256")
        != archive_identity["rootfs_layers_sha256"]
        or manager_record.get("config_contract_sha256")
        != archive_identity["config_contract_sha256"]
        or manager_record.get("platform") != "linux/arm64"
    ):
        raise PackageError("manager_archive_identity_binding_invalid")

    inventory = manager_record.get("python_distributions")
    if not isinstance(inventory, dict):
        raise PackageError("python_distributions_manifest_invalid")
    inventory_path = root / str(inventory.get("artifact_path", ""))
    if (
        inventory_path.is_symlink()
        or not inventory_path.is_file()
        or sha256_file(inventory_path) != inventory.get("sha256")
        or inventory_path.stat().st_size != inventory.get("size")
    ):
        raise PackageError("python_distributions_binding_invalid")
    distribution_document = _load_distributions(inventory_path)
    if len(distribution_document) != inventory.get("count"):
        raise PackageError("python_distributions_count_invalid")

    executor = manifest.get("executor")
    if not isinstance(executor, dict):
        raise PackageError("executor_manifest_invalid")
    executor_path = root / str(executor.get("artifact_path", ""))
    if (
        executor_path.is_symlink()
        or not executor_path.is_file()
        or sha256_file(executor_path) != executor.get("sha256")
        or executor_path.stat().st_size != executor.get("size")
    ):
        raise PackageError("executor_binding_invalid")
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser("build")
    build_parser.add_argument("--output", required=True)
    build_parser.add_argument("--package-head", required=True)
    build_parser.add_argument("--predecessor-source", required=True)
    build_parser.add_argument("--target-source", required=True)
    build_parser.add_argument("--target-tree", required=True)
    build_parser.add_argument("--manager-tar", required=True)
    build_parser.add_argument("--manager-image", required=True)
    build_parser.add_argument("--manager-image-id", required=True)
    build_parser.add_argument("--manager-image-size-bytes", type=int, required=True)
    build_parser.add_argument("--base-image-ref", required=True)
    build_parser.add_argument("--base-arm64-digest", required=True)
    build_parser.add_argument("--base-image-id", required=True)
    build_parser.add_argument("--python-distributions", required=True)
    build_parser.add_argument("--executor", required=True)
    build_parser.add_argument("--candidate-ttl-seconds", type=int, required=True)

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
