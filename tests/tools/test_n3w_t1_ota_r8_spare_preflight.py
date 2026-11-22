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
    target, predecessor, backup, source, layout = module.recovery_material_documents(
        {
            "prepared_image_materials": prepared,
            "install_recovery_materials": installed,
        }
    )
    assert target == prepared["target"]
    assert predecessor == prepared["predecessor"]
    assert backup == {}
    assert source == "prepared_image_materials"
    assert layout == "transaction_directory_v2"


def test_recovery_material_documents_accepts_legacy_install_records():
    module = load_module()
    installed = {
        "target": {"kind": "target"},
        "predecessor": {"kind": "predecessor"},
        "backup": {},
    }
    target, predecessor, backup, source, layout = module.recovery_material_documents(
        {"install_recovery_materials": installed}
    )
    assert target == installed["target"]
    assert predecessor == installed["predecessor"]
    assert backup == installed["backup"]
    assert source == "install_recovery_materials_legacy"
    assert layout == "transaction_directory_v2"


def test_recovery_material_documents_fails_closed_without_records():
    module = load_module()
    with pytest.raises(ValueError, match="recovery_material_records_unavailable"):
        module.recovery_material_documents({})


def test_recovery_material_documents_accepts_original_p3_fields():
    module = load_module()
    document = {
        "target_artifact_identity": {"kind": "target"},
        "predecessor_recovery_identity": {"kind": "predecessor"},
        "ha_data_backup_identity": {"archive_sha256": "a" * 64},
    }
    target, predecessor, backup, source, layout = module.recovery_material_documents(document)
    assert target == document["target_artifact_identity"]
    assert predecessor == document["predecessor_recovery_identity"]
    assert backup == document["ha_data_backup_identity"]
    assert source == "p3_terminal_identity_fields"
    assert layout == "p3_n3w_update_layout"


def test_p3_recovery_content_manifest_matches_original_canonical_contract():
    module = load_module()
    document = {
        "transaction_id_sha256": "1" * 64,
        "target_manifest_identity": {"release_identity": "release-a"},
        "target_artifact_identity": {"kind": "target", "archive_sha256": "2" * 64},
        "predecessor_recovery_identity": {"kind": "predecessor", "archive_sha256": "3" * 64},
        "ha_data_backup_identity": {"archive_sha256": "4" * 64},
    }
    authority = {
        "transaction_id_sha256": document["transaction_id_sha256"],
        "release_identity": "release-a",
        "target_artifact_identity": document["target_artifact_identity"],
        "predecessor_recovery_identity": document["predecessor_recovery_identity"],
        "ha_data_backup_identity": document["ha_data_backup_identity"],
    }
    expected = hashlib.sha256(
        json.dumps(authority, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert module.p3_recovery_content_manifest(document) == expected


def test_p3_recovery_content_manifest_fails_closed_when_authority_incomplete():
    module = load_module()
    with pytest.raises(ValueError, match="p3_recovery_content_authority_incomplete"):
        module.p3_recovery_content_manifest(
            {
                "transaction_id_sha256": "1" * 64,
                "target_manifest_identity": {},
                "target_artifact_identity": {},
                "predecessor_recovery_identity": {},
                "ha_data_backup_identity": {},
            }
        )
