from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import n3w_t1_golden_master_build as build
from n3w_t1_golden_master_common import public_tree_sha256


class FakeLive:
    def preflight_master(self):
        return {
            "status": "PASS",
            "instance_material_absent": True,
            "production_service_start": False,
        }

    def load_images(self):
        return {
            "status": "PASS",
            "image_count": 3,
            "offline": True,
            "registry_pull": False,
            "platform": "linux/arm64",
            "production_service_start": False,
        }

    def stage_public_runtime(self, candidate_root: Path):
        product = candidate_root / "stage/opt-HomeAssistant"
        production = product / "infra/n3w-t1/production"
        production.mkdir(parents=True)
        (product / "public.txt").write_text("public", encoding="utf-8")
        (production / "image-lock.json").write_text(
            json.dumps(MANIFEST["image_lock"], sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "status": "PASS",
            "public_only": True,
            "instance_material_created": False,
            "services_stopped": True,
            "production_service_start": False,
        }


MANIFEST = {
    "source_head": "a" * 40,
    "image_lock": {"schema": "lock/1", "source_head": "a" * 40},
    "images": {
        label: {
            "image": f"local/{label}:1",
            "image_id": "sha256:" + char * 64,
            "platform": "linux/arm64",
            "tar_sha256": char * 64,
            "rootfs_layers_sha256": char * 64,
            "config_contract_sha256": char * 64,
        }
        for label, char in (
            ("homeassistant", "1"),
            ("manager", "2"),
            ("broker", "3"),
        )
    },
}


def test_build_adapter_stages_public_release_manifest(tmp_path: Path) -> None:
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "payload-manifest.json").write_text("{}\n", encoding="utf-8")
    candidate = tmp_path / "candidate"
    candidate.mkdir()

    adapter = build.GoldenMasterBuildAdapters(
        FakeLive(),
        payload_root=payload,
        manifest=MANIFEST,
        release_id="release-1",
    )
    report = adapter.stage_public_runtime(candidate)

    product = candidate / "stage/opt-HomeAssistant"
    release_path = product / build.RELEASE_RELATIVE_PATH
    document = json.loads(release_path.read_text(encoding="utf-8"))
    assert report["release_manifest_sha256"] == adapter.release_sha256
    assert document["schema"] == build.RELEASE_SCHEMA
    assert document["release_id"] == "release-1"
    assert document["instance_material_absent"] is True
    assert document["secret_values_included"] is False
    assert document["seal_state"] == "UNSEALED"
    assert document["public_source_tree_sha256"] == public_tree_sha256(
        product,
        excluded=frozenset({build.RELEASE_RELATIVE_PATH.as_posix()}),
    )
