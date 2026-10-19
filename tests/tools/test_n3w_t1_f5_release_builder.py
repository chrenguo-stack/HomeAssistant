from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path

from tools import n3w_t1_f5_release_builder as builder


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _runtime_archive(manifest: dict) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as bundle:
        raw = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
        info = tarfile.TarInfo("payload-manifest.json")
        info.size = len(raw)
        bundle.addfile(info, io.BytesIO(raw))
    return output.getvalue()


def test_mac_files_exist_and_use_real_f2_identity_probe() -> None:
    root = Path(__file__).resolve().parents[2]
    real_identity_probe = "tools/n3w_t1_os_identity_readonly_probe.py"
    stale_identity_executor = (
        "tools/execution_packages/n3w/f2/"
        "t1_fresh_readonly_identity/executor.py"
    )

    assert real_identity_probe in builder.MAC_FILES
    assert stale_identity_executor not in builder.MAC_FILES
    assert all((root / relative).is_file() for relative in builder.MAC_FILES)


def test_verify_f3_artifact_binds_images_transport_and_source(tmp_path: Path) -> None:
    source_head = "a" * 40
    image_bytes = {
        "manager": b"manager-image",
        "broker": b"broker-image",
        "homeassistant": b"ha-image",
    }
    filenames = {
        "manager": "greenhouse-manager-arm64.tar",
        "broker": "broker-arm64.tar",
        "homeassistant": "homeassistant-arm64.tar",
    }
    images = {
        label: {
            "artifact_file": filenames[label],
            "tar_sha256": _sha(raw),
            "tar_size_bytes": len(raw),
            "loaded_size_bytes": len(raw) * 2,
            "required_free_bytes": len(raw) * 3,
            "path": "incoming/" + filenames[label],
            "image": "local/" + label,
            "image_id": "sha256:" + _sha(label.encode()),
        }
        for label, raw in image_bytes.items()
    }
    transport_images = {
        label: {
            "path": record["path"],
            "artifact_file": record["artifact_file"],
            "tar_sha256": record["tar_sha256"],
            "tar_size_bytes": record["tar_size_bytes"],
            "loaded_size_bytes": record["loaded_size_bytes"],
            "required_free_bytes": record["required_free_bytes"],
            "image_ref": record["image"],
        }
        for label, record in images.items()
    }
    manifest = {
        "schema": builder.F3_SCHEMA,
        "source_head": source_head,
        "images": images,
        "files": [],
        "transport": {"images": transport_images},
        "secret_values_included": False,
        "production_service_start": False,
        "board_access": False,
    }
    runtime = _runtime_archive(manifest)
    with tarfile.open(fileobj=io.BytesIO(runtime), mode="r:gz") as bundle:
        member = bundle.getmember("payload-manifest.json")
        stream = bundle.extractfile(member)
        assert stream is not None
        manifest_raw = stream.read()
    capacity = {
        "schema": builder.CAPACITY_SCHEMA,
        "source_head": source_head,
        "images": transport_images,
    }
    capacity_raw = (json.dumps(capacity, sort_keys=True) + "\n").encode()
    baseline = b"print('baseline')\n"
    artifact = tmp_path / "f3.zip"
    with zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_STORED) as outer:
        outer.writestr("runtime-payload.tar.gz", runtime)
        outer.writestr("runtime-payload.sha256", _sha(runtime) + "\n")
        outer.writestr("payload-manifest.sha256", _sha(manifest_raw) + "\n")
        outer.writestr("capacity-contract.json", capacity_raw)
        outer.writestr("capacity-contract.sha256", _sha(capacity_raw) + "\n")
        for label, raw in image_bytes.items():
            outer.writestr(filenames[label], raw)
        outer.writestr("executor.sha256", "0" * 64 + "\n")
        outer.writestr("host-wrapper.py", b"wrapper\n")
        outer.writestr("host-wrapper.sha256", _sha(b"wrapper\n") + "\n")
        outer.writestr("host-baseline.py", baseline)
        outer.writestr("host-baseline.sha256", _sha(baseline) + "\n")

    result = builder.verify_f3(
        artifact,
        builder.sha_file(artifact),
        source_head,
    )

    assert result["f3_payload"] == builder.sha_file(artifact)
    assert result["manager_image_tar"] == images["manager"]["tar_sha256"]
    assert result["manager_image_content"] == builder.canonical_sha256(
        images["manager"]
    )
    assert result["transport_contract"] == _sha(capacity_raw)


def test_control_artifact_extracts_exact_manifest(tmp_path: Path) -> None:
    source_head = "b" * 40
    payload = b"payload\n"
    manifest = {
        "schema": "example/1",
        "source_head": source_head,
        "files": [
            {
                "path": "tools/item.py",
                "sha256": _sha(payload),
                "size": len(payload),
            }
        ],
        "secret_values_included": False,
        "board_access": False,
    }
    manifest_raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as bundle:
        for name, raw in (
            ("pkg/tools/item.py", payload),
            ("pkg/manifest.json", manifest_raw),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            bundle.addfile(info, io.BytesIO(raw))
    tar_bytes = tar_buffer.getvalue()
    report = {
        "status": "PASS",
        "source_head": source_head,
        "secret_values_included": False,
        "board_access": False,
    }
    outer = tmp_path / "control.zip"
    with zipfile.ZipFile(outer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("pkg.tar", tar_bytes)
        archive.writestr("pkg.tar.sha256", _sha(tar_bytes) + "  pkg.tar\n")
        archive.writestr("report.json", json.dumps(report))

    out = tmp_path / "out"
    digest = builder.extract_control(
        outer,
        builder.sha_file(outer),
        "pkg.tar",
        "pkg.tar.sha256",
        "report.json",
        "pkg",
        "manifest.json",
        out,
        source_head,
    )

    assert digest == builder.sha_file(out / "manifest.json")
    assert (out / "tools/item.py").read_bytes() == payload


def test_file_set_manifest_is_sorted_and_bound(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    records = [
        {"path": "b", "sha256": _sha(b"b"), "size": 1},
        {"path": "a", "sha256": _sha(b"a"), "size": 1},
    ]
    path = root / "manifest.json"
    digest = builder.file_set_manifest(path, "scope", "c" * 40, records)
    document = json.loads(path.read_text())

    assert [item["path"] for item in document["files"]] == ["a", "b"]
    assert digest == builder.sha_file(path)
