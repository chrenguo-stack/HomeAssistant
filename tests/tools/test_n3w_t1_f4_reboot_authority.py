from __future__ import annotations

import hashlib
import importlib.util
import json
from contextlib import nullcontext
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


def test_claim_install_persists_consumed_authority_before_return(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    claim_path = tmp_path / "install-claim.json"
    payload = {
        "schema": tool.SCHEMA_INSTALL,
        "stage": "INSTALL_CLAIMED",
        "control_repair_authorization_claimed": True,
        "control_repair_authorization_consumed": True,
        "control_repair_authorization_replay_allowed": False,
        "live_runtime_mutation": False,
        "reboot_executed": False,
        "board_access": False,
    }

    monkeypatch.setattr(tool, "INSTALL_CLAIM_PATH", claim_path)
    monkeypatch.setattr(tool, "_exclusive", lambda: nullcontext())
    monkeypatch.setattr(tool, "install_claim_payload", lambda **_kwargs: payload)

    def write_record(path: Path, document: dict[str, object]) -> None:
        path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        path.chmod(0o600)

    monkeypatch.setattr(tool, "_atomic_write_record", write_record)
    monkeypatch.setattr(
        tool,
        "_record",
        lambda path, _mode: json.loads(path.read_text(encoding="utf-8")),
    )

    result = tool.claim_install(
        package_root=tmp_path,
        source_head="a" * 40,
        manifest_sha256="b" * 64,
        authorization_id="N3W_T1_F4_REBOOT_CONTROL_REPAIR_20261016_01",
        expected_transaction_sha256="c" * 64,
    )

    assert claim_path.is_file()
    assert json.loads(claim_path.read_text()) == payload
    assert result["state"] == "INSTALL_CLAIMED"
    assert result["control_repair_authorization_consumed"] is True
    assert result["claim_sha256"] == hashlib.sha256(
        claim_path.read_bytes()
    ).hexdigest()


def test_install_control_marks_applying_before_any_control_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    claim_path = tmp_path / "install-claim.json"
    manifest_target = tmp_path / "installed-manifest.json"
    package_root = tmp_path / "package"
    package_root.mkdir()

    fake_targets = {
        "guard.py": (tmp_path / "guard-target.py", 0o755),
        "authority.py": (tmp_path / "authority-target.py", 0o755),
        "verify.py": (tmp_path / "verify-target.py", 0o755),
        "dropin.conf": (tmp_path / "dropin-target.conf", 0o644),
    }
    for relative in fake_targets:
        (package_root / relative).write_text(relative, encoding="utf-8")
    (package_root / tool.MANIFEST_NAME).write_text("{}", encoding="utf-8")

    fake_module = SimpleNamespace(
        _runtime_container_snapshot=lambda: {"broker": {"id": "b"}},
        _certificate_identity_snapshot=lambda: {"server": "s"},
    )
    runtime_sha = tool._canonical_sha(fake_module._runtime_container_snapshot())
    cert_sha = tool._canonical_sha(fake_module._certificate_identity_snapshot())
    claim = {
        "schema": tool.SCHEMA_INSTALL,
        "stage": "INSTALL_CLAIMED",
        "source_head": "a" * 40,
        "control_manifest_sha256": "b" * 64,
        "f4_transaction_sha256": "c" * 64,
        "pre_runtime_snapshot_sha256": runtime_sha,
        "pre_certificate_snapshot_sha256": cert_sha,
        "control_repair_authorization_claimed": True,
        "control_repair_authorization_consumed": True,
        "control_repair_authorization_replay_allowed": False,
        "board_access": False,
    }
    claim_path.write_text(json.dumps(claim), encoding="utf-8")
    claim_path.chmod(0o600)

    events: list[str] = []
    monkeypatch.setattr(tool, "INSTALL_CLAIM_PATH", claim_path)
    monkeypatch.setattr(tool, "CONTROL_MANIFEST", manifest_target)
    monkeypatch.setattr(tool, "CONTROL_TARGETS", fake_targets)
    monkeypatch.setattr(tool, "_exclusive", lambda: nullcontext())
    monkeypatch.setattr(
        tool,
        "_record",
        lambda path, _mode: json.loads(path.read_text(encoding="utf-8")),
    )

    def write_record(path: Path, document: dict[str, object]) -> None:
        events.append(f"state:{document['stage']}")
        path.write_text(json.dumps(document), encoding="utf-8")
        path.chmod(0o600)

    monkeypatch.setattr(tool, "_atomic_write_record", write_record)
    monkeypatch.setattr(
        tool,
        "_package",
        lambda *_args, **_kwargs: {
            "root": package_root,
            "source_head": "a" * 40,
            "manifest_sha256": "b" * 64,
            "files": {
                relative: {
                    "sha256": "d" * 64,
                    "size": (package_root / relative).stat().st_size,
                }
                for relative in fake_targets
            },
        },
    )
    monkeypatch.setattr(
        tool,
        "_base_pre_reboot",
        lambda _sha: (fake_module, {}),
    )

    def install_file(_source: Path, target: Path, _mode: int) -> None:
        current = json.loads(claim_path.read_text(encoding="utf-8"))
        assert current["stage"] == "CONTROL_APPLYING"
        events.append(f"install:{target.name}")

    monkeypatch.setattr(tool, "_install_exact_file", install_file)
    monkeypatch.setattr(tool, "_run", lambda *_args, **_kwargs: "")

    def verify_control(**_kwargs):
        current = json.loads(claim_path.read_text(encoding="utf-8"))
        assert current["stage"] == "CONTROL_APPLYING"
        events.append("verify")
        return fake_module, {}, current

    monkeypatch.setattr(tool, "_verify_installed_control", verify_control)

    result = tool.install_control(
        package_root=package_root,
        source_head="a" * 40,
        manifest_sha256="b" * 64,
        expected_transaction_sha256="c" * 64,
    )

    assert events[0] == "state:CONTROL_APPLYING"
    assert events[-2] == "verify"
    assert events[-1] == "state:CONTROL_READY"
    assert result["state"] == "CONTROL_READY"


def test_claim_reboot_persists_consumed_authority_before_actuation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    claim_path = tmp_path / "reboot-claim.json"
    payload = {
        "schema": tool.SCHEMA_REBOOT,
        "stage": "REBOOT_PENDING",
        "reboot_authorization_claimed": True,
        "reboot_authorization_consumed": True,
        "reboot_authorization_replay_allowed": False,
        "reboot_acceptance_passed": False,
        "pre_boot_id_sha256": "a" * 64,
        "board_access": False,
    }

    monkeypatch.setattr(tool, "REBOOT_CLAIM_PATH", claim_path)
    monkeypatch.setattr(tool, "_exclusive", lambda: nullcontext())
    monkeypatch.setattr(tool, "reboot_claim_payload", lambda **_kwargs: payload)

    def write_record(path: Path, document: dict[str, object]) -> None:
        path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        path.chmod(0o600)

    monkeypatch.setattr(tool, "_atomic_write_record", write_record)
    monkeypatch.setattr(
        tool,
        "_record",
        lambda path, _mode: json.loads(path.read_text(encoding="utf-8")),
    )

    result = tool.claim_reboot(
        source_head="a" * 40,
        manifest_sha256="b" * 64,
        authorization_id="N3W_T1_F4_REBOOT_SUCCESSOR_LIVE_20261016_01",
        expected_transaction_sha256="c" * 64,
    )

    assert claim_path.is_file()
    assert json.loads(claim_path.read_text()) == payload
    assert result["state"] == "REBOOT_PENDING"
    assert result["reboot_authorization_consumed"] is True
    assert result["host_reboot_actuation_required"] is True
