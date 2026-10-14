from __future__ import annotations

import importlib.util
import sqlite3
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST_SRC = ROOT / "host/greenhouse-manager/src"
TOOL = ROOT / "tools/n3w_t1_fresh_product_state_prepare.py"
SYSTEM_ID_SHA256 = "a" * 64

if str(HOST_SRC) not in sys.path:
    sys.path.insert(0, str(HOST_SRC))


def load_tool():
    name = "n3w_t1_fresh_product_state_prepare"
    specification = importlib.util.spec_from_file_location(name, TOOL)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700)
    path.chmod(0o700)
    return path


def test_create_and_audit_fresh_product_state(tmp_path: Path) -> None:
    tool = load_tool()
    manager = private_dir(tmp_path / "manager")
    n3w = private_dir(tmp_path / "n3w")

    created = tool.create_fresh_state(
        manager,
        n3w,
        expected_system_id_sha256=SYSTEM_ID_SHA256,
    )

    assert created["status"] == "PASS"
    assert created["phase"] == "create"
    assert created["fresh_product_state"] is True
    assert created["legacy_state_imported"] is False
    assert created["legacy_provenance_present"] is False
    assert created["manager_table_count"] == 7
    assert created["manager_business_row_count"] == 0
    assert created["replay_node_count"] == 0
    assert created["replay_tuple_count"] == 0
    assert created["relay_active_node_count"] == 0
    assert created["relay_key_file_count"] == 0
    assert created["node_credential_count"] == 0
    assert created["production_service_start"] is False
    assert created["network_operation"] is False

    manager_db = manager / "manager-state.sqlite3"
    assert stat.S_IMODE(manager_db.stat().st_mode) == 0o600
    assert stat.S_IMODE((n3w / "replay.sqlite3").stat().st_mode) == 0o600
    assert stat.S_IMODE((n3w / "relay-authorization.sqlite3").stat().st_mode) == 0o600
    assert stat.S_IMODE((n3w / "relay-keys").stat().st_mode) == 0o700

    with sqlite3.connect(manager_db) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    assert tables == set(tool.EXPECTED_MANAGER_TABLES)
    assert "h0h1_legacy_adoption_provenance" not in tables

    audited = tool.audit_fresh_state(
        manager,
        n3w,
        expected_system_id_sha256=SYSTEM_ID_SHA256,
    )
    assert audited["status"] == "PASS"
    assert audited["phase"] == "audit"
    assert audited["manager_database_sha256"] == created["manager_database_sha256"]


def test_create_rejects_dirty_manager_root(tmp_path: Path) -> None:
    tool = load_tool()
    manager = private_dir(tmp_path / "manager")
    n3w = private_dir(tmp_path / "n3w")
    (manager / "unexpected").write_text("x", encoding="utf-8")

    with pytest.raises(
        tool.FreshProductStateError,
        match="manager_root_not_empty",
    ):
        tool.create_fresh_state(
            manager,
            n3w,
            expected_system_id_sha256=SYSTEM_ID_SHA256,
        )


def test_create_rejects_dirty_n3w_root(tmp_path: Path) -> None:
    tool = load_tool()
    manager = private_dir(tmp_path / "manager")
    n3w = private_dir(tmp_path / "n3w")
    (n3w / "unexpected").write_text("x", encoding="utf-8")

    with pytest.raises(
        tool.FreshProductStateError,
        match="n3w_root_not_empty",
    ):
        tool.create_fresh_state(
            manager,
            n3w,
            expected_system_id_sha256=SYSTEM_ID_SHA256,
        )


def test_rejects_invalid_system_identity_digest(tmp_path: Path) -> None:
    tool = load_tool()
    manager = private_dir(tmp_path / "manager")
    n3w = private_dir(tmp_path / "n3w")

    with pytest.raises(
        tool.FreshProductStateError,
        match="system_id_sha256_invalid",
    ):
        tool.create_fresh_state(
            manager,
            n3w,
            expected_system_id_sha256="not-a-sha",
        )


def test_audit_rejects_business_rows(tmp_path: Path) -> None:
    tool = load_tool()
    manager = private_dir(tmp_path / "manager")
    n3w = private_dir(tmp_path / "n3w")
    tool.create_fresh_state(
        manager,
        n3w,
        expected_system_id_sha256=SYSTEM_ID_SHA256,
    )

    with sqlite3.connect(manager / "manager-state.sqlite3") as connection:
        connection.execute(
            """
            INSERT INTO pairing_sessions (
                pairing_id,
                hardware_id,
                pairing_epoch,
                model,
                fw_version,
                node_nonce,
                capabilities_json,
                state,
                first_seen_at,
                last_seen_at,
                expires_at,
                reason
            ) VALUES (?, ?, 1, ?, ?, ?, '[]', 'pending', ?, ?, ?, NULL)
            """,
            (
                "00000000-0000-0000-0000-000000000001",
                "ghw-test-000000000001",
                "test",
                "test",
                "nonce",
                "2026-01-01T00:00:00.000Z",
                "2026-01-01T00:00:00.000Z",
                "2026-01-01T00:02:00.000Z",
            ),
        )

    with pytest.raises(
        tool.FreshProductStateError,
        match="manager_database_not_clean",
    ):
        tool.audit_fresh_state(
            manager,
            n3w,
            expected_system_id_sha256=SYSTEM_ID_SHA256,
        )
