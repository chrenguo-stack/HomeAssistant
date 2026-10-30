from __future__ import annotations

import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import n3w_t1_portable_image_identity as identity  # noqa: E402


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _tar_add(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def _classic_archive(
    path: Path,
    *,
    tag: str = "local/manager:test",
    cmd: list[str] | None = None,
    raw_config: bytes | None = None,
) -> tuple[dict[str, object], bytes]:
    layer = b"classic-layer-content\n"
    diff_id = "sha256:" + _sha(layer)
    config_doc = {
        "architecture": "arm64",
        "os": "linux",
        "rootfs": {"type": "layers", "diff_ids": [diff_id]},
        "config": {
            "Entrypoint": ["greenhouse-manager"],
            "Cmd": cmd,
            "User": "greenhouse",
            "Env": ["A=1", "B=2"],
            "WorkingDir": "/app",
            "Labels": {"org.example.release": "r10"},
            "Healthcheck": None,
            "StopSignal": None,
            "Volumes": None,
            "ExposedPorts": None,
        },
    }
    config_bytes = raw_config or json.dumps(
        config_doc, sort_keys=True, separators=(",", ":")
    ).encode()
    config_name = _sha(config_bytes) + ".json"
    manifest = [{
        "Config": config_name,
        "RepoTags": [tag],
        "Layers": ["layer/layer.tar"],
    }]
    with tarfile.open(path, "w") as tar:
        _tar_add(tar, config_name, config_bytes)
        _tar_add(
            tar,
            "manifest.json",
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(),
        )
        _tar_add(tar, "layer/layer.tar", layer)
    return config_doc, layer


def _runtime(config_doc: dict[str, object], *, runtime_id: str = "sha256:" + "f" * 64):
    return {
        "Id": runtime_id,
        "Architecture": config_doc["architecture"],
        "Os": config_doc["os"],
        "Config": config_doc["config"],
        "RootFS": {"Layers": config_doc["rootfs"]["diff_ids"]},
    }


def _oci_archive(path: Path, *, duplicate_platform: bool = False) -> dict[str, object]:
    uncompressed_layer = b"uncompressed-rootfs"
    layer = gzip.compress(uncompressed_layer, mtime=0)
    diff = "sha256:" + _sha(uncompressed_layer)
    config = {
        "architecture": "arm64",
        "os": "linux",
        "rootfs": {"type": "layers", "diff_ids": [diff]},
        "config": {
            "Entrypoint": ["greenhouse-manager"],
            "Cmd": None,
            "User": "greenhouse",
            "Env": ["A=1"],
            "WorkingDir": "/app",
            "Labels": {"org.example.release": "r10"},
            "Healthcheck": None,
            "StopSignal": None,
            "Volumes": None,
            "ExposedPorts": None,
        },
    }
    config_bytes = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    config_digest = "sha256:" + _sha(config_bytes)
    layer_digest = "sha256:" + _sha(layer)
    manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "digest": config_digest,
            "size": len(config_bytes),
        },
        "layers": [{
            "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
            "digest": layer_digest,
            "size": len(layer),
        }],
    }
    manifest_bytes = json.dumps(
        manifest, sort_keys=True, separators=(",", ":")
    ).encode()
    manifest_digest = "sha256:" + _sha(manifest_bytes)
    descriptor = {
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "digest": manifest_digest,
        "size": len(manifest_bytes),
        "platform": {"os": "linux", "architecture": "arm64"},
    }
    manifests = [descriptor, dict(descriptor)] if duplicate_platform else [descriptor]
    index = {
        "schemaVersion": 2,
        "manifests": manifests,
    }
    with tarfile.open(path, "w") as tar:
        _tar_add(tar, "oci-layout", b'{"imageLayoutVersion":"1.0.0"}')
        _tar_add(
            tar,
            "index.json",
            json.dumps(index, sort_keys=True, separators=(",", ":")).encode(),
        )
        _tar_add(tar, "blobs/sha256/" + config_digest.split(":", 1)[1], config_bytes)
        _tar_add(tar, "blobs/sha256/" + manifest_digest.split(":", 1)[1], manifest_bytes)
        _tar_add(tar, "blobs/sha256/" + layer_digest.split(":", 1)[1], layer)
    return config


def test_classic_archive_accepts_different_host_local_dot_id(tmp_path: Path) -> None:
    archive = tmp_path / "image.tar"
    config, _ = _classic_archive(archive)
    parsed = identity.parse_image_archive(archive, expected_tag="local/manager:test")

    assert parsed.representation == "docker-save"
    assert parsed.config_digest.startswith("sha256:")
    assert parsed.manifest_digest is None

    verdict = identity.verify_runtime_document(
        parsed,
        _runtime(config, runtime_id="sha256:" + "9" * 64),
    )
    assert verdict.status == "VERIFIED"
    assert verdict.reason == "portable_identity_match"
    assert verdict.runtime_image_id == "sha256:" + "9" * 64


def test_runtime_same_rootfs_but_changed_cmd_is_mismatch(tmp_path: Path) -> None:
    archive = tmp_path / "image.tar"
    config, _ = _classic_archive(archive, cmd=["serve"])
    parsed = identity.parse_image_archive(archive)
    runtime = _runtime(config)
    runtime["Config"] = dict(runtime["Config"])
    runtime["Config"]["Cmd"] = ["other"]

    verdict = identity.verify_runtime_document(parsed, runtime)
    assert verdict.status == "MISMATCH"
    assert verdict.reason == "config_semantics_mismatch"


def test_runtime_rootfs_drift_is_mismatch(tmp_path: Path) -> None:
    archive = tmp_path / "image.tar"
    config, _ = _classic_archive(archive)
    parsed = identity.parse_image_archive(archive)
    runtime = _runtime(config)
    runtime["RootFS"] = {"Layers": ["sha256:" + "0" * 64]}

    verdict = identity.verify_runtime_document(parsed, runtime)
    assert verdict.status == "MISMATCH"
    assert verdict.reason == "rootfs_diff_ids_mismatch"


def test_archive_sha_and_size_binding_are_enforced(tmp_path: Path) -> None:
    archive = tmp_path / "image.tar"
    _classic_archive(archive)
    with pytest.raises(identity.PortableImageIdentityError, match="archive_sha256_mismatch"):
        identity.parse_image_archive(archive, expected_archive_sha256="0" * 64)
    with pytest.raises(identity.PortableImageIdentityError, match="archive_size_mismatch"):
        identity.parse_image_archive(
            archive,
            expected_archive_size_bytes=archive.stat().st_size + 1,
        )


def test_classic_layer_diff_id_is_verified(tmp_path: Path) -> None:
    archive = tmp_path / "image.tar"
    config, _ = _classic_archive(archive)
    config["rootfs"]["diff_ids"] = ["sha256:" + "0" * 64]
    config_bytes = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    config_name = _sha(config_bytes) + ".json"
    manifest = [{"Config": config_name, "RepoTags": [], "Layers": ["layer.tar"]}]
    with tarfile.open(archive, "w") as tar:
        _tar_add(tar, config_name, config_bytes)
        _tar_add(tar, "manifest.json", json.dumps(manifest).encode())
        _tar_add(tar, "layer.tar", b"real-layer")
    with pytest.raises(identity.PortableImageIdentityError, match="docker_layer_diff_id_mismatch"):
        identity.parse_image_archive(archive)


def test_oci_graph_and_platform_are_verified(tmp_path: Path) -> None:
    archive = tmp_path / "oci.tar"
    config = _oci_archive(archive)
    parsed = identity.parse_image_archive(archive)

    assert parsed.representation == "oci-layout"
    assert parsed.manifest_digest is not None
    assert parsed.index_digest is not None
    assert identity.verify_runtime_document(parsed, _runtime(config)).status == "VERIFIED"


def test_oci_ambiguous_platform_stops(tmp_path: Path) -> None:
    archive = tmp_path / "oci.tar"
    _oci_archive(archive, duplicate_platform=True)
    with pytest.raises(identity.PortableImageIdentityError, match="oci_platform_ambiguous"):
        identity.parse_image_archive(archive)


def test_duplicate_tar_member_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "dup.tar"
    with tarfile.open(archive, "w") as tar:
        _tar_add(tar, "manifest.json", b"[]")
        _tar_add(tar, "manifest.json", b"[]")
    with pytest.raises(identity.PortableImageIdentityError, match="archive_duplicate_member"):
        identity.parse_image_archive(archive)


def test_path_traversal_member_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bad.tar"
    with tarfile.open(archive, "w") as tar:
        _tar_add(tar, "../manifest.json", b"[]")
    with pytest.raises(identity.PortableImageIdentityError, match="archive_path_traversal"):
        identity.parse_image_archive(archive)


def test_symlink_member_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bad-link.tar"
    with tarfile.open(archive, "w") as tar:
        info = tarfile.TarInfo("manifest.json")
        info.type = tarfile.SYMTYPE
        info.linkname = "elsewhere"
        tar.addfile(info)
    with pytest.raises(identity.PortableImageIdentityError, match="archive_link_member_forbidden"):
        identity.parse_image_archive(archive)


def test_duplicate_json_key_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "dup-json.tar"
    layer = b"x"
    diff = "sha256:" + _sha(layer)
    raw = (
        '{"architecture":"arm64","os":"linux","rootfs":{"type":"layers","diff_ids":["'
        + diff
        + '"]},"config":{"Cmd":["a"],"Cmd":["b"]}}'
    ).encode()
    config_name = _sha(raw) + ".json"
    manifest = [{"Config": config_name, "RepoTags": [], "Layers": ["layer.tar"]}]
    with tarfile.open(archive, "w") as tar:
        _tar_add(tar, config_name, raw)
        _tar_add(tar, "manifest.json", json.dumps(manifest).encode())
        _tar_add(tar, "layer.tar", layer)
    with pytest.raises(identity.PortableImageIdentityError, match="duplicate_json_key"):
        identity.parse_image_archive(archive)


@pytest.mark.parametrize(
    ("stderr", "status", "reason"),
    [
        (b"Error: No such image", "NOT_FOUND", "image_not_found"),
        (b"permission denied", "PERMISSION_DENIED", "docker_permission_denied"),
        (b"Cannot connect to the Docker daemon", "DAEMON_UNAVAILABLE", "docker_daemon_unavailable"),
    ],
)
def test_docker_observation_distinguishes_failure_classes(
    stderr: bytes,
    status: str,
    reason: str,
) -> None:
    def runner(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 1, b"", stderr)

    observed = identity.observe_docker_image("local/manager:test", runner=runner)
    assert observed.status == status
    assert observed.reason == reason


def test_malformed_docker_inspect_is_unsupported() -> None:
    def runner(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 0, b"not-json", b"")

    observed = identity.observe_docker_image("local/manager:test", runner=runner)
    assert observed.status == "MALFORMED_RESPONSE"
    assert observed.reason == "docker_inspect_malformed"


def test_runtime_known_docker_default_representations_are_normalized(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "image.tar"
    config, _ = _classic_archive(archive)
    parsed = identity.parse_image_archive(archive)
    runtime = _runtime(config)
    runtime["Config"] = dict(runtime["Config"])
    runtime["Config"].update({
        "Entrypoint": runtime["Config"].get("Entrypoint"),
        "Cmd": [],
        "Env": runtime["Config"].get("Env"),
        "User": runtime["Config"].get("User"),
        "WorkingDir": runtime["Config"].get("WorkingDir"),
        "Labels": runtime["Config"].get("Labels"),
        "Healthcheck": {},
        "StopSignal": "",
        "Volumes": {},
        "ExposedPorts": {},
    })
    assert identity.verify_runtime_document(parsed, runtime).status == "VERIFIED"


def test_classic_config_filename_must_bind_content_digest(tmp_path: Path) -> None:
    archive = tmp_path / "image.tar"
    layer = b"layer"
    diff = "sha256:" + _sha(layer)
    config = {
        "architecture": "arm64",
        "os": "linux",
        "rootfs": {"type": "layers", "diff_ids": [diff]},
        "config": {},
    }
    config_bytes = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    manifest = [{"Config": "wrong.json", "RepoTags": [], "Layers": ["layer.tar"]}]
    with tarfile.open(archive, "w") as tar:
        _tar_add(tar, "wrong.json", config_bytes)
        _tar_add(tar, "manifest.json", json.dumps(manifest).encode())
        _tar_add(tar, "layer.tar", layer)
    with pytest.raises(
        identity.PortableImageIdentityError,
        match="docker_config_digest_binding_mismatch",
    ):
        identity.parse_image_archive(archive)


def test_nul_archive_member_name_is_rejected() -> None:
    with pytest.raises(
        identity.PortableImageIdentityError,
        match="archive_member_name_invalid",
    ):
        identity._safe_name("bad\x00name")


def test_verifier_maps_observation_failure_classes_without_false_not_found(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "image.tar"
    config, _ = _classic_archive(archive)
    parsed = identity.parse_image_archive(archive)

    def missing(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 1, b"", b"Error: No such image")

    def daemon(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            [],
            1,
            b"",
            b"Cannot connect to the Docker daemon",
        )

    assert identity.verify_docker_image(
        parsed, "local/manager:test", runner=missing
    ).status == "MISMATCH"
    assert identity.verify_docker_image(
        parsed, "local/manager:test", runner=daemon
    ).status == "UNAVAILABLE"


def test_runtime_malformed_shape_is_unsupported_representation(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "image.tar"
    _classic_archive(archive)
    parsed = identity.parse_image_archive(archive)
    verdict = identity.verify_runtime_document(parsed, {"Id": "sha256:" + "1" * 64})
    assert verdict.status == "UNSUPPORTED_REPRESENTATION"


def test_archive_size_limit_is_enforced_before_hashing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = tmp_path / "image.tar"
    _classic_archive(archive)
    monkeypatch.setattr(identity, "MAX_ARCHIVE_BYTES", archive.stat().st_size - 1)
    with pytest.raises(
        identity.PortableImageIdentityError,
        match="archive_size_limit_exceeded",
    ):
        identity.parse_image_archive(archive)


def test_tar_member_limit_is_enforced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = tmp_path / "image.tar"
    _classic_archive(archive)
    monkeypatch.setattr(identity, "MAX_TAR_MEMBERS", 1)
    with pytest.raises(
        identity.PortableImageIdentityError,
        match="archive_member_limit_exceeded",
    ):
        identity.parse_image_archive(archive)


def test_identity_record_rejects_non_string_diff_id() -> None:
    value = {
        "schema": identity.SCHEMA,
        "representation": "docker-save",
        "archive_sha256": "1" * 64,
        "archive_size_bytes": 1,
        "os": "linux",
        "architecture": "arm64",
        "variant": None,
        "config_digest": "sha256:" + "2" * 64,
        "manifest_digest": None,
        "index_digest": None,
        "config_semantics_sha256": "3" * 64,
        "rootfs_diff_ids": [123],
        "rootfs_diff_ids_sha256": "4" * 64,
    }
    with pytest.raises(
        identity.PortableImageIdentityError,
        match="identity_rootfs_invalid",
    ):
        identity.identity_from_dict(value)


@pytest.mark.parametrize("invalid_size", [True, -1, "1"])
def test_expected_archive_size_type_is_strict(
    tmp_path: Path,
    invalid_size,
) -> None:
    archive = tmp_path / "image.tar"
    _classic_archive(archive)
    with pytest.raises(
        identity.PortableImageIdentityError,
        match="archive_expected_size_invalid",
    ):
        identity.parse_image_archive(
            archive,
            expected_archive_size_bytes=invalid_size,
        )
