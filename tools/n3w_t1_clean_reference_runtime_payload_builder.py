#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any

SOURCE_RE = re.compile(r"[0-9a-f]{40}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
S1_SCHEMA = "gh.n3w.t1-fresh-exact-arm64-binding/1"
PAYLOAD_SCHEMA = "gh.n3w-t1-fresh-bootstrap-payload/1"
TRANSPORT_SCHEMA = "gh.n3w-t1-fresh-transport/2"
CAPACITY_SCHEMA = "gh.n3w-t1-fresh-capacity/1"
IMAGE_LOCK_SCHEMA = "gh.n3w-t1-fresh-production-image-lock/1"
RUNTIME_BINDING_SCHEMA = "gh.n3w-t1-clean-reference-runtime-binding/1"
MIN_POST_PEAK_FREE_BYTES = 5 * 1024 * 1024 * 1024

IMAGE_FILES = {
    "manager": "greenhouse-manager-arm64.tar",
    "homeassistant": "homeassistant-arm64.tar",
    "broker": "broker-arm64.tar",
}
IMAGE_ORDER = ("homeassistant", "manager", "broker")
S1_FILES = frozenset({"binding.json", *IMAGE_FILES.values()})
BASE_FILES = frozenset(
    {
        "runtime-payload.tar.gz",
        "runtime-payload.sha256",
        "payload-manifest.sha256",
        "capacity-contract.json",
        "capacity-contract.sha256",
        "homeassistant-arm64.tar",
        "greenhouse-manager-arm64.tar",
        "broker-arm64.tar",
        "executor.sha256",
        "host-wrapper.py",
        "host-wrapper.sha256",
        "host-baseline.py",
        "host-baseline.sha256",
    }
)
OUTPUT_FILES = frozenset(
    {
        "runtime-payload.tar.gz",
        "runtime-payload.sha256",
        "payload-manifest.sha256",
        "capacity-contract.json",
        "capacity-contract.sha256",
        "executor.sha256",
        "host-wrapper.py",
        "host-wrapper.sha256",
        "host-baseline.py",
        "host-baseline.sha256",
        "runtime-binding.json",
    }
)
CONFIG_KEYS = (
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
)


class CleanReferenceRuntimeBuildError(RuntimeError):
    pass


class Runner:
    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float = 1800.0,
        allowed: frozenset[int] = frozenset({0}),
    ) -> str:
        completed = subprocess.run(
            tuple(argv),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if completed.returncode not in allowed:
            reason = completed.stderr.strip() or completed.stdout.strip()
            raise CleanReferenceRuntimeBuildError(
                f"command_failed:{Path(argv[0]).name}:{completed.returncode}:{reason[:400]}"
            )
        return completed.stdout.strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _normalized_hash(value: Any) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _read_json(path: Path, error_code: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CleanReferenceRuntimeBuildError(error_code)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CleanReferenceRuntimeBuildError(error_code) from error
    if not isinstance(value, dict):
        raise CleanReferenceRuntimeBuildError(error_code)
    return value


def _read_sidecar(path: Path, error_code: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise CleanReferenceRuntimeBuildError(error_code)
    value = path.read_text(encoding="ascii").strip()
    if SHA256_RE.fullmatch(value) is None:
        raise CleanReferenceRuntimeBuildError(error_code)
    return value


def _exact_files(root: Path, expected: frozenset[str], error_code: str) -> None:
    if root.is_symlink() or not root.is_dir():
        raise CleanReferenceRuntimeBuildError(error_code)
    actual = {path.name for path in root.iterdir()}
    if actual != expected:
        raise CleanReferenceRuntimeBuildError(error_code)
    for path in root.iterdir():
        if path.is_symlink() or not path.is_file():
            raise CleanReferenceRuntimeBuildError(error_code)


def _config_contract(config: Any) -> dict[str, Any]:
    value = config if isinstance(config, dict) else {}
    result: dict[str, Any] = {}
    sequence_fields = {"Entrypoint", "Cmd", "Env"}
    string_fields = {"User", "WorkingDir", "StopSignal"}
    mapping_fields = {"Labels", "Healthcheck", "Volumes", "ExposedPorts"}
    for key in CONFIG_KEYS:
        observed = value.get(key)
        if key in sequence_fields and observed is None:
            observed = []
        elif key in string_fields and observed is None:
            observed = ""
        elif key in mapping_fields and observed is None:
            observed = {}
        result[key] = observed
    return result


def _normalize_tar_name(value: str, error_code: str) -> str:
    if not value or "\x00" in value or "\\" in value or value.startswith("/"):
        raise CleanReferenceRuntimeBuildError(error_code)
    normalized = value
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized in {"", "."}:
        return ""
    path = PurePosixPath(normalized)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise CleanReferenceRuntimeBuildError(error_code)
    if path.as_posix() != normalized:
        raise CleanReferenceRuntimeBuildError(error_code)
    return normalized


def _safe_extract_runtime(archive: Path, destination: Path) -> None:
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            seen: set[str] = set()
            for member in bundle.getmembers():
                name = _normalize_tar_name(
                    member.name,
                    "runtime_archive_member_invalid",
                )
                if not name:
                    if member.isdir():
                        continue
                    raise CleanReferenceRuntimeBuildError(
                        "runtime_archive_member_invalid"
                    )
                if name in seen or member.issym() or member.islnk():
                    raise CleanReferenceRuntimeBuildError(
                        "runtime_archive_member_invalid"
                    )
                seen.add(name)
                target = destination / name
                resolved_parent = target.parent.resolve()
                if destination.resolve() not in {
                    resolved_parent,
                    *resolved_parent.parents,
                }:
                    raise CleanReferenceRuntimeBuildError(
                        "runtime_archive_path_escape"
                    )
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    raise CleanReferenceRuntimeBuildError(
                        "runtime_archive_member_invalid"
                    )
                target.parent.mkdir(parents=True, exist_ok=True)
                stream = bundle.extractfile(member)
                if stream is None:
                    raise CleanReferenceRuntimeBuildError(
                        "runtime_archive_member_unreadable"
                    )
                with target.open("wb") as output:
                    shutil.copyfileobj(stream, output, length=1024 * 1024)
    except tarfile.TarError as error:
        raise CleanReferenceRuntimeBuildError("runtime_archive_invalid") from error


def _manifest_from_runtime(root: Path) -> dict[str, Any]:
    path = root / "payload-manifest.json"
    return _read_json(path, "payload_manifest_invalid")


def _verify_base(root: Path, source_head: str) -> tuple[Path, dict[str, Any]]:
    _exact_files(root, BASE_FILES, "base_deployable_file_set_invalid")
    runtime = root / "runtime-payload.tar.gz"
    if _sha256_file(runtime) != _read_sidecar(
        root / "runtime-payload.sha256",
        "base_runtime_sidecar_invalid",
    ):
        raise CleanReferenceRuntimeBuildError("base_runtime_sha256_mismatch")
    for name in ("host-wrapper.py", "host-baseline.py"):
        if _sha256_file(root / name) != _read_sidecar(
            root / name.replace(".py", ".sha256"),
            f"base_{name}_sidecar_invalid",
        ):
            raise CleanReferenceRuntimeBuildError(f"base_{name}_sha256_mismatch")
    temporary = Path(tempfile.mkdtemp(prefix="n3w-clean-reference-base."))
    try:
        _safe_extract_runtime(runtime, temporary)
        manifest = _manifest_from_runtime(temporary)
        manifest_bytes = (temporary / "payload-manifest.json").read_bytes()
        if _sha256_bytes(manifest_bytes) != _read_sidecar(
            root / "payload-manifest.sha256",
            "base_manifest_sidecar_invalid",
        ):
            raise CleanReferenceRuntimeBuildError("base_manifest_sha256_mismatch")
        if (
            manifest.get("schema") != PAYLOAD_SCHEMA
            or manifest.get("source_head") != source_head
        ):
            raise CleanReferenceRuntimeBuildError("base_source_binding_invalid")
        if manifest.get("production_service_start") is not False:
            raise CleanReferenceRuntimeBuildError("base_service_boundary_invalid")
        if manifest.get("secret_values_included") is not False:
            raise CleanReferenceRuntimeBuildError("base_secret_boundary_invalid")
        return temporary, manifest
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _verify_s1(root: Path, source_head: str) -> dict[str, Any]:
    _exact_files(root, S1_FILES, "s1_image_file_set_invalid")
    binding = _read_json(root / "binding.json", "s1_binding_invalid")
    if (
        binding.get("schema") != S1_SCHEMA
        or binding.get("source_head") != source_head
        or binding.get("fresh_runtime_identity_binding") is not True
        or binding.get("node_credential_count") != 0
        or binding.get("production_service_start") is not False
        or binding.get("secret_values_included") is not False
        or binding.get("t1_access") is not False
        or binding.get("board_access") is not False
    ):
        raise CleanReferenceRuntimeBuildError("s1_binding_contract_invalid")
    for label, filename in IMAGE_FILES.items():
        record = binding.get(label)
        if not isinstance(record, dict):
            raise CleanReferenceRuntimeBuildError(f"s1_image_record_invalid:{label}")
        path = root / filename
        if (
            record.get("platform") != "linux/arm64"
            or path.stat().st_size != record.get("tar_size_bytes")
            or _sha256_file(path) != record.get("tar_sha256")
        ):
            raise CleanReferenceRuntimeBuildError(f"s1_image_binding_invalid:{label}")
    manager = binding["manager"]
    if manager.get("image") != f"local/greenhouse-manager:fresh-{source_head[:12]}":
        raise CleanReferenceRuntimeBuildError("s1_manager_image_invalid")
    homeassistant = binding["homeassistant"]
    if (
        homeassistant.get("image")
        != "local/n3w-homeassistant:2026.10.0-0c73235a"
        or homeassistant.get("manifest_digest")
        != "sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4"
    ):
        raise CleanReferenceRuntimeBuildError("s1_homeassistant_identity_invalid")
    broker = binding["broker"]
    if (
        broker.get("image") != "local/n3w-mosquitto:2.1.2-3184566d"
        or broker.get("manifest_digest")
        != "sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549"
    ):
        raise CleanReferenceRuntimeBuildError("s1_broker_identity_invalid")
    return binding


def _docker_archive_binding(path: Path, image_ref: str) -> dict[str, Any]:
    try:
        with tarfile.open(path, "r:*") as bundle:
            manifest_member = bundle.getmember("manifest.json")
            stream = bundle.extractfile(manifest_member)
            if stream is None or not manifest_member.isfile():
                raise CleanReferenceRuntimeBuildError(
                    "docker_archive_manifest_invalid"
                )
            manifest_bytes = stream.read()
            manifest = json.loads(manifest_bytes)
            matches = [
                item
                for item in manifest
                if isinstance(item, dict)
                and image_ref in (item.get("RepoTags") or [])
            ]
            if len(matches) != 1:
                raise CleanReferenceRuntimeBuildError(
                    "docker_archive_tag_binding_invalid"
                )
            selected = matches[0]
            config_path = selected.get("Config")
            if not isinstance(config_path, str):
                raise CleanReferenceRuntimeBuildError(
                    "docker_archive_config_invalid"
                )
            config_member = bundle.getmember(config_path)
            config_stream = bundle.extractfile(config_member)
            if config_stream is None or not config_member.isfile():
                raise CleanReferenceRuntimeBuildError(
                    "docker_archive_config_invalid"
                )
            config_bytes = config_stream.read()
            config_digest = _sha256_bytes(config_bytes)
            if Path(config_path).name.removesuffix(".json") != config_digest:
                raise CleanReferenceRuntimeBuildError(
                    "docker_archive_config_path_mismatch"
                )
            document = json.loads(config_bytes)
            rootfs = document.get("rootfs")
            diff_ids = rootfs.get("diff_ids") if isinstance(rootfs, dict) else None
            if not isinstance(diff_ids, list) or not diff_ids:
                raise CleanReferenceRuntimeBuildError(
                    "docker_archive_rootfs_invalid"
                )
            contract = _config_contract(document.get("config"))
            return {
                "config_digest": "sha256:" + config_digest,
                "config_contract": contract,
                "config_contract_sha256": _normalized_hash(contract),
                "rootfs_layers_sha256": _normalized_hash(diff_ids),
                "docker_archive_manifest_sha256": _sha256_bytes(manifest_bytes),
                "docker_archive_record_sha256": _normalized_hash(selected),
            }
    except (KeyError, json.JSONDecodeError, tarfile.TarError) as error:
        raise CleanReferenceRuntimeBuildError("docker_archive_invalid") from error


def _inspect_exact_images(
    image_root: Path,
    binding: dict[str, Any],
    runner: Runner,
) -> dict[str, dict[str, Any]]:
    images: dict[str, dict[str, Any]] = {}
    for label in ("manager", "homeassistant", "broker"):
        source_record = binding[label]
        image = str(source_record["image"])
        tar_path = image_root / IMAGE_FILES[label]
        runner.run(("docker", "load", "--input", str(tar_path)))
        try:
            inspected = json.loads(
                runner.run(("docker", "image", "inspect", image))
            )
        except json.JSONDecodeError as error:
            raise CleanReferenceRuntimeBuildError(
                f"image_inspect_invalid:{label}"
            ) from error
        if (
            not isinstance(inspected, list)
            or len(inspected) != 1
            or not isinstance(inspected[0], dict)
        ):
            raise CleanReferenceRuntimeBuildError(
                f"image_inspect_invalid:{label}"
            )
        item = inspected[0]
        if (
            item.get("Id") != source_record.get("image_id")
            or item.get("Architecture") != "arm64"
            or item.get("Os") != "linux"
        ):
            raise CleanReferenceRuntimeBuildError(
                f"image_runtime_identity_invalid:{label}"
            )
        rootfs = item.get("RootFS")
        layers = rootfs.get("Layers") if isinstance(rootfs, dict) else None
        if not isinstance(layers, list) or not layers:
            raise CleanReferenceRuntimeBuildError(
                f"image_runtime_rootfs_invalid:{label}"
            )
        archive = _docker_archive_binding(tar_path, image)
        if archive["config_digest"] != source_record["image_id"]:
            raise CleanReferenceRuntimeBuildError(
                f"image_archive_config_drift:{label}"
            )
        runtime_contract = _config_contract(item.get("Config"))
        if archive["config_contract_sha256"] != _normalized_hash(runtime_contract):
            raise CleanReferenceRuntimeBuildError(
                f"image_archive_config_contract_drift:{label}"
            )
        if archive["rootfs_layers_sha256"] != _normalized_hash(layers):
            raise CleanReferenceRuntimeBuildError(
                f"image_archive_rootfs_drift:{label}"
            )
        record = {
            "image": image,
            "image_id": source_record["image_id"],
            "platform": "linux/arm64",
            "artifact_file": IMAGE_FILES[label],
            "path": f"incoming/{IMAGE_FILES[label]}",
            "tar_sha256": source_record["tar_sha256"],
            "tar_size_bytes": source_record["tar_size_bytes"],
            "loaded_size_bytes": int(item["Size"]),
            **{key: value for key, value in archive.items() if key != "config_contract"},
        }
        images[label] = record
    return images


def _image_lock(
    source_head: str,
    binding: dict[str, Any],
    images: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": IMAGE_LOCK_SCHEMA,
        "source_head": source_head,
        "manager": {
            "source_sha": source_head,
            "image": images["manager"]["image"],
            "image_id": images["manager"]["image_id"],
            "tar_sha256": images["manager"]["tar_sha256"],
            "platform": "linux/arm64",
            "entrypoint": ["greenhouse-manager"],
            "user": "greenhouse",
            "runtime_uid": 999,
            "runtime_gid": 999,
            "pull_policy": "never",
        },
        "homeassistant": {
            "source_ref": "ghcr.io/home-assistant/home-assistant:2026.10.0",
            "image": images["homeassistant"]["image"],
            "manifest_digest": binding["homeassistant"]["manifest_digest"],
            "image_id": images["homeassistant"]["image_id"],
            "platform": "linux/arm64",
            "entrypoint": ["/init"],
            "effective_default_uid": 0,
            "effective_default_gid": 0,
            "pull_policy": "never",
        },
        "broker": {
            "source_ref": "m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine",
            "image": images["broker"]["image"],
            "manifest_digest": binding["broker"]["manifest_digest"],
            "image_id": images["broker"]["image_id"],
            "platform": "linux/arm64",
            "entrypoint": ["/docker-entrypoint.sh"],
            "pull_policy": "never",
        },
    }


def _verify_runtime_files(root: Path, manifest: dict[str, Any]) -> int:
    records = manifest.get("files")
    if not isinstance(records, list):
        raise CleanReferenceRuntimeBuildError("runtime_file_records_invalid")
    total = 0
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {"path", "sha256", "size"}:
            raise CleanReferenceRuntimeBuildError("runtime_file_record_invalid")
        relative = str(record["path"])
        if relative in seen:
            raise CleanReferenceRuntimeBuildError("runtime_file_record_duplicate")
        seen.add(relative)
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise CleanReferenceRuntimeBuildError("runtime_file_missing")
        if (
            path.stat().st_size != record["size"]
            or _sha256_file(path) != record["sha256"]
        ):
            raise CleanReferenceRuntimeBuildError("runtime_file_binding_invalid")
        total += int(record["size"])
    return total


def _write_runtime_tar(root: Path, destination: Path) -> None:
    with tarfile.open(destination, "w:gz") as bundle:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            bundle.add(path, arcname=relative, recursive=False)


def build_runtime_bundle(
    base_root: Path,
    image_root: Path,
    destination: Path,
    *,
    source_head: str,
    runner: Runner | None = None,
) -> dict[str, Any]:
    if SOURCE_RE.fullmatch(source_head) is None:
        raise CleanReferenceRuntimeBuildError("source_head_invalid")
    if destination.exists() or destination.is_symlink():
        raise CleanReferenceRuntimeBuildError("destination_already_exists")
    active = runner or Runner()
    extracted, base_manifest = _verify_base(base_root.resolve(), source_head)
    try:
        binding = _verify_s1(image_root.resolve(), source_head)
        images = _inspect_exact_images(image_root.resolve(), binding, active)
        data_size = _verify_runtime_files(extracted, base_manifest)
        transport_images: dict[str, dict[str, Any]] = {}
        for label, record in images.items():
            required = (
                int(record["tar_size_bytes"])
                + int(record["loaded_size_bytes"])
                + MIN_POST_PEAK_FREE_BYTES
            )
            record["required_free_bytes"] = required
            transport_images[label] = {
                "path": record["path"],
                "artifact_file": record["artifact_file"],
                "tar_sha256": record["tar_sha256"],
                "tar_size_bytes": record["tar_size_bytes"],
                "loaded_size_bytes": record["loaded_size_bytes"],
                "required_free_bytes": required,
                "image_ref": record["image"],
            }
        manifest = {
            "schema": PAYLOAD_SCHEMA,
            "source_head": source_head,
            "authorization_id": base_manifest.get("authorization_id"),
            "authorization_claimed": False,
            "authorization_consumed": False,
            "images": images,
            "image_lock": _image_lock(source_head, binding, images),
            "files": base_manifest["files"],
            "transport": {
                "schema": TRANSPORT_SCHEMA,
                "remote_staging_root": "/var/tmp",
                "minimum_post_peak_free_bytes": MIN_POST_PEAK_FREE_BYTES,
                "runtime_payload_uncompressed_bytes": 0,
                "image_load_order": list(IMAGE_ORDER),
                "images": transport_images,
            },
            "secret_values_included": False,
            "production_service_start": False,
            "activation_authorized": False,
            "board_access": False,
        }
        for _ in range(8):
            encoded = (
                json.dumps(manifest, sort_keys=True, indent=2) + "\n"
            ).encode("utf-8")
            total = data_size + len(encoded)
            if manifest["transport"]["runtime_payload_uncompressed_bytes"] == total:
                break
            manifest["transport"]["runtime_payload_uncompressed_bytes"] = total
        else:
            raise CleanReferenceRuntimeBuildError(
                "runtime_payload_size_did_not_converge"
            )
        manifest_path = extracted / "payload-manifest.json"
        manifest_path.write_bytes(
            (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
        )

        destination.mkdir(parents=True, mode=0o700)
        runtime_tar = destination / "runtime-payload.tar.gz"
        _write_runtime_tar(extracted, runtime_tar)
        runtime_sha = _sha256_file(runtime_tar)
        manifest_sha = _sha256_file(manifest_path)
        (destination / "runtime-payload.sha256").write_text(
            runtime_sha + "\n", encoding="ascii"
        )
        (destination / "payload-manifest.sha256").write_text(
            manifest_sha + "\n", encoding="ascii"
        )

        capacity = {
            "schema": CAPACITY_SCHEMA,
            "source_head": source_head,
            "minimum_post_peak_free_bytes": MIN_POST_PEAK_FREE_BYTES,
            "image_load_order": list(IMAGE_ORDER),
            "images": transport_images,
        }
        capacity_bytes = (
            json.dumps(capacity, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        (destination / "capacity-contract.json").write_bytes(capacity_bytes)
        (destination / "capacity-contract.sha256").write_text(
            _sha256_bytes(capacity_bytes) + "\n",
            encoding="ascii",
        )

        for name in ("host-wrapper.py", "host-wrapper.sha256", "host-baseline.py", "host-baseline.sha256"):
            shutil.copy2(base_root / name, destination / name)
        executor = extracted / "tools/n3w_t1_fresh_product_bootstrap.py"
        (destination / "executor.sha256").write_text(
            _sha256_file(executor) + "\n",
            encoding="ascii",
        )

        binding_document = {
            "schema": RUNTIME_BINDING_SCHEMA,
            "source_head": source_head,
            "s1_binding_sha256": _sha256_file(image_root / "binding.json"),
            "runtime_payload_sha256": runtime_sha,
            "payload_manifest_sha256": manifest_sha,
            "images": {
                label: {
                    "image": images[label]["image"],
                    "image_id": images[label]["image_id"],
                    "tar_sha256": images[label]["tar_sha256"],
                    "tar_size_bytes": images[label]["tar_size_bytes"],
                    "platform": "linux/arm64",
                }
                for label in ("manager", "homeassistant", "broker")
            },
            "image_rebuild_performed": False,
            "registry_pull_performed": False,
            "production_service_start": False,
            "t1_access": False,
            "board_access": False,
        }
        (destination / "runtime-binding.json").write_text(
            json.dumps(binding_document, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        _exact_files(destination, OUTPUT_FILES, "runtime_output_file_set_invalid")
        return {
            "schema": RUNTIME_BINDING_SCHEMA,
            "status": "PASS",
            "source_head": source_head,
            "runtime_payload_sha256": runtime_sha,
            "payload_manifest_sha256": manifest_sha,
            "s1_binding_sha256": binding_document["s1_binding_sha256"],
            "manager_image_id": images["manager"]["image_id"],
            "image_rebuild_performed": False,
            "registry_pull_performed": False,
            "production_service_start": False,
            "t1_access": False,
            "board_access": False,
        }
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(extracted, ignore_errors=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source-head", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        report = build_runtime_bundle(
            args.base_root,
            args.image_root,
            args.destination,
            source_head=args.source_head,
        )
    except (CleanReferenceRuntimeBuildError, OSError, subprocess.SubprocessError) as error:
        print(
            json.dumps(
                {
                    "schema": RUNTIME_BINDING_SCHEMA,
                    "status": "STOP",
                    "reason": str(error)[:400],
                    "image_rebuild_performed": False,
                    "registry_pull_performed": False,
                    "production_service_start": False,
                    "t1_access": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
