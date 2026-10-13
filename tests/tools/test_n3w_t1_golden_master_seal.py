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
from n3w_t1_golden_master_common import (
    claim_authorization,
    public_tree_sha256,
    sha256_file,
)


class FakeRunner:
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
            return json.dumps(
                [
                    {
                        "Id": "sha256:" + image * 64,
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


def _configure_host_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, Path]:
    guard = tmp_path / "n3w-broker-ingress-guard"
    guard.write_text("guard\n", encoding="utf-8")
    guard.chmod(0o755)
    unit = tmp_path / "n3wfc4-broker-ingress-guard.service"
    unit.write_text("[Unit]\n", encoding="utf-8")
    unit.chmod(0o644)
    monkeypatch.setattr(
        seal,
        "PUBLIC_EXTERNAL_FILES",
        {
            "guard_binary": guard,
            "guard_unit": unit,
        },
    )
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
    namespace = tmp_path / "namespace"
    namespace.mkdir()
    allowed = namespace / "HomeAssistant"
    allowed.mkdir()
    monkeypatch.setattr(
        seal,
        "PRODUCT_NAMESPACE_RULES",
        ((namespace, ("HomeAssistant", "greenhouse-"), frozenset({"HomeAssistant"})),),
    )
    ledger = tmp_path / "ledger"
    monkeypatch.setattr(seal, "AUTHORIZATION_LEDGER_ROOT", ledger)
    return guard, unit


def _source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    guard, unit = _configure_host_policy(monkeypatch, tmp_path)
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
        "public_external_bindings": {
            "guard_binary": {
                "destination": str(guard),
                "sha256": sha256_file(guard),
                "mode": 0o755,
            },
            "guard_unit": {
                "destination": str(unit),
                "sha256": sha256_file(unit),
                "mode": 0o644,
            },
        },
        "architecture": "linux/arm64",
        "instance_material_absent": True,
        "secret_values_included": False,
        "build_authorization_id": seal.BUILD_AUTHORIZATION_ID,
        "authorization_ledger_policy": seal.AUTHORIZATION_LEDGER_POLICY,
        "seal_state": "UNSEALED",
        "production_service_start": False,
    }
    release["public_source_tree_sha256"] = public_tree_sha256(root)
    path = root / seal.RELEASE_RELATIVE_PATH
    path.write_text(
        json.dumps(release, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    claim_authorization(
        seal.AUTHORIZATION_LEDGER_ROOT,
        authorization_id=seal.BUILD_AUTHORIZATION_ID,
        operation="BUILD",
        source_head=release["source_head"],
        payload_manifest_sha256=release["payload_manifest_sha256"],
        release_id=release["release_id"],
    )
    return root


def test_release_manifest_tree_binding_detects_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _source(monkeypatch, tmp_path)
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
        seal.audit_public_master(root, runner=FakeRunner())


def test_public_audit_rejects_source_root_symlink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _source(monkeypatch, tmp_path)
    alias = tmp_path / "source-link"
    alias.symlink_to(root, target_is_directory=True)

    with pytest.raises(
        seal.GoldenMasterSealHostError,
        match="source_root_invalid",
    ):
        seal.audit_public_master(alias, runner=FakeRunner())


def test_public_audit_proves_positive_product_whitelist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report = seal.audit_public_master(
        _source(monkeypatch, tmp_path),
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
    assert report["product_namespace_whitelist_exact"] is True
    assert report["forbidden_instance_inventory_absent"] is True
    assert report["public_external_files_exact"] is True
    assert report["authorization_ledger_classified"] is True
    assert report["build_authorization_proven"] is True
    assert report["disk_capture_ready"] is False


def test_public_audit_rejects_unknown_product_namespace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _source(monkeypatch, tmp_path)
    parent, _, _ = seal.PRODUCT_NAMESPACE_RULES[0]
    (parent / "greenhouse-secret-copy").mkdir()

    with pytest.raises(
        seal.GoldenMasterSealHostError,
        match="product_namespace_not_whitelisted",
    ):
        seal.audit_public_master(root, runner=FakeRunner())


def test_public_audit_rejects_unknown_authorization_residue(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _source(monkeypatch, tmp_path)
    unknown = seal.AUTHORIZATION_LEDGER_ROOT / "unknown.json"
    unknown.write_text("{}\n", encoding="utf-8")
    unknown.chmod(0o600)

    with pytest.raises(
        seal.GoldenMasterSealHostError,
        match="authorization_ledger_unknown_residue",
    ):
        seal.audit_public_master(root, runner=FakeRunner())


def test_public_audit_rejects_external_public_file_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _source(monkeypatch, tmp_path)
    seal.PUBLIC_EXTERNAL_FILES["guard_binary"].write_text(
        "drift\n",
        encoding="utf-8",
    )

    with pytest.raises(
        seal.GoldenMasterSealHostError,
        match="public_external_file_binding_invalid",
    ):
        seal.audit_public_master(root, runner=FakeRunner())


def test_public_audit_rejects_instance_material(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _source(monkeypatch, tmp_path)
    present = tmp_path / "instance-present"
    present.mkdir()
    monkeypatch.setattr(seal, "INSTANCE_PATHS", (str(present),))

    with pytest.raises(
        seal.GoldenMasterSealHostError,
        match="instance_or_activation_path_present",
    ):
        seal.audit_public_master(root, runner=FakeRunner())


def test_public_audit_rejects_image_id_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _source(monkeypatch, tmp_path)
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
