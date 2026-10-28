from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = ROOT / "tools/recovery/n3w_r10_r2_failed_residue_reconcile.py"


def load():
    spec = importlib.util.spec_from_file_location("r10_residue_reconcile", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load()


def failed_transaction(workspace_path: Path) -> dict:
    return {
        "schema": "gh.n3w.r10-t1-candidate-upgrade-transaction/1",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "authorization_id": tool.FAILED_AUTH,
        "board_access": False,
        "committed": False,
        "current_registration_count": 1,
        "package_head": tool.FAILED_HEAD,
        "package_manifest_sha256": tool.FAILED_MANIFEST_SHA256,
        "predecessor_source": "03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6",
        "target_source": "e299c937a7b89bb8a7b9a7432186ba46a416cd44",
        "predecessor_f4_transaction_sha256": tool.EXPECTED_F4_SHA256,
        "predecessor_f4_installed_files_sha256": (
            "66f8c89a10363fbf12cbd711f26257dd7cfacdfc178e7f0b4de229ba573f21a5"
        ),
        "current_registration_count": 1,
        "static_backup_complete": True,
        "phase": "ROLLBACK_FAILED",
        "predecessor_manager_image": tool.PREDECESSOR_MANAGER_IMAGE,
        "replay_allowed": False,
        "rollback_completed": False,
        "rollback_error_classes": ["firewall:UpgradeError"],
        "rollback_error_count": 1,
        "status": "FAIL",
        "target_manager_image": tool.TARGET_MANAGER_IMAGE,
        "workspace_sha256": tool.sha256_bytes(
            str(workspace_path).encode("utf-8")
        ),
    }


def test_failed_transaction_contract_is_exact(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / tool.FAILED_WORKSPACE_SUFFIX
    monkeypatch.setattr(tool, "FAILED_WORKSPACE_PATH", workspace)
    tool.validate_failed_transaction(failed_transaction(workspace))

    invalid = failed_transaction(workspace)
    invalid["phase"] = "ROLLED_BACK"
    with pytest.raises(
        tool.ReconcileError,
        match="failed_transaction_binding_invalid:phase",
    ):
        tool.validate_failed_transaction(invalid)


def test_reconcile_authorization_is_separate_and_one_shot() -> None:
    assert tool.valid_reconcile_authorization(
        "N3W_R10_FAILED_RESIDUE_RECONCILE_R2_20261028_01"
    )
    assert not tool.valid_reconcile_authorization(tool.FAILED_AUTH)


def test_execute_reconcile_archives_without_deleting_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    provision = tmp_path / "provision"
    provision.mkdir(mode=0o700)
    transaction = provision / "R10_CANDIDATE_UPGRADE_TRANSACTION.json"

    work_root = tmp_path / "work"
    failed_workspace = work_root / tool.FAILED_WORKSPACE_SUFFIX
    failed_workspace.mkdir(parents=True, mode=0o700)
    evidence = failed_workspace / "evidence.bin"
    evidence.write_bytes(b"historical-evidence\n")

    history = tmp_path / "history"
    claims = history / "claims"

    monkeypatch.setattr(tool, "PROVISION_ROOT", provision)
    monkeypatch.setattr(tool, "TRANSACTION", transaction)
    monkeypatch.setattr(tool, "WORK_ROOT", work_root)
    monkeypatch.setattr(tool, "FAILED_WORKSPACE_PATH", failed_workspace)
    monkeypatch.setattr(tool, "HISTORY_ROOT", history)
    monkeypatch.setattr(tool, "CLAIMS_ROOT", claims)
    monkeypatch.setattr(tool, "require_root", lambda: None)
    monkeypatch.setattr(
        tool,
        "validate_workspace",
        lambda: {
            "workspace_file_count": 1,
            "workspace_inventory_sha256": "w" * 64,
            "workspace_files": [],
            "index_sha256": "i" * 64,
            "firewall_prestate_sha256": "f" * 64,
        },
    )
    monkeypatch.setattr(
        tool,
        "validate_live_predecessor",
        lambda: {
            "predecessor_runtime_proven": True,
        },
    )

    def fake_claim(
        authorization_id: str,
        *,
        transaction_sha256: str,
        workspace_inventory_sha256: str,
    ) -> None:
        history.mkdir(mode=0o700, exist_ok=True)
        claims.mkdir(mode=0o700, exist_ok=True)
        tool.write_json_exclusive(
            tool.claim_path(authorization_id),
            {
                "schema": tool.SCHEMA,
                "authorization_id": authorization_id,
                "authorization_consumed": True,
                "replay_allowed": False,
                "transaction_sha256": transaction_sha256,
                "workspace_inventory_sha256": workspace_inventory_sha256,
            },
        )

    monkeypatch.setattr(tool, "claim_authorization", fake_claim)

    document = failed_transaction(failed_workspace)
    original = (json.dumps(document, sort_keys=True) + "\n").encode()
    transaction.write_bytes(original)

    authorization = (
        "N3W_R10_FAILED_RESIDUE_RECONCILE_R2_20261028_01"
    )
    result = tool.execute_reconcile(
        authorization_id=authorization,
        confirmation=tool.CONFIRMATION,
    )

    assert result["status"] == "PASS"
    assert result["authorization_consumed"] is True
    assert not transaction.exists()
    assert not work_root.exists()

    final = history / f"r2-{tool.FAILED_WORKSPACE_SUFFIX}"
    assert (final / "transaction.json").read_bytes() == original
    assert (
        final
        / "workspace-root"
        / tool.FAILED_WORKSPACE_SUFFIX
        / "evidence.bin"
    ).read_bytes() == b"historical-evidence\n"
    reconciliation = json.loads(
        (final / "reconciliation.json").read_text(encoding="utf-8")
    )
    assert reconciliation["active_transaction_absent"] is True
    assert reconciliation["active_workspace_absent"] is True

    claim_files = list(claims.glob("*.json"))
    assert len(claim_files) == 1
    claim = json.loads(claim_files[0].read_text(encoding="utf-8"))
    assert claim["authorization_consumed"] is True
    assert claim["replay_allowed"] is False

    with pytest.raises(
        tool.ReconcileError,
        match="authorization_replay_forbidden",
    ):
        tool.execute_reconcile(
            authorization_id=authorization,
            confirmation=tool.CONFIRMATION,
        )


def test_confirmation_fails_before_any_claim(
    tmp_path: Path,
    monkeypatch,
) -> None:
    history = tmp_path / "history"
    claims = history / "claims"
    monkeypatch.setattr(tool, "HISTORY_ROOT", history)
    monkeypatch.setattr(tool, "CLAIMS_ROOT", claims)
    monkeypatch.setattr(tool, "require_root", lambda: None)

    with pytest.raises(tool.ReconcileError, match="confirmation_invalid"):
        tool.execute_reconcile(
            authorization_id=(
                "N3W_R10_FAILED_RESIDUE_RECONCILE_R2_20261028_01"
            ),
            confirmation="NO",
        )
    assert not history.exists()


def test_archived_backup_mode_is_0600_while_live_mode_remains_original(
    tmp_path: Path,
    monkeypatch,
) -> None:
    payload = b"services:\n  manager: {}\n"
    backup = tmp_path / "backup.bin"
    live = tmp_path / "docker-compose.yml"
    backup.write_bytes(payload)
    live.write_bytes(payload)
    backup.chmod(0o600)
    live.chmod(0o644)

    real_binding = tool._binding

    def normalized_binding(path: Path) -> dict:
        value = real_binding(path)
        value["uid"] = 0
        value["gid"] = 0
        return value

    monkeypatch.setattr(tool, "_binding", normalized_binding)
    binding = normalized_binding(live)

    tool.validate_archived_backup_copy(backup, live, binding)


def test_archived_backup_content_mismatch_is_rejected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backup = tmp_path / "backup.bin"
    live = tmp_path / "docker-compose.yml"
    backup.write_bytes(b"old\n")
    live.write_bytes(b"new\n")
    backup.chmod(0o600)
    live.chmod(0o644)

    real_binding = tool._binding

    def normalized_binding(path: Path) -> dict:
        value = real_binding(path)
        value["uid"] = 0
        value["gid"] = 0
        return value

    monkeypatch.setattr(tool, "_binding", normalized_binding)
    binding = normalized_binding(live)

    with pytest.raises(
        tool.ReconcileError,
        match="workspace_backup_copy_invalid",
    ):
        tool.validate_archived_backup_copy(backup, live, binding)


def test_source_has_no_destructive_delete_path() -> None:
    source = TOOL_PATH.read_text(encoding="utf-8")
    assert "meta.st_uid != 0" in source
    assert "meta.st_gid != 0" in source
    assert "shutil.rmtree" not in source
    assert ".unlink(" not in source
    assert 'run(("rm"' not in source
    assert "os.replace(WORK_ROOT" in source
    assert "os.replace(TRANSACTION" in source
