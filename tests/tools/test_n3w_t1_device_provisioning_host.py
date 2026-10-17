from __future__ import annotations

import importlib.util
import json
import re
import sys
import types
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
    assert '"--production-phase-context"' in source
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



def _production_context(tool):
    binding = {
        "source_head": "a" * 40,
        "release_id": "b" * 64,
        "artifact_sha256": "c" * 64,
        "predecessor_sha256": "d" * 64,
        "target_binding_sha256": "e" * 64,
    }
    return {
        "schema": "gh.n3w-t1-production-phase-context/1",
        "run_id": "f" * 64,
        "phase": tool.PRODUCTION_PHASE,
        "claim_sha256": "1" * 64,
        "plan_sha256": "2" * 64,
        "binding": binding,
        "binding_sha256": "3" * 64,
        "authorization_consumed": True,
        "replay_allowed": False,
        "board_access": False,
    }


def _install_fake_production_authority(monkeypatch, context):
    authority = types.ModuleType("n3w_t1_production_authority")

    def validate_phase_context(document, *, required_phase):
        assert document == context
        assert required_phase == "PROVISION"
        return {
            "status": "PASS",
            "run_id": context["run_id"],
            "phase": context["phase"],
            "claim_sha256": context["claim_sha256"],
            "authorization_consumed": True,
            "replay_allowed": False,
            "board_access": False,
        }

    authority.validate_phase_context = validate_phase_context
    monkeypatch.setitem(
        sys.modules,
        "n3w_t1_production_authority",
        authority,
    )


def _production_release():
    return {
        "release_id": "a" * 40,
        "source_head": "a" * 40,
    }


class FakeFirstboot:
    TRANSACTION_NAME = "transaction.json"
    COMPLETE_NAME = "FIRSTBOOT_COMPLETE.json"

    def __init__(self, transaction_root, *, fail=False):
        self.transaction_root = transaction_root
        self.fail = fail
        self.starts = 0

    def start_device_provisioning(
        self,
        _adapters,
        transaction_root,
        _candidate_root,
        *,
        release_id,
        confirmation,
    ):
        self.starts += 1
        assert transaction_root == self.transaction_root
        assert release_id == "a" * 40
        assert confirmation == "START DEVICE PROVISIONING: YES"
        if self.fail:
            raise RuntimeError("injected_provision_failure")
        transaction_root.mkdir(mode=0o700, exist_ok=True)
        (transaction_root / self.TRANSACTION_NAME).write_text(
            '{"state":"DEVICE_READY"}\n',
            encoding="utf-8",
        )
        (transaction_root / self.COMPLETE_NAME).write_text(
            '{"state":"DEVICE_READY"}\n',
            encoding="utf-8",
        )
        return {
            "status": "PASS",
            "state": "DEVICE_READY",
            "production_service_start": False,
        }


def test_production_start_uses_phase_context_once_without_second_confirmation(
    monkeypatch,
    tmp_path,
):
    tool = load_tool()
    context = _production_context(tool)
    context_path = tmp_path / "phase-context.json"
    context_path.write_text(json.dumps(context), encoding="utf-8")
    _install_fake_production_authority(monkeypatch, context)
    ledger = tmp_path / "ledger"
    transaction = tmp_path / "transaction"
    monkeypatch.setattr(tool, "PRODUCTION_EXECUTION_LEDGER_ROOT", ledger)
    monkeypatch.setattr(tool, "TRANSACTION_ROOT", transaction)
    firstboot = FakeFirstboot(transaction)

    report = tool._start_device_provisioning(
        firstboot,
        object(),
        _production_release(),
        confirmation=None,
        production_phase_context=context_path,
    )

    assert report["status"] == "PASS"
    assert report["state"] == "DEVICE_READY"
    assert report["production_run_id"] == context["run_id"]
    assert report["production_phase"] == "PROVISION"
    assert report["authorization_consumed"] is True
    assert report["replay_allowed"] is False
    claim_path, complete_path = tool._production_execution_paths(context)
    assert claim_path.is_file()
    assert complete_path.is_file()
    completion = json.loads(complete_path.read_text(encoding="utf-8"))
    assert completion["transaction_sha256"] == tool._sha256_file(
        transaction / firstboot.TRANSACTION_NAME
    )
    assert completion["firstboot_complete_sha256"] == tool._sha256_file(
        transaction / firstboot.COMPLETE_NAME
    )

    with pytest.raises(
        tool.ProvisionHostError,
        match="production_execution_already_consumed",
    ):
        tool._start_device_provisioning(
            firstboot,
            object(),
            _production_release(),
            confirmation=None,
            production_phase_context=context_path,
        )
    assert firstboot.starts == 1


def test_production_start_failure_after_claim_is_not_replayable(
    monkeypatch,
    tmp_path,
):
    tool = load_tool()
    context = _production_context(tool)
    context_path = tmp_path / "phase-context.json"
    context_path.write_text(json.dumps(context), encoding="utf-8")
    _install_fake_production_authority(monkeypatch, context)
    ledger = tmp_path / "ledger"
    transaction = tmp_path / "transaction"
    monkeypatch.setattr(tool, "PRODUCTION_EXECUTION_LEDGER_ROOT", ledger)
    monkeypatch.setattr(tool, "TRANSACTION_ROOT", transaction)
    firstboot = FakeFirstboot(transaction, fail=True)

    with pytest.raises(
        RuntimeError,
        match="injected_provision_failure",
    ) as captured:
        tool._start_device_provisioning(
            firstboot,
            object(),
            _production_release(),
            confirmation=None,
            production_phase_context=context_path,
        )
    assert getattr(captured.value, "production_claimed", False) is True
    claim_path, complete_path = tool._production_execution_paths(context)
    assert claim_path.is_file()
    assert not complete_path.exists()

    with pytest.raises(
        tool.ProvisionHostError,
        match="production_execution_already_consumed",
    ):
        tool._start_device_provisioning(
            firstboot,
            object(),
            _production_release(),
            confirmation=None,
            production_phase_context=context_path,
        )
    assert firstboot.starts == 1


def test_production_start_rejects_source_mismatch_before_local_claim(
    monkeypatch,
    tmp_path,
):
    tool = load_tool()
    context = _production_context(tool)
    context["binding"]["source_head"] = "9" * 40
    context_path = tmp_path / "phase-context.json"
    context_path.write_text(json.dumps(context), encoding="utf-8")
    _install_fake_production_authority(monkeypatch, context)
    ledger = tmp_path / "ledger"
    monkeypatch.setattr(tool, "PRODUCTION_EXECUTION_LEDGER_ROOT", ledger)

    with pytest.raises(
        tool.ProvisionHostError,
        match="production_context_source_head_mismatch",
    ):
        tool._start_device_provisioning(
            FakeFirstboot(tmp_path / "transaction"),
            object(),
            _production_release(),
            confirmation=None,
            production_phase_context=context_path,
        )
    assert not ledger.exists()


def test_production_start_rejects_legacy_confirmation_mixed_with_context(
    monkeypatch,
    tmp_path,
):
    tool = load_tool()
    context = _production_context(tool)
    context_path = tmp_path / "phase-context.json"
    context_path.write_text(json.dumps(context), encoding="utf-8")
    _install_fake_production_authority(monkeypatch, context)

    with pytest.raises(
        tool.ProvisionHostError,
        match="provisioning_authority_mode_conflict",
    ):
        tool._start_device_provisioning(
            FakeFirstboot(tmp_path / "transaction"),
            object(),
            _production_release(),
            confirmation=tool.CONFIRMATION,
            production_phase_context=context_path,
        )
