from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

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


@pytest.fixture
def provisioning_host(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    tool = load_tool()
    firstboot = tool._load_module(
        ROOT / "host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_firstboot.py",
        "n3w_test_device_firstboot",
    )
    release = {
        "source_head": "a" * 40,
        "release_id": "a" * 40,
        "images": {
            name: {"image": f"local/{name}:factory"}
            for name in ("homeassistant", "manager", "broker")
        },
        "image_lock": {},
    }
    inspected = []

    def verify_runtime_image(_runner, component, record):
        inspected.append(component)
        if component == "manager":
            raise RuntimeError(f"command_failed:docker:1:No such image: {record['image']}")
        return {"runtime_id": "fixture"}

    fresh = SimpleNamespace(
        LiveFreshInstallerAdapters=lambda _root, _manifest, runner: SimpleNamespace(
            runner=runner,
            loaded_image_bindings={},
        ),
        Runner=object,
        _verify_runtime_image=verify_runtime_image,
    )
    monkeypatch.setattr(
        tool,
        "_load_module",
        lambda path, _name: fresh if path == tool.FRESH_TOOL_PATH else firstboot,
    )
    monkeypatch.setattr(tool, "_read_release", lambda: release)
    monkeypatch.setattr(tool, "os", SimpleNamespace(geteuid=lambda: 0))
    monkeypatch.setattr(tool, "TRANSACTION_ROOT", tmp_path / "firstboot")
    monkeypatch.setattr(tool, "CANDIDATE_ROOT", tmp_path / "candidate")
    monkeypatch.setattr(
        tool,
        "_host_identity",
        lambda: {
            "status": "PASS",
            "host_instance_id": "fixture-host",
            "machine_id_ready": True,
            "ssh_host_identity_ready": True,
            "production_service_start": False,
            "network_operation": False,
        },
    )
    return tool, firstboot, release["release_id"], inspected


@pytest.mark.parametrize(
    ("command", "state", "boot_action"),
    [
        ("status", "DEVICE_READY", None),
        ("verify", "DEVICE_READY", None),
        ("resume-if-needed", "DEVICE_READY", "VERIFY_ONLY"),
        ("resume-if-needed", "UNPROVISIONED", "NOOP"),
    ],
)
def test_observation_does_not_require_factory_images(
    monkeypatch, capsys, provisioning_host, command, state, boot_action
) -> None:
    tool, firstboot, release_id, inspected = provisioning_host
    root = tool.TRANSACTION_ROOT
    if state == "DEVICE_READY":
        root.mkdir(mode=0o700)
        transaction = firstboot._create_transaction_once(root, release_id, tool.CANDIDATE_ROOT)
        identity = {
            "host_instance_id": "fixture-host",
            "system_id": "fixture-system",
            "system_id_sha256": hashlib.sha256(b"fixture-system").hexdigest(),
        }
        firstboot._write_atomic(
            root / firstboot.TRANSACTION_NAME, {**transaction, **identity, "stage": "VERIFY"}
        )
        firstboot._write_atomic(
            root / firstboot.COMPLETE_NAME,
            {
                "schema": firstboot.COMPLETE_SCHEMA,
                "release_id": release_id,
                "status": "PASS",
                **identity,
            },
        )
    monkeypatch.setattr(sys, "argv", [str(TOOL), command])

    assert tool.main() == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["state"] == state
    assert report.get("boot_action") == boot_action
    assert report["production_service_start"] is False
    assert captured.err == ""
    assert inspected == []


@pytest.mark.parametrize("command", ["start", "resume-if-needed"])
def test_provisioning_actions_reject_missing_factory_image(
    monkeypatch, capsys, provisioning_host, command
) -> None:
    tool, firstboot, release_id, inspected = provisioning_host
    root = tool.TRANSACTION_ROOT
    transaction_path = root / firstboot.TRANSACTION_NAME
    arguments = [str(TOOL), command]
    if command == "start":
        arguments.extend(["--confirm", tool.CONFIRMATION])
        previous = None
    else:
        root.mkdir(mode=0o700)
        firstboot._create_transaction_once(root, release_id, tool.CANDIDATE_ROOT)
        previous = transaction_path.read_bytes()
    monkeypatch.setattr(sys, "argv", arguments)

    assert tool.main() == 2
    captured = capsys.readouterr()
    assert json.loads(captured.err)["error_code"] == (
        "command_failed:docker:1:No such image: local/manager:factory"
    )
    assert captured.out == ""
    assert inspected == ["homeassistant", "manager"]
    assert (transaction_path.read_bytes() if transaction_path.exists() else None) == previous
    assert not tool.CANDIDATE_ROOT.exists()
