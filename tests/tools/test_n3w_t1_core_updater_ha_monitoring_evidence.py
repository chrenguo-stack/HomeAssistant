from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from n3w_t1_core_updater_ha_acceptance import NATURAL_MONITORING_METHOD
from n3w_t1_core_updater_ha_monitoring_evidence import (
    LocalHaMonitoringEvidence, READ_HA_RECEIPTS, SERVICES,
)
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
from n3w_t1_core_updater_v2_common import UpdaterV2Error


SYSTEM = "test-greenhouse"
NODE = "node_0001"
BOOT = "boot_0000000000000001"
TOPIC = f"gh/v1/{SYSTEM}/state/{NODE}/telemetry"


def stamp(seconds_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds_ago)).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


@pytest.fixture
def scenario(tmp_path):
    db = tmp_path / "replay.sqlite3"
    received = stamp(2)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE n3w_canonical_cursors ("
            "node_id TEXT PRIMARY KEY, boot_session_hex TEXT, seq INTEGER,"
            "updated_at TEXT, last_source TEXT)"
        )
        connection.execute(
            "INSERT INTO n3w_canonical_cursors VALUES (?, ?, ?, ?, ?)",
            (NODE, BOOT[5:], 42, received, "relay"),
        )
    runtimes = {
        name: {"started_at": stamp(20), "container_id": name} for name in SERVICES
    }
    receipt = {"system_id": SYSTEM, "records": [[NODE, BOOT, 42, received, time.monotonic_ns()]]}
    observer = LocalHaMonitoringEvidence(
        SYSTEM, db, runtimes.__getitem__, lambda _: json.dumps(receipt).encode(),
    )
    return SimpleNamespace(
        db=db, receipt=receipt, runtimes=runtimes, observer=observer, received=received,
    )


def test_ha_client_delivery_correlates_with_manager_cursor(monkeypatch, tmp_path, scenario):
    source = ROOT / "infra/n3w-t1/homeassistant/custom_components/n3w_ota_monitoring/__init__.py"
    spec = importlib.util.spec_from_file_location("n3w_ota_monitoring_test", source)
    component = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(component)
    receipt_path = tmp_path / "receipt.json"
    monkeypatch.setattr(component, "RECEIPTS", receipt_path)
    payload = json.dumps({
        "schema": "gh.telemetry/1", "node_id": NODE, "boot_id": BOOT, "seq": 42,
        "received_at": scenario.received, "measurements": {"air_temperature_c": 24.5},
    }).encode()

    def read_receipt(container_id):
        assert container_id == "homeassistant"
        reader = READ_HA_RECEIPTS.replace('"/dev/shm/n3w-ota-monitoring.json"', repr(str(receipt_path)))
        return subprocess.check_output((sys.executable, "-I", "-c", reader), timeout=5)

    async def exercise():
        async def wait_for_client(hass):
            return True

        async def subscribe(hass, topic, callback, **options):
            assert topic == f"gh/v1/{SYSTEM}/state/+/telemetry"
            assert options == {"qos": 1, "encoding": None}
            for message in (
                SimpleNamespace(topic=TOPIC, payload=payload, retain=True),
                SimpleNamespace(topic=TOPIC.replace(NODE, "other_node"), payload=payload, retain=False),
                SimpleNamespace(topic=TOPIC, payload=b'{"schema":', retain=False),
            ):
                await callback(message)
                assert not receipt_path.exists()
            await callback(SimpleNamespace(topic=TOPIC, payload=payload, retain=False))

        mqtt = SimpleNamespace(async_subscribe=subscribe, async_wait_for_mqtt_client=wait_for_client)
        package = ModuleType("homeassistant")
        subpackage = ModuleType("homeassistant.components")
        subpackage.mqtt = mqtt
        monkeypatch.setitem(sys.modules, package.__name__, package)
        monkeypatch.setitem(sys.modules, subpackage.__name__, subpackage)
        tasks = []

        def background(coroutine, _):
            tasks.append(asyncio.create_task(coroutine))

        hass = SimpleNamespace(async_add_executor_job=asyncio.to_thread, async_create_background_task=background)
        assert await component.async_setup(hass, {component.DOMAIN: {"system_id": SYSTEM}})
        await asyncio.gather(*tasks)

    asyncio.run(exercise())
    scenario.observer.read_receipts = read_receipt
    proof = scenario.observer.capture_baseline({})
    assert scenario.observer.observe({}, fallback=False).sha256 == proof
    assert scenario.observer.observe({}, fallback=True).verdict == "EVIDENCE_UNAVAILABLE"
    assert len(proof) == 64
    raw = receipt_path.read_bytes()
    assert b"24.5" not in raw and receipt_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    ("field", "value"),
    [(1, "boot_0000000000000002"), (2, 41), (2, True), (3, "no-time-zone"), (4, 0)],
)
def test_invalid_or_unmatched_receipt_is_unavailable(scenario, field, value):
    scenario.receipt["records"][0][field] = value
    assert scenario.observer.observe({}, fallback=False).verdict == "EVIDENCE_UNAVAILABLE"
    with pytest.raises(UpdaterV2Error, match="natural_monitoring_baseline_unavailable"):
        scenario.observer.capture_baseline({})


@pytest.mark.parametrize("name", SERVICES)
def test_rejects_telemetry_from_before_any_bound_service_start(scenario, name):
    scenario.runtimes[name]["started_at"] = stamp(1)
    assert scenario.observer.observe({}, fallback=False).verdict == "EVIDENCE_UNAVAILABLE"


def test_rejects_wall_clock_old_receipt_even_if_monotonic_age_is_recent(scenario):
    received = stamp(40)
    scenario.receipt["records"][0][3] = received
    for runtime in scenario.runtimes.values():
        runtime["started_at"] = stamp(60)
    with sqlite3.connect(scenario.db) as connection:
        connection.execute("UPDATE n3w_canonical_cursors SET updated_at = ?", (received,))
    assert scenario.observer.observe({}, fallback=False).verdict == "EVIDENCE_UNAVAILABLE"


def test_rejects_runtime_turnover_during_observation(scenario):
    def read(_):
        scenario.runtimes["broker"] = {"started_at": stamp(0), "container_id": "replaced"}
        return json.dumps(scenario.receipt).encode()

    scenario.observer.read_receipts = read
    assert scenario.observer.observe({}, fallback=False).verdict == "EVIDENCE_UNAVAILABLE"


def test_runtime_wires_live_observer_from_bound_mounts(monkeypatch, tmp_path):
    runtime = LocalHaPredecessorRuntime()
    replay_root = "/var/lib/greenhouse-manager/n3w"
    origins = {
        "manager": {replay_root: str(tmp_path), "/var/lib/greenhouse-manager/manager": str(tmp_path)},
        "homeassistant": {"/config": str(tmp_path)},
    }
    monkeypatch.setattr(runtime, "_restart_binding", lambda: ({}, origins))
    monkeypatch.setattr(runtime, "_check_running_predecessor", lambda *_: dict.fromkeys(SERVICES, 1))
    environment = {"GH_SYSTEM_ID": SYSTEM, "GH_N3W_REPLAY_DB_PATH": f"{replay_root}/replay.sqlite3"}
    monkeypatch.setattr(runtime, "render_compose", lambda: {"services": {"manager": {"environment": environment}}})
    observer = runtime.acceptance_observer()
    assert observer.monitoring_method == NATURAL_MONITORING_METHOD
    assert observer.monitoring.system_id == SYSTEM
    assert observer.monitoring.replay_db == tmp_path / "replay.sqlite3"
    assert observer.protected_data.history == tmp_path / "home-assistant_v2.db"
