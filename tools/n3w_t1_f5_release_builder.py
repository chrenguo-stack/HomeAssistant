#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

FILE_SET_SCHEMA = "gh.n3w-t1-production-file-set/1"
PROVENANCE_SCHEMA = "gh.n3w-t1-f5-approved-release-provenance/1"
INDEX_SCHEMA = "gh.n3w-t1-f5-approved-release-file-index/1"
F3_SCHEMA = "gh.n3w-t1-fresh-bootstrap-payload/2"
CAPACITY_SCHEMA = "gh.n3w-t1-fresh-capacity/1"

MAC_FILES = (
    "tools/n3w_t1_production.py",
    "tools/n3w_t1_production_runtime.py",
    "tools/n3w_t1_ssh_transport.py",
    "tools/n3w_t1_production_contract.py",
    "tools/n3w_t1_fresh_product_staging_host.py",
    "tools/n3w_t1_minimal_baseline_readonly_inventory.py",
    "tools/execution_packages/n3w/f2/t1_fresh_readonly_preflight/executor.py",
    "tools/n3w_t1_os_identity_readonly_probe.py",
)

TARGET_FILES = (
    "tools/n3w_t1_production_authority.py",
    "tools/n3w_t1_production_contract.py",
    "tools/n3w_t1_fresh_host_baseline.py",
)

F3_FILES = frozenset({
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
})


class ReleaseBuildError(RuntimeError):
    pass


def sha_stream(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def sha_file(path: Path):
    with path.open("rb") as stream:
        return sha_stream(stream)


def canonical_sha256(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def sidecar(raw: bytes):
    text = raw.decode("utf-8").strip()
    token = text.split()[0] if text else ""
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise ReleaseBuildError("sha256_sidecar_invalid")
    return token


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReleaseBuildError(f"module_load_failed:{path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def verify_source(root: Path, head: str, tree: str):
    observed_head = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    observed_tree = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"], text=True
    ).strip()
    if observed_head != head:
        raise ReleaseBuildError("source_head_mismatch")
    if observed_tree != tree:
        raise ReleaseBuildError("source_tree_mismatch")


def copy_record(source_root: Path, output_root: Path, relative: str):
    source = source_root / relative
    target = output_root / relative
    if source.is_symlink() or not source.is_file():
        raise ReleaseBuildError(f"source_file_invalid:{relative}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return {
        "path": relative,
        "sha256": sha_file(target),
        "size": target.stat().st_size,
    }


def file_set_manifest(path: Path, scope: str, head: str, records):
    document = {
        "schema": FILE_SET_SCHEMA,
        "scope": scope,
        "source_head": head,
        "files": sorted(records, key=lambda item: item["path"]),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(document))
    return sha_file(path)


def runtime_manifest(outer: zipfile.ZipFile):
    expected_archive = sidecar(outer.read("runtime-payload.sha256"))
    with outer.open("runtime-payload.tar.gz") as stream:
        if sha_stream(stream) != expected_archive:
            raise ReleaseBuildError("f3_runtime_archive_sha256_mismatch")
    expected_manifest = sidecar(outer.read("payload-manifest.sha256"))
    with outer.open("runtime-payload.tar.gz") as stream:
        with tarfile.open(fileobj=stream, mode="r|gz") as bundle:
            for member in bundle:
                if member.isfile() and member.name.lstrip("./") == "payload-manifest.json":
                    handle = bundle.extractfile(member)
                    if handle is None:
                        break
                    raw = handle.read()
                    if hashlib.sha256(raw).hexdigest() != expected_manifest:
                        raise ReleaseBuildError("f3_manifest_sha256_mismatch")
                    value = json.loads(raw.decode("utf-8"))
                    if isinstance(value, dict):
                        return value
    raise ReleaseBuildError("f3_manifest_missing")


def verify_f3(path: Path, expected_sha: str, head: str):
    if sha_file(path) != expected_sha:
        raise ReleaseBuildError("f3_artifact_sha256_mismatch")
    with zipfile.ZipFile(path) as outer:
        names = {item.filename for item in outer.infolist() if not item.is_dir()}
        if names != F3_FILES:
            raise ReleaseBuildError("f3_artifact_file_set_invalid")
        manifest = runtime_manifest(outer)
        if manifest.get("schema") != F3_SCHEMA or manifest.get("source_head") != head:
            raise ReleaseBuildError("f3_manifest_binding_invalid")
        if any(
            key in manifest
            for key in ("authorization_id", "authorization_claimed", "authorization_consumed")
        ):
            raise ReleaseBuildError("f3_artifact_contains_runtime_authority")
        if (
            manifest.get("secret_values_included") is not False
            or manifest.get("production_service_start") is not False
            or manifest.get("board_access") is not False
        ):
            raise ReleaseBuildError("f3_artifact_safety_boundary_invalid")
        capacity_raw = outer.read("capacity-contract.json")
        if hashlib.sha256(capacity_raw).hexdigest() != sidecar(
            outer.read("capacity-contract.sha256")
        ):
            raise ReleaseBuildError("f3_capacity_sha256_mismatch")
        capacity = json.loads(capacity_raw.decode("utf-8"))
        if (
            not isinstance(capacity, dict)
            or capacity.get("schema") != CAPACITY_SCHEMA
            or capacity.get("source_head") != head
            or capacity.get("images") != manifest.get("transport", {}).get("images")
        ):
            raise ReleaseBuildError("f3_capacity_binding_invalid")
        images = manifest.get("images")
        if not isinstance(images, dict) or set(images) != {"manager", "broker", "homeassistant"}:
            raise ReleaseBuildError("f3_images_invalid")
        file_names = {
            "manager": "greenhouse-manager-arm64.tar",
            "broker": "broker-arm64.tar",
            "homeassistant": "homeassistant-arm64.tar",
        }
        release_names = {
            "manager": ("manager_image_tar", "manager_image_content"),
            "broker": ("mosquitto_image_tar", "mosquitto_image_content"),
            "homeassistant": ("home_assistant_image_tar", "home_assistant_image_content"),
        }
        result = {
            "f3_payload": expected_sha,
            "transport_contract": hashlib.sha256(capacity_raw).hexdigest(),
        }
        for label, filename in file_names.items():
            record = images[label]
            if not isinstance(record, dict):
                raise ReleaseBuildError(f"f3_image_record_invalid:{label}")
            info = outer.getinfo(filename)
            if info.file_size != record.get("tar_size_bytes"):
                raise ReleaseBuildError(f"f3_image_size_mismatch:{label}")
            with outer.open(filename) as stream:
                observed = sha_stream(stream)
            if observed != record.get("tar_sha256"):
                raise ReleaseBuildError(f"f3_image_sha256_mismatch:{label}")
            tar_name, content_name = release_names[label]
            result[tar_name] = observed
            result[content_name] = canonical_sha256(record)
        with outer.open("host-baseline.py") as stream:
            baseline_sha = sha_stream(stream)
        if baseline_sha != sidecar(outer.read("host-baseline.sha256")):
            raise ReleaseBuildError("f3_host_baseline_sha256_mismatch")
        return result


def extract_control(
    outer_path: Path,
    expected_outer_sha: str,
    tar_name: str,
    sidecar_name: str,
    report_name: str,
    prefix: str,
    manifest_name: str,
    output_root: Path,
    head: str,
):
    if sha_file(outer_path) != expected_outer_sha:
        raise ReleaseBuildError(f"control_outer_sha256_mismatch:{prefix}")
    with zipfile.ZipFile(outer_path) as outer:
        names = {item.filename for item in outer.infolist() if not item.is_dir()}
        if names != {tar_name, sidecar_name, report_name}:
            raise ReleaseBuildError(f"control_outer_file_set_invalid:{prefix}")
        tar_bytes = outer.read(tar_name)
        if hashlib.sha256(tar_bytes).hexdigest() != sidecar(outer.read(sidecar_name)):
            raise ReleaseBuildError(f"control_tar_sha256_mismatch:{prefix}")
        report = json.loads(outer.read(report_name).decode("utf-8"))
        if (
            not isinstance(report, dict)
            or report.get("status") != "PASS"
            or report.get("source_head") != head
            or report.get("secret_values_included") is not False
            or report.get("board_access") is not False
        ):
            raise ReleaseBuildError(f"control_build_report_invalid:{prefix}")
    output_root.mkdir(parents=True, exist_ok=True)
    expected_prefix = prefix.rstrip("/") + "/"
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as bundle:
        for member in bundle.getmembers():
            if not member.isfile():
                continue
            if not member.name.startswith(expected_prefix):
                raise ReleaseBuildError(f"control_prefix_invalid:{prefix}")
            relative = member.name[len(expected_prefix):]
            rel = Path(relative)
            if not relative or rel.is_absolute() or ".." in rel.parts:
                raise ReleaseBuildError(f"control_path_invalid:{prefix}")
            source = bundle.extractfile(member)
            if source is None:
                raise ReleaseBuildError(f"control_member_unreadable:{prefix}")
            target = output_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as stream:
                shutil.copyfileobj(source, stream)
    manifest_path = output_root / manifest_name
    if not manifest_path.is_file():
        raise ReleaseBuildError(f"control_manifest_missing:{prefix}")
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    if document.get("source_head") != head:
        raise ReleaseBuildError(f"control_manifest_source_mismatch:{prefix}")
    records = document.get("files")
    if not isinstance(records, list):
        raise ReleaseBuildError(f"control_manifest_files_invalid:{prefix}")
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise ReleaseBuildError(f"control_manifest_record_invalid:{prefix}")
        item = output_root / record["path"]
        if (
            item.is_symlink()
            or not item.is_file()
            or item.stat().st_size != record.get("size")
            or sha_file(item) != record.get("sha256")
        ):
            raise ReleaseBuildError(f"control_file_binding_invalid:{record['path']}")
    return sha_file(manifest_path)


def write_index(root: Path):
    index_path = root / "release-file-index.json"
    sidecar_path = root / "release-file-index.sha256"
    records = []
    for item in sorted(p for p in root.rglob("*") if p.is_file()):
        if item in {index_path, sidecar_path}:
            continue
        records.append({
            "path": item.relative_to(root).as_posix(),
            "sha256": sha_file(item),
            "size": item.stat().st_size,
        })
    index_path.write_bytes(json_bytes({"schema": INDEX_SCHEMA, "files": records}))
    digest = sha_file(index_path)
    sidecar_path.write_text(digest + "\n", encoding="utf-8")
    return digest


def verify_index(root: Path):
    index_path = root / "release-file-index.json"
    sidecar_path = root / "release-file-index.sha256"
    if (
        index_path.is_symlink()
        or not index_path.is_file()
        or sidecar_path.is_symlink()
        or not sidecar_path.is_file()
    ):
        raise ReleaseBuildError("release_index_missing")
    if sha_file(index_path) != sidecar(sidecar_path.read_bytes()):
        raise ReleaseBuildError("release_index_sha256_mismatch")
    document = json.loads(index_path.read_text(encoding="utf-8"))
    records = document.get("files") if isinstance(document, dict) else None
    if document.get("schema") != INDEX_SCHEMA or not isinstance(records, list):
        raise ReleaseBuildError("release_index_invalid")
    expected = {}
    for record in records:
        if (
            not isinstance(record, dict)
            or set(record) != {"path", "sha256", "size"}
            or not isinstance(record.get("path"), str)
            or not isinstance(record.get("sha256"), str)
            or not isinstance(record.get("size"), int)
            or isinstance(record.get("size"), bool)
        ):
            raise ReleaseBuildError("release_index_record_invalid")
        relative = Path(record["path"])
        if (
            relative.is_absolute()
            or not relative.parts
            or ".." in relative.parts
            or record["path"] in expected
        ):
            raise ReleaseBuildError("release_index_record_invalid")
        expected[record["path"]] = record
        item = root / relative
        if (
            item.is_symlink()
            or not item.is_file()
            or item.stat().st_size != record["size"]
            or sha_file(item) != record["sha256"]
        ):
            raise ReleaseBuildError(
                f"release_index_file_binding_invalid:{record['path']}"
            )
    actual = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item not in {index_path, sidecar_path}
    }
    if set(expected) != actual:
        raise ReleaseBuildError("release_index_file_set_mismatch")
    return sha_file(index_path)


def verify_release(root: Path):
    release_path = root / "approved-release.json"
    contract = load_module(
        root / "tools/n3w_t1_production_contract.py",
        "n3w_f5_verify_contract",
    )
    release = json.loads(release_path.read_text(encoding="utf-8"))
    normalized = contract.validate_release(release)
    sys.path.insert(0, str(root / "tools"))
    try:
        runtime = load_module(
            root / "tools/n3w_t1_production_runtime.py",
            "n3w_t1_production_runtime",
        )
        runtime._file_set_manifest(
            root / "artifacts/mac/manifest.json",
            root,
            expected_scope=runtime.MAC_FILE_SET_SCOPE,
            expected_sha256=normalized["artifacts"]["mac_orchestrator"]["sha256"],
            source_head=normalized["source_head"],
            required_files=runtime.MAC_REQUIRED_FILES,
        )
        target_records = runtime._file_set_manifest(
            root / "artifacts/target/manifest.json",
            root / "artifacts/target/files",
            expected_scope=runtime.TARGET_FILE_SET_SCOPE,
            expected_sha256=normalized["artifacts"]["target_authority"]["sha256"],
            source_head=normalized["source_head"],
            required_files=runtime.TARGET_REQUIRED_FILES,
        )
        runtime._package_manifest(
            root / "artifacts/f4",
            runtime.F4_MANIFEST_NAME,
            expected_sha256=normalized["artifacts"]["f4_control"]["sha256"],
            source_head=normalized["source_head"],
        )
        runtime._package_manifest(
            root / "artifacts/reboot",
            runtime.REBOOT_MANIFEST_NAME,
            expected_sha256=normalized["artifacts"]["reboot_control"]["sha256"],
            source_head=normalized["source_head"],
        )
        f3 = root / "artifacts/f3/artifact.zip"
        if sha_file(f3) != normalized["artifacts"]["f3_payload"]["sha256"]:
            raise ReleaseBuildError("release_f3_payload_binding_invalid")
        runtime._f3_payload_authority_binding(f3, target_records)
    finally:
        sys.path = [item for item in sys.path if item != str(root / "tools")]
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(root / "tools/n3w_t1_production.py"),
            "run",
            "--help",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ReleaseBuildError("release_entrypoint_not_runnable")
    if sha_file(root / "approved-release.json") != sidecar(
        (root / "approved-release.sha256").read_bytes()
    ):
        raise ReleaseBuildError("approved_release_sha256_mismatch")
    if (root / "release-file-index.json").is_file():
        verify_index(root)
    return normalized


def build(args):
    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    verify_source(source_root, args.source_head, args.source_tree)
    if output_root.exists():
        raise ReleaseBuildError("output_root_exists")
    output_root.mkdir(parents=True)

    mac_records = [
        copy_record(source_root, output_root, relative)
        for relative in MAC_FILES
    ]
    mac_sha = file_set_manifest(
        output_root / "artifacts/mac/manifest.json",
        "mac_orchestrator",
        args.source_head,
        mac_records,
    )

    target_records = []
    target_root = output_root / "artifacts/target/files"
    for relative in TARGET_FILES:
        source = source_root / relative
        target = target_root / Path(relative).name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target_records.append({
            "path": target.name,
            "sha256": sha_file(target),
            "size": target.stat().st_size,
        })
    target_sha = file_set_manifest(
        output_root / "artifacts/target/manifest.json",
        "target_authority",
        args.source_head,
        target_records,
    )

    f3 = verify_f3(args.f3_artifact, args.f3_artifact_sha256, args.source_head)
    f3_target = output_root / "artifacts/f3/artifact.zip"
    f3_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.f3_artifact, f3_target)

    f4_sha = extract_control(
        args.f4_artifact,
        args.f4_artifact_sha256,
        "n3w-t1-f4-control-package.tar",
        "n3w-t1-f4-control-package.tar.sha256",
        "build-report.json",
        "f4-package",
        "f4-package-manifest.json",
        output_root / "artifacts/f4",
        args.source_head,
    )
    reboot_sha = extract_control(
        args.reboot_artifact,
        args.reboot_artifact_sha256,
        "n3w-t1-f4-reboot-successor-control.tar",
        "n3w-t1-f4-reboot-successor-control.tar.sha256",
        "reboot-successor-build-report.json",
        "reboot-successor-control",
        "reboot-successor-manifest.json",
        output_root / "artifacts/reboot",
        args.source_head,
    )

    contract = load_module(
        source_root / "tools/n3w_t1_production_contract.py",
        "n3w_f5_build_contract",
    )
    artifacts = {
        "mac_orchestrator": {"sha256": mac_sha},
        "target_authority": {"sha256": target_sha},
        "f3_payload": {"sha256": f3["f3_payload"]},
        "f4_control": {"sha256": f4_sha},
        "reboot_control": {"sha256": reboot_sha},
        "manager_image_tar": {"sha256": f3["manager_image_tar"]},
        "manager_image_content": {"sha256": f3["manager_image_content"]},
        "mosquitto_image_tar": {"sha256": f3["mosquitto_image_tar"]},
        "mosquitto_image_content": {"sha256": f3["mosquitto_image_content"]},
        "home_assistant_image_tar": {"sha256": f3["home_assistant_image_tar"]},
        "home_assistant_image_content": {"sha256": f3["home_assistant_image_content"]},
        "transport_contract": {"sha256": f3["transport_contract"]},
    }
    release = {
        "schema": contract.RELEASE_SCHEMA,
        "release_id": "0" * 64,
        "source_head": args.source_head,
        "artifacts": artifacts,
        "environment": {
            "os": {
                "id": "ubuntu",
                "version": "26.04",
                "codename": "resolute",
            },
            "architecture": "aarch64",
            "package_source": "ubuntu_apt",
            "packages": {
                "docker.io": args.docker_package_version,
                "docker-compose-v2": args.compose_package_version,
            },
        },
        "check_policy": {
            "schema": contract.CHECK_POLICY_SCHEMA,
            "allow_overrides": [],
        },
        "result_schema": contract.RESULT_SCHEMA,
    }
    release["release_id"] = contract.canonical_sha256(
        {key: value for key, value in release.items() if key != "release_id"}
    )
    contract.validate_release(release)
    (output_root / "approved-release.json").write_bytes(json_bytes(release))
    (output_root / "approved-release.sha256").write_text(
        sha_file(output_root / "approved-release.json") + "\n",
        encoding="utf-8",
    )

    provenance = {
        "schema": PROVENANCE_SCHEMA,
        "source_head": args.source_head,
        "source_tree": args.source_tree,
        "builder_head": args.builder_head,
        "inputs": {
            "f3": {
                "workflow_run_id": args.f3_run_id,
                "artifact_id": args.f3_artifact_id,
                "artifact_sha256": args.f3_artifact_sha256,
            },
            "f4": {
                "workflow_run_id": args.f4_run_id,
                "artifact_id": args.f4_artifact_id,
                "artifact_sha256": args.f4_artifact_sha256,
            },
            "reboot": {
                "workflow_run_id": args.f4_run_id,
                "artifact_id": args.reboot_artifact_id,
                "artifact_sha256": args.reboot_artifact_sha256,
            },
        },
        "environment_authority": args.environment_authority,
        "approved_release_sha256": sha_file(output_root / "approved-release.json"),
        "secret_values_included": False,
        "production_run_included": False,
        "t1_access": False,
        "board_access": False,
    }
    (output_root / "release-provenance.json").write_bytes(json_bytes(provenance))
    index_sha = write_index(output_root)
    verify_release(output_root)

    return {
        "status": "PASS",
        "release_id": release["release_id"],
        "release_sha256": sha_file(output_root / "approved-release.json"),
        "source_head": args.source_head,
        "source_tree": args.source_tree,
        "f3_payload_sha256": f3["f3_payload"],
        "f4_control_sha256": f4_sha,
        "reboot_control_sha256": reboot_sha,
        "file_index_sha256": index_sha,
        "t1_access": False,
        "board_access": False,
    }


def make_parser():
    parser = argparse.ArgumentParser(prog="n3w-t1-f5-release-builder")
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    for name in (
        "source-head",
        "source-tree",
        "builder-head",
        "f3-artifact-sha256",
        "f4-artifact-sha256",
        "reboot-artifact-sha256",
        "docker-package-version",
        "compose-package-version",
        "environment-authority",
    ):
        build_parser.add_argument("--" + name, required=True)
    for name in ("f3-run-id", "f3-artifact-id", "f4-run-id", "f4-artifact-id", "reboot-artifact-id"):
        build_parser.add_argument("--" + name, type=int, required=True)
    for name in ("source-root", "output-root", "f3-artifact", "f4-artifact", "reboot-artifact"):
        build_parser.add_argument("--" + name, type=Path, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--release-root", type=Path, required=True)
    return parser


def main(argv=None):
    args = make_parser().parse_args(argv)
    try:
        if args.command == "build":
            result = build(args)
        else:
            release = verify_release(args.release_root.resolve())
            result = {
                "status": "PASS",
                "release_id": release["release_id"],
                "source_head": release["source_head"],
                "t1_access": False,
                "board_access": False,
            }
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
        tarfile.TarError,
        ReleaseBuildError,
        subprocess.SubprocessError,
    ) as error:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": str(error)[:300] or type(error).__name__,
                    "t1_access": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
