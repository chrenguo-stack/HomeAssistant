from __future__ import annotations

import argparse
import hashlib
import importlib.util
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = (
    ROOT
    / "tools/execution_packages/n3w/production/board_b_preflight/executor.py"
)

spec = importlib.util.spec_from_file_location(
    "n3w_production_board_b_preflight_executor", MODULE_PATH
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_exact_production_artifact_binding() -> None:
    assert module.PRODUCT_SOURCE == "c1b3d9d016d06c21c9ff7070c0043163739565ca"
    assert module.PRODUCT_TREE == "0c857fb0f830239717a2e937d176903a6acae8ac"
    assert module.WORKFLOW_TRIGGER_SHA == "433b91c19bf436a832021d821bda53261b7e3532"
    assert module.WORKFLOW_RUN_ID == 35612622035
    assert module.ARTIFACT_ID == 10644667734
    assert module.ARTIFACT_ZIP_SIZE == 4269260
    assert (
        module.ARTIFACT_ZIP_SHA256
        == "02fbe69f78511f33dec150dee635925dd4decf81048de3adfc6db8af4acc7a72"
    )
    assert module.RELEASE_BUNDLE_SIZE == 4268748
    assert (
        module.RELEASE_BUNDLE_SHA256
        == "93d830368b74e0dae904a9f5c4450378694575c68b917e749b480455662ff065"
    )
    assert (
        module.MEMBER_BINDINGS["firmware.bin"][1]
        == "8bcd89aaf0be64188f8f98a64795fe78d573ae82dd2dd360c7ff459f80e58efa"
    )
    assert (
        module.MEMBER_BINDINGS["firmware.factory.bin"][1]
        == "434a3996ea8dc74c4a356f54d8a9405202f17b500680a66f5d49a2089cf67774"
    )


def test_target_binding_does_not_reuse_stale_historical_identity_or_override() -> None:
    assert not hasattr(module, "EXPECTED_HARDWARE_ID_SHA256")
    assert module.CURRENT_DEPLOYED_SOURCE == "4270f24a92a87dd5239d781ebba624c2f34b7fc2"
    assert module.CURRENT_DEPLOYED_ARTIFACT_ID == 10619047221
    assert module.CURRENT_DEPLOYED_APPLICATION_SIZE == 1145984
    assert (
        module.CURRENT_DEPLOYED_APPLICATION_SHA256
        == "b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843"
    )


def test_validate_artifact_requires_outer_inner_sidecar_and_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_bytes = b"A=1\n"
    app_bytes = b"app"

    inner = tmp_path / "release.zip"
    with zipfile.ZipFile(inner, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("MANIFEST.txt", manifest_bytes)
        zf.writestr("firmware.bin", app_bytes)
    inner_bytes = inner.read_bytes()
    inner_sha = hashlib.sha256(inner_bytes).hexdigest()

    outer = tmp_path / "artifact.zip"
    sidecar_name = "release.zip.sha256"
    sidecar = f"{inner_sha}  release.zip\n".encode()
    with zipfile.ZipFile(outer, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("release.zip", inner_bytes)
        zf.writestr(sidecar_name, sidecar)

    monkeypatch.setattr(module, "RELEASE_BUNDLE", "release.zip")
    monkeypatch.setattr(module, "RELEASE_BUNDLE_SIZE", len(inner_bytes))
    monkeypatch.setattr(module, "RELEASE_BUNDLE_SHA256", inner_sha)
    monkeypatch.setattr(module, "RELEASE_SIDECAR", sidecar_name)
    monkeypatch.setattr(
        module, "EXPECTED_OUTER_MEMBERS", {"release.zip", sidecar_name}
    )
    monkeypatch.setattr(
        module, "EXPECTED_RELEASE_MEMBERS", {"MANIFEST.txt", "firmware.bin"}
    )
    monkeypatch.setattr(
        module,
        "MEMBER_BINDINGS",
        {
            "MANIFEST.txt": (
                len(manifest_bytes),
                hashlib.sha256(manifest_bytes).hexdigest(),
            ),
            "firmware.bin": (
                len(app_bytes),
                hashlib.sha256(app_bytes).hexdigest(),
            ),
        },
    )
    monkeypatch.setattr(module, "EXPECTED_MANIFEST", {"A": "1"})
    monkeypatch.setattr(module, "ARTIFACT_ZIP_SIZE", outer.stat().st_size)
    monkeypatch.setattr(
        module, "ARTIFACT_ZIP_SHA256", hashlib.sha256(outer.read_bytes()).hexdigest()
    )

    extracted = tmp_path / "extracted"
    extracted.mkdir()
    result = module.validate_artifact(outer, extracted)

    assert result["application"].read_bytes() == app_bytes
    assert result["manifest"].read_bytes() == manifest_bytes


def test_probe_is_read_only_and_binds_fresh_rom_plus_current_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_mac = "02:00:00:00:00:42"
    partition = bytes((index % 251 for index in range(64)))
    current_app = bytes((index % 239 for index in range(128)))

    monkeypatch.setattr(module, "PARTITION_TABLE_SIZE", len(partition))
    monkeypatch.setattr(
        module, "PARTITION_TABLE_SHA256", hashlib.sha256(partition).hexdigest()
    )
    monkeypatch.setattr(module, "CURRENT_DEPLOYED_APPLICATION_SIZE", len(current_app))
    monkeypatch.setattr(
        module,
        "CURRENT_DEPLOYED_APPLICATION_SHA256",
        hashlib.sha256(current_app).hexdigest(),
    )

    calls: list[list[str]] = []

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        calls.append(args)
        if args[-1] == "get-security-info":
            return (
                "Chip is ESP32-C6 (QFN40)\n"
                f"MAC: {raw_mac}\n"
                "Secure Boot: Disabled\n"
                "Flash Encryption: Disabled\n"
            )
        if args[-1] == "flash-id":
            return "Detected flash size: 8 MB\n"
        if "read-flash" in args:
            idx = args.index("read-flash")
            offset = int(args[idx + 1], 16)
            destination = Path(args[idx + 3])
            if offset == module.PARTITION_TABLE_OFFSET:
                destination.write_bytes(partition)
            elif offset == module.CURRENT_DEPLOYED_APPLICATION_OFFSET:
                destination.write_bytes(current_app)
            else:
                raise AssertionError(args)
            return "Read complete\n"
        raise AssertionError(args)

    monkeypatch.setattr(module, "run_capture", fake_run)

    result = module.probe_board("/dev/cu.synthetic")
    assert result["hardware_id_sha256"] == module.public_identity_sha256(raw_mac)
    assert "raw_mac" not in result
    assert result["chip"] == "ESP32-C6"
    assert result["flash_size"] == "8MB"
    assert result["secure_boot"] is False
    assert result["flash_encryption"] is False
    assert result["current_application_sha256"] == hashlib.sha256(current_app).hexdigest()

    flattened = [token for call in calls for token in call]
    assert "get-security-info" in flattened
    assert "flash-id" in flattened
    assert flattened.count("read-flash") == 2
    forbidden = {
        "write-flash",
        "erase-flash",
        "erase-region",
        "write-mem",
        "write-flash-status",
    }
    assert forbidden.isdisjoint(flattened)
    assert all("--no-stub" in call for call in calls)


def test_probe_rejects_current_application_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_mac = "02:00:00:00:00:42"
    partition = b"p" * 32
    current_app = b"a" * 64

    monkeypatch.setattr(module, "PARTITION_TABLE_SIZE", len(partition))
    monkeypatch.setattr(
        module, "PARTITION_TABLE_SHA256", hashlib.sha256(partition).hexdigest()
    )
    monkeypatch.setattr(module, "CURRENT_DEPLOYED_APPLICATION_SIZE", len(current_app))
    monkeypatch.setattr(module, "CURRENT_DEPLOYED_APPLICATION_SHA256", "0" * 64)

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        if args[-1] == "get-security-info":
            return (
                "Chip is ESP32-C6 (QFN40)\n"
                f"MAC: {raw_mac}\n"
                "Secure Boot: Disabled\n"
                "Flash Encryption: Disabled\n"
            )
        if args[-1] == "flash-id":
            return "Detected flash size: 8 MB\n"
        if "read-flash" in args:
            idx = args.index("read-flash")
            offset = int(args[idx + 1], 16)
            destination = Path(args[idx + 3])
            destination.write_bytes(
                partition
                if offset == module.PARTITION_TABLE_OFFSET
                else current_app
            )
            return "Read complete\n"
        raise AssertionError(args)

    monkeypatch.setattr(module, "run_capture", fake_run)

    with pytest.raises(module.StopExecution, match="current deployed PR437"):
        module.probe_board("/dev/cu.synthetic")


def test_operator_confirmation_is_required_before_board_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    touched = False

    def fake_validate(*args: object, **kwargs: object) -> dict[str, Path]:
        nonlocal touched
        touched = True
        raise AssertionError("must not be called")

    monkeypatch.setattr(module, "validate_artifact", fake_validate)

    args = argparse.Namespace(
        confirm_target="WRONG",
        artifact_zip="/tmp/artifact.zip",
        port="/dev/cu.synthetic",
        output="/tmp/preflight.json",
    )
    with pytest.raises(module.StopExecution, match="target confirmation"):
        module.run_preflight(args)
    assert touched is False
