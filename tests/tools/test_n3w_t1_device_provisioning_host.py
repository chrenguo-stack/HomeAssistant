from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_device_provisioning_host.py"


def load_tool():
    name = "n3w_t1_device_provisioning_host"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_command_surface_retains_explicit_start() -> None:
    tool = load_tool()
    source = TOOL.read_text(encoding="utf-8")
    assert 'prog="n3w-t1-provision"' in source
    assert 'subparsers.add_parser("status")' in source
    assert 'subparsers.add_parser("start")' in source
    assert 'subparsers.add_parser("resume-if-needed")' in source
    assert 'subparsers.add_parser("verify")' in source
    assert tool.CONFIRMATION == "START DEVICE PROVISIONING: YES"
    assert "n3w-t1-provision-start" not in source


def test_host_identity_is_stable_and_does_not_expose_raw_machine_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    machine = tmp_path / "machine-id"
    ssh = tmp_path / "ssh_host_ed25519_key.pub"
    machine.write_text("0123456789abcdef0123456789abcdef\n", encoding="utf-8")
    ssh.write_text("ssh-ed25519 AAAATEST host\n", encoding="utf-8")
    monkeypatch.setattr(tool, "MACHINE_ID_PATH", machine)
    monkeypatch.setattr(tool, "SSH_HOST_PUBLIC_KEY", ssh)

    first = tool._host_identity()
    second = tool._host_identity()

    assert first == second
    assert first["status"] == "PASS"
    assert re.fullmatch(r"t1h-[0-9a-f]{24}", first["host_instance_id"])
    assert "0123456789abcdef0123456789abcdef" not in str(first)


def test_resume_path_has_no_start_authority() -> None:
    source = TOOL.read_text(encoding="utf-8")
    reconcile = source.split("def _reconcile(", 1)[1].split("\ndef main(", 1)[0]
    assert "start_device_provisioning" not in reconcile
    assert "RESUME_EXISTING" in reconcile
    assert '"boot_action": "NOOP"' in reconcile
    assert '"boot_action": "VERIFY_ONLY"' in reconcile


def test_release_reader_rejects_image_lock_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    release = tmp_path / "fresh-release.json"
    release.write_text(
        json.dumps(
            {
                "schema": tool.RELEASE_SCHEMA,
                "release_id": "a" * 40,
                "source_head": "a" * 40,
                "instance_material_absent": True,
                "explicit_provisioning_required": True,
                "images": {
                    label: {
                        "image": f"local/{label}:exact",
                        "image_id": "sha256:" + "1" * 64,
                        "platform": "linux/arm64",
                    }
                    for label in ("homeassistant", "manager", "broker")
                },
                "image_lock": {
                    "schema": "gh.n3w-t1-fresh-production-image-lock/1",
                    "source_head": "a" * 40,
                    **{
                        label: {
                            "image": f"local/{label}:exact",
                            "image_id": "sha256:" + (
                                "2" * 64 if label == "manager" else "1" * 64
                            ),
                        }
                        for label in ("homeassistant", "manager", "broker")
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    release.chmod(0o644)
    monkeypatch.setattr(tool.os, "geteuid", lambda: release.stat().st_uid)

    with pytest.raises(
        tool.ProvisionHostError,
        match="fresh_release_image_binding_invalid:manager",
    ):
        tool._read_release(release)
