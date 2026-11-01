from __future__ import annotations

import importlib.util
import json
import sys
import tarfile
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
    "n3w_t1_production_v2_contract_release_inputs",
    "n3w_t1_production_v2_contract.py",
)
builder = load(
    "n3w_t1_f5_v2_release_inputs_builder_test",
    "n3w_t1_f5_v2_release_inputs_builder.py",
)

HEAD = "a" * 40
TREE = "b" * 40


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def write_sidecar(path: Path, target: Path) -> None:
    path.write_text(sha256(target) + "\n", encoding="ascii")


def repository_fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    for relative in builder.MAC_TOOL_FILES:
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative + "\n", encoding="utf-8")
    return repository


def profile_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "profile.json"
    write_json(
        path,
        {
            "schema": builder.PROFILE_SCHEMA,
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
            "public_evidence_fields": [
                "status",
                "release_id",
                "release_sha256",
                "source_head",
                "run_id_sha256",
            ],
        },
    )
    return path


def f3_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "f3"
    root.mkdir()
    image_records = {}
    transport_images = {}
    for index, name in enumerate(builder.F3_IMAGE_FILES, start=1):
        path = root / name
        path.write_bytes((name + "\n").encode("utf-8") * index)
        label = {
            "broker-arm64.tar": "broker",
            "greenhouse-manager-arm64.tar": "manager",
            "homeassistant-arm64.tar": "homeassistant",
        }[name]
        image_records[label] = {
            "artifact_file": name,
            "tar_sha256": sha256(path),
            "tar_size_bytes": path.stat().st_size,
            "path": f"incoming/{name}",
        }
        transport_images[label] = {
            "artifact_file": name,
            "tar_sha256": sha256(path),
            "tar_size_bytes": path.stat().st_size,
            "loaded_size_bytes": 1000 + index,
            "required_free_bytes": 5 * 1024**3 + 1000 + index + path.stat().st_size,
            "path": f"incoming/{name}",
            "image_ref": f"local/{label}:test",
        }

    manifest = {
        "schema": "gh.n3w-t1-fresh-bootstrap-payload/1",
        "source_head": HEAD,
        "images": image_records,
        "transport": {
            "schema": "gh.n3w-t1-fresh-transport/2",
            "remote_staging_root": "/var/tmp",
            "minimum_post_peak_free_bytes": 5 * 1024**3,
            "runtime_payload_uncompressed_bytes": 1234,
            "image_load_order": ["homeassistant", "manager", "broker"],
            "images": transport_images,
        },
        "secret_values_included": False,
        "production_service_start": False,
        "board_access": False,
    }
    runtime = root / "runtime-payload.tar.gz"
    payload_manifest = tmp_path / "payload-manifest.json"
    write_json(payload_manifest, manifest)
    with tarfile.open(runtime, "w:gz") as bundle:
        bundle.add(payload_manifest, arcname="payload-manifest.json")
        payload_tool = tmp_path / "n3w_t1_fresh_product_bootstrap.py"
        payload_tool.write_text("print('ok')\n", encoding="utf-8")
        bundle.add(
            payload_tool,
            arcname="tools/n3w_t1_fresh_product_bootstrap.py",
        )
    write_sidecar(root / "runtime-payload.sha256", runtime)
    (root / "payload-manifest.sha256").write_text(
        sha256(payload_manifest) + "\n",
        encoding="ascii",
    )

    capacity = {
        "schema": "gh.n3w-t1-fresh-capacity/1",
        "source_head": HEAD,
        "minimum_post_peak_free_bytes": 5 * 1024**3,
        "image_load_order": ["homeassistant", "manager", "broker"],
        "images": transport_images,
    }
    capacity_path = root / "capacity-contract.json"
    write_json(capacity_path, capacity)
    write_sidecar(root / "capacity-contract.sha256", capacity_path)

    for name in ("host-wrapper.py", "host-baseline.py"):
        path = root / name
        path.write_text(name + "\n", encoding="utf-8")
        write_sidecar(root / name.replace(".py", ".sha256"), path)

    (root / "executor.sha256").write_text(
        sha256(payload_tool) + "\n",
        encoding="ascii",
    )

    assert {path.name for path in root.iterdir()} == set(builder.F3_FILES)
    return root


def control_fixture(
    tmp_path: Path,
    *,
    reboot: bool,
) -> Path:
    root = tmp_path / ("reboot" if reboot else "f4")
    root.mkdir()
    if reboot:
        tar_name = "n3w-t1-f4-reboot-successor-control.tar"
        sidecar_name = tar_name + ".sha256"
        report_name = "reboot-successor-build-report.json"
        prefix = "reboot-successor-control"
        manifest_name = "reboot-successor-manifest.json"
        schema = builder.REBOOT_PACKAGE_SCHEMA
        boundary = {
            "secret_values_included": False,
            "live_runtime_mutation": False,
            "reboot_executed": False,
            "board_access": False,
        }
    else:
        tar_name = "n3w-t1-f4-control-package.tar"
        sidecar_name = tar_name + ".sha256"
        report_name = "build-report.json"
        prefix = "f4-package"
        manifest_name = "f4-package-manifest.json"
        schema = builder.F4_PACKAGE_SCHEMA
        boundary = {
            "secret_values_included": False,
            "production_service_start": False,
            "board_access": False,
        }

    package = tmp_path / f"{prefix}-source"
    payload = package / "tools/example.py"
    payload.parent.mkdir(parents=True)
    payload.write_text("control\n", encoding="utf-8")
    manifest = {
        "schema": schema,
        "source_head": HEAD,
        "files": [
            {
                "path": "tools/example.py",
                "sha256": sha256(payload),
                "size": payload.stat().st_size,
            }
        ],
        **boundary,
    }
    manifest_path = package / manifest_name
    write_json(manifest_path, manifest)

    archive = root / tar_name
    with tarfile.open(archive, "w") as bundle:
        bundle.add(package, arcname=prefix)
    (root / sidecar_name).write_text(
        f"{sha256(archive)}  out/{tar_name}\n",
        encoding="ascii",
    )
    report = {
        "status": "PASS",
        "source_head": HEAD,
        "file_count": 1,
        "manifest_sha256": sha256(manifest_path),
        **boundary,
    }
    write_json(root / report_name, report)
    return root


def rewrite_control_archive(
    root: Path,
    tmp_path: Path,
    *,
    reboot: bool,
    mode: str,
) -> None:
    if reboot:
        tar_name = "n3w-t1-f4-reboot-successor-control.tar"
        sidecar_name = tar_name + ".sha256"
        prefix = "reboot-successor-control"
        manifest_name = "reboot-successor-manifest.json"
        report_name = "reboot-successor-build-report.json"
        schema = builder.REBOOT_PACKAGE_SCHEMA
        boundary = {
            "secret_values_included": False,
            "live_runtime_mutation": False,
            "reboot_executed": False,
            "board_access": False,
        }
    else:
        tar_name = "n3w-t1-f4-control-package.tar"
        sidecar_name = tar_name + ".sha256"
        prefix = "f4-package"
        manifest_name = "f4-package-manifest.json"
        report_name = "build-report.json"
        schema = builder.F4_PACKAGE_SCHEMA
        boundary = {
            "secret_values_included": False,
            "production_service_start": False,
            "board_access": False,
        }

    package = tmp_path / f"{prefix}-{mode}"
    payload = package / "tools/example.py"
    payload.parent.mkdir(parents=True)
    payload.write_text(
        "tampered\n" if mode == "tamper" else "control\n",
        encoding="utf-8",
    )
    expected_payload = tmp_path / f"{prefix}-{mode}-expected.py"
    expected_payload.write_text("control\n", encoding="utf-8")
    manifest = {
        "schema": schema,
        "source_head": HEAD,
        "files": [
            {
                "path": "tools/example.py",
                "sha256": sha256(expected_payload),
                "size": expected_payload.stat().st_size,
            }
        ],
        **boundary,
    }
    manifest_path = package / manifest_name
    write_json(manifest_path, manifest)
    report = json.loads((root / report_name).read_text(encoding="utf-8"))
    report["manifest_sha256"] = sha256(manifest_path)
    write_json(root / report_name, report)

    if mode == "symlink":
        payload.unlink()
        payload.symlink_to(expected_payload)

    archive = root / tar_name
    with tarfile.open(archive, "w") as bundle:
        bundle.add(package, arcname=prefix)
        if mode == "path_escape":
            info = tarfile.TarInfo("../escape")
            body = b"escape"
            info.size = len(body)
            import io

            bundle.addfile(info, io.BytesIO(body))
    if mode == "duplicate":
        with tarfile.open(archive, "a") as bundle:
            bundle.add(
                manifest_path,
                arcname=f"{prefix}/{manifest_name}",
            )
    (root / sidecar_name).write_text(
        f"{sha256(archive)}  out/{tar_name}\n",
        encoding="ascii",
    )


def exact_git(
    repository: Path,
    *args: str,
) -> str:
    if args == ("rev-parse", "HEAD"):
        return HEAD
    if args == ("rev-parse", "HEAD^{tree}"):
        return TREE
    if args == ("rev-parse", "origin/main"):
        return HEAD
    raise AssertionError(args)


def test_builds_and_verifies_exact_release_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = repository_fixture(tmp_path)
    profile = profile_fixture(tmp_path)
    f3 = f3_fixture(tmp_path)
    f4 = control_fixture(tmp_path, reboot=False)
    reboot = control_fixture(tmp_path, reboot=True)
    monkeypatch.setattr(builder, "_git", exact_git)

    destination = tmp_path / "release-inputs"
    report = builder.build_inputs(
        repository,
        profile,
        f3,
        f4,
        reboot,
        destination,
        source_head=HEAD,
        source_tree=TREE,
        production_authority=True,
    )
    verified = builder.verify_inputs_directory(destination)
    document = json.loads(
        (destination / "release-inputs.json").read_text(encoding="utf-8")
    )

    assert report["status"] == "PASS"
    assert report["production_authority"] is True
    assert verified["status"] == "PASS"
    assert document["source_head"] == HEAD
    assert document["source_tree"] == TREE
    assert set(document["artifacts"]) == set(contract.REQUIRED_RELEASE_ARTIFACTS)
    assert report["artifact_count"] == len(contract.REQUIRED_RELEASE_ARTIFACTS)
    assert report["t1_access"] is False
    assert report["board_access"] is False


def test_rejects_f3_image_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = repository_fixture(tmp_path)
    profile = profile_fixture(tmp_path)
    f3 = f3_fixture(tmp_path)
    f4 = control_fixture(tmp_path, reboot=False)
    reboot = control_fixture(tmp_path, reboot=True)
    monkeypatch.setattr(builder, "_git", exact_git)
    target = f3 / "broker-arm64.tar"
    target.write_bytes(target.read_bytes() + b"tamper")

    with pytest.raises(
        builder.ReleaseInputsBuildError,
        match="f3_image_size_mismatch|f3_image_sha256_mismatch",
    ):
        builder.build_inputs(
            repository,
            profile,
            f3,
            f4,
            reboot,
            tmp_path / "release-inputs",
            source_head=HEAD,
            source_tree=TREE,
        )


def test_production_authority_rejects_non_main_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = repository_fixture(tmp_path)

    def mismatched_git(repository: Path, *args: str) -> str:
        if args == ("rev-parse", "origin/main"):
            return "c" * 40
        return exact_git(repository, *args)

    monkeypatch.setattr(builder, "_git", mismatched_git)
    with pytest.raises(
        builder.ReleaseInputsBuildError,
        match="production_source_not_exact_merged_main",
    ):
        builder.build_inputs(
            repository,
            profile_fixture(tmp_path),
            f3_fixture(tmp_path),
            control_fixture(tmp_path, reboot=False),
            control_fixture(tmp_path, reboot=True),
            tmp_path / "release-inputs",
            source_head=HEAD,
            source_tree=TREE,
            production_authority=True,
        )


def test_rejects_f4_source_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = repository_fixture(tmp_path)
    profile = profile_fixture(tmp_path)
    f3 = f3_fixture(tmp_path)
    f4 = control_fixture(tmp_path, reboot=False)
    reboot = control_fixture(tmp_path, reboot=True)
    report = json.loads((f4 / "build-report.json").read_text(encoding="utf-8"))
    report["source_head"] = "c" * 40
    write_json(f4 / "build-report.json", report)
    monkeypatch.setattr(builder, "_git", exact_git)

    with pytest.raises(
        builder.ReleaseInputsBuildError,
        match="f4_control_report_binding_invalid",
    ):
        builder.build_inputs(
            repository,
            profile,
            f3,
            f4,
            reboot,
            tmp_path / "release-inputs",
            source_head=HEAD,
            source_tree=TREE,
        )


def test_release_inputs_freeze_component_bytes_after_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = repository_fixture(tmp_path)
    monkeypatch.setattr(builder, "_git", exact_git)
    destination = tmp_path / "release-inputs"
    builder.build_inputs(
        repository,
        profile_fixture(tmp_path),
        f3_fixture(tmp_path),
        control_fixture(tmp_path, reboot=False),
        control_fixture(tmp_path, reboot=True),
        destination,
        source_head=HEAD,
        source_tree=TREE,
    )
    document_before = (destination / "release-inputs.json").read_bytes()
    target = destination / contract.RELEASE_INPUT_ARTIFACT_PATHS["f3_payload"]
    target.write_bytes(target.read_bytes() + b"tamper")
    assert (destination / "release-inputs.json").read_bytes() == document_before
    with pytest.raises(
        builder.ReleaseInputsBuildError,
        match="release_inputs_artifact_binding_mismatch:f3_payload",
    ):
        builder.verify_inputs_directory(destination)


def test_release_inputs_reject_extra_physical_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = repository_fixture(tmp_path)
    monkeypatch.setattr(builder, "_git", exact_git)
    destination = tmp_path / "release-inputs"
    builder.build_inputs(
        repository,
        profile_fixture(tmp_path),
        f3_fixture(tmp_path),
        control_fixture(tmp_path, reboot=False),
        control_fixture(tmp_path, reboot=True),
        destination,
        source_head=HEAD,
        source_tree=TREE,
    )
    (destination / "unexpected").write_text("x", encoding="utf-8")
    with pytest.raises(
        builder.ReleaseInputsBuildError,
        match="release_inputs_root_set_invalid",
    ):
        builder.verify_inputs_directory(destination)


def test_release_inputs_reject_component_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = repository_fixture(tmp_path)
    monkeypatch.setattr(builder, "_git", exact_git)
    destination = tmp_path / "release-inputs"
    builder.build_inputs(
        repository,
        profile_fixture(tmp_path),
        f3_fixture(tmp_path),
        control_fixture(tmp_path, reboot=False),
        control_fixture(tmp_path, reboot=True),
        destination,
        source_head=HEAD,
        source_tree=TREE,
    )
    target = destination / contract.RELEASE_INPUT_ARTIFACT_PATHS["transport_contract"]
    saved = tmp_path / "saved-transport.json"
    saved.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(saved)
    with pytest.raises(
        builder.ReleaseInputsBuildError,
        match="release_inputs_artifact_symlink:transport_contract",
    ):
        builder.verify_inputs_directory(destination)


@pytest.mark.parametrize(
    "mode,pattern",
    [
        ("tamper", "f4_control_manifest_file_binding_invalid"),
        ("symlink", "f4_control_tar_member_invalid"),
        ("duplicate", "f4_control_tar_member_invalid"),
        ("path_escape", "f4_control_tar_member_invalid"),
    ],
)
def test_rejects_unsafe_or_unbound_f4_inner_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    pattern: str,
) -> None:
    repository = repository_fixture(tmp_path)
    profile = profile_fixture(tmp_path)
    f3 = f3_fixture(tmp_path)
    f4 = control_fixture(tmp_path, reboot=False)
    reboot = control_fixture(tmp_path, reboot=True)
    rewrite_control_archive(
        f4,
        tmp_path,
        reboot=False,
        mode=mode,
    )
    monkeypatch.setattr(builder, "_git", exact_git)
    with pytest.raises(builder.ReleaseInputsBuildError, match=pattern):
        builder.build_inputs(
            repository,
            profile,
            f3,
            f4,
            reboot,
            tmp_path / "release-inputs",
            source_head=HEAD,
            source_tree=TREE,
        )


def test_rejects_control_report_manifest_digest_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = repository_fixture(tmp_path)
    f4 = control_fixture(tmp_path, reboot=False)
    report_path = f4 / "build-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["manifest_sha256"] = "f" * 64
    write_json(report_path, report)
    monkeypatch.setattr(builder, "_git", exact_git)
    with pytest.raises(
        builder.ReleaseInputsBuildError,
        match="f4_control_manifest_sha256_mismatch",
    ):
        builder.build_inputs(
            repository,
            profile_fixture(tmp_path),
            f3_fixture(tmp_path),
            f4,
            control_fixture(tmp_path, reboot=True),
            tmp_path / "release-inputs",
            source_head=HEAD,
            source_tree=TREE,
        )
