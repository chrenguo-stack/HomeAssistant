from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_f4_reboot_verify.py"


def load_tool():
    name = "n3w_t1_f4_reboot_verify"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_requires_new_boot_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    claim = {
        "schema": tool.CLAIM_SCHEMA,
        "stage": "REBOOT_PENDING",
        "reboot_authorization_claimed": True,
        "reboot_authorization_consumed": True,
        "reboot_authorization_replay_allowed": False,
        "reboot_acceptance_passed": False,
        "pre_boot_id_sha256": "a" * 64,
        "f4_transaction_sha256": "b" * 64,
        "board_access": False,
    }
    monkeypatch.setattr(tool, "_json", lambda _path, _mode: claim)
    monkeypatch.setattr(tool, "_boot_id_sha256", lambda: "a" * 64)

    with pytest.raises(tool.VerifyError, match="reboot_not_observed"):
        tool.verify()


def test_verify_rejects_changed_f4_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    claim = {
        "schema": tool.CLAIM_SCHEMA,
        "stage": "REBOOT_PENDING",
        "reboot_authorization_claimed": True,
        "reboot_authorization_consumed": True,
        "reboot_authorization_replay_allowed": False,
        "reboot_acceptance_passed": False,
        "pre_boot_id_sha256": "a" * 64,
        "f4_transaction_sha256": "b" * 64,
        "board_access": False,
    }
    monkeypatch.setattr(tool, "_json", lambda _path: claim)
    monkeypatch.setattr(tool, "_boot_id_sha256", lambda: "c" * 64)
    monkeypatch.setattr(tool, "_sha256", lambda _path: "d" * 64)

    with pytest.raises(
        tool.VerifyError,
        match="f4_transaction_changed_across_reboot",
    ):
        tool.verify()


def test_verifier_is_read_only_for_reboot_control() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '("systemctl", "reboot")' not in source
    assert '("systemctl", "poweroff")' not in source
    assert '("shutdown"' not in source
    assert "write_text(" not in source
    assert "os.replace(" not in source



def test_inactive_certificate_oneshot_must_have_success_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    monkeypatch.setattr(
        tool,
        "_run",
        lambda *_args, **_kwargs: (
            "ActiveState=inactive\n"
            "Result=exit-code\n"
            "ExecMainStatus=2\n"
        ),
    )
    with pytest.raises(tool.VerifyError, match="oneshot_not_successful"):
        tool._inactive_oneshot_success("certificate.service")


def test_inactive_certificate_oneshot_success_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    monkeypatch.setattr(
        tool,
        "_run",
        lambda *_args, **_kwargs: (
            "ActiveState=inactive\n"
            "Result=success\n"
            "ExecMainStatus=0\n"
        ),
    )
    tool._inactive_oneshot_success("certificate.service")



def test_control_binding_rejects_tampered_installed_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    manifest = tmp_path / "manifest.json"
    target = tmp_path / "guard.py"
    target.write_text("exact", encoding="utf-8")
    target.chmod(0o755)

    monkeypatch.setattr(tool, "CONTROL_MANIFEST", manifest)
    monkeypatch.setattr(
        tool,
        "CONTROL_TARGETS",
        {"guard.py": (target, 0o755)},
    )

    document = {
        "schema": tool.PACKAGE_SCHEMA,
        "source_head": "a" * 40,
        "files": [
            {
                "path": "guard.py",
                "sha256": "0" * 64,
                "size": target.stat().st_size,
            }
        ],
    }
    manifest.write_text(
        __import__("json").dumps(document) + "\n",
        encoding="utf-8",
    )
    manifest.chmod(0o644)

    monkeypatch.setattr(
        tool,
        "_json",
        lambda path, _mode: __import__("json").loads(
            path.read_text(encoding="utf-8")
        ),
    )

    claim = {
        "source_head": "a" * 40,
        "control_manifest_sha256": tool._sha256(manifest),
    }
    with pytest.raises(tool.VerifyError, match="control_target_binding_invalid"):
        tool._installed_control_binding(claim)
