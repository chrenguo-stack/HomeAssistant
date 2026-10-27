from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST_SRC = ROOT / "host/greenhouse-manager/src"
TOOL = ROOT / "tools/n3w_t1_production_manager_state_prepare.py"
SYSTEM_ID_SHA256 = "a" * 64
SYSTEM_FINGERPRINT = SYSTEM_ID_SHA256[:24]

if str(HOST_SRC) not in sys.path:
    sys.path.insert(0, str(HOST_SRC))


def load_tool():
    name = "n3w_t1_production_manager_state_prepare"
    specification = importlib.util.spec_from_file_location(name, TOOL)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def manager_database(root: Path) -> Path:
    manager = root / "manager"
    manager.mkdir(mode=0o700)
    manager.chmod(0o700)
    path = manager / "manager-state.sqlite3"

    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE registrations (id INTEGER);
            CREATE TABLE pairing_sessions (id INTEGER);
            CREATE TABLE registration_events (id INTEGER);
            CREATE TABLE registration_node_history (id INTEGER);
            CREATE TABLE node_id_leases (id INTEGER);
            CREATE TABLE retirement_outbox (id INTEGER);
            CREATE TABLE credential_assignments (id INTEGER);
            CREATE TABLE first_registration_attempts (id INTEGER);
            CREATE TABLE h0h1_legacy_adoption_provenance (
                schema TEXT NOT NULL,
                classification_result_sha256 TEXT NOT NULL,
                system_id_fingerprint TEXT NOT NULL,
                structured_legacy_manager_state_imported INTEGER NOT NULL,
                anonymous_nodes_reconstructed INTEGER NOT NULL
            );
            """
        )
        connection.execute(
            """
            INSERT INTO h0h1_legacy_adoption_provenance
            VALUES (?, ?, ?, 0, 0)
            """,
            (
                "gh.h0h1.legacy-adoption-provenance/1",
                "b" * 64,
                SYSTEM_FINGERPRINT,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    path.chmod(0o600)
    return path


def n3w_root(root: Path) -> Path:
    path = root / "n3w"
    path.mkdir(mode=0o700)
    path.chmod(0o700)
    return path


def test_prepare_creates_exact_empty_runtime_state(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    manager_db = manager_database(tmp_path)
    runtime_root = n3w_root(tmp_path)
    before = tool._sha256_file(manager_db)

    report = tool.prepare(
        manager_db,
        runtime_root,
        expected_system_id_sha256=SYSTEM_ID_SHA256,
    )

    assert report["n3w_state_prepared"] is True
    assert report["manager_database_mutated"] is False
    assert report["manager_database_sha256"] == before
    assert report["replay_node_count"] == 0
    assert report["replay_tuple_count"] == 0
    assert report["relay_active_node_count"] == 0
    assert report["relay_key_file_count"] == 0

    assert (runtime_root / "replay.sqlite3").is_file()
    assert (runtime_root / "relay-authorization.sqlite3").is_file()
    assert (runtime_root / "relay-keys").is_dir()

    audit = tool.audit(
        manager_db,
        runtime_root,
        expected_system_id_sha256=SYSTEM_ID_SHA256,
    )
    assert audit["n3w_state_prepared"] is True


def test_preflight_rejects_legacy_registration_collision(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    manager_db = manager_database(tmp_path)
    runtime_root = n3w_root(tmp_path)
    (manager_db.parent / "registration.sqlite3").mkdir()

    with pytest.raises(
        tool.ManagerStatePrepareError,
        match="legacy_registration_collision_present",
    ):
        tool.preflight(
            manager_db,
            runtime_root,
            expected_system_id_sha256=SYSTEM_ID_SHA256,
        )


def test_prepare_rejects_nonempty_runtime_root(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    manager_db = manager_database(tmp_path)
    runtime_root = n3w_root(tmp_path)
    (runtime_root / "unexpected").write_text("x", encoding="utf-8")

    with pytest.raises(
        tool.ManagerStatePrepareError,
        match="n3w_state_root_not_empty",
    ):
        tool.prepare(
            manager_db,
            runtime_root,
            expected_system_id_sha256=SYSTEM_ID_SHA256,
        )


def test_rejects_manager_business_rows(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    manager_db = manager_database(tmp_path)
    runtime_root = n3w_root(tmp_path)

    connection = sqlite3.connect(manager_db)
    try:
        connection.execute(
            "INSERT INTO registrations VALUES (1)"
        )
        connection.commit()
    finally:
        connection.close()
    manager_db.chmod(0o600)

    with pytest.raises(
        tool.ManagerStatePrepareError,
        match="manager_database_not_clean",
    ):
        tool.preflight(
            manager_db,
            runtime_root,
            expected_system_id_sha256=SYSTEM_ID_SHA256,
        )


def test_rejects_system_identity_binding_mismatch(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    manager_db = manager_database(tmp_path)
    runtime_root = n3w_root(tmp_path)

    with pytest.raises(
        tool.ManagerStatePrepareError,
        match="manager_database_system_identity_binding_invalid",
    ):
        tool.preflight(
            manager_db,
            runtime_root,
            expected_system_id_sha256="c" * 64,
        )


def test_rejects_legacy_full_sha_in_provenance(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    manager_db = manager_database(tmp_path)
    runtime_root = n3w_root(tmp_path)

    connection = sqlite3.connect(manager_db)
    try:
        connection.execute(
            "UPDATE h0h1_legacy_adoption_provenance "
            "SET system_id_fingerprint = ?",
            (SYSTEM_ID_SHA256,),
        )
        connection.commit()
    finally:
        connection.close()
    manager_db.chmod(0o600)

    with pytest.raises(
        tool.ManagerStatePrepareError,
        match="manager_database_system_identity_binding_invalid",
    ):
        tool.preflight(
            manager_db,
            runtime_root,
            expected_system_id_sha256=SYSTEM_ID_SHA256,
        )


def test_expected_provenance_fingerprint_uses_h0h1_prefix() -> None:
    tool = load_tool()

    assert (
        tool._expected_provenance_fingerprint(SYSTEM_ID_SHA256)
        == SYSTEM_FINGERPRINT
    )
