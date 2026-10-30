#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Sequence

SCHEMA = "gh.n3w-t1-portable-image-identity/1"
VERDICT_SCHEMA = "gh.n3w-t1-portable-image-verdict/1"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024 * 1024
MAX_TAR_MEMBERS = 200_000

CONFIG_FIELDS = (
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


class PortableImageIdentityError(RuntimeError):
    pass


class UnsupportedImageArchive(PortableImageIdentityError):
    pass


@dataclass(frozen=True)
class PortableImageIdentity:
    schema: str
    representation: str
    archive_sha256: str
    archive_size_bytes: int
    os: str
    architecture: str
    variant: str | None
    config_digest: str
    manifest_digest: str | None
    index_digest: str | None
    config_semantics_sha256: str
    rootfs_diff_ids: tuple[str, ...]
    rootfs_diff_ids_sha256: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["rootfs_diff_ids"] = list(self.rootfs_diff_ids)
        return value


@dataclass(frozen=True)
class DockerObservation:
    status: str
    reason: str
    reference: str
    document: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "reference": self.reference,
            "document": self.document,
        }


@dataclass(frozen=True)
class VerificationVerdict:
    schema: str
    status: str
    reason: str
    runtime_image_id: str | None
    config_digest: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise PortableImageIdentityError("archive_invalid")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PortableImageIdentityError("duplicate_json_key")
        result[key] = value
    return result


def strict_json(data: bytes, *, name: str) -> Any:
    if len(data) > MAX_JSON_BYTES:
        raise PortableImageIdentityError(f"{name}_too_large")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_strict_object)
    except UnicodeDecodeError as error:
        raise PortableImageIdentityError(f"{name}_encoding_invalid") from error
    except json.JSONDecodeError as error:
        raise PortableImageIdentityError(f"{name}_json_invalid") from error


def _safe_name(name: str) -> str:
    if not name or "\x00" in name:
        raise PortableImageIdentityError("archive_member_name_invalid")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PortableImageIdentityError("archive_path_traversal")
    normalized = str(path)
    if normalized.startswith("../") or "/../" in normalized:
        raise PortableImageIdentityError("archive_path_traversal")
    return normalized


class SafeTar:
    def __init__(self, path: Path):
        self.path = path
        self.tar: tarfile.TarFile | None = None
        self.members: dict[str, tarfile.TarInfo] = {}

    def __enter__(self) -> "SafeTar":
        try:
            self.tar = tarfile.open(self.path, mode="r:*")
        except (tarfile.TarError, OSError) as error:
            raise PortableImageIdentityError("archive_open_failed") from error
        member_count = 0
        for member in self.tar:
            member_count += 1
            if member_count > MAX_TAR_MEMBERS:
                raise PortableImageIdentityError("archive_member_limit_exceeded")
            name = _safe_name(member.name)
            if name in self.members:
                raise PortableImageIdentityError("archive_duplicate_member")
            if member.issym() or member.islnk():
                raise PortableImageIdentityError("archive_link_member_forbidden")
            if not (member.isfile() or member.isdir()):
                raise PortableImageIdentityError("archive_special_member_forbidden")
            self.members[name] = member
        return self

    def __exit__(self, *_exc: Any) -> None:
        if self.tar is not None:
            self.tar.close()
        self.tar = None

    def _member(self, name: str) -> tarfile.TarInfo:
        normalized = _safe_name(name)
        member = self.members.get(normalized)
        if member is None or not member.isfile():
            raise PortableImageIdentityError(f"archive_member_missing:{normalized}")
        return member

    def read(self, name: str, *, max_bytes: int = MAX_JSON_BYTES) -> bytes:
        member = self._member(name)
        if member.size < 0 or member.size > max_bytes:
            raise PortableImageIdentityError("archive_member_size_invalid")
        assert self.tar is not None
        stream = self.tar.extractfile(member)
        if stream is None:
            raise PortableImageIdentityError("archive_member_read_failed")
        data = stream.read(max_bytes + 1)
        if len(data) != member.size or len(data) > max_bytes:
            raise PortableImageIdentityError("archive_member_size_mismatch")
        return data

    def hash_and_size(self, name: str) -> tuple[str, int]:
        member = self._member(name)
        assert self.tar is not None
        stream = self.tar.extractfile(member)
        if stream is None:
            raise PortableImageIdentityError("archive_member_read_failed")
        digest = hashlib.sha256()
        size = 0
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
        if size != member.size:
            raise PortableImageIdentityError("archive_member_size_mismatch")
        return digest.hexdigest(), size


def _digest_blob_path(digest: str) -> str:
    match = DIGEST.fullmatch(digest)
    if match is None:
        raise PortableImageIdentityError("descriptor_digest_invalid")
    return f"blobs/sha256/{match.group(1)}"


def _descriptor_blob(
    archive: SafeTar,
    descriptor: Any,
    *,
    name: str,
    json_blob: bool,
) -> tuple[bytes | None, str]:
    if not isinstance(descriptor, dict):
        raise PortableImageIdentityError(f"{name}_descriptor_invalid")
    digest = descriptor.get("digest")
    size = descriptor.get("size")
    if not isinstance(digest, str) or DIGEST.fullmatch(digest) is None:
        raise PortableImageIdentityError(f"{name}_digest_invalid")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise PortableImageIdentityError(f"{name}_size_invalid")
    path = _digest_blob_path(digest)
    actual, actual_size = archive.hash_and_size(path)
    if f"sha256:{actual}" != digest or actual_size != size:
        raise PortableImageIdentityError(f"{name}_binding_mismatch")
    if not json_blob:
        return None, path
    return archive.read(path), path


def _platform(value: dict[str, Any]) -> tuple[str, str, str | None]:
    os_name = value.get("os")
    architecture = value.get("architecture")
    variant = value.get("variant")
    if not isinstance(os_name, str) or not os_name:
        raise PortableImageIdentityError("config_os_invalid")
    if not isinstance(architecture, str) or not architecture:
        raise PortableImageIdentityError("config_architecture_invalid")
    if variant is not None and (not isinstance(variant, str) or not variant):
        raise PortableImageIdentityError("config_variant_invalid")
    return os_name, architecture, variant


def normalized_config_contract(config: Any) -> dict[str, Any]:
    raw = config if isinstance(config, dict) else {}
    sequence_fields = {"Entrypoint", "Cmd", "Env"}
    string_fields = {"User", "WorkingDir", "StopSignal"}
    mapping_fields = {"Labels", "Healthcheck", "Volumes", "ExposedPorts"}
    result: dict[str, Any] = {}
    for field in CONFIG_FIELDS:
        observed = raw.get(field)
        if field in sequence_fields and observed is None:
            observed = []
        elif field in string_fields and observed is None:
            observed = ""
        elif field in mapping_fields and observed is None:
            observed = {}
        result[field] = observed
    return result


def _config_semantics(config_doc: dict[str, Any]) -> dict[str, Any]:
    raw = config_doc.get("config")
    if raw is not None and not isinstance(raw, dict):
        raise PortableImageIdentityError("image_config_shape_invalid")
    return normalized_config_contract(raw)


def _rootfs_diff_ids(config_doc: dict[str, Any]) -> tuple[str, ...]:
    rootfs = config_doc.get("rootfs")
    if not isinstance(rootfs, dict) or rootfs.get("type") != "layers":
        raise PortableImageIdentityError("rootfs_invalid")
    values = rootfs.get("diff_ids")
    if not isinstance(values, list) or not values:
        raise PortableImageIdentityError("rootfs_diff_ids_invalid")
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or DIGEST.fullmatch(value) is None:
            raise PortableImageIdentityError("rootfs_diff_id_invalid")
        result.append(value)
    return tuple(result)


def _identity(
    *,
    representation: str,
    archive_sha256: str,
    archive_size_bytes: int,
    config_doc: dict[str, Any],
    config_digest: str,
    manifest_digest: str | None,
    index_digest: str | None,
) -> PortableImageIdentity:
    os_name, architecture, variant = _platform(config_doc)
    rootfs = _rootfs_diff_ids(config_doc)
    semantics = _config_semantics(config_doc)
    return PortableImageIdentity(
        schema=SCHEMA,
        representation=representation,
        archive_sha256=archive_sha256,
        archive_size_bytes=archive_size_bytes,
        os=os_name,
        architecture=architecture,
        variant=variant,
        config_digest=config_digest,
        manifest_digest=manifest_digest,
        index_digest=index_digest,
        config_semantics_sha256=_sha256_bytes(_canonical_bytes(semantics)),
        rootfs_diff_ids=rootfs,
        rootfs_diff_ids_sha256=_sha256_bytes(_canonical_bytes(list(rootfs))),
    )


def _parse_docker_save(
    archive: SafeTar,
    *,
    archive_sha256: str,
    archive_size_bytes: int,
    expected_tag: str | None,
) -> PortableImageIdentity:
    manifest = strict_json(archive.read("manifest.json"), name="docker_manifest")
    if not isinstance(manifest, list) or not manifest:
        raise PortableImageIdentityError("docker_manifest_shape_invalid")
    candidates: list[dict[str, Any]] = []
    for item in manifest:
        if not isinstance(item, dict):
            raise PortableImageIdentityError("docker_manifest_entry_invalid")
        tags = item.get("RepoTags")
        if tags is None:
            tags = []
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise PortableImageIdentityError("docker_manifest_tags_invalid")
        if expected_tag is None or expected_tag in tags:
            candidates.append(item)
    if len(candidates) != 1:
        raise PortableImageIdentityError("docker_manifest_image_ambiguous")
    item = candidates[0]
    config_name = item.get("Config")
    layers = item.get("Layers")
    if not isinstance(config_name, str) or not config_name:
        raise PortableImageIdentityError("docker_config_path_invalid")
    if not isinstance(layers, list) or not layers or not all(isinstance(x, str) for x in layers):
        raise PortableImageIdentityError("docker_layers_invalid")
    config_bytes = archive.read(config_name)
    config_sha = _sha256_bytes(config_bytes)
    expected_config_name = config_sha + ".json"
    if PurePosixPath(config_name).name != expected_config_name:
        raise PortableImageIdentityError("docker_config_digest_binding_mismatch")
    config_doc = strict_json(config_bytes, name="image_config")
    if not isinstance(config_doc, dict):
        raise PortableImageIdentityError("image_config_invalid")
    rootfs = _rootfs_diff_ids(config_doc)
    if len(rootfs) != len(layers):
        raise PortableImageIdentityError("docker_layer_count_mismatch")
    for layer_path, expected_diff_id in zip(layers, rootfs):
        actual, _ = archive.hash_and_size(layer_path)
        if f"sha256:{actual}" != expected_diff_id:
            raise PortableImageIdentityError("docker_layer_diff_id_mismatch")
    return _identity(
        representation="docker-save",
        archive_sha256=archive_sha256,
        archive_size_bytes=archive_size_bytes,
        config_doc=config_doc,
        config_digest=f"sha256:{config_sha}",
        manifest_digest=None,
        index_digest=None,
    )


def _parse_oci(
    archive: SafeTar,
    *,
    archive_sha256: str,
    archive_size_bytes: int,
    platform_os: str,
    platform_architecture: str,
    platform_variant: str | None,
) -> PortableImageIdentity:
    layout = strict_json(archive.read("oci-layout"), name="oci_layout")
    if layout != {"imageLayoutVersion": "1.0.0"}:
        raise UnsupportedImageArchive("oci_layout_unsupported")
    index_bytes = archive.read("index.json")
    index = strict_json(index_bytes, name="oci_index")
    if not isinstance(index, dict) or index.get("schemaVersion") != 2:
        raise UnsupportedImageArchive("oci_index_unsupported")
    manifests = index.get("manifests")
    if not isinstance(manifests, list) or not manifests:
        raise PortableImageIdentityError("oci_index_manifests_invalid")
    selected: list[dict[str, Any]] = []
    for descriptor in manifests:
        if not isinstance(descriptor, dict):
            raise PortableImageIdentityError("oci_manifest_descriptor_invalid")
        platform = descriptor.get("platform")
        if not isinstance(platform, dict):
            continue
        if (
            platform.get("os") == platform_os
            and platform.get("architecture") == platform_architecture
            and platform.get("variant") == platform_variant
        ):
            selected.append(descriptor)
    if len(selected) != 1:
        raise PortableImageIdentityError("oci_platform_ambiguous")
    descriptor = selected[0]
    manifest_bytes, _ = _descriptor_blob(
        archive, descriptor, name="manifest", json_blob=True
    )
    assert manifest_bytes is not None
    manifest = strict_json(manifest_bytes, name="oci_manifest")
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 2:
        raise UnsupportedImageArchive("oci_manifest_unsupported")
    config_descriptor = manifest.get("config")
    config_bytes, _ = _descriptor_blob(
        archive, config_descriptor, name="config", json_blob=True
    )
    assert config_bytes is not None
    config_doc = strict_json(config_bytes, name="image_config")
    if not isinstance(config_doc, dict):
        raise PortableImageIdentityError("image_config_invalid")
    os_name, architecture, variant = _platform(config_doc)
    if (os_name, architecture, variant) != (
        platform_os,
        platform_architecture,
        platform_variant,
    ):
        raise PortableImageIdentityError("oci_config_platform_mismatch")
    layers = manifest.get("layers")
    if not isinstance(layers, list) or not layers:
        raise PortableImageIdentityError("oci_layers_invalid")
    for layer in layers:
        _descriptor_blob(archive, layer, name="layer", json_blob=False)
    rootfs = _rootfs_diff_ids(config_doc)
    if len(rootfs) != len(layers):
        raise PortableImageIdentityError("oci_layer_count_mismatch")
    return _identity(
        representation="oci-layout",
        archive_sha256=archive_sha256,
        archive_size_bytes=archive_size_bytes,
        config_doc=config_doc,
        config_digest=str(config_descriptor["digest"]),
        manifest_digest=str(descriptor["digest"]),
        index_digest=f"sha256:{_sha256_bytes(index_bytes)}",
    )


def parse_image_archive(
    path: Path,
    *,
    expected_archive_sha256: str | None = None,
    expected_archive_size_bytes: int | None = None,
    expected_tag: str | None = None,
    platform_os: str = "linux",
    platform_architecture: str = "arm64",
    platform_variant: str | None = None,
) -> PortableImageIdentity:
    if path.is_symlink() or not path.is_file():
        raise PortableImageIdentityError("archive_invalid")
    size = path.stat().st_size
    if size > MAX_ARCHIVE_BYTES:
        raise PortableImageIdentityError("archive_size_limit_exceeded")
    digest = sha256_file(path)
    if expected_archive_sha256 is not None:
        if (
            not isinstance(expected_archive_sha256, str)
            or SHA256.fullmatch(expected_archive_sha256) is None
            or digest != expected_archive_sha256
        ):
            raise PortableImageIdentityError("archive_sha256_mismatch")
    if expected_archive_size_bytes is not None:
        if (
            isinstance(expected_archive_size_bytes, bool)
            or not isinstance(expected_archive_size_bytes, int)
            or expected_archive_size_bytes < 0
        ):
            raise PortableImageIdentityError("archive_expected_size_invalid")
        if size != expected_archive_size_bytes:
            raise PortableImageIdentityError("archive_size_mismatch")
    with SafeTar(path) as archive:
        if "oci-layout" in archive.members or "index.json" in archive.members:
            if "oci-layout" not in archive.members or "index.json" not in archive.members:
                raise UnsupportedImageArchive("partial_oci_layout")
            return _parse_oci(
                archive,
                archive_sha256=digest,
                archive_size_bytes=size,
                platform_os=platform_os,
                platform_architecture=platform_architecture,
                platform_variant=platform_variant,
            )
        if "manifest.json" in archive.members:
            return _parse_docker_save(
                archive,
                archive_sha256=digest,
                archive_size_bytes=size,
                expected_tag=expected_tag,
            )
    raise UnsupportedImageArchive("archive_layout_unsupported")


def _runtime_semantics(document: dict[str, Any]) -> tuple[str, str, str | None, dict[str, Any], tuple[str, ...]]:
    os_name = document.get("Os")
    architecture = document.get("Architecture")
    variant = document.get("Variant")
    if not isinstance(os_name, str) or not isinstance(architecture, str):
        raise PortableImageIdentityError("runtime_platform_invalid")
    if variant is not None and not isinstance(variant, str):
        raise PortableImageIdentityError("runtime_platform_invalid")
    config = document.get("Config")
    if not isinstance(config, dict):
        raise PortableImageIdentityError("runtime_config_invalid")
    semantics = normalized_config_contract(config)
    rootfs = document.get("RootFS")
    layers = rootfs.get("Layers") if isinstance(rootfs, dict) else None
    if not isinstance(layers, list) or not layers or not all(isinstance(x, str) for x in layers):
        raise PortableImageIdentityError("runtime_rootfs_invalid")
    return os_name, architecture, variant, semantics, tuple(layers)


def verify_runtime_document(
    identity: PortableImageIdentity,
    document: dict[str, Any],
) -> VerificationVerdict:
    runtime_id = document.get("Id") if isinstance(document.get("Id"), str) else None
    try:
        os_name, architecture, variant, semantics, layers = _runtime_semantics(document)
    except PortableImageIdentityError as error:
        return VerificationVerdict(
            VERDICT_SCHEMA, "UNSUPPORTED_REPRESENTATION", str(error), runtime_id, identity.config_digest
        )
    if (os_name, architecture, variant) != (
        identity.os,
        identity.architecture,
        identity.variant,
    ):
        return VerificationVerdict(
            VERDICT_SCHEMA, "MISMATCH", "platform_mismatch", runtime_id, identity.config_digest
        )
    if _sha256_bytes(_canonical_bytes(semantics)) != identity.config_semantics_sha256:
        return VerificationVerdict(
            VERDICT_SCHEMA, "MISMATCH", "config_semantics_mismatch", runtime_id, identity.config_digest
        )
    if layers != identity.rootfs_diff_ids:
        return VerificationVerdict(
            VERDICT_SCHEMA, "MISMATCH", "rootfs_diff_ids_mismatch", runtime_id, identity.config_digest
        )
    return VerificationVerdict(
        VERDICT_SCHEMA, "VERIFIED", "portable_identity_match", runtime_id, identity.config_digest
    )


def observe_docker_image(
    reference: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] | None = None,
    timeout: int = 30,
) -> DockerObservation:
    if not isinstance(reference, str) or not reference or reference.strip() != reference:
        return DockerObservation("UNSUPPORTED", "reference_invalid", reference, None)
    execute = runner or subprocess.run
    try:
        result = execute(
            ("docker", "image", "inspect", reference),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return DockerObservation("DAEMON_UNAVAILABLE", "docker_cli_unavailable", reference, None)
    except subprocess.TimeoutExpired:
        return DockerObservation("TIMEOUT", "docker_timeout", reference, None)
    if result.returncode:
        detail = (result.stderr or result.stdout).decode(errors="replace").casefold()
        if "no such image" in detail or "not found" in detail:
            return DockerObservation("NOT_FOUND", "image_not_found", reference, None)
        if "permission denied" in detail:
            return DockerObservation("PERMISSION_DENIED", "docker_permission_denied", reference, None)
        if "cannot connect" in detail or "daemon" in detail:
            return DockerObservation("DAEMON_UNAVAILABLE", "docker_daemon_unavailable", reference, None)
        return DockerObservation("UNAVAILABLE", "docker_inspect_failed", reference, None)
    try:
        value = strict_json(result.stdout, name="docker_inspect")
    except PortableImageIdentityError:
        return DockerObservation("MALFORMED_RESPONSE", "docker_inspect_malformed", reference, None)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        return DockerObservation("MALFORMED_RESPONSE", "docker_inspect_shape_invalid", reference, None)
    return DockerObservation("AVAILABLE", "docker_inspect_ok", reference, value[0])


def verify_docker_image(
    identity: PortableImageIdentity,
    reference: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] | None = None,
    timeout: int = 30,
) -> VerificationVerdict:
    observation = observe_docker_image(reference, runner=runner, timeout=timeout)
    if observation.status == "NOT_FOUND":
        return VerificationVerdict(
            VERDICT_SCHEMA, "MISMATCH", observation.reason, None, identity.config_digest
        )
    if observation.status in {
        "DAEMON_UNAVAILABLE",
        "PERMISSION_DENIED",
        "TIMEOUT",
        "UNAVAILABLE",
    }:
        return VerificationVerdict(
            VERDICT_SCHEMA, "UNAVAILABLE", observation.reason, None, identity.config_digest
        )
    if observation.status != "AVAILABLE" or observation.document is None:
        return VerificationVerdict(
            VERDICT_SCHEMA,
            "UNSUPPORTED_REPRESENTATION",
            observation.reason,
            None,
            identity.config_digest,
        )
    return verify_runtime_document(identity, observation.document)


def identity_from_dict(value: Any) -> PortableImageIdentity:
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise PortableImageIdentityError("identity_schema_invalid")
    expected = {
        "schema",
        "representation",
        "archive_sha256",
        "archive_size_bytes",
        "os",
        "architecture",
        "variant",
        "config_digest",
        "manifest_digest",
        "index_digest",
        "config_semantics_sha256",
        "rootfs_diff_ids",
        "rootfs_diff_ids_sha256",
    }
    if set(value) != expected:
        raise PortableImageIdentityError("identity_keys_invalid")
    if value.get("representation") not in {"docker-save", "oci-layout"}:
        raise PortableImageIdentityError("identity_representation_invalid")
    if not isinstance(value.get("os"), str) or not value["os"]:
        raise PortableImageIdentityError("identity_os_invalid")
    if not isinstance(value.get("architecture"), str) or not value["architecture"]:
        raise PortableImageIdentityError("identity_architecture_invalid")
    if value.get("variant") is not None and (
        not isinstance(value["variant"], str) or not value["variant"]
    ):
        raise PortableImageIdentityError("identity_variant_invalid")
    if SHA256.fullmatch(value.get("archive_sha256", "")) is None:
        raise PortableImageIdentityError("identity_archive_sha_invalid")
    if (
        isinstance(value.get("archive_size_bytes"), bool)
        or not isinstance(value.get("archive_size_bytes"), int)
        or value["archive_size_bytes"] < 0
    ):
        raise PortableImageIdentityError("identity_archive_size_invalid")
    if SHA256.fullmatch(value.get("config_semantics_sha256", "")) is None:
        raise PortableImageIdentityError("identity_config_semantics_sha_invalid")
    if DIGEST.fullmatch(value.get("config_digest", "")) is None:
        raise PortableImageIdentityError("identity_config_digest_invalid")
    for key in ("manifest_digest", "index_digest"):
        digest = value.get(key)
        if digest is not None and (
            not isinstance(digest, str) or DIGEST.fullmatch(digest) is None
        ):
            raise PortableImageIdentityError(f"identity_{key}_invalid")
    rootfs = value.get("rootfs_diff_ids")
    if (
        not isinstance(rootfs, list)
        or not rootfs
        or not all(
            isinstance(item, str) and DIGEST.fullmatch(item) is not None
            for item in rootfs
        )
    ):
        raise PortableImageIdentityError("identity_rootfs_invalid")
    if _sha256_bytes(_canonical_bytes(rootfs)) != value.get("rootfs_diff_ids_sha256"):
        raise PortableImageIdentityError("identity_rootfs_hash_mismatch")
    return PortableImageIdentity(
        schema=SCHEMA,
        representation=str(value["representation"]),
        archive_sha256=str(value["archive_sha256"]),
        archive_size_bytes=int(value["archive_size_bytes"]),
        os=str(value["os"]),
        architecture=str(value["architecture"]),
        variant=value["variant"],
        config_digest=str(value["config_digest"]),
        manifest_digest=value["manifest_digest"],
        index_digest=value["index_digest"],
        config_semantics_sha256=str(value["config_semantics_sha256"]),
        rootfs_diff_ids=tuple(rootfs),
        rootfs_diff_ids_sha256=str(value["rootfs_diff_ids_sha256"]),
    )
