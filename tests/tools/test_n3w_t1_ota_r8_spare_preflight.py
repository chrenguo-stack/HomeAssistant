import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SOURCE = (
    Path(__file__).resolve().parents[2]
    / "tools/execution_packages/n3w/t1_ota_r8_spare_preflight/preflight.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("r8_spare_preflight", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r8_spare_preflight_package_binding_is_fail_closed(tmp_path, monkeypatch):
    module = load_module()
    package = b"synthetic-pyz"
    files = {"ha-recovery.pyz": hashlib.sha256(package).hexdigest()}
    for index in range(10):
        name = f"fixture-{index}.txt"
        payload = f"fixture-{index}".encode()
        (tmp_path / name).write_bytes(payload)
        files[name] = hashlib.sha256(payload).hexdigest()
    (tmp_path / "ha-recovery.pyz").write_bytes(package)
    manifest = {
        "schema": "gh.n3w-t1-ha-recovery-install/1",
        "source_head": module.SOURCE_HEAD,
        "files": files,
    }
    manifest_bytes = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    (tmp_path / "manifest.json").write_bytes(manifest_bytes)
    monkeypatch.setattr(module, "MANIFEST_SHA256", hashlib.sha256(manifest_bytes).hexdigest())
    monkeypatch.setattr(module, "PACKAGE_SHA256", hashlib.sha256(package).hexdigest())
    assert module.read_package(tmp_path) == package

    (tmp_path / "fixture-0.txt").write_text("drift")
    with pytest.raises(ValueError, match="recovery_package_file_sha256_mismatch"):
        module.read_package(tmp_path)


def test_r8_spare_preflight_wrapper_contains_no_live_mutation_commands():
    source = SOURCE.read_text()
    forbidden = (
        'docker", "image", "rm',
        'docker", "image", "load',
        'docker", "container", "rm',
        'systemctl", "stop',
        'systemctl", "start',
        'systemctl", "restart',
        'mount", "--internal-only',
        '"umount"',
        '"wipefs"',
        '"mkfs',
    )
    for token in forbidden:
        assert token not in source


def test_recovery_material_documents_prefers_prepared_records():
    module = load_module()
    prepared = {
        "target": {"kind": "target"},
        "predecessor": {"kind": "predecessor"},
    }
    installed = {
        "target": {"kind": "target-old"},
        "predecessor": {"kind": "predecessor-old"},
        "backup": {},
    }
    target, predecessor, source = module.recovery_material_documents(
        {
            "prepared_image_materials": prepared,
            "install_recovery_materials": installed,
        }
    )
    assert target == prepared["target"]
    assert predecessor == prepared["predecessor"]
    assert source == "prepared_image_materials"


def test_recovery_material_documents_accepts_legacy_install_records():
    module = load_module()
    installed = {
        "target": {"kind": "target"},
        "predecessor": {"kind": "predecessor"},
        "backup": {},
    }
    target, predecessor, source = module.recovery_material_documents(
        {"install_recovery_materials": installed}
    )
    assert target == installed["target"]
    assert predecessor == installed["predecessor"]
    assert source == "install_recovery_materials_legacy"


def test_recovery_material_documents_fails_closed_without_records():
    module = load_module()
    with pytest.raises(ValueError, match="recovery_material_records_unavailable"):
        module.recovery_material_documents({})
