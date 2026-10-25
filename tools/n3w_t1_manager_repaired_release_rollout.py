#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from n3w_t1_production_v2_contract import (
    REQUIRED_RELEASE_ARTIFACTS,
    canonical_json_bytes,
    validate_release,
)
from n3w_t1_ssh_transport import (
    SSHTransport,
    SSHTransportError,
)

SCHEMA = "gh.n3w-t1-manager-repaired-release-rollout-host/1"
LOCAL_BINDING_SCHEMA = "gh.n3w-t1-f5-v2-local-release-binding/1"
FINAL_WORKFLOW = ".github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml"
FINAL_PREFIX = "n3w-t1-f5-v2-exact-production-release-"
RELEASE_ROOT = "n3w-t1-f5-v2-release"
RELEASE_MANIFEST = "release.json"
RELEASE_SHA = "release.sha256"
FINAL_TAR = "n3w-t1-f5-v2-release.tar.gz"
FINAL_TAR_SHA = "n3w-t1-f5-v2-release.tar.gz.sha256"
F3_IMAGE_FILES = {
    "broker-arm64.tar",
    "greenhouse-manager-arm64.tar",
    "homeassistant-arm64.tar",
    "image-set.json",
}
F3_PAYLOAD_FILES = {
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
}
SHA256_RE = re.compile(r"[0-9a-f]{64}")
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
CONFIRMATION = "APPLY MANAGER REPAIRED RELEASE: YES"
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


class RolloutHostError(RuntimeError):
    pass


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(block)
    return digest.hexdigest()


def _sha_text(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _normalized_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RolloutHostError(
            "json_file_invalid:" + path.name
        )
    try:
        value = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as error:
        raise RolloutHostError(
            "json_invalid:" + path.name
        ) from error
    if not isinstance(value, dict):
        raise RolloutHostError(
            "json_invalid:" + path.name
        )
    return value


def _normalize(
    value: str,
    code: str,
) -> str:
    if (
        not value
        or "\x00" in value
        or "\\" in value
        or value.startswith("/")
    ):
        raise RolloutHostError(code)
    normalized = value
    while normalized.startswith("./"):
        normalized = normalized[2:]
    path = PurePosixPath(normalized)
    if (
        normalized in {"", "."}
        or any(
            part in {"", ".", ".."}
            for part in path.parts
        )
        or path.as_posix() != normalized
    ):
        raise RolloutHostError(code)
    return normalized


def _zip_index(
    archive: Path,
) -> dict[str, zipfile.ZipInfo]:
    if archive.is_symlink() or not archive.is_file():
        raise RolloutHostError(
            "release_artifact_zip_invalid"
        )
    result: dict[str, zipfile.ZipInfo] = {}
    try:
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                name = _normalize(
                    info.filename,
                    "release_artifact_zip_member_invalid",
                )
                mode = (
                    info.external_attr >> 16
                ) & 0o170000
                if (
                    info.is_dir()
                    or "/" in name
                    or mode == 0o120000
                    or name in result
                ):
                    raise RolloutHostError(
                        "release_artifact_zip_member_invalid"
                    )
                result[name] = info
    except zipfile.BadZipFile as error:
        raise RolloutHostError(
            "release_artifact_zip_invalid"
        ) from error
    if set(result) != {
        FINAL_TAR,
        FINAL_TAR_SHA,
    }:
        raise RolloutHostError(
            "release_artifact_zip_file_set_invalid"
        )
    return result


def _extract_zip_member(
    archive: Path,
    name: str,
    destination: Path,
) -> None:
    with zipfile.ZipFile(archive) as bundle:
        info = bundle.getinfo(name)
        with (
            bundle.open(info) as source,
            destination.open("xb") as output,
        ):
            for block in iter(
                lambda: source.read(
                    1024 * 1024
                ),
                b"",
            ):
                output.write(block)


def _tar_index(
    archive: Path,
) -> dict[str, tarfile.TarInfo]:
    if archive.is_symlink() or not archive.is_file():
        raise RolloutHostError(
            "tar_invalid"
        )
    regular: dict[str, tarfile.TarInfo] = {}
    try:
        with tarfile.open(
            archive,
            "r:*",
        ) as bundle:
            for member in bundle.getmembers():
                raw = member.name
                if raw in {".", "./"} and member.isdir():
                    continue
                name = _normalize(
                    raw,
                    "tar_member_invalid",
                )
                if (
                    member.issym()
                    or member.islnk()
                ):
                    raise RolloutHostError(
                        "tar_member_invalid"
                    )
                if member.isfile():
                    if name in regular:
                        raise RolloutHostError(
                            "tar_member_duplicate"
                        )
                    regular[name] = member
                elif not member.isdir():
                    raise RolloutHostError(
                        "tar_member_invalid"
                    )
    except tarfile.TarError as error:
        raise RolloutHostError(
            "tar_invalid"
        ) from error
    return regular


def _tar_bytes(
    archive: Path,
    member: tarfile.TarInfo,
    *,
    maximum: int = 8 * 1024 * 1024,
) -> bytes:
    if member.size > maximum:
        raise RolloutHostError(
            "tar_member_too_large"
        )
    with tarfile.open(
        archive,
        "r:*",
    ) as bundle:
        selected = bundle.getmember(
            member.name
        )
        stream = bundle.extractfile(
            selected
        )
        if stream is None:
            raise RolloutHostError(
                "tar_member_unreadable"
            )
        return stream.read()


def _tar_sha(
    archive: Path,
    member: tarfile.TarInfo,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    with tarfile.open(
        archive,
        "r:*",
    ) as bundle:
        selected = bundle.getmember(
            member.name
        )
        stream = bundle.extractfile(
            selected
        )
        if stream is None:
            raise RolloutHostError(
                "tar_member_unreadable"
            )
        for block in iter(
            lambda: stream.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(block)
    return digest.hexdigest(), member.size


def _extract_tar_member(
    archive: Path,
    member: tarfile.TarInfo,
    destination: Path,
) -> None:
    with tarfile.open(
        archive,
        "r:*",
    ) as bundle:
        selected = bundle.getmember(
            member.name
        )
        stream = bundle.extractfile(
            selected
        )
        if stream is None:
            raise RolloutHostError(
                "tar_member_unreadable"
            )
        with destination.open(
            "xb"
        ) as output:
            for block in iter(
                lambda: stream.read(
                    1024 * 1024
                ),
                b"",
            ):
                output.write(block)


def _parse_sidecar(
    payload: bytes,
) -> str:
    try:
        lines = payload.decode(
            "ascii"
        ).strip().splitlines()
    except UnicodeError as error:
        raise RolloutHostError(
            "sha_sidecar_invalid"
        ) from error
    if (
        len(lines) != 1
        or SHA256_RE.fullmatch(
            lines[0]
        )
        is None
    ):
        raise RolloutHostError(
            "sha_sidecar_invalid"
        )
    return lines[0]


def _validate_binding(
    path: Path,
    artifact_zip: Path,
) -> dict[str, Any]:
    value = _read_json(path)
    if (
        set(value)
        != {
            "artifact_id",
            "artifact_name",
            "artifact_zip_sha256",
            "release_id",
            "release_sha256",
            "repository",
            "run_attempt",
            "run_id",
            "schema",
            "source_head",
            "source_tree",
            "workflow_path",
        }
        or value.get("schema")
        != LOCAL_BINDING_SCHEMA
        or value.get("repository")
        != "chrenguo-stack/HomeAssistant"
        or value.get("workflow_path")
        != FINAL_WORKFLOW
        or not isinstance(
            value.get("artifact_id"),
            int,
        )
        or value["artifact_id"] <= 0
        or not isinstance(
            value.get("run_id"),
            int,
        )
        or value["run_id"] <= 0
        or not isinstance(
            value.get("run_attempt"),
            int,
        )
        or value["run_attempt"] <= 0
    ):
        raise RolloutHostError(
            "local_binding_invalid"
        )
    for key in (
        "artifact_zip_sha256",
        "release_id",
        "release_sha256",
    ):
        if SHA256_RE.fullmatch(
            str(value.get(key, ""))
        ) is None:
            raise RolloutHostError(
                "local_binding_hash_invalid:"
                + key
            )
    for key in (
        "source_head",
        "source_tree",
    ):
        if GIT_SHA_RE.fullmatch(
            str(value.get(key, ""))
        ) is None:
            raise RolloutHostError(
                "local_binding_git_sha_invalid:"
                + key
            )
    expected_name = (
        FINAL_PREFIX
        + value["source_head"]
    )
    if value.get(
        "artifact_name"
    ) != expected_name:
        raise RolloutHostError(
            "local_binding_artifact_name_invalid"
        )
    if (
        _sha_file(artifact_zip)
        != value[
            "artifact_zip_sha256"
        ]
    ):
        raise RolloutHostError(
            "local_binding_artifact_digest_mismatch"
        )
    return value


def _config_contract(
    config: Any,
) -> dict[str, Any]:
    value = (
        config
        if isinstance(config, dict)
        else {}
    )
    result: dict[str, Any] = {}
    sequence = {
        "Entrypoint",
        "Cmd",
        "Env",
    }
    strings = {
        "User",
        "WorkingDir",
        "StopSignal",
    }
    mappings = {
        "Labels",
        "Healthcheck",
        "Volumes",
        "ExposedPorts",
    }
    for key in CONFIG_KEYS:
        observed = value.get(key)
        if (
            key in sequence
            and observed is None
        ):
            observed = []
        elif (
            key in strings
            and observed is None
        ):
            observed = ""
        elif (
            key in mappings
            and observed is None
        ):
            observed = {}
        result[key] = observed
    return result


def _docker_tar_binding(
    path: Path,
    image_ref: str,
) -> dict[str, str]:
    index = _tar_index(path)
    manifest = index.get(
        "manifest.json"
    )
    if manifest is None:
        raise RolloutHostError(
            "manager_docker_manifest_missing"
        )
    try:
        document = json.loads(
            _tar_bytes(
                path,
                manifest,
            )
        )
    except json.JSONDecodeError as error:
        raise RolloutHostError(
            "manager_docker_manifest_invalid"
        ) from error
    matches = [
        item
        for item in document
        if (
            isinstance(item, dict)
            and image_ref
            in (item.get("RepoTags") or [])
        )
    ]
    if len(matches) != 1:
        raise RolloutHostError(
            "manager_docker_tag_binding_invalid"
        )
    selected = matches[0]
    config_name = selected.get(
        "Config"
    )
    layers = selected.get(
        "Layers"
    )
    if (
        not isinstance(
            config_name,
            str,
        )
        or not isinstance(
            layers,
            list,
        )
        or not layers
    ):
        raise RolloutHostError(
            "manager_docker_record_invalid"
        )
    normalized_config = _normalize(
        config_name,
        "manager_docker_config_path_invalid",
    )
    config_member = index.get(
        normalized_config
    )
    if config_member is None:
        raise RolloutHostError(
            "manager_docker_config_missing"
        )
    config_bytes = _tar_bytes(
        path,
        config_member,
    )
    config_digest = hashlib.sha256(
        config_bytes
    ).hexdigest()
    leaf = Path(
        normalized_config
    ).name.removesuffix(".json")
    if leaf != config_digest:
        raise RolloutHostError(
            "manager_docker_config_digest_path_mismatch"
        )
    try:
        config = json.loads(config_bytes)
    except json.JSONDecodeError as error:
        raise RolloutHostError(
            "manager_docker_config_invalid"
        ) from error
    rootfs = config.get("rootfs")
    diff_ids = (
        rootfs.get("diff_ids")
        if isinstance(rootfs, dict)
        else None
    )
    if (
        not isinstance(
            diff_ids,
            list,
        )
        or not diff_ids
    ):
        raise RolloutHostError(
            "manager_docker_rootfs_invalid"
        )
    return {
        "config_digest":
            "sha256:" + config_digest,
        "rootfs_layers_sha256":
            _normalized_sha(diff_ids),
        "config_contract_sha256":
            _normalized_sha(
                _config_contract(
                    config.get("config")
                )
            ),
        "docker_archive_manifest_sha256":
            hashlib.sha256(
                _tar_bytes(
                    path,
                    manifest,
                )
            ).hexdigest(),
        "docker_archive_record_sha256":
            _normalized_sha(selected),
    }


def _payload_manifest(
    f3_payload: Path,
    root: Path,
) -> dict[str, Any]:
    index = _tar_index(f3_payload)
    if set(index) != F3_PAYLOAD_FILES:
        raise RolloutHostError(
            "f3_payload_file_set_invalid"
        )
    runtime = root / "runtime-payload.tar.gz"
    _extract_tar_member(
        f3_payload,
        index[
            "runtime-payload.tar.gz"
        ],
        runtime,
    )
    expected = _parse_sidecar(
        _tar_bytes(
            f3_payload,
            index[
                "runtime-payload.sha256"
            ],
        )
    )
    if _sha_file(runtime) != expected:
        raise RolloutHostError(
            "runtime_payload_sha256_mismatch"
        )
    runtime_index = _tar_index(
        runtime
    )
    manifest_member = (
        runtime_index.get(
            "payload-manifest.json"
        )
    )
    if manifest_member is None:
        raise RolloutHostError(
            "payload_manifest_missing"
        )
    payload_bytes = _tar_bytes(
        runtime,
        manifest_member,
    )
    expected_manifest = _parse_sidecar(
        _tar_bytes(
            f3_payload,
            index[
                "payload-manifest.sha256"
            ],
        )
    )
    if (
        hashlib.sha256(
            payload_bytes
        ).hexdigest()
        != expected_manifest
    ):
        raise RolloutHostError(
            "payload_manifest_sha256_mismatch"
        )
    try:
        value = json.loads(
            payload_bytes
        )
    except json.JSONDecodeError as error:
        raise RolloutHostError(
            "payload_manifest_invalid"
        ) from error
    if (
        not isinstance(value, dict)
        or value.get("schema")
        != "gh.n3w-t1-fresh-bootstrap-payload/1"
    ):
        raise RolloutHostError(
            "payload_manifest_invalid"
        )
    return value


def _manager_authority(
    artifact_zip: Path,
    binding_json: Path,
    work: Path,
) -> dict[str, Any]:
    binding = _validate_binding(
        binding_json,
        artifact_zip,
    )
    _zip_index(artifact_zip)
    release_tar = (
        work / FINAL_TAR
    )
    release_sidecar = (
        work / FINAL_TAR_SHA
    )
    _extract_zip_member(
        artifact_zip,
        FINAL_TAR,
        release_tar,
    )
    _extract_zip_member(
        artifact_zip,
        FINAL_TAR_SHA,
        release_sidecar,
    )
    if (
        _sha_file(release_tar)
        != _parse_sidecar(
            release_sidecar.read_bytes()
        )
    ):
        raise RolloutHostError(
            "release_tar_sha256_mismatch"
        )

    release_index = _tar_index(
        release_tar
    )
    expected = {
        RELEASE_ROOT
        + "/"
        + RELEASE_MANIFEST,
        RELEASE_ROOT
        + "/"
        + RELEASE_SHA,
        *{
            RELEASE_ROOT
            + "/artifacts/"
            + name
            for name
            in REQUIRED_RELEASE_ARTIFACTS
        },
    }
    if set(release_index) != expected:
        raise RolloutHostError(
            "release_tar_file_set_invalid"
        )
    manifest_bytes = _tar_bytes(
        release_tar,
        release_index[
            RELEASE_ROOT
            + "/"
            + RELEASE_MANIFEST
        ],
    )
    try:
        raw_release = json.loads(
            manifest_bytes
        )
        release = validate_release(
            raw_release
        )
    except Exception as error:
        raise RolloutHostError(
            "release_manifest_invalid"
        ) from error
    if (
        manifest_bytes
        != canonical_json_bytes(release)
    ):
        raise RolloutHostError(
            "release_manifest_not_canonical"
        )
    release_sha = _parse_sidecar(
        _tar_bytes(
            release_tar,
            release_index[
                RELEASE_ROOT
                + "/"
                + RELEASE_SHA
            ],
        )
    )
    if (
        hashlib.sha256(
            manifest_bytes
        ).hexdigest()
        != release_sha
    ):
        raise RolloutHostError(
            "release_manifest_sha256_mismatch"
        )
    if (
        release["release_id"]
        != binding["release_id"]
        or release_sha
        != binding["release_sha256"]
        or release["source_head"]
        != binding["source_head"]
        or release["source_tree"]
        != binding["source_tree"]
    ):
        raise RolloutHostError(
            "release_local_binding_mismatch"
        )

    extracted: dict[str, Path] = {}
    for name in sorted(
        REQUIRED_RELEASE_ARTIFACTS
    ):
        member = release_index[
            RELEASE_ROOT
            + "/artifacts/"
            + name
        ]
        observed_sha, observed_size = (
            _tar_sha(
                release_tar,
                member,
            )
        )
        record = release[
            "artifacts"
        ][name]
        if (
            observed_sha
            != record["sha256"]
            or observed_size
            != record["size_bytes"]
        ):
            raise RolloutHostError(
                "release_artifact_binding_invalid:"
                + name
            )
        if name in {
            "f3_image",
            "f3_payload",
        }:
            destination = work / name
            _extract_tar_member(
                release_tar,
                member,
                destination,
            )
            extracted[name] = (
                destination
            )

    image_index = _tar_index(
        extracted["f3_image"]
    )
    if set(image_index) != F3_IMAGE_FILES:
        raise RolloutHostError(
            "f3_image_file_set_invalid"
        )
    try:
        image_set = json.loads(
            _tar_bytes(
                extracted["f3_image"],
                image_index[
                    "image-set.json"
                ],
            )
        )
    except json.JSONDecodeError as error:
        raise RolloutHostError(
            "image_set_invalid"
        ) from error
    if (
        not isinstance(image_set, dict)
        or set(image_set)
        != {
            "schema",
            "source_head",
            "files",
        }
        or image_set.get("schema")
        != "gh.n3w-t1-f5-v2-image-set/1"
        or image_set.get(
            "source_head"
        )
        != binding["source_head"]
        or not isinstance(
            image_set.get("files"),
            list,
        )
    ):
        raise RolloutHostError(
            "image_set_invalid"
        )
    records = {
        item.get("path"): item
        for item in image_set["files"]
        if isinstance(item, dict)
    }
    if (
        set(records)
        != {
            "broker-arm64.tar",
            "greenhouse-manager-arm64.tar",
            "homeassistant-arm64.tar",
        }
    ):
        raise RolloutHostError(
            "image_set_records_invalid"
        )

    manager_tar = (
        work
        / "greenhouse-manager-arm64.tar"
    )
    _extract_tar_member(
        extracted["f3_image"],
        image_index[
            "greenhouse-manager-arm64.tar"
        ],
        manager_tar,
    )
    manager_record = records[
        "greenhouse-manager-arm64.tar"
    ]
    if (
        set(manager_record)
        != {
            "path",
            "sha256",
            "size_bytes",
        }
        or _sha_file(
            manager_tar
        )
        != manager_record[
            "sha256"
        ]
        or manager_tar.stat().st_size
        != manager_record[
            "size_bytes"
        ]
    ):
        raise RolloutHostError(
            "manager_image_set_binding_invalid"
        )

    payload = _payload_manifest(
        extracted["f3_payload"],
        work,
    )
    if (
        payload.get("source_head")
        != binding["source_head"]
        or payload.get(
            "secret_values_included"
        )
        is not False
        or payload.get(
            "production_service_start"
        )
        is not False
        or payload.get(
            "board_access"
        )
        is not False
    ):
        raise RolloutHostError(
            "payload_manifest_boundary_invalid"
        )
    images = payload.get("images")
    lock = payload.get(
        "image_lock"
    )
    if (
        not isinstance(images, dict)
        or not isinstance(lock, dict)
        or not isinstance(
            images.get("manager"),
            dict,
        )
        or not isinstance(
            lock.get("manager"),
            dict,
        )
    ):
        raise RolloutHostError(
            "manager_payload_binding_missing"
        )
    manager = images["manager"]
    locked = lock["manager"]
    expected_image = (
        "local/greenhouse-manager:fresh-"
        + binding["source_head"][:12]
    )
    required_hashes = (
        "tar_sha256",
        "rootfs_layers_sha256",
        "config_contract_sha256",
        "docker_archive_manifest_sha256",
        "docker_archive_record_sha256",
    )
    if (
        manager.get("image")
        != expected_image
        or manager.get(
            "artifact_file"
        )
        != "greenhouse-manager-arm64.tar"
        or manager.get("platform")
        != "linux/arm64"
        or manager.get(
            "tar_sha256"
        )
        != manager_record["sha256"]
        or manager.get(
            "tar_size_bytes"
        )
        != manager_record["size_bytes"]
        or not isinstance(
            manager.get("image_id"),
            str,
        )
        or not manager["image_id"].startswith(
            "sha256:"
        )
        or SHA256_RE.fullmatch(
            manager["image_id"][7:]
        )
        is None
        or any(
            SHA256_RE.fullmatch(
                str(
                    manager.get(
                        key,
                        "",
                    )
                )
            )
            is None
            for key in required_hashes
        )
    ):
        raise RolloutHostError(
            "manager_payload_binding_invalid"
        )
    if (
        manager.get(
            "config_digest"
        )
        != manager["image_id"]
        or locked.get(
            "source_sha"
        )
        != binding["source_head"]
        or locked.get("image")
        != expected_image
        or locked.get(
            "image_id"
        )
        != manager["image_id"]
        or locked.get(
            "tar_sha256"
        )
        != manager[
            "tar_sha256"
        ]
        or locked.get(
            "platform"
        )
        != "linux/arm64"
        or locked.get(
            "entrypoint"
        )
        != ["greenhouse-manager"]
        or locked.get(
            "runtime_uid"
        )
        != 999
        or locked.get(
            "runtime_gid"
        )
        != 999
        or locked.get(
            "pull_policy"
        )
        != "never"
    ):
        raise RolloutHostError(
            "manager_image_lock_invalid"
        )

    archive = _docker_tar_binding(
        manager_tar,
        expected_image,
    )
    for key, observed in archive.items():
        if manager.get(key) != observed:
            raise RolloutHostError(
                "manager_docker_archive_binding_invalid:"
                + key
            )

    return {
        "binding": binding,
        "manager_tar": manager_tar,
        "manager": {
            "image": expected_image,
            "image_id": manager["image_id"],
            "tar_sha256":
                manager["tar_sha256"],
            "tar_size_bytes":
                manager["tar_size_bytes"],
            "rootfs_layers_sha256":
                manager[
                    "rootfs_layers_sha256"
                ],
            "config_contract_sha256":
                manager[
                    "config_contract_sha256"
                ],
        },
    }


def _remote_source() -> tuple[str, str]:
    path = (
        Path(__file__).resolve().parent
        / "n3w_t1_manager_repaired_release_rollout_remote.py"
    )
    if path.is_symlink() or not path.is_file():
        raise RolloutHostError(
            "remote_rollout_tool_missing"
        )
    source = path.read_text(
        encoding="utf-8"
    )
    return source, _sha_file(path)


def _parse_remote(
    stdout: str,
) -> dict[str, Any]:
    documents = []
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            documents.append(value)
    if not documents:
        raise RolloutHostError(
            "remote_report_missing"
        )
    return documents[-1]


def _remote_call(
    transport: SSHTransport,
    source: str,
    *arguments: str,
    allowed: frozenset[int] = frozenset(
        {0}
    ),
) -> dict[str, Any]:
    completed = transport.run_remote(
        (
            "sudo",
            "-n",
            "python3",
            "-B",
            "-c",
            source,
            *arguments,
        ),
        timeout=240,
        check=False,
    )
    if (
        completed.returncode
        not in allowed
    ):
        report = _parse_remote(
            completed.stdout
        )
        raise RolloutHostError(
            "remote_operation_failed:"
            + str(
                report.get(
                    "error",
                    "unknown",
                )
            )
        )
    return _parse_remote(
        completed.stdout
    )


def _transport(
    args: argparse.Namespace,
) -> SSHTransport:
    return SSHTransport(
        target=args.target,
        known_hosts=args.known_hosts,
        expected_host_key_sha256=(
            args.expected_host_key_sha256
        ),
    )


def _public_authority(
    authority: dict[str, Any],
) -> dict[str, Any]:
    binding = authority["binding"]
    manager = authority["manager"]
    return {
        "release_id":
            binding["release_id"],
        "release_sha256":
            binding["release_sha256"],
        "release_source_head":
            binding["source_head"],
        "release_source_tree":
            binding["source_tree"],
        "artifact_id":
            binding["artifact_id"],
        "artifact_zip_sha256":
            binding[
                "artifact_zip_sha256"
            ],
        "manager_image_sha256":
            _sha_text(manager["image"]),
        "manager_image_id_sha256":
            _sha_text(
                manager["image_id"]
            ),
        "manager_tar_sha256":
            manager["tar_sha256"],
        "manager_rootfs_layers_sha256":
            manager[
                "rootfs_layers_sha256"
            ],
        "manager_config_contract_sha256":
            manager[
                "config_contract_sha256"
            ],
    }


def inspect(args: argparse.Namespace) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="n3w-manager-rollout-"
    ) as raw:
        authority = _manager_authority(
            args.release_artifact_zip,
            args.local_binding_json,
            Path(raw),
        )
        source, remote_sha = (
            _remote_source()
        )
        host_sha = _sha_file(
            Path(__file__).resolve()
        )
        transport = _transport(args)
        try:
            transport.start_epoch()
            report = _remote_call(
                transport,
                source,
                "inspect",
            )
        finally:
            transport.close_epoch()
    if (
        report.get("status")
        != "PASS"
        or report.get(
            "operation"
        )
        != "inspect"
        or report.get("mutation")
        is not False
        or report.get(
            "authorization_consumed"
        )
        is not False
        or report.get(
            "raw_locator_in_output"
        )
        is not False
        or report.get(
            "board_access"
        )
        is not False
        or SHA256_RE.fullmatch(
            str(
                report.get(
                    "baseline_sha256",
                    "",
                )
            )
        )
        is None
    ):
        raise RolloutHostError(
            "remote_inspect_contract_invalid"
        )
    return {
        **report,
        **_public_authority(
            authority
        ),
        "host_tool_sha256": host_sha,
        "remote_tool_sha256":
            remote_sha,
        "target_binding_sha256":
            _sha_text(args.target),
        "t1_access": True,
        "t1_mutation": False,
    }


def apply(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise RolloutHostError(
            "apply_confirmation_invalid"
        )
    if SHA256_RE.fullmatch(
        args.baseline_sha256
    ) is None:
        raise RolloutHostError(
            "baseline_sha256_invalid"
        )
    with tempfile.TemporaryDirectory(
        prefix="n3w-manager-rollout-"
    ) as raw:
        authority = _manager_authority(
            args.release_artifact_zip,
            args.local_binding_json,
            Path(raw),
        )
        source, remote_sha = (
            _remote_source()
        )
        host_sha = _sha_file(
            Path(__file__).resolve()
        )
        manager = authority["manager"]
        binding = authority["binding"]
        transport = _transport(args)
        claimed = False
        stage_path = ""
        try:
            transport.start_epoch()
            before = _remote_call(
                transport,
                source,
                "inspect",
            )
            if (
                before.get(
                    "baseline_sha256"
                )
                != args.baseline_sha256
            ):
                raise RolloutHostError(
                    "apply_baseline_drift"
                )
            claim = _remote_call(
                transport,
                source,
                "claim",
                "--authorization-id",
                args.authorization_id,
                "--baseline-sha256",
                args.baseline_sha256,
                "--release-id",
                binding["release_id"],
                "--release-sha256",
                binding["release_sha256"],
                "--source-head",
                binding["source_head"],
                "--new-image",
                manager["image"],
                "--image-id",
                manager["image_id"],
                "--manager-tar-sha256",
                manager["tar_sha256"],
                "--rootfs-layers-sha256",
                manager[
                    "rootfs_layers_sha256"
                ],
                "--config-contract-sha256",
                manager[
                    "config_contract_sha256"
                ],
                "--host-tool-sha256",
                host_sha,
                "--remote-tool-sha256",
                remote_sha,
            )
            if (
                claim.get("status")
                != "PASS"
                or claim.get(
                    "authorization_consumed"
                )
                is not True
                or claim.get(
                    "replay_allowed"
                )
                is not False
                or not isinstance(
                    claim.get(
                        "stage_path"
                    ),
                    str,
                )
            ):
                raise RolloutHostError(
                    "remote_claim_contract_invalid"
                )
            claimed = True
            stage_path = claim[
                "stage_path"
            ]
            try:
                transport.scp_to(
                    authority[
                        "manager_tar"
                    ],
                    stage_path
                    + "/greenhouse-manager-arm64.tar",
                    timeout=1800,
                )
            except Exception as error:
                reason = _sha_text(
                    type(error).__name__
                    + ":"
                    + str(error)
                )
                try:
                    _remote_call(
                        transport,
                        source,
                        "abort",
                        "--reason-sha256",
                        reason,
                        allowed=frozenset(
                            {0, 2}
                        ),
                    )
                except Exception:
                    pass
                raise RolloutHostError(
                    "manager_tar_transfer_failed"
                ) from error
            result = _remote_call(
                transport,
                source,
                "commit",
                allowed=frozenset(
                    {0, 2}
                ),
            )
            if (
                result.get("status")
                != "PASS"
                or result.get(
                    "transaction_state"
                )
                != "CLOSED_PASS"
                or result.get(
                    "authorization_consumed"
                )
                is not True
                or result.get(
                    "replay_allowed"
                )
                is not False
                or result.get(
                    "broker_continuity"
                )
                is not True
                or result.get(
                    "homeassistant_continuity"
                )
                is not True
                or result.get(
                    "manager_state_unchanged"
                )
                is not True
                or result.get(
                    "recovery_capability_present"
                )
                is not True
                or result.get(
                    "pairing_window_state"
                )
                != "CLOSED"
            ):
                raise RolloutHostError(
                    "manager_rollout_not_closed_pass:"
                    + str(
                        result.get(
                            "error",
                            "unknown",
                        )
                    )
                )
        finally:
            transport.close_epoch()
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "apply",
        "authorization_claimed":
            claimed,
        "authorization_consumed":
            True,
        "replay_allowed": False,
        "baseline_sha256":
            args.baseline_sha256,
        **_public_authority(
            authority
        ),
        "host_tool_sha256": host_sha,
        "remote_tool_sha256":
            remote_sha,
        "target_binding_sha256":
            _sha_text(args.target),
        "new_manager_container_id_sha256":
            result[
                "new_manager_container_id_sha256"
            ],
        "broker_continuity": True,
        "homeassistant_continuity":
            True,
        "manager_state_unchanged":
            True,
        "pairing_window_state":
            "CLOSED",
        "recovery_capability_present":
            True,
        "raw_locator_in_output": False,
        "t1_access": True,
        "t1_mutation": True,
        "board_access": False,
    }


def _common(
    command: argparse.ArgumentParser,
) -> None:
    command.add_argument(
        "--release-artifact-zip",
        type=Path,
        required=True,
    )
    command.add_argument(
        "--local-binding-json",
        type=Path,
        required=True,
    )
    command.add_argument(
        "--target",
        required=True,
    )
    command.add_argument(
        "--known-hosts",
        type=Path,
        required=True,
    )
    command.add_argument(
        "--expected-host-key-sha256",
        required=True,
    )


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    commands = value.add_subparsers(
        dest="command",
        required=True,
    )
    inspect_command = (
        commands.add_parser("inspect")
    )
    _common(inspect_command)
    apply_command = (
        commands.add_parser("apply")
    )
    _common(apply_command)
    apply_command.add_argument(
        "--baseline-sha256",
        required=True,
    )
    apply_command.add_argument(
        "--authorization-id",
        required=True,
    )
    apply_command.add_argument(
        "--confirm",
        required=True,
    )
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "inspect":
            report = inspect(args)
        else:
            report = apply(args)
    except (
        OSError,
        RolloutHostError,
        SSHTransportError,
        RuntimeError,
        TypeError,
        ValueError,
        zipfile.BadZipFile,
        tarfile.TarError,
    ) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "error": str(error),
                    "raw_locator_in_output": False,
                    "t1_mutation": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(
        json.dumps(
            report,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
