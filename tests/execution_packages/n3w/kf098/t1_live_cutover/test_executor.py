from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
PACKAGE = (
    ROOT
    / "tools/execution_packages/n3w/kf098/t1_live_cutover"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load_module("kf098_host_executor", PACKAGE / "executor.py")
remote = load_module(
    "kf098_remote_cutover",
    PACKAGE / "remote_cutover.py",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_host_transport_disables_stdin_consumption() -> None:
    ssh = host.ssh_argv("root@t1", "true")
    scp = host.scp_argv(Path("/tmp/a"), "root@t1", "/tmp/b")
    assert "-n" in ssh
    assert "BatchMode=yes" in ssh
    assert "-B" in scp
    assert "BatchMode=yes" in scp


@pytest.mark.parametrize(
    "value",
    (
        "",
        " root@t1",
        "root@t1 ",
        "root @t1",
        "t1_ssh_target",
        "<root@host>",
    ),
)
def test_host_target_validation_rejects_unsafe_values(
    value: str,
) -> None:
    with pytest.raises(host.StopExecution):
        host.validate_target(value)


def test_local_artifact_requires_exact_manifest_and_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = tmp_path / "greenhouse-manager-arm64.tar"
    image.write_bytes(b"image")
    image_sha = sha256(b"image")
    monkeypatch.setattr(host, "IMAGE_TAR_SHA256", image_sha)

    manifest = {
        "schema": "gh.n3w-manager-exact-source-artifact/1",
        "source": {"commit": host.SOURCE_SHA},
        "image": {
            "id": host.IMAGE_ID,
            "architecture": "arm64",
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_sha = sha256(manifest_path.read_bytes())
    (tmp_path / "manifest.sha256").write_text(
        f"{manifest_sha}  manifest.json\n",
        encoding="utf-8",
    )

    result = host.verify_local_artifact(tmp_path)
    assert result["artifact_id"] == host.ARTIFACT_ID
    assert result["image_tar_sha256"] == image_sha


def test_remote_env_rewrite_changes_only_pairing_value(
    tmp_path: Path,
) -> None:
    path = tmp_path / "manager.env"
    path.write_text(
        "GH_ALPHA=one\n"
        "GH_N3W_PAIRING_ADVERTISED_HOST=192.0.2.10\n"
        "GH_BETA=two\n",
        encoding="utf-8",
    )
    before = remote.env_without_target_hash(path)
    remote.rewrite_pairing_env_to_auto(path)
    assert remote.env_values(path, remote.PAIRING_KEY) == ["auto"]
    assert remote.env_without_target_hash(path) == before
    assert path.read_text(encoding="utf-8") == (
        "GH_ALPHA=one\n"
        "GH_N3W_PAIRING_ADVERTISED_HOST=auto\n"
        "GH_BETA=two\n"
    )


def test_remote_env_rewrite_rejects_duplicate_target(
    tmp_path: Path,
) -> None:
    path = tmp_path / "manager.env"
    path.write_text(
        "GH_N3W_PAIRING_ADVERTISED_HOST=192.0.2.10\n"
        "GH_N3W_PAIRING_ADVERTISED_HOST=192.0.2.11\n",
        encoding="utf-8",
    )
    with pytest.raises(remote.StopExecution):
        remote.rewrite_pairing_env_to_auto(path)


def test_remote_overlay_changes_only_manager_image_and_name(
    tmp_path: Path,
) -> None:
    path = tmp_path / "overlay.yml"
    remote.make_overlay(path, remote.NEW_IMAGE_TAG)
    text = path.read_text(encoding="utf-8")
    assert "services:" in text
    assert "manager:" in text
    assert f"image: {remote.NEW_IMAGE_TAG}" in text
    assert "container_name: greenhouse-manager" in text
    assert "pull_policy: never" in text
    assert "broker:" not in text
    assert "--remove-orphans" not in text


def test_remote_uses_current_pr480_activation_blob() -> None:
    assert (
        remote.EXPECTED_ACTIVATION_UNIT_BLOB
        == "5033b7475f4fafb1409ed277425197a93fd0d5a5"
    )


def test_remote_does_not_mutate_service_identities_source() -> None:
    source = (PACKAGE / "remote_cutover.py").read_text(
        encoding="utf-8"
    )
    assert "SERVICE_ENV" in source
    assert "rewrite_pairing_env_to_auto(MANAGER_ENV)" in source
    assert "rewrite_pairing_env_to_auto(SERVICE_ENV)" not in source
    assert "--remove-orphans" not in source


def test_git_blob_hash_uses_canonical_nul_header(
    tmp_path: Path,
) -> None:
    path = tmp_path / "blob"
    path.write_bytes(b"hello")
    expected = hashlib.sha1(b"blob 5\0hello").hexdigest()
    assert remote.git_blob_hash(path) == expected
