from __future__ import annotations

import importlib.util
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_f4_reboot_successor_postclaim_recovery.py"


def load_tool():
    name = "n3w_t1_f4_reboot_successor_postclaim_recovery"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_package(
    tmp_path: Path,
    tool,
    *,
    source_head: str,
    hashes: dict[str, str] | None = None,
) -> tuple[Path, str, dict[str, dict[str, object]]]:
    root = tmp_path / "package"
    root.mkdir()
    records = []
    bindings = {}
    for index, relative in enumerate(tool.TARGETS):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"{relative}|{index}\n".encode()
        path.write_bytes(payload)
        digest = __import__("hashlib").sha256(payload).hexdigest()
        if hashes is not None and relative in hashes:
            digest = hashes[relative]
        records.append(
            {
                "path": relative,
                "sha256": digest,
                "size": len(payload),
            }
        )
        bindings[relative] = {"sha256": digest, "size": len(payload)}
    manifest = {
        "schema": tool.PACKAGE_SCHEMA,
        "source_head": source_head,
        "files": records,
        "secret_values_included": False,
        "live_runtime_mutation": False,
        "reboot_executed": False,
        "board_access": False,
    }
    manifest_path = root / "reboot-successor-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    manifest_sha = __import__("hashlib").sha256(
        manifest_path.read_bytes()
    ).hexdigest()
    return root, manifest_sha, bindings


def test_repair_delta_accepts_guard_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    root, manifest_sha, target = build_package(
        tmp_path,
        tool,
        source_head="a" * 40,
    )
    old = {
        relative: dict(binding)
        for relative, binding in target.items()
    }
    old[tool.GUARD_RELATIVE]["sha256"] = "0" * 64

    _manifest, observed = tool.repair_delta_contract(
        package_root=root,
        target_source_head="a" * 40,
        target_manifest_sha256=manifest_sha,
        old_bindings=old,
    )

    assert observed == target


def test_repair_delta_rejects_unexpected_authority_change(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    root, manifest_sha, target = build_package(
        tmp_path,
        tool,
        source_head="a" * 40,
    )
    old = {
        relative: dict(binding)
        for relative, binding in target.items()
    }
    old[tool.GUARD_RELATIVE]["sha256"] = "0" * 64
    authority = "tools/n3w_t1_f4_reboot_authority.py"
    old[authority]["sha256"] = "1" * 64

    with pytest.raises(tool.RecoveryError, match="unexpected_repair_delta"):
        tool.repair_delta_contract(
            package_root=root,
            target_source_head="a" * 40,
            target_manifest_sha256=manifest_sha,
            old_bindings=old,
        )


def test_claim_recovery_consumes_fresh_authorization_before_return(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    recovery_path = tmp_path / "recovery.json"
    monkeypatch.setattr(tool, "RECOVERY_CLAIM", recovery_path)
    monkeypatch.setattr(tool, "exclusive", lambda: nullcontext())

    old_bindings = {
        relative: {"sha256": "0" * 64, "size": 1}
        for relative in tool.TARGETS
    }
    target_bindings = {
        relative: {"sha256": "0" * 64, "size": 1}
        for relative in tool.TARGETS
    }
    target_bindings[tool.GUARD_RELATIVE] = {
        "sha256": "1" * 64,
        "size": 2,
    }
    module = SimpleNamespace(
        _runtime_container_snapshot=lambda: {"runtime": "stable"},
        _certificate_identity_snapshot=lambda: {"certificate": "stable"},
    )
    transaction = {
        "certificate_timer_authorization_id":
            "N3W_T1_F4_CERTIFICATE_TIMER_ENABLEMENT_SUCCESSOR_LIVE_20261016_01"
    }
    install_claim = {
        "control_repair_authorization_id":
            "N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01"
    }
    monkeypatch.setattr(
        tool,
        "old_control_applying_contract",
        lambda **_kwargs: (
            module,
            transaction,
            install_claim,
            old_bindings,
        ),
    )
    monkeypatch.setattr(
        tool,
        "repair_delta_contract",
        lambda **_kwargs: ({}, target_bindings),
    )
    monkeypatch.setattr(tool, "boot_id_sha256", lambda: "b" * 64)

    def write_record(path: Path, document: dict[str, object]) -> None:
        path.write_text(json.dumps(document), encoding="utf-8")
        path.chmod(0o600)

    monkeypatch.setattr(tool, "atomic_write_record", write_record)
    monkeypatch.setattr(
        tool,
        "read_record",
        lambda path, _mode: json.loads(path.read_text(encoding="utf-8")),
    )
    monkeypatch.setattr(
        tool,
        "sha256_file",
        lambda path: __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
    )

    result = tool.claim_recovery(
        package_root=tmp_path,
        authorization_id=(
            "N3W_T1_F4_REBOOT_SUCCESSOR_POSTCLAIM_RECOVERY_LIVE_20261016_01"
        ),
        old_source_head="a" * 40,
        old_manifest_sha256="c" * 64,
        old_claim_sha256="d" * 64,
        target_source_head="e" * 40,
        target_manifest_sha256="f" * 64,
        expected_transaction_sha256="1" * 64,
        expected_runtime_snapshot_sha256=tool.canonical_sha(
            {"runtime": "stable"}
        ),
        expected_certificate_snapshot_sha256=tool.canonical_sha(
            {"certificate": "stable"}
        ),
        expected_boot_id_sha256="b" * 64,
    )

    persisted = json.loads(recovery_path.read_text(encoding="utf-8"))
    assert persisted["stage"] == "RECOVERY_CLAIMED"
    assert persisted["recovery_authorization_claimed"] is True
    assert persisted["recovery_authorization_consumed"] is True
    assert persisted["recovery_authorization_replay_allowed"] is False
    assert result["state"] == "RECOVERY_CLAIMED"


def test_recovery_source_never_actuates_reboot() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '("systemctl", "reboot")' not in source
    assert '("systemctl", "poweroff")' not in source
    assert '("shutdown"' not in source
    assert "reboot_authorization_claimed" not in source
