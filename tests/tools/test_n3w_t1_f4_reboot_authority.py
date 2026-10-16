from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_f4_reboot_authority.py"


def load_tool():
    name = "n3w_t1_f4_reboot_authority"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_install_claim_payload_is_consumed_before_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    monkeypatch.setattr(tool, "INSTALL_CLAIM_PATH", tmp_path / "install.json")

    fake_module = SimpleNamespace(
        _runtime_container_snapshot=lambda: {"broker": {"id": "b"}},
        _certificate_identity_snapshot=lambda: {"server": "s"},
    )
    transaction = {
        "runtime_acceptance_authorization_id": "N3W_T1_F4_OLD_RUNTIME_ACCEPTANCE_01"
    }
    monkeypatch.setattr(
        tool,
        "_base_pre_reboot",
        lambda _sha: (fake_module, transaction),
    )
    monkeypatch.setattr(
        tool,
        "_package",
        lambda *_args, **_kwargs: {
            "root": tmp_path,
            "manifest_sha256": "b" * 64,
            "source_head": "a" * 40,
            "files": {
                relative: {"sha256": "c" * 64, "size": 10}
                for relative in tool.CONTROL_TARGETS
            },
        },
    )

    result = tool.install_claim_payload(
        package_root=tmp_path,
        source_head="a" * 40,
        manifest_sha256="b" * 64,
        authorization_id="N3W_T1_F4_REBOOT_CONTROL_REPAIR_20261016_01",
        expected_transaction_sha256="d" * 64,
    )

    assert result["stage"] == "INSTALL_CLAIMED"
    assert result["control_repair_authorization_claimed"] is True
    assert result["control_repair_authorization_consumed"] is True
    assert result["control_repair_authorization_replay_allowed"] is False
    assert result["live_runtime_mutation"] is False
    assert result["reboot_executed"] is False
    assert result["board_access"] is False


def test_reboot_claim_payload_is_one_shot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    monkeypatch.setattr(tool, "REBOOT_CLAIM_PATH", tmp_path / "reboot.json")
    transaction = {
        "certificate_timer_authorization_id": (
            "N3W_T1_F4_CERTIFICATE_TIMER_ENABLEMENT_SUCCESSOR_LIVE_20261016_01"
        )
    }
    install_claim = {
        "control_repair_authorization_id": (
            "N3W_T1_F4_REBOOT_CONTROL_REPAIR_20261016_01"
        )
    }
    monkeypatch.setattr(
        tool,
        "_verify_installed_control",
        lambda **_kwargs: (SimpleNamespace(), transaction, install_claim),
    )
    monkeypatch.setattr(tool, "_boot_id_sha256", lambda: "e" * 64)

    result = tool.reboot_claim_payload(
        source_head="a" * 40,
        manifest_sha256="b" * 64,
        authorization_id="N3W_T1_F4_REBOOT_SUCCESSOR_LIVE_20261016_01",
        expected_transaction_sha256="d" * 64,
    )

    assert result["stage"] == "REBOOT_PENDING"
    assert result["reboot_authorization_claimed"] is True
    assert result["reboot_authorization_consumed"] is True
    assert result["reboot_authorization_replay_allowed"] is False
    assert result["reboot_acceptance_passed"] is False
    assert result["pre_boot_id_sha256"] == "e" * 64
    assert result["board_access"] is False


def test_fresh_authorization_rejects_prior_f4_id() -> None:
    tool = load_tool()
    transaction = {
        "runtime_acceptance_authorization_id": (
            "N3W_T1_F4_RUNTIME_ACCEPTANCE_SUCCESSOR_LIVE_20261016_01"
        )
    }
    with pytest.raises(tool.AuthorityError, match="authorization_replay_forbidden"):
        tool._fresh_authorization(
            "N3W_T1_F4_RUNTIME_ACCEPTANCE_SUCCESSOR_LIVE_20261016_01",
            f4_transaction=transaction,
        )


def test_authority_never_actuates_reboot() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '("systemctl", "reboot")' not in source
    assert '("systemctl", "poweroff")' not in source
    assert '("shutdown"' not in source
