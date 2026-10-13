from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import n3w_t1_golden_master_seal as seal
from n3w_t1_golden_master_common import public_tree_sha256, sha256_file


def _source(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    production = root / "infra/n3w-t1/production"
    production.mkdir(parents=True)
    image_lock = production / "image-lock.json"
    image_lock.write_text("{}\n", encoding="utf-8")
    (root / "public.txt").write_text("public", encoding="utf-8")
    release = {
        "schema": seal.RELEASE_SCHEMA,
        "release_id": "release-1",
        "source_head": "a" * 40,
        "payload_manifest_sha256": "b" * 64,
        "image_lock_sha256": sha256_file(image_lock),
        "public_source_tree_sha256": "",
        "images": {
            label: {
                "image": f"local/{label}:1",
                "rootfs_layers_sha256": "c" * 64,
                "config_contract_sha256": "d" * 64,
            }
            for label in ("homeassistant", "manager", "broker")
        },
        "architecture": "linux/arm64",
        "instance_material_absent": True,
        "secret_values_included": False,
        "seal_state": "UNSEALED",
        "production_service_start": False,
    }
    release["public_source_tree_sha256"] = public_tree_sha256(root)
    path = root / seal.RELEASE_RELATIVE_PATH
    path.write_text(
        json.dumps(release, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def test_release_manifest_tree_binding_detects_drift(tmp_path: Path) -> None:
    root = _source(tmp_path)
    release = seal._load_release(root)
    assert (
        public_tree_sha256(
            root,
            excluded=frozenset({seal.RELEASE_RELATIVE_PATH.as_posix()}),
        )
        == release["public_source_tree_sha256"]
    )
    (root / "public.txt").write_text("drift", encoding="utf-8")
    with pytest.raises(
        seal.GoldenMasterSealHostError,
        match="public_source_tree_binding_invalid",
    ):
        seal.audit_public_master(root, runner=object())


def test_seal_fails_before_authorization_without_target_adapter(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        seal.GoldenMasterSealHostError,
        match="target_identity_adapter_required",
    ):
        seal.execute_seal(
            tmp_path,
            seal.AUTHORIZATION_ID,
        )
