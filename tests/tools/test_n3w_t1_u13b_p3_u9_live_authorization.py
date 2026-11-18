from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u13b_p3_u1_u4_recovery"
    / "u9_live_authorization.py"
)
GRANT = SCRIPT.with_name("u9_live_authorization_grant.json")

U8_SHA = "c9210a75ba4496b42fd080ca4ef261cf669a56452f99531066f921a5fcbe4908"
U8_RECEIPT_SHA = "8340d0b4a5be925c954932113b8c593668e83b5f60d1271714f2ce91d521a63a"
RECOVERY_MANIFEST_SHA = "d534be84e38817b10eab8a2f8a47c6dae3fd0946da9eba1e1d7f12090e23e9d3"
AUTHORIZATION = "N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_P3_U9_20261118_01"
AUTHORIZATION_RE = re.compile(r"^N3W_T1_CORE_UPDATER_[A-Za-z0-9_-]{1,160}$")


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_source_compiles_and_candidate_has_no_grant() -> None:
    compile(source(), str(SCRIPT), "exec")
    assert GRANT.exists() is False


def test_u9_binds_exact_live_u8_evidence() -> None:
    text = source()
    assert f'U8_SHA = "{U8_SHA}"' in text
    assert f'U8_RECEIPT_SHA = "{U8_RECEIPT_SHA}"' in text
    assert f'RECOVERY_MANIFEST_SHA = "{RECOVERY_MANIFEST_SHA}"' in text
    assert '"u8_transaction_sha256": U8_SHA' in text
    assert '"u8_receipt_sha256": U8_RECEIPT_SHA' in text
    assert '"recovery_content_manifest_sha256": RECOVERY_MANIFEST_SHA' in text


def test_product_authorization_id_uses_valid_namespace() -> None:
    text = source()
    assert f'AUTHORIZATION_ID = "{AUTHORIZATION}"' in text
    assert AUTHORIZATION_RE.fullmatch(AUTHORIZATION)
    assert "N3W_T1_U13B_P3_U9" not in AUTHORIZATION


def test_preflight_is_read_only_and_stops_before_u10() -> None:
    text = source()
    start = text.index("def preflight_only(")
    end = text.index("def execute(", start)
    block = text[start:end]
    assert 'projected_u9(snapshot["tx"])' in block
    assert "store.write(" not in block
    assert "sync_transaction_metadata(" not in block
    assert "ledger.mkdir(" not in block
    assert "u9_transition=False" in block
    assert "u10_plus=False" in block
    assert "destructive_cutover=False" in block


def test_execute_claims_product_authorization_once_then_usb_then_host() -> None:
    text = source()
    start = text.index("def execute(")
    end = text.index("def inspect(", start)
    block = text[start:end]
    assert block.count("projected_u9(tx)") == 1
    claim = block.index("claimed = projected_u9(tx)")
    ledger = block.index('ledger / "claim.json"')
    usb = block.index("backend.sync_transaction_metadata(claimed, device)")
    host = block.index("store.write(claimed)")
    assert claim < ledger < usb < host


def test_execute_never_performs_u10_or_destructive_cutover() -> None:
    text = source()
    start = text.index("def execute(")
    end = text.index("def inspect(", start)
    block = text[start:end]
    assert "u10_plus=False" in block
    assert "destructive_cutover=False" in block
    assert "predecessor_image_delete=False" in block
    assert "target_image_load=False" in block
    assert "service_mutation=False" in block
    assert "docker image rm" not in block
    assert "docker load" not in block
    assert '["systemctl", "start"' not in block
    assert '["systemctl", "stop"' not in block


def test_separate_grant_commit_is_required() -> None:
    text = source()
    start = text.index("def attach_grant(")
    end = text.index("def state_bytes(", start)
    block = text[start:end]
    assert '"diff-tree"' in block
    assert '"A\\t" + path' in block
    assert 'git("rev-parse", head + "^")' in block
    assert "validate_grant(plan)" in block


def test_preclaim_requires_durable_u8_and_unclaimed_product_authorization() -> None:
    text = source()
    start = text.index("def verify_u8(")
    end = text.index("def device_from(", start)
    block = text[start:end]
    assert "u8.inspect(plan, u8_result)" in block
    assert 'u8_result.get("status") == u8.STATUS_PASS' in block
    assert 'tx["authorization_claimed"] is False' in block
    assert 'tx["authorization_consumed"] is False' in block
    assert 'tx["authorization_id_sha256"] is None' in block
    assert "ha_backup.verify_quiesced" in block
    assert "u6_preflight.image_binding(tx)" in block


def test_postclaim_failure_is_non_replayable_status_only() -> None:
    text = source()
    start = text.index("def execute(")
    end = text.index("def inspect(", start)
    block = text[start:end]
    assert '"STOP_POSTCLAIM"' in block
    assert "read_only_status_required=True" in block
    assert "u9_ledger_exists_never_replay" in block
    assert "replay_permitted" in text
