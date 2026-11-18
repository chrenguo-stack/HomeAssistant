from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u13b_p3_u1_u4_recovery"
    / "u10_preflight.py"
)
U9_SHA = "2b3812af093c1f73a95744413e238f1ca3763407241f889c0646b9495e35a84b"
RECOVERY_MANIFEST_SHA = "d534be84e38817b10eab8a2f8a47c6dae3fd0946da9eba1e1d7f12090e23e9d3"


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_source_compiles_and_binds_exact_live_u9() -> None:
    text = source()
    compile(text, str(SCRIPT), "exec")
    assert f'U9_SHA = "{U9_SHA}"' in text
    assert f'RECOVERY_MANIFEST_SHA = "{RECOVERY_MANIFEST_SHA}"' in text
    assert 'u9.inspect(plan, u9_result)' in text
    assert 'u9_result.get("status") == u9.STATUS_PASS' in text


def test_gate_has_no_execute_mode_or_grant_path() -> None:
    text = source()
    assert 'choices=("source-check", "preflight")' in text
    assert "--execute" not in text
    assert "GRANT_FILE" not in text
    assert "attach_grant" not in text


def test_preflight_cannot_mutate_transaction_usb_or_services() -> None:
    text = source()
    assert "store.write(" not in text
    assert "sync_transaction_metadata(" not in text
    assert '["docker", "rm"' not in text
    assert '"docker", "image", "rm"' not in text
    assert '["systemctl", "start"' not in text
    assert '["systemctl", "stop"' not in text
    assert "u10_transition=False" in text
    assert "predecessor_runtime_delete=False" in text
    assert "predecessor_image_delete=False" in text
    assert "target_image_load=False" in text
    assert "service_mutation=False" in text


def test_u10_projection_is_in_memory_only() -> None:
    text = source()
    start = text.index("def project_u10(")
    end = text.index("def inspect(", start)
    block = text[start:end]
    assert "destructive_cutover_allowed(tx) is True" in block
    assert "record_predecessor_capacity_released(" in block
    assert 'projected["phase"] == U10' in block
    assert "store.write(" not in block
    assert "sync_transaction_metadata(" not in block


def test_recovery_assets_are_rehashed_and_backup_reverified() -> None:
    text = source()
    start = text.index("def verify_recovery_assets(")
    end = text.index("def project_u10(", start)
    block = text[start:end]
    assert "preflight.read_private(" in block
    assert "target.archive_sha256" in block
    assert "predecessor.archive_sha256" in block
    assert "ProtectedHaDataBackupProvider().verify_backup(" in block
    assert "compute_recovery_admission_capacity(" in block
    assert "capacity.capacity_pass is True" in block


def test_release_candidate_is_exact_ha_container_only() -> None:
    text = source()
    start = text.index("def verify_release_candidate(")
    end = text.index("def verify_recovery_assets(", start)
    block = text[start:end]
    assert 'original["peers"]["homeassistant"]["container_id"]' in block
    assert "users == [expected_ha]" in block
    assert 'get("Status") == "exited"' in block
    assert 'get("RestartCount") == 0' in block
    assert "u6_preflight.image_binding(tx)" in block


def test_receipt_stops_before_u10_and_u11() -> None:
    text = source()
    assert "read_only=True" in text
    assert "destructive_cutover=False" in text
    assert "destructive_cutover_eligible=True" in text
    assert "u10_transition=False" in text
    assert "u11_plus=False" in text
