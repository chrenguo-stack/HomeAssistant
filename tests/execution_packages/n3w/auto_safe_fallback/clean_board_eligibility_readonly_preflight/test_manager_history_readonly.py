from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
SCRIPT = ROOT / "tools/execution_packages/n3w/auto_safe_fallback/clean_board_eligibility_readonly_preflight/manager_history_readonly.py"


def load_module():
    spec = importlib.util.spec_from_file_location("clean_board_manager_history_readonly", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def registration_db(path: Path, hardware_id: str | None = None) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE registrations(hardware_id TEXT,node_id TEXT);
            CREATE TABLE pairing_sessions(hardware_id TEXT);
            CREATE TABLE registration_events(hardware_id TEXT,node_id TEXT);
            CREATE TABLE registration_node_history(hardware_id TEXT,node_id TEXT);
            CREATE TABLE node_id_leases(hardware_id TEXT,node_id TEXT);
            CREATE TABLE retirement_outbox(hardware_id TEXT);
            """
        )
        if hardware_id is not None:
            connection.execute("INSERT INTO registrations VALUES(?,?)", (hardware_id, "node_old"))


def credential_db(path: Path, hardware_id: str | None = None) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE credential_assignments(assignment_id INTEGER PRIMARY KEY,hardware_id TEXT,node_id TEXT,last_node_id TEXT)"
        )
        if hardware_id is not None:
            connection.execute(
                "INSERT INTO credential_assignments(hardware_id,node_id,last_node_id) VALUES(?,?,?)",
                (hardware_id, "node_old", "node_old"),
            )


def replay_db(path: Path, node_id: str | None = None) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE n3w_replay_meta(schema_version INTEGER)")
        connection.execute("INSERT INTO n3w_replay_meta VALUES(1)")
        connection.execute("CREATE TABLE n3w_replay_state(node_id TEXT,highest_session INTEGER,highest_seq INTEGER)")
        if node_id is not None:
            connection.execute("INSERT INTO n3w_replay_state VALUES(?,?,?)", (node_id, 7, 9))


def test_clean_history_is_absent(tmp_path: Path):
    module = load_module()
    target = "ghw-c6-112233445566"
    target_hash = module.hardware_hash(target)
    registration = tmp_path / "registration.sqlite3"
    credential = tmp_path / "credential.sqlite3"
    replay = tmp_path / "replay.sqlite3"
    registration_db(registration)
    credential_db(credential)
    replay_db(replay)
    counts, nodes, registration_match = module.registration_history(registration, target_hash)
    credential_count, credential_nodes, credential_match = module.credential_history(credential, target_hash)
    total, matches = module.replay_history(replay, nodes | credential_nodes)
    assert sum(counts.values()) == 0
    assert credential_count == 0
    assert registration_match is False
    assert credential_match is False
    assert nodes == set()
    assert credential_nodes == set()
    assert total == 0
    assert matches == 0


def test_historical_binding_is_detected(tmp_path: Path):
    module = load_module()
    target = "ghw-c6-112233445566"
    target_hash = module.hardware_hash(target)
    registration = tmp_path / "registration.sqlite3"
    credential = tmp_path / "credential.sqlite3"
    replay = tmp_path / "replay.sqlite3"
    registration_db(registration, target)
    credential_db(credential, target)
    replay_db(replay, "node_old")
    counts, nodes, registration_match = module.registration_history(registration, target_hash)
    credential_count, credential_nodes, credential_match = module.credential_history(credential, target_hash)
    total, matches = module.replay_history(replay, nodes | credential_nodes)
    assert counts["registrations"] == 1
    assert credential_count == 1
    assert registration_match is True
    assert credential_match is True
    assert nodes | credential_nodes == {"node_old"}
    assert total == 1
    assert matches == 1


def test_script_contains_no_sql_mutation_statements():
    source = SCRIPT.read_text(encoding="utf-8").upper()
    for statement in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE", "ALTER TABLE"):
        assert statement not in source
    assert "PRAGMA QUERY_ONLY=ON" in source
    assert "--PRODUCT-HARDWARE-ID-SHA256" in source
    assert "--HARDWARE-ID-SHA256" not in source
    assert "RUNTIME_QR_EQUALS_MANAGER_PENDING" in source
