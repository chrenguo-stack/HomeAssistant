from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from n3w_t1_core_updater_common import UpdaterError
from n3w_t1_core_updater_ha_acceptance import HaAcceptanceEvidence, LocalHaAcceptanceObserver
from n3w_t1_core_updater_ha_backup import HA_DATABASE_NAME
from n3w_t1_core_updater_ha_data_evidence import MANAGER_PAIRING_DB, HaProtectedDataEvidence
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime


@pytest.fixture
def databases(tmp_path):
    history = tmp_path / "ha" / HA_DATABASE_NAME
    pairing = tmp_path / "manager" / MANAGER_PAIRING_DB.name
    history.parent.mkdir()
    pairing.parent.mkdir()
    with closing(sqlite3.connect(history)) as connection:
        connection.executescript(
            """
            CREATE TABLE states_meta (metadata_id INTEGER PRIMARY KEY, entity_id TEXT NOT NULL);
            CREATE TABLE states (
                state_id INTEGER PRIMARY KEY, metadata_id INTEGER, last_updated_ts REAL, state TEXT
            );
            INSERT INTO states_meta VALUES (1, 'sensor.fixture_temperature');
            """
        )
    with closing(sqlite3.connect(pairing)) as connection:
        connection.executescript(
            """
            CREATE TABLE registrations (
                node_id TEXT PRIMARY KEY, current_pairing_id TEXT, pairing_epoch INTEGER, retired_at TEXT
            );
            CREATE TABLE pairing_sessions (pairing_id TEXT PRIMARY KEY, state TEXT);
            """
        )
    return history, pairing


def test_live_wal_and_stable_sample_are_observed_read_only(databases):
    history, pairing = databases
    protected = HaProtectedDataEvidence(history, pairing)
    with closing(sqlite3.connect(history)) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO states VALUES (1, 1, 1900000000.125, '16.3')")
        writer.commit()
        wal = history.with_name(history.name + "-wal")
        before = (history.read_bytes(), wal.read_bytes())
        sample = protected.capture()
        assert sample["history"]["at"] == 1900000000.125
        assert protected.compare(sample) == "PASS"
        assert (history.read_bytes(), wal.read_bytes()) == before
        writer.execute("UPDATE states SET state_id=7")
        writer.execute("INSERT INTO states VALUES (9, 1, 1900000001.125, '17.5')")
        writer.commit()
        assert protected.compare(sample) == "PASS"
        writer.execute("DELETE FROM states WHERE state_id=7")
        writer.commit()
        assert protected.compare(sample) == "EVIDENCE_UNAVAILABLE"


def test_empty_baseline_accepts_new_data_but_matching_pairing_must_persist(databases):
    history, pairing = databases
    protected = HaProtectedDataEvidence(history, pairing)
    empty = protected.capture()
    assert empty == {"history": None, "pairing": None}
    with closing(sqlite3.connect(pairing)) as writer:
        writer.executescript(
            """
            INSERT INTO pairing_sessions VALUES ('fixture-assignment', 'approved');
            INSERT INTO registrations VALUES ('fixture-node', 'fixture-assignment', 1, NULL);
            """
        )
        assert protected.compare(empty) == "PASS"
        sampled = protected.capture()
        assert sampled["pairing"]["node"] == "fixture-node"
        assert protected.compare(sampled) == "PASS"
        writer.execute("UPDATE registrations SET pairing_epoch = 2")
        writer.commit()
        assert protected.compare(sampled) == "PROVEN_FAIL"


def test_unavailable_wal_sidecars_are_not_created_by_probe(databases):
    history, pairing = databases
    protected = HaProtectedDataEvidence(history, pairing)
    sample = protected.capture()
    with closing(sqlite3.connect(history)) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("INSERT INTO states VALUES (1, 1, 1900000000.125, '16.3')")
        writer.commit()
    sidecars = [history.with_name(history.name + suffix) for suffix in ("-wal", "-shm")]
    assert not any(path.exists() for path in sidecars)
    assert protected.compare(sample) == "EVIDENCE_UNAVAILABLE"
    assert not any(path.exists() for path in sidecars)


def test_rollback_health_rechecks_frozen_data_without_running_observer(databases, monkeypatch):
    history, pairing = databases
    protected = HaProtectedDataEvidence(history, pairing)
    monitoring = SimpleNamespace(
        capture_baseline=lambda _: "a" * 64,
        observe=lambda *_args, **_kwargs: pytest.fail("status/data checks must not run monitoring probes"),
    )
    observer = LocalHaAcceptanceObserver(monitoring, protected)
    baseline = observer.capture_baseline({})
    document = {"target_acceptance": {"data_sample": baseline.data_sample}, "predecessor_start": {"binding": "fixture"}}
    verdict = observer.observe(document, "protected_data", fallback=False)
    assert verdict == HaAcceptanceEvidence("PASS", baseline.checks["protected_data"])

    origins = {
        "homeassistant": {"/config": str(history.parent)},
        "manager": {str(MANAGER_PAIRING_DB.parent): str(pairing.parent)},
    }
    runtime = LocalHaPredecessorRuntime()
    monkeypatch.setattr(runtime, "_restart_binding", lambda: (document["predecessor_start"], origins))
    monkeypatch.setattr(runtime, "_verify_published_launch", lambda _: (document["predecessor_start"], origins))
    monkeypatch.setattr(runtime, "_verify_rollback_health", lambda *_: None)
    runtime.verify_published_predecessor_health(document)
    history.rename(history.with_name("unavailable"))
    with pytest.raises(UpdaterError, match="rollback_protected_data_evidence_pending"):
        runtime.verify_published_predecessor_health(document)
    assert not history.exists()
    history.with_name("unavailable").rename(history)
    runtime.verify_resident_predecessor_health(document)
