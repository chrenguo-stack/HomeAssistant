from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load(
    "n3w_t1_production_v2_contract_release_builder",
    "n3w_t1_production_v2_contract.py",
)
builder = load(
    "n3w_t1_f5_v2_release_builder_test",
    "n3w_t1_f5_v2_release_builder.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_inputs(tmp_path: Path) -> Path:
    artifacts = {}
    for index, name in enumerate(sorted(contract.REQUIRED_RELEASE_ARTIFACTS), start=1):
        relative = contract.RELEASE_INPUT_ARTIFACT_PATHS[name]
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((name + "\n").encode() * index)
        artifacts[name] = {
            "path": relative,
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        }
    head, tree = exact_source()
    document = {
        "schema": builder.INPUT_SCHEMA,
        "source_head": head,
        "source_tree": tree,
        "os_contract": {
            "ID": "ubuntu",
            "VERSION_ID": "26.04",
            "VERSION_CODENAME": "resolute",
            "PRETTY_NAME": "Armbian OS 26.05.0 resolute",
            "BOARD": "S912-Phicomm-T1",
            "BOARD_NAME": "Aml.S912",
            "VERSION": "26.05.0",
            "BRANCH": "current",
            "ARCH": "arm64",
            "IMAGE_TYPE": "rebuild",
            "kernel_arch": "aarch64",
        },
        "packages": {
            "docker.io": "29.1.3-0ubuntu4.1",
            "docker-compose-v2": "2.40.3+ds1-0ubuntu1",
        },
        "apt_source_policy": {
            "host": "ports.ubuntu.com",
            "suite": "resolute",
            "component": "universe",
            "architecture": "arm64",
        },
        "artifacts": artifacts,
        "capacity": {"minimum_post_peak_free_bytes": 5 * 1024**3},
        "public_evidence_fields": [
            "status",
            "release_id",
            "source_head",
            "run_id_sha256",
        ],
    }
    path = tmp_path / "release-inputs.json"
    path.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return path


def exact_source():
    head = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD^{tree}"],
        text=True,
    ).strip()
    return head, tree


def test_builder_binds_exact_source_and_every_required_artifact(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    head, tree = exact_source()
    destination = tmp_path / "release"
    report = builder.build_release(
        ROOT,
        inputs,
        destination,
        source_head=head,
        source_tree=tree,
        production_authority=False,
    )
    verified = builder.verify_release_directory(destination)
    manifest = json.loads(
        (destination / builder.MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert report["status"] == "PASS"
    assert report["production_authority"] is False
    assert report["source_head"] == head
    assert report["source_tree"] == tree
    assert set(manifest["artifacts"]) == set(contract.REQUIRED_RELEASE_ARTIFACTS)
    assert verified["release_sha256"] == report["release_sha256"]


def test_builder_is_deterministic_for_same_source_and_inputs(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    head, tree = exact_source()
    first = builder.build_release(
        ROOT,
        inputs,
        tmp_path / "first",
        source_head=head,
        source_tree=tree,
    )
    second = builder.build_release(
        ROOT,
        inputs,
        tmp_path / "second",
        source_head=head,
        source_tree=tree,
    )
    assert first["release_id"] == second["release_id"]
    assert first["release_sha256"] == second["release_sha256"]


def test_verify_rejects_artifact_tamper(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    head, tree = exact_source()
    destination = tmp_path / "release"
    builder.build_release(
        ROOT,
        inputs,
        destination,
        source_head=head,
        source_tree=tree,
    )
    target = destination / builder.ARTIFACT_DIR / "f3_payload"
    target.write_bytes(target.read_bytes() + b"tamper")
    with pytest.raises(
        builder.ReleaseBuildError,
        match="release_artifact_binding_invalid:f3_payload",
    ):
        builder.verify_release_directory(destination)


def test_production_authority_requires_exact_origin_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    inputs = write_inputs(tmp_path)
    head, tree = exact_source()
    original = builder._git

    def fake_git(repository, *args):
        if args == ("rev-parse", "origin/main"):
            return "0" * 40
        return original(repository, *args)

    monkeypatch.setattr(builder, "_git", fake_git)
    with pytest.raises(
        builder.ReleaseBuildError,
        match="production_source_not_exact_merged_main",
    ):
        builder.build_release(
            ROOT,
            inputs,
            tmp_path / "release",
            source_head=head,
            source_tree=tree,
            production_authority=True,
        )


def test_inputs_cannot_escape_artifact_root(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    document = json.loads(inputs.read_text(encoding="utf-8"))
    document["artifacts"]["f3_payload"]["path"] = "../outside"
    inputs.write_text(json.dumps(document) + "\n", encoding="utf-8")
    head, tree = exact_source()
    with pytest.raises(
        builder.ReleaseBuildError,
        match="release_inputs_artifact_path_invalid:f3_payload",
    ):
        builder.build_release(
            ROOT,
            inputs,
            tmp_path / "release",
            source_head=head,
            source_tree=tree,
        )



def test_builder_rejects_release_inputs_from_different_source(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    document = json.loads(inputs.read_text(encoding="utf-8"))
    document["source_head"] = "0" * 40
    inputs.write_text(json.dumps(document) + "\n", encoding="utf-8")
    head, tree = exact_source()
    with pytest.raises(
        builder.ReleaseBuildError,
        match="release_inputs_source_head_mismatch",
    ):
        builder.build_release(
            ROOT,
            inputs,
            tmp_path / "release",
            source_head=head,
            source_tree=tree,
        )


def test_builder_rejects_symlinked_artifact_input(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    target = tmp_path / contract.RELEASE_INPUT_ARTIFACT_PATHS["f3_payload"]
    real = tmp_path / "real-f3-payload.bin"
    real.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(real)
    head, tree = exact_source()
    with pytest.raises(
        builder.ReleaseBuildError,
        match="artifact_source_symlink:f3_payload",
    ):
        builder.build_release(
            ROOT,
            inputs,
            tmp_path / "release",
            source_head=head,
            source_tree=tree,
        )



def test_builder_rejects_unreviewed_extra_artifact_name(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    document = json.loads(inputs.read_text(encoding="utf-8"))
    extra = tmp_path / "extra.bin"
    extra.write_bytes(b"unexpected")
    document["artifacts"]["unexpected_extra"] = {
        "path": extra.name,
        "sha256": sha256(extra),
        "size_bytes": extra.stat().st_size,
    }
    inputs.write_text(json.dumps(document) + "\n", encoding="utf-8")
    head, tree = exact_source()
    with pytest.raises(
        builder.ReleaseBuildError,
        match="release_inputs_artifact_set_invalid",
    ):
        builder.build_release(
            ROOT,
            inputs,
            tmp_path / "release",
            source_head=head,
            source_tree=tree,
        )


def test_builder_rejects_frozen_input_component_tamper(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    target = tmp_path / contract.RELEASE_INPUT_ARTIFACT_PATHS["f3_payload"]
    target.write_bytes(target.read_bytes() + b"tamper")
    head, tree = exact_source()
    with pytest.raises(
        builder.ReleaseBuildError,
        match="artifact_input_binding_mismatch:f3_payload",
    ):
        builder.build_release(
            ROOT,
            inputs,
            tmp_path / "release",
            source_head=head,
            source_tree=tree,
        )


def test_verify_rejects_wrong_release_id_even_with_updated_sidecar(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    head, tree = exact_source()
    destination = tmp_path / "release"
    builder.build_release(
        ROOT,
        inputs,
        destination,
        source_head=head,
        source_tree=tree,
    )
    manifest_path = destination / builder.MANIFEST_NAME
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["release_id"] = "f" * 64
    manifest_path.write_bytes(builder.canonical_json_bytes(document))
    (destination / builder.SHA_NAME).write_text(
        sha256(manifest_path) + "\n",
        encoding="ascii",
    )
    with pytest.raises(
        builder.ReleaseBuildError,
        match="release_manifest_invalid",
    ):
        builder.verify_release_directory(destination)


def test_verify_rejects_manifest_and_directory_with_extra_artifact(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    head, tree = exact_source()
    destination = tmp_path / "release"
    builder.build_release(
        ROOT,
        inputs,
        destination,
        source_head=head,
        source_tree=tree,
    )
    extra = destination / builder.ARTIFACT_DIR / "unexpected"
    extra.write_bytes(b"unexpected")
    manifest_path = destination / builder.MANIFEST_NAME
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["artifacts"]["unexpected"] = {
        "sha256": sha256(extra),
        "size_bytes": extra.stat().st_size,
    }
    material = dict(document)
    material.pop("release_id")
    document["release_id"] = builder.canonical_sha256(material)
    manifest_path.write_bytes(builder.canonical_json_bytes(document))
    (destination / builder.SHA_NAME).write_text(
        sha256(manifest_path) + "\n",
        encoding="ascii",
    )
    with pytest.raises(
        builder.ReleaseBuildError,
        match="release_manifest_invalid",
    ):
        builder.verify_release_directory(destination)


def test_verify_rejects_extra_release_root_file(tmp_path: Path):
    inputs = write_inputs(tmp_path)
    head, tree = exact_source()
    destination = tmp_path / "release"
    builder.build_release(
        ROOT,
        inputs,
        destination,
        source_head=head,
        source_tree=tree,
    )
    (destination / "unexpected").write_text("x", encoding="utf-8")
    with pytest.raises(
        builder.ReleaseBuildError,
        match="release_root_set_invalid",
    ):
        builder.verify_release_directory(destination)


def _write_flat_tar(path: Path, entries: dict[str, bytes]) -> None:
    with tarfile.open(path, "w") as bundle:
        for name, payload in sorted(entries.items()):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.mtime = 0
            bundle.addfile(info, io.BytesIO(payload))


def _write_control_tar(
    path: Path,
    tmp_path: Path,
    *,
    source_head: str,
    reboot: bool,
) -> None:
    root_name = "reboot-successor-control" if reboot else "f4-package"
    manifest_name = (
        "reboot-successor-manifest.json"
        if reboot
        else "f4-package-manifest.json"
    )
    schema = builder.REBOOT_PACKAGE_SCHEMA if reboot else builder.F4_PACKAGE_SCHEMA
    package = tmp_path / f"{root_name}-local"
    payload = package / "tools/example.py"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_text("control\n", encoding="utf-8")
    boundary = (
        {
            "secret_values_included": False,
            "live_runtime_mutation": False,
            "reboot_executed": False,
            "board_access": False,
        }
        if reboot
        else {
            "secret_values_included": False,
            "production_service_start": False,
            "board_access": False,
        }
    )
    manifest = {
        "schema": schema,
        "source_head": source_head,
        "files": [
            {
                "path": "tools/example.py",
                "sha256": sha256(payload),
                "size": payload.stat().st_size,
            }
        ],
        **boundary,
    }
    (package / manifest_name).write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    with tarfile.open(path, "w") as bundle:
        bundle.add(package, arcname=root_name)


def _write_mac_tools_tar(
    path: Path,
    *,
    source_head: str,
    tamper: bool = False,
) -> None:
    records = []
    entries: dict[str, bytes] = {}
    for index, relative in enumerate(builder.MAC_TOOL_FILES):
        payload = (ROOT / relative).read_bytes()
        if tamper and index == 0:
            payload += b"tamper"
        entries[relative] = payload
        records.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    manifest = {
        "schema": builder.MAC_TOOLS_SCHEMA,
        "source_head": source_head,
        "files": records,
    }
    entries["manifest.json"] = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    _write_flat_tar(path, entries)


def write_valid_local_bundle(
    tmp_path: Path,
    *,
    source_head: str,
    source_tree: str,
    mac_tool_tamper: bool = False,
) -> tuple[Path, str]:
    input_root = tmp_path / "local-inputs"
    artifacts_root = input_root / "artifacts"
    artifacts_root.mkdir(parents=True)

    _write_flat_tar(
        artifacts_root / "f3-payload.tar",
        {name: (name + "\n").encode() for name in builder.F3_PAYLOAD_FILES},
    )
    _write_flat_tar(
        artifacts_root / "f3-images.tar",
        {name: (name + "\n").encode() for name in builder.F3_IMAGE_FILES},
    )
    _write_control_tar(
        artifacts_root / "f4-control.tar",
        tmp_path,
        source_head=source_head,
        reboot=False,
    )
    _write_control_tar(
        artifacts_root / "reboot-control.tar",
        tmp_path,
        source_head=source_head,
        reboot=True,
    )
    _write_mac_tools_tar(
        artifacts_root / "v2-mac-tools.tar",
        source_head=source_head,
        tamper=mac_tool_tamper,
    )
    (artifacts_root / "transport-contract.json").write_text(
        json.dumps(
            {
                "schema": builder.TRANSPORT_SCHEMA,
                "source_head": source_head,
                "transport": {"schema": "fixture/1"},
                "capacity": {"fixture": True},
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )

    records = {}
    for name, relative in contract.RELEASE_INPUT_ARTIFACT_PATHS.items():
        artifact = input_root / relative
        records[name] = {
            "path": relative,
            "sha256": sha256(artifact),
            "size_bytes": artifact.stat().st_size,
        }
    inputs = {
        "schema": builder.INPUT_SCHEMA,
        "source_head": source_head,
        "source_tree": source_tree,
        "os_contract": {
            "ID": "ubuntu",
            "VERSION_ID": "26.04",
            "VERSION_CODENAME": "resolute",
            "PRETTY_NAME": "Armbian OS 26.05.0 resolute",
            "BOARD": "S912-Phicomm-T1",
            "BOARD_NAME": "Aml.S912",
            "VERSION": "26.05.0",
            "BRANCH": "current",
            "ARCH": "arm64",
            "IMAGE_TYPE": "rebuild",
            "kernel_arch": "aarch64",
        },
        "packages": {
            "docker.io": "29.1.3-0ubuntu4.1",
            "docker-compose-v2": "2.40.3+ds1-0ubuntu1",
        },
        "apt_source_policy": {
            "host": "ports.ubuntu.com",
            "suite": "resolute",
            "component": "universe",
            "architecture": "arm64",
        },
        "artifacts": records,
        "capacity": {"minimum_post_peak_free_bytes": 5 * 1024**3},
        "public_evidence_fields": [
            "status",
            "release_id",
            "source_head",
            "run_id_sha256",
        ],
    }
    inputs_path = input_root / "release-inputs.json"
    inputs_path.write_text(
        json.dumps(inputs, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    release_root = tmp_path / builder.RELEASE_ROOT_NAME
    builder.build_release(
        ROOT,
        inputs_path,
        release_root,
        source_head=source_head,
        source_tree=source_tree,
    )
    release_tar = tmp_path / builder.FINAL_TAR_NAME
    with tarfile.open(release_tar, "w:gz") as bundle:
        bundle.add(release_root, arcname=builder.RELEASE_ROOT_NAME)
    release_sidecar = tmp_path / builder.FINAL_TAR_SHA_NAME
    release_sidecar.write_text(
        sha256(release_tar) + "  " + str(release_tar) + "\n",
        encoding="ascii",
    )
    artifact_zip = tmp_path / "artifact.zip"
    with zipfile.ZipFile(artifact_zip, "w") as bundle:
        bundle.write(release_tar, arcname=builder.FINAL_TAR_NAME)
        bundle.write(release_sidecar, arcname=builder.FINAL_TAR_SHA_NAME)
    return artifact_zip, sha256(artifact_zip)


def write_github_metadata(
    tmp_path: Path,
    *,
    source_head: str,
    artifact_sha256: str,
    artifact_name: str,
    run_id: int,
    run_attempt: int,
    artifact_id: int,
) -> tuple[Path, Path]:
    run_path = tmp_path / f"run-{run_id}-{artifact_id}.json"
    artifact_path = tmp_path / f"artifact-{artifact_id}.json"
    run_path.write_text(
        json.dumps(
            {
                "id": run_id,
                "path": (
                    ".github/workflows/"
                    "n3w-t1-f5-v2-exact-production-release-ci.yml"
                ),
                "head_sha": source_head,
                "head_branch": "main",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "run_attempt": run_attempt,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    artifact_path.write_text(
        json.dumps(
            {
                "id": artifact_id,
                "name": artifact_name,
                "expired": False,
                "digest": "sha256:" + artifact_sha256,
                "workflow_run": {"id": run_id},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return run_path, artifact_path


def test_local_bundle_validation_binds_external_and_internal_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_head = "a" * 40
    source_tree = "b" * 40

    def fake_git(repository: Path, *args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return source_head
        if args == ("rev-parse", "HEAD^{tree}"):
            return source_tree
        if args == ("rev-parse", "origin/main"):
            return source_head
        raise AssertionError(args)

    monkeypatch.setattr(builder, "_git", fake_git)
    artifact_zip, artifact_sha = write_valid_local_bundle(
        tmp_path,
        source_head=source_head,
        source_tree=source_tree,
    )
    binding_path = tmp_path / "binding.json"
    artifact_name = builder.FINAL_ARTIFACT_NAME_PREFIX + source_head
    run_metadata, artifact_metadata = write_github_metadata(
        tmp_path,
        source_head=source_head,
        artifact_sha256=artifact_sha,
        artifact_name=artifact_name,
        run_id=456,
        run_attempt=1,
        artifact_id=123,
    )
    report = builder.verify_release_bundle(
        ROOT,
        artifact_zip,
        expected_artifact_sha256=artifact_sha,
        run_metadata=run_metadata,
        artifact_metadata=artifact_metadata,
        artifact_name=artifact_name,
        artifact_id=123,
        run_id=456,
        run_attempt=1,
        source_head=source_head,
        source_tree=source_tree,
        binding_json=binding_path,
    )
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["artifact_zip_sha256"] == artifact_sha
    assert report["source_head"] == source_head
    assert report["source_tree"] == source_tree
    assert binding["artifact_id"] == 123
    assert binding["run_id"] == 456
    assert binding["release_id"] == report["release_id"]


def test_local_bundle_validation_rejects_github_artifact_digest_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_head = "a" * 40
    source_tree = "b" * 40
    monkeypatch.setattr(
        builder,
        "_git",
        lambda _repository, *args: {
            ("rev-parse", "HEAD"): source_head,
            ("rev-parse", "HEAD^{tree}"): source_tree,
            ("rev-parse", "origin/main"): source_head,
        }[args],
    )
    artifact_zip, _ = write_valid_local_bundle(
        tmp_path,
        source_head=source_head,
        source_tree=source_tree,
    )
    artifact_name = builder.FINAL_ARTIFACT_NAME_PREFIX + source_head
    run_metadata, artifact_metadata = write_github_metadata(
        tmp_path,
        source_head=source_head,
        artifact_sha256="f" * 64,
        artifact_name=artifact_name,
        run_id=2,
        run_attempt=1,
        artifact_id=1,
    )
    with pytest.raises(
        builder.ReleaseBuildError,
        match="local_artifact_zip_sha256_mismatch",
    ):
        builder.verify_release_bundle(
            ROOT,
            artifact_zip,
            expected_artifact_sha256="f" * 64,
            run_metadata=run_metadata,
            artifact_metadata=artifact_metadata,
            artifact_name=artifact_name,
            artifact_id=1,
            run_id=2,
            run_attempt=1,
            source_head=source_head,
            source_tree=source_tree,
        )


def test_local_bundle_validation_rejects_mac_tool_source_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_head = "a" * 40
    source_tree = "b" * 40
    monkeypatch.setattr(
        builder,
        "_git",
        lambda _repository, *args: {
            ("rev-parse", "HEAD"): source_head,
            ("rev-parse", "HEAD^{tree}"): source_tree,
            ("rev-parse", "origin/main"): source_head,
        }[args],
    )
    artifact_zip, artifact_sha = write_valid_local_bundle(
        tmp_path,
        source_head=source_head,
        source_tree=source_tree,
        mac_tool_tamper=True,
    )
    artifact_name = builder.FINAL_ARTIFACT_NAME_PREFIX + source_head
    run_metadata, artifact_metadata = write_github_metadata(
        tmp_path,
        source_head=source_head,
        artifact_sha256=artifact_sha,
        artifact_name=artifact_name,
        run_id=2,
        run_attempt=1,
        artifact_id=1,
    )
    with pytest.raises(
        builder.ReleaseBuildError,
        match="local_mac_tools_source_binding_mismatch",
    ):
        builder.verify_release_bundle(
            ROOT,
            artifact_zip,
            expected_artifact_sha256=artifact_sha,
            run_metadata=run_metadata,
            artifact_metadata=artifact_metadata,
            artifact_name=artifact_name,
            artifact_id=1,
            run_id=2,
            run_attempt=1,
            source_head=source_head,
            source_tree=source_tree,
        )


def test_local_bundle_validation_rejects_unexpected_zip_member(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_head = "a" * 40
    source_tree = "b" * 40
    monkeypatch.setattr(
        builder,
        "_git",
        lambda _repository, *args: {
            ("rev-parse", "HEAD"): source_head,
            ("rev-parse", "HEAD^{tree}"): source_tree,
            ("rev-parse", "origin/main"): source_head,
        }[args],
    )
    artifact_zip, _ = write_valid_local_bundle(
        tmp_path,
        source_head=source_head,
        source_tree=source_tree,
    )
    with zipfile.ZipFile(artifact_zip, "a") as bundle:
        bundle.writestr("../unexpected", b"x")
    artifact_sha = sha256(artifact_zip)
    artifact_name = builder.FINAL_ARTIFACT_NAME_PREFIX + source_head
    run_metadata, artifact_metadata = write_github_metadata(
        tmp_path,
        source_head=source_head,
        artifact_sha256=artifact_sha,
        artifact_name=artifact_name,
        run_id=2,
        run_attempt=1,
        artifact_id=1,
    )
    with pytest.raises(
        builder.ReleaseBuildError,
        match="local_artifact_zip_file_set_invalid",
    ):
        builder.verify_release_bundle(
            ROOT,
            artifact_zip,
            expected_artifact_sha256=artifact_sha,
            run_metadata=run_metadata,
            artifact_metadata=artifact_metadata,
            artifact_name=artifact_name,
            artifact_id=1,
            run_id=2,
            run_attempt=1,
            source_head=source_head,
            source_tree=source_tree,
        )


def test_local_bundle_validation_rejects_run_metadata_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_head = "a" * 40
    source_tree = "b" * 40
    monkeypatch.setattr(
        builder,
        "_git",
        lambda _repository, *args: {
            ("rev-parse", "HEAD"): source_head,
            ("rev-parse", "HEAD^{tree}"): source_tree,
            ("rev-parse", "origin/main"): source_head,
        }[args],
    )
    artifact_zip, artifact_sha = write_valid_local_bundle(
        tmp_path,
        source_head=source_head,
        source_tree=source_tree,
    )
    artifact_name = builder.FINAL_ARTIFACT_NAME_PREFIX + source_head
    run_metadata, artifact_metadata = write_github_metadata(
        tmp_path,
        source_head=source_head,
        artifact_sha256=artifact_sha,
        artifact_name=artifact_name,
        run_id=2,
        run_attempt=1,
        artifact_id=1,
    )
    run_document = json.loads(run_metadata.read_text(encoding="utf-8"))
    run_document["head_sha"] = "c" * 40
    run_metadata.write_text(json.dumps(run_document) + "\n", encoding="utf-8")
    with pytest.raises(
        builder.ReleaseBuildError,
        match="local_run_metadata_binding_invalid",
    ):
        builder.verify_release_bundle(
            ROOT,
            artifact_zip,
            expected_artifact_sha256=artifact_sha,
            run_metadata=run_metadata,
            artifact_metadata=artifact_metadata,
            artifact_name=artifact_name,
            artifact_id=1,
            run_id=2,
            run_attempt=1,
            source_head=source_head,
            source_tree=source_tree,
        )
