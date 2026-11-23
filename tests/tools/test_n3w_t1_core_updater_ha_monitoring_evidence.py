from __future__ import annotations

import asyncio
import importlib.util
import json
import os
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

from n3w_t1_core_updater_ha_acceptance import (
    NATURAL_MONITORING_METHOD, SELF_TEST_MONITORING_METHOD, HaAcceptanceEvidence, LocalHaAcceptanceObserver,
)
from n3w_t1_core_updater_common import UpdaterError
import n3w_t1_core_updater_ha_monitoring_evidence as monitoring_module
from n3w_t1_core_updater_ha_monitoring_evidence import (
    LocalHaMonitoringEvidence, READ_HA_RECEIPTS, REQUEST_MANAGER_SELF_TEST, SERVICES,
)
from n3w_t1_core_updater_ha_recovery_startup import HaRecoveryMonitoringPending, LocalHaPredecessorRuntime
from n3w_t1_core_updater_ha_usb import _observe_target
from n3w_t1_core_updater_v2_common import UpdaterV2Error


SYSTEM = "test-greenhouse"
NODE = "node_0001"
BOOT = "boot_0000000000000001"
TOPIC = f"gh/v1/{SYSTEM}/state/{NODE}/telemetry"
SELF_TEST_TOPIC = f"gh/v1/{SYSTEM}/state/ota-monitoring/self-test"


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
    owner = os.getpid()
    owner_stat = Path(f"/proc/{owner}/task/{owner}/stat").read_text()
    owner_fields = owner_stat.rsplit(")", 1)[1].split()
    qemu_fields = owner_fields.copy()
    qemu_fields[19] = str(int(owner_fields[19]) + 1)

    def proc_path(path):
        if path in {"/proc/self/stat", f"/proc/{owner}/stat"}:
            return SimpleNamespace(read_text=lambda: f"{owner} (qemu) {' '.join(qemu_fields)}")
        return Path(path)

    monkeypatch.setattr(component, "Path", proc_path)
    payload = json.dumps({
        "schema": "gh.telemetry/1", "node_id": NODE, "boot_id": BOOT, "seq": 42,
        "received_at": scenario.received, "measurements": {"air_temperature_c": 24.5},
    }).encode()

    def read_receipt(container_id):
        assert container_id == "homeassistant"
        reader = READ_HA_RECEIPTS.replace('"/dev/shm/n3w-ota-monitoring.json"', repr(str(receipt_path)))
        return subprocess.check_output((sys.executable, "-I", "-c", reader), stderr=subprocess.PIPE, timeout=5)

    subscriptions = {}

    async def exercise():
        async def wait_for_client(hass):
            return True

        async def subscribe(hass, topic, callback, **options):
            subscriptions[topic] = callback
            if topic == SELF_TEST_TOPIC:
                assert options == {"qos": 0, "encoding": None}
                return
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
    document = json.loads(raw)
    assert document["owner"] == [owner, owner_fields[19]]
    document["owner"][1] = qemu_fields[19]
    receipt_path.write_text(json.dumps(document))
    with pytest.raises(subprocess.CalledProcessError) as rejected:
        read_receipt("homeassistant")
    assert rejected.value.stderr.strip() == b"ha_monitoring_receipt_owner_mismatch"
    receipt_path.write_bytes(raw)

    request_path = tmp_path / "request.json"

    def request(container_id, challenge, started):
        assert container_id == "manager"
        writer = REQUEST_MANAGER_SELF_TEST.replace(
            '"/dev/shm/n3w-ota-monitoring-request.json"', repr(str(request_path)),
        )
        subprocess.run((sys.executable, "-I", "-c", writer, challenge, str(started)), check=True, timeout=5)
        assert request_path.stat().st_mode & 0o777 == 0o600
        document = json.loads(request_path.read_bytes())
        assert document == {"challenge": challenge, "requested_ns": started}
        probe = json.dumps({"schema": "gh.ota-monitoring-self-test/1", "challenge": document["challenge"]}).encode()
        receive = subscriptions[SELF_TEST_TOPIC]
        asyncio.run(receive(SimpleNamespace(topic=SELF_TEST_TOPIC, payload=probe, retain=True)))
        assert receipt_path.read_bytes() == raw
        asyncio.run(receive(SimpleNamespace(topic=SELF_TEST_TOPIC, payload=probe, retain=False)))

    scenario.observer.request_self_test = request
    assert scenario.observer.run_self_test().verdict == "PASS"
    assert scenario.observer.observe({}, fallback=False).sha256 == proof


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
    monkeypatch.setattr(runtime, "candidate_manager_monitoring_self_test_available", lambda: False)
    observer = runtime.acceptance_observer()
    assert observer.monitoring_method == NATURAL_MONITORING_METHOD
    assert observer.self_test is None
    assert observer.monitoring.system_id == SYSTEM
    assert observer.monitoring.replay_db == tmp_path / "replay.sqlite3"
    assert observer.protected_data.history == tmp_path / "home-assistant_v2.db"


def test_runtime_adds_self_test_only_when_manager_supports_it(monkeypatch, tmp_path):
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
    monkeypatch.setattr(runtime, "candidate_manager_monitoring_self_test_available", lambda: True)
    observer = runtime.acceptance_observer()
    assert observer.monitoring_method == NATURAL_MONITORING_METHOD
    assert observer.self_test == observer.monitoring.run_self_test


@pytest.mark.parametrize(("returncode", "expected"), [(0, True), (42, False)])
def test_manager_monitoring_self_test_capability_probe(monkeypatch, returncode, expected):
    runtime = LocalHaPredecessorRuntime()
    monkeypatch.setattr(runtime, "_runtime", lambda name: {"container_id": "manager"})
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=returncode)

    monkeypatch.setattr(runtime, "_run", run)
    assert runtime.candidate_manager_monitoring_self_test_available() is expected
    assert calls and calls[0][1] == {"check": False, "timeout": 10}


def test_manager_monitoring_self_test_probe_fails_closed(monkeypatch):
    runtime = LocalHaPredecessorRuntime()
    monkeypatch.setattr(runtime, "_runtime", lambda name: {"container_id": "manager"})
    monkeypatch.setattr(
        runtime,
        "_run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1),
    )
    with pytest.raises(UpdaterError, match="manager_monitoring_probe_failed"):
        runtime.candidate_manager_monitoring_self_test_available()


@pytest.mark.parametrize("fault", ["wrong_challenge", "stale_receipt", "instance_changed"])
def test_self_test_requires_current_challenge_and_runtime(monkeypatch, scenario, fault):
    clock = 2_000_000_000
    monkeypatch.setattr(monitoring_module, "SELF_TEST_TIMEOUT_SECONDS", 1)

    def sleep(seconds):
        nonlocal clock
        clock += int(seconds * 10**9)

    monkeypatch.setattr(monitoring_module, "time", SimpleNamespace(monotonic_ns=lambda: clock, sleep=sleep))

    def request(_, challenge, started):
        receipt_challenge = "invalid" if fault == "wrong_challenge" else challenge
        stamp_ns = started - 1 if fault == "stale_receipt" else started
        scenario.receipt["records"] = [["self-test", receipt_challenge, stamp_ns]]
        if fault == "instance_changed":
            scenario.runtimes["broker"] = {"started_at": stamp(0), "container_id": "replaced"}

    scenario.observer.request_self_test = request
    assert scenario.observer.run_self_test().verdict == "EVIDENCE_UNAVAILABLE"


def test_only_preverified_method_can_issue_target_self_test(monkeypatch, scenario):
    import n3w_t1_core_updater_ha_usb as ha_usb

    actions = []

    def exercise():
        actions.append("request")
        return HaAcceptanceEvidence("PASS", "3" * 64)

    observer = LocalHaAcceptanceObserver(
        scenario.observer, SimpleNamespace(capture=lambda: {"history": None, "pairing": None}),
        monitoring_method=NATURAL_MONITORING_METHOD, self_test=exercise,
    )
    baseline = observer.capture_baseline({})
    assert baseline.monitoring_method == NATURAL_MONITORING_METHOD
    assert baseline.monitoring_fallback_sha256 == "3" * 64
    assert baseline.checks["monitoring_path"] != baseline.monitoring_fallback_sha256
    assert actions == ["request"]

    monkeypatch.setattr(ha_usb, "validate_transaction_document", lambda document: document)
    target = {"target_acceptance": {"monitoring_method": NATURAL_MONITORING_METHOD}}
    assert _observe_target(observer, target, "monitoring_path", fallback=True).verdict == "EVIDENCE_UNAVAILABLE"
    assert actions == ["request"]
    target["target_acceptance"]["monitoring_fallback_sha256"] = baseline.monitoring_fallback_sha256
    assert _observe_target(observer, target, "monitoring_path", fallback=False).verdict == "PASS"
    assert actions == ["request"]

    scenario.receipt["records"] = []
    assert _observe_target(observer, target, "monitoring_path", fallback=False).verdict == "EVIDENCE_UNAVAILABLE"
    assert actions == ["request"]
    assert _observe_target(observer, target, "monitoring_path", fallback=True).verdict == "PASS"
    assert actions == ["request", "request"]
    offline_baseline = observer.capture_baseline({})
    assert offline_baseline.monitoring_method == SELF_TEST_MONITORING_METHOD
    assert offline_baseline.checks["monitoring_path"] == "3" * 64
    assert offline_baseline.monitoring_fallback_sha256 is None


def test_natural_only_baseline_remains_fail_closed_without_fallback(scenario):
    observer = LocalHaAcceptanceObserver(
        scenario.observer,
        SimpleNamespace(capture=lambda: {"history": None, "pairing": None}),
        monitoring_method=NATURAL_MONITORING_METHOD,
        self_test=None,
    )
    baseline = observer.capture_baseline({})
    assert baseline.monitoring_method == NATURAL_MONITORING_METHOD
    assert baseline.monitoring_fallback_sha256 is None
    assert baseline.checks["monitoring_path"]

    scenario.receipt["records"] = []
    with pytest.raises(UpdaterV2Error, match="natural_monitoring_baseline_unavailable"):
        observer.capture_baseline({})


def test_fallback_with_no_proof_defers_install_even_with_natural_traffic(scenario):
    observer = LocalHaAcceptanceObserver(
        scenario.observer, SimpleNamespace(capture=lambda: {"history": None, "pairing": None}),
        monitoring_method=NATURAL_MONITORING_METHOD,
        self_test=lambda: HaAcceptanceEvidence("EVIDENCE_UNAVAILABLE"),
    )
    with pytest.raises(UpdaterV2Error, match="ha_usb_monitoring_fallback_unavailable"):
        observer.capture_baseline({})


def test_rollback_observes_restored_path_before_terminal_status(monkeypatch, scenario):
    runtime = LocalHaPredecessorRuntime()
    monkeypatch.setattr(runtime, "_monitoring_evidence", lambda _: scenario.observer)
    document = {"target_acceptance": {"monitoring_method": NATURAL_MONITORING_METHOD}}
    scenario.runtimes["homeassistant"]["started_at"] = stamp(1)
    with pytest.raises(HaRecoveryMonitoringPending, match="monitoring_evidence_pending"):
        runtime._verify_recovered_monitoring(document, {})

    def request(_, challenge, started):
        scenario.receipt["records"] = [["self-test", challenge, started]]

    scenario.observer.request_self_test = request
    document["target_acceptance"]["monitoring_fallback_sha256"] = "3" * 64
    runtime._verify_recovered_monitoring(document, {})


@pytest.mark.parametrize("business_healthy", [True, False])
def test_rollback_follows_frozen_business_evidence_independent_of_broker_logs(monkeypatch, business_healthy):
    runtime = LocalHaPredecessorRuntime()
    binding = {"images": {}}
    document = {"predecessor_start": binding, "target_acceptance": {"monitoring_method": NATURAL_MONITORING_METHOD}}
    checks = []

    def broker_logs(_):
        checks.append("logs")
        if business_healthy:
            raise UpdaterError("broker_log_coverage_insufficient")
        return True

    def observe(*_args, **_kwargs):
        checks.append("business")
        return HaAcceptanceEvidence("PASS", "3" * 64) if business_healthy else HaAcceptanceEvidence("EVIDENCE_UNAVAILABLE")

    monkeypatch.setattr(runtime, "_restart_binding", lambda: (binding, {}))
    monkeypatch.setattr(runtime, "_systemctl", lambda *_: "active")
    monkeypatch.setattr(runtime, "_check_running_predecessor", lambda *_: dict.fromkeys(SERVICES, 1))
    monkeypatch.setattr(runtime, "_mqtt_authenticated", broker_logs)
    monkeypatch.setattr(runtime, "_monitoring_evidence", lambda _: SimpleNamespace(observe=observe))
    if business_healthy:
        runtime.verify_resident_predecessor_health(document)
        runtime.verify_predecessor_health(document)
        assert checks == ["business", "business"]
    else:
        with pytest.raises(HaRecoveryMonitoringPending, match="monitoring_evidence_pending"):
            runtime.verify_resident_predecessor_health(document)
        assert checks == ["business"]
