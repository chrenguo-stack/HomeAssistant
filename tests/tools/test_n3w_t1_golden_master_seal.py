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


class FakeRunner:
    def __init__(self, image_id: str = "sha256:" + "1" * 64) -> None:
        self.image_id = image_id

    def run(
        self,
        argv,
        *,
        allowed=frozenset({0}),
    ) -> str:
        command = tuple(argv)
        if command[:3] == ("docker", "image", "inspect"):
            image = {
                "local/homeassistant:1": "1",
                "local/manager:1": "2",
                "local/broker:1": "3",
            }[command[3]]
            char = image
            return json.dumps(
                [
                    {
                        "Id": "sha256:" + char * 64,
                        "Architecture": "arm64",
                        "Os": "linux",
                        "RootFS": {"Layers": []},
                        "Config": {},
                    }
                ]
            )
        if command == ("docker", "ps", "-aq"):
            return ""
        if command == ("docker", "volume", "ls", "-q"):
            return ""
        if command == ("docker", "network", "ls", "--format", "{{.Name}}"):
            return "bridge\nhost\nnone\n"
        if command == ("ss", "-H", "-lntu"):
            return ""
        if command == ("iptables-save", "-t", "filter"):
            return ""
        if command[:5] == (
            "systemctl",
            "show",
            "-p",
            "LoadState",
            "--value",
        ):
            return "loaded\n" if command[5] == seal.GUARD_UNIT else "not-found\n"
        if command == ("systemctl", "is-active", seal.GUARD_UNIT):
            return "inactive\n"
        if command == ("systemctl", "is-enabled", seal.GUARD_UNIT):
            return "disabled\n"
        raise AssertionError(command)


def _normalized_hash(value: object) -> str:
    return seal._normalized_hash(value)


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
                "image_id": "sha256:" + char * 64,
                "platform": "linux/arm64",
                "tar_sha256": char * 64,
                "rootfs_layers_sha256": _normalized_hash([]),
                "config_contract_sha256": _normalized_hash(
                    seal._image_config_contract({})
                ),
            }
            for label, char in (
                ("homeassistant", "1"),
                ("manager", "2"),
                ("broker", "3"),
            )
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


def _neutralize_host_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        seal,
        "INSTANCE_PATHS",
        (str(tmp_path / "instance-absent"),),
    )
    monkeypatch.setattr(
        seal,
        "EXTRA_ABSENT",
        (str(tmp_path / "extra-absent"),),
    )
    monkeypatch.setattr(seal, "STAGING_GLOBS", ())


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


def test_public_audit_proves_non_identity_quiescence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _neutralize_host_paths(monkeypatch, tmp_path)
    report = seal.audit_public_master(
        _source(tmp_path),
        runner=FakeRunner(),
    )

    assert report["status"] == "PASS"
    assert report["instance_material_absent"] is True
    assert report["product_container_count"] == 0
    assert report["product_volume_count"] == 0
    assert report["product_network_count"] == 0
    assert report["product_listener_count"] == 0
    assert report["product_firewall_active"] is False
    assert report["activation_units_absent"] is True
    assert report["staging_residue_absent"] is True
    assert report["disk_capture_ready"] is False


def test_public_audit_rejects_instance_material(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    present = tmp_path / "instance-present"
    present.mkdir()
    monkeypatch.setattr(seal, "INSTANCE_PATHS", (str(present),))
    monkeypatch.setattr(seal, "EXTRA_ABSENT", ())
    monkeypatch.setattr(seal, "STAGING_GLOBS", ())

    with pytest.raises(
        seal.GoldenMasterSealHostError,
        match="instance_or_activation_path_present",
    ):
        seal.audit_public_master(
            _source(tmp_path),
            runner=FakeRunner(),
        )


def test_public_audit_rejects_image_id_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _neutralize_host_paths(monkeypatch, tmp_path)
    root = _source(tmp_path)
    runner = FakeRunner()

    original = runner.run

    def drift(argv, *, allowed=frozenset({0})):
        output = original(argv, allowed=allowed)
        if tuple(argv)[:3] == ("docker", "image", "inspect"):
            document = json.loads(output)
            document[0]["Id"] = "sha256:" + "f" * 64
            return json.dumps(document)
        return output

    runner.run = drift

    with pytest.raises(
        seal.GoldenMasterSealHostError,
        match="image_exact_binding_invalid",
    ):
        seal.audit_public_master(root, runner=runner)


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
