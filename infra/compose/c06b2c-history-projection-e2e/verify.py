from __future__ import annotations

import copy
import hashlib
import json
import os
import queue
import sqlite3
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from greenhouse_manager.runtime.history_projection_store import ProjectionStore
from greenhouse_manager.runtime.history_store import HistoryStore

BROKER = "broker"
PORT = 1883
SYSTEM_ID = "greenhouse"
NODE_ID = "node-0001"
SAMPLE_HOUR = "2026-08-03T04:00:00.000Z"
IDEMPOTENCY_KEY = f"{NODE_ID}|{SAMPLE_HOUR}|v1"
REQUEST_TOPIC = f"gh/v1/{SYSTEM_ID}/out/homeassistant/history/projection"
RESULT_TOPIC = f"gh/v1/{SYSTEM_ID}/ingress/homeassistant/history/projection/result"
PROBE_PATH = Path("/ha-config/c06b2c-probe-state.json")
DATABASE = Path("/state/manager/manager-state.sqlite3")
EVIDENCE = Path("/evidence")
EXPECTED_UNIQUE_IDS = {
    "node-0001_air_temperature_c": ("°C", "temperature", 25.0),
    "node-0001_air_humidity_pct": ("%", "humidity", 65.0),
}


def canonical_json(document: dict[str, Any]) -> str:
    return json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def projection_hash(projection: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(projection).encode("utf-8")).hexdigest()


def write_json(name: str, document: dict[str, Any]) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    target = EVIDENCE / name
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    temporary.replace(target)


def read_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return document if isinstance(document, dict) else {}


def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout_s: float,
    description: str,
    interval_s: float = 0.5,
) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval_s)
    raise AssertionError(f"timed out waiting for {description}")


class Session:
    def __init__(self, client_id: str) -> None:
        self.connected = threading.Event()
        self.subscribed = threading.Event()
        self.subscription_allowed = False
        self.messages: queue.Queue[mqtt.MQTTMessage] = queue.Queue()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv5,
        )
        self.client.username_pw_set(
            os.environ.get("GH_C06B2C_MQTT_USERNAME", "tester"),
            os.environ["GH_C06B2C_MQTT_PASSWORD"],
        )
        self.client.on_connect = self._on_connect
        self.client.on_subscribe = self._on_subscribe
        self.client.on_message = self._on_message

    def _on_connect(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            raise AssertionError(f"MQTT connection rejected: {reason_code}")
        self.connected.set()

    def _on_subscribe(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        _mid: int,
        reason_codes: list[mqtt.ReasonCode],
        _properties: mqtt.Properties | None,
    ) -> None:
        self.subscription_allowed = bool(reason_codes) and all(
            not reason_code.is_failure for reason_code in reason_codes
        )
        self.subscribed.set()

    def _on_message(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        self.messages.put(message)

    def start(self) -> None:
        self.client.connect(BROKER, PORT, keepalive=30)
        self.client.loop_start()
        if not self.connected.wait(10):
            raise AssertionError("MQTT connection timed out")

    def subscribe(self, topics: tuple[str, ...]) -> None:
        self.subscribed.clear()
        result, _mid = self.client.subscribe([(topic, 1) for topic in topics])
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise AssertionError("MQTT subscribe call failed")
        if not self.subscribed.wait(10) or not self.subscription_allowed:
            raise AssertionError("MQTT subscription was not acknowledged")

    def publish(
        self,
        topic: str,
        document: dict[str, Any],
        *,
        retain: bool,
    ) -> None:
        info = self.client.publish(
            topic,
            canonical_json(document).encode("utf-8"),
            qos=1,
            retain=retain,
        )
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise AssertionError(f"MQTT publish failed for {topic}")
        info.wait_for_publish(timeout=10)
        if not info.is_published():
            raise AssertionError(f"MQTT PUBACK timed out for {topic}")

    def result_for(self, request_id: str, *, timeout_s: float = 30.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                message = self.messages.get(
                    timeout=max(0.1, deadline - time.monotonic())
                )
            except queue.Empty:
                break
            if message.topic != RESULT_TOPIC:
                continue
            try:
                document = json.loads(bytes(message.payload).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(document, dict) and document.get("request_id") == request_id:
                document["_qos"] = message.qos
                document["_retain"] = bool(message.retain)
                return document
        raise AssertionError(f"timed out waiting for result {request_id}")

    def close(self) -> None:
        try:
            self.client.disconnect()
        finally:
            self.client.loop_stop()


def runtime_ready() -> bool:
    probe = read_json(PROBE_PATH)
    return bool(
        probe.get("ready") is True
        and probe.get("runtime_loaded") is True
        and probe.get("runtime_enabled") is True
        and probe.get("mqtt_bridge_active") is True
        and probe.get("recorder_write_active") is True
    )


def probe_ready(*, expected_revision: int | None = None) -> bool:
    probe = read_json(PROBE_PATH)
    if not (
        probe.get("ready") is True
        and probe.get("runtime_loaded") is True
        and probe.get("runtime_enabled") is True
        and probe.get("mqtt_bridge_active") is True
        and probe.get("recorder_write_active") is True
    ):
        return False
    entities = probe.get("entities")
    if not isinstance(entities, dict) or set(entities) != set(EXPECTED_UNIQUE_IDS):
        return False
    for unique_id, (unit, _device_class, _value) in EXPECTED_UNIQUE_IDS.items():
        entity = entities.get(unique_id)
        if not isinstance(entity, dict):
            return False
        if (
            entity.get("platform") != "mqtt"
            or entity.get("disabled") is not False
            or entity.get("unit_of_measurement") != unit
            or entity.get("state_class") != "measurement"
        ):
            return False
    if expected_revision is not None:
        entry = probe.get("ledger_entries", {}).get(IDEMPOTENCY_KEY)
        if not isinstance(entry, dict):
            return False
        if entry.get("state") != "verified" or entry.get("revision") != expected_revision:
            return False
    return True


def expected_statistics(probe: dict[str, Any], values: dict[str, float]) -> bool:
    statistics = probe.get("statistics")
    entities = probe.get("entities")
    if not isinstance(statistics, dict) or not isinstance(entities, dict):
        return False
    for unique_id, expected in values.items():
        entity = entities.get(unique_id)
        if not isinstance(entity, dict):
            return False
        entity_id = entity.get("entity_id")
        row = statistics.get(entity_id)
        if not isinstance(row, dict):
            return False
        if (
            row.get("start") != SAMPLE_HOUR
            or row.get("unit_of_measurement") != EXPECTED_UNIQUE_IDS[unique_id][0]
            or row.get("mean") != expected
            or row.get("min") != expected
            or row.get("max") != expected
        ):
            return False
    return True


def expected_statistic_triplets(
    probe: dict[str, Any],
    values: dict[str, tuple[float, float, float]],
) -> bool:
    statistics = probe.get("statistics")
    entities = probe.get("entities")
    if not isinstance(statistics, dict) or not isinstance(entities, dict):
        return False
    for unique_id, (mean, minimum, maximum) in values.items():
        entity = entities.get(unique_id)
        if not isinstance(entity, dict):
            return False
        row = statistics.get(entity.get("entity_id"))
        if not isinstance(row, dict):
            return False
        if (
            row.get("start") != SAMPLE_HOUR
            or row.get("unit_of_measurement") != EXPECTED_UNIQUE_IDS[unique_id][0]
            or row.get("mean") != mean
            or row.get("min") != minimum
            or row.get("max") != maximum
        ):
            return False
    return True


def discovery_document(
    *,
    name: str,
    unique_id: str,
    state_topic: str,
    unit: str,
    device_class: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "unique_id": unique_id,
        "state_topic": state_topic,
        "unit_of_measurement": unit,
        "device_class": device_class,
        "state_class": "measurement",
        "value_template": "{{ value_json.value }}",
        "device": {
            "identifiers": ["c06b2c-node-0001"],
            "name": "C06-B2C Node 0001",
            "manufacturer": "C06-B2C isolated lab",
            "model": "virtual-mqtt-sensor",
        },
    }


def phase_prepare() -> None:
    wait_until(runtime_ready, timeout_s=120, description="Home Assistant C06-B2 runtime")
    session = Session("c06b2c-prepare")
    session.start()
    try:
        for unique_id, (unit, device_class, value) in EXPECTED_UNIQUE_IDS.items():
            state_topic = f"c06b2c/state/{unique_id}"
            session.publish(
                f"homeassistant/sensor/{unique_id}/config",
                discovery_document(
                    name=(
                        "C06-B2C Air Temperature"
                        if unique_id.endswith("air_temperature_c")
                        else "C06-B2C Air Humidity"
                    ),
                    unique_id=unique_id,
                    state_topic=state_topic,
                    unit=unit,
                    device_class=device_class,
                ),
                retain=True,
            )
            session.publish(state_topic, {"value": value}, retain=True)
        wait_until(probe_ready, timeout_s=90, description="MQTT target entities")
        probe = read_json(PROBE_PATH)
        write_json(
            "prepare.json",
            {
                "schema": "gh.c06b2c.prepare/1",
                "boot_token": probe.get("boot_token"),
                "runtime_loaded": probe.get("runtime_loaded"),
                "runtime_enabled": probe.get("runtime_enabled"),
                "mqtt_bridge_active": probe.get("mqtt_bridge_active"),
                "recorder_write_active": probe.get("recorder_write_active"),
                "entity_unique_ids": sorted(probe.get("entities", {})),
                "mqtt_discovery_used": True,
                "production_state_modified": False,
                "secret_values_included": False,
            },
        )
    finally:
        session.close()


def message_summary(message: mqtt.MQTTMessage) -> dict[str, Any]:
    document = json.loads(bytes(message.payload).decode("utf-8"))
    if not isinstance(document, dict):
        raise TypeError("captured MQTT payload is not an object")
    projection = document.get("projection")
    return {
        "topic": message.topic,
        "qos": message.qos,
        "retain": bool(message.retain),
        "payload_bytes": len(message.payload),
        "schema": document.get("schema"),
        "request_id": document.get("request_id"),
        "status": document.get("status"),
        "code": document.get("code"),
        "detail": document.get("detail"),
        "idempotency_key": (
            document.get("idempotency_key")
            if projection is None
            else projection.get("idempotency_key")
        ),
        "revision": (
            document.get("revision")
            if projection is None
            else projection.get("revision")
        ),
        "projection_hash": document.get("projection_hash"),
    }


def phase_observer() -> None:
    session = Session("c06b2c-observer")
    session.start()
    try:
        session.subscribe((REQUEST_TOPIC, RESULT_TOPIC))
        write_json(
            "observer-ready.json",
            {
                "schema": "gh.c06b2c.observer-ready/1",
                "subscribed": True,
                "topics": [REQUEST_TOPIC, RESULT_TOPIC],
                "secret_values_included": False,
            },
        )
        captured: dict[str, dict[str, Any]] = {}
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and set(captured) != {"request", "result"}:
            try:
                message = session.messages.get(
                    timeout=max(0.1, deadline - time.monotonic())
                )
            except queue.Empty:
                break
            if message.topic == REQUEST_TOPIC and "request" not in captured:
                captured["request"] = message_summary(message)
            elif message.topic == RESULT_TOPIC and "result" not in captured:
                captured["result"] = message_summary(message)
        if set(captured) != {"request", "result"}:
            raise AssertionError("did not capture the initial request and result")
        if captured["request"]["request_id"] != captured["result"]["request_id"]:
            raise AssertionError("captured result is not bound to captured request")
        write_json(
            "mqtt-capture.json",
            {
                "schema": "gh.c06b2c.mqtt-capture/2",
                **captured,
                "secret_values_included": False,
                "production_broker_accessed": False,
            },
        )
    finally:
        session.close()


def completed_job() -> tuple[dict[str, Any], str, int]:
    with ProjectionStore(DATABASE) as store:
        job = store.get_job(NODE_ID, SAMPLE_HOUR)
        if job is None or job.state != "completed":
            raise AssertionError("Manager projection job is not completed")
        if job.payload_json is None or job.projection_hash is None:
            raise AssertionError("completed Manager job lacks projection evidence")
        projection = json.loads(job.payload_json)
        if not isinstance(projection, dict):
            raise TypeError("completed projection payload is invalid")
        return projection, job.projection_hash, job.revision


def phase_initial() -> None:
    wait_until(
        _job_is_completed,
        timeout_s=120,
        description="Manager projection completion",
    )
    wait_until(
        lambda: (
            probe_ready(expected_revision=1)
            and expected_statistics(
                read_json(PROBE_PATH),
                {
                    "node-0001_air_temperature_c": 25.0,
                    "node-0001_air_humidity_pct": 65.0,
                },
            )
        ),
        timeout_s=120,
        description="Recorder exact readback and verified ledger",
    )
    projection, digest, revision = completed_job()
    capture = read_json(EVIDENCE / "mqtt-capture.json")
    request = capture.get("request", {})
    result = capture.get("result", {})
    if request.get("qos") != 1 or request.get("retain") is not False:
        raise AssertionError("initial request did not use QoS 1 retain=false")
    if result.get("qos") != 1 or result.get("retain") is not False:
        raise AssertionError("initial result did not use QoS 1 retain=false")
    if result.get("status") != "verified":
        raise AssertionError("initial result was not verified")
    if request.get("projection_hash") != digest or result.get("projection_hash") != digest:
        raise AssertionError("initial MQTT capture does not bind completed projection")
    probe = read_json(PROBE_PATH)
    write_json(
        "initial.json",
        {
            "schema": "gh.c06b2c.initial-closure/1",
            "boot_token": probe.get("boot_token"),
            "manager_job_state": "completed",
            "manager_revision": revision,
            "manager_projection_hash": digest,
            "projection_series_count": len(projection.get("series", [])),
            "target_ledger_state": "verified",
            "recorder_readback_exact": True,
            "request_qos": request.get("qos"),
            "request_retain": request.get("retain"),
            "result_qos": result.get("qos"),
            "result_retain": result.get("retain"),
            "result_status": result.get("status"),
            "direct_home_assistant_database_read": False,
            "direct_home_assistant_database_write": False,
            "production_state_modified": False,
            "secret_values_included": False,
        },
    )


def _job_is_completed() -> bool:
    try:
        with ProjectionStore(DATABASE) as store:
            job = store.get_job(NODE_ID, SAMPLE_HOUR)
            return bool(job and job.state == "completed")
    except (OSError, RuntimeError, ValueError, sqlite3.Error):
        return False


def request_document(projection: dict[str, Any], request_id: str) -> dict[str, Any]:
    return {
        "schema": "gh.c06b2-ha-projection-request/1",
        "request_id": request_id,
        "system_id": SYSTEM_ID,
        "sent_at": datetime.now(UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "projection_hash": projection_hash(projection),
        "projection": projection,
    }


def dispatch_direct(
    session: Session,
    projection: dict[str, Any],
    request_id: str,
) -> dict[str, Any]:
    session.publish(
        REQUEST_TOPIC,
        request_document(projection, request_id),
        retain=False,
    )
    result = session.result_for(request_id)
    if result.get("_qos") != 1 or result.get("_retain") is not False:
        raise AssertionError("direct result did not use QoS 1 retain=false")
    return result


def result_evidence(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": result.get("request_id"),
        "status": result.get("status"),
        "code": result.get("code"),
        "detail": result.get("detail"),
        "idempotency_key": result.get("idempotency_key"),
        "revision": result.get("revision"),
        "projection_hash": result.get("projection_hash"),
        "qos": result.get("_qos"),
        "retain": result.get("_retain"),
    }


def write_monotonic_attempt(attempts: dict[str, Any]) -> None:
    write_json(
        "monotonic-attempt.json",
        {
            "schema": "gh.c06b2c.monotonic-attempt/1",
            "attempts": attempts,
            "direct_home_assistant_database_read": False,
            "direct_home_assistant_database_write": False,
            "production_state_modified": False,
            "secret_values_included": False,
        },
    )


def dispatch_recorded(
    session: Session,
    projection: dict[str, Any],
    request_id: str,
    label: str,
    attempts: dict[str, Any],
) -> dict[str, Any]:
    try:
        result = dispatch_direct(session, projection, request_id)
    except Exception as exc:
        attempts[label] = {
            "request_id": request_id,
            "exception_class": type(exc).__name__,
            "exception_detail": str(exc)[:512],
        }
        write_monotonic_attempt(attempts)
        raise
    attempts[label] = result_evidence(result)
    write_monotonic_attempt(attempts)
    return result


def revision_two_projection(original: dict[str, Any]) -> dict[str, Any]:
    projection = copy.deepcopy(original)
    projection["revision"] = 2
    for item in projection["series"]:
        if item["measurement_key"] == "air_temperature_c":
            item["mean"] = item["min"] = item["max"] = 26.0
        elif item["measurement_key"] == "air_humidity_pct":
            item["mean"] = item["min"] = item["max"] = 66.0
    return projection


def phase_fault_seed() -> None:
    record = {
        "boot_id": "boot-00000001",
        "seq": 2,
        "uptime_ms": 2000,
        "sampled_at": "2026-08-03T04:30:00Z",
        "time_quality": "trusted",
        "time_anchor": None,
        "cap_hash": "cap-hash-0001",
        "fw_version": "1.0.0",
        "measurements": {
            "air_temperature_c": 27.0,
            "air_humidity_pct": 67.0,
        },
        "quality": {
            "air_temperature_c": "ok",
            "air_humidity_pct": "ok",
        },
        "power": {"source": "battery", "battery_v": 3.9, "low": False},
    }
    batch_id = "c06-fault-batch-0002"
    with HistoryStore(DATABASE) as history:
        result = history.commit_page(
            node_id=NODE_ID,
            batch_id=batch_id,
            page_index=0,
            page_count=1,
            records=[record],
            payload_sha256=hashlib.sha256(batch_id.encode()).hexdigest(),
            received_at=datetime(2026, 8, 3, 4, 40, tzinfo=UTC),
        )
    with ProjectionStore(DATABASE) as store:
        job = store.get_job(NODE_ID, SAMPLE_HOUR)
        write_json(
            "fault-seed.json",
            {
                "schema": "gh.c06-history-fault-seed/1",
                "commit_status": result.status,
                "revision": job.revision if job is not None else None,
                "state": job.state if job is not None else None,
                "attempts": job.attempts if job is not None else None,
                "record_count": 2,
                "manager_stopped_before_seed": True,
                "production_state_modified": False,
                "secret_values_included": False,
            },
        )
        if (
            result.status != "accepted"
            or job is None
            or job.state != "pending"
            or job.revision != 2
            or job.attempts != 0
        ):
            raise AssertionError("fault revision was not durably seeded as pending")


def _retry_job() -> dict[str, Any] | None:
    try:
        with ProjectionStore(DATABASE) as store:
            job = store.get_job(NODE_ID, SAMPLE_HOUR)
            if job is None or job.state != "retry" or job.revision != 2:
                return None
            return {
                "revision": job.revision,
                "state": job.state,
                "attempts": job.attempts,
                "error_code": job.last_error_code,
                "next_attempt_recorded": job.next_attempt_at is not None,
            }
    except (OSError, RuntimeError, ValueError, sqlite3.Error):
        return None


def phase_fault_wait_retry() -> None:
    observed: dict[str, Any] = {}

    def retry_observed() -> bool:
        value = _retry_job()
        if value is None:
            return False
        observed.update(value)
        return True

    wait_until(
        retry_observed,
        timeout_s=120,
        description="Manager retry while Home Assistant is unavailable",
        interval_s=0.2,
    )
    if observed.get("attempts", 0) < 1:
        raise AssertionError("fault retry did not record an attempt")
    write_json(
        "fault-retry.json",
        {
            "schema": "gh.c06-history-fault-retry/1",
            **observed,
            "homeassistant_unavailable": True,
            "retry_fail_closed": True,
            "production_state_modified": False,
            "secret_values_included": False,
        },
    )


def phase_fault_recovery() -> None:
    wait_until(
        lambda: (
            _job_is_completed()
            and probe_ready(expected_revision=2)
            and expected_statistic_triplets(
                read_json(PROBE_PATH),
                {
                    "node-0001_air_temperature_c": (26.0, 25.0, 27.0),
                    "node-0001_air_humidity_pct": (66.0, 65.0, 67.0),
                },
            )
        ),
        timeout_s=180,
        description="durable Manager and Home Assistant fault recovery",
    )
    projection, digest, revision = completed_job()
    if revision != 2 or projection_hash(projection) != digest:
        raise AssertionError("recovered Manager tuple is inconsistent")
    write_json(
        "fault-recovery.json",
        {
            "schema": "gh.c06-history-fault-recovery/1",
            "revision": revision,
            "manager_job_state": "completed",
            "target_ledger_state": "verified",
            "recorder_readback_exact": True,
            "manager_restarted": True,
            "homeassistant_restarted": True,
            "durable_retry_reconciled": True,
            "projection_hash_recorded": bool(digest),
            "direct_home_assistant_database_read": False,
            "direct_home_assistant_database_write": False,
            "production_state_modified": False,
            "secret_values_included": False,
        },
    )


def phase_fault_broker_restart() -> None:
    wait_until(runtime_ready, timeout_s=120, description="runtime after Broker restart")
    projection, digest, revision = completed_job()
    session = Session("c06-fault-broker-restart")
    session.start()
    try:
        session.subscribe((RESULT_TOPIC,))
        result = dispatch_direct(
            session,
            projection,
            "c06-fault-broker-restart-idempotent-0001",
        )
        if (
            result.get("status") != "verified"
            or result.get("revision") != revision
            or result.get("projection_hash") != digest
        ):
            raise AssertionError("Broker restart idempotent reconciliation failed")
        write_json(
            "fault-broker-restart.json",
            {
                "schema": "gh.c06-history-fault-broker-restart/1",
                "broker_restarted": True,
                "mqtt_clients_reconnected": True,
                "same_revision_idempotent_status": result.get("status"),
                "revision": result.get("revision"),
                "projection_hash_exact": result.get("projection_hash") == digest,
                "result_qos": result.get("_qos"),
                "result_retain": result.get("_retain"),
                "production_state_modified": False,
                "secret_values_included": False,
            },
        )
    finally:
        session.close()


def phase_monotonic() -> None:
    original, original_hash, original_revision = completed_job()
    if original_revision != 1 or projection_hash(original) != original_hash:
        raise AssertionError("completed Manager projection tuple is inconsistent")
    session = Session("c06b2c-monotonic")
    session.start()
    attempts: dict[str, Any] = {}
    write_monotonic_attempt(attempts)
    try:
        session.subscribe((RESULT_TOPIC,))
        idempotent = dispatch_recorded(
            session,
            original,
            "c06b2c-idempotent-0001",
            "idempotent",
            attempts,
        )
        if idempotent.get("status") != "verified":
            raise AssertionError("same revision and hash was not idempotently verified")

        higher = revision_two_projection(original)
        higher_hash = projection_hash(higher)
        higher_result = dispatch_recorded(
            session,
            higher,
            "c06b2c-higher-revision-0001",
            "higher_revision",
            attempts,
        )
        if higher_result.get("status") != "verified":
            raise AssertionError("higher revision was not verified")
        wait_until(
            lambda: (
                probe_ready(expected_revision=2)
                and expected_statistics(
                    read_json(PROBE_PATH),
                    {
                        "node-0001_air_temperature_c": 26.0,
                        "node-0001_air_humidity_pct": 66.0,
                    },
                )
            ),
            timeout_s=90,
            description="higher revision Recorder replacement",
        )

        lower = dispatch_recorded(
            session,
            original,
            "c06b2c-lower-revision-0001",
            "lower_revision",
            attempts,
        )
        if (
            lower.get("status") != "blocked"
            or lower.get("code") != "target_newer_revision"
        ):
            raise AssertionError("lower revision was not blocked by target ledger")

        conflict_projection = copy.deepcopy(higher)
        for item in conflict_projection["series"]:
            if item["measurement_key"] == "air_temperature_c":
                item["mean"] = item["min"] = item["max"] = 27.0
        conflict = dispatch_recorded(
            session,
            conflict_projection,
            "c06b2c-same-revision-conflict-0001",
            "same_revision_conflict",
            attempts,
        )
        if (
            conflict.get("status") != "blocked"
            or conflict.get("code") != "target_same_revision_hash_conflict"
        ):
            raise AssertionError("same revision hash conflict was not blocked")

        probe = read_json(PROBE_PATH)
        write_json(
            "monotonic.json",
            {
                "schema": "gh.c06b2c.monotonic-closure/1",
                "boot_token": probe.get("boot_token"),
                "idempotent_status": idempotent.get("status"),
                "higher_revision_status": higher_result.get("status"),
                "higher_revision": 2,
                "higher_projection_hash": higher_hash,
                "higher_readback_exact": True,
                "lower_revision_status": lower.get("status"),
                "lower_revision_code": lower.get("code"),
                "same_revision_conflict_status": conflict.get("status"),
                "same_revision_conflict_code": conflict.get("code"),
                "direct_home_assistant_database_read": False,
                "direct_home_assistant_database_write": False,
                "production_state_modified": False,
                "secret_values_included": False,
            },
        )
    finally:
        session.close()


def phase_restart() -> None:
    initial = read_json(EVIDENCE / "monotonic.json")
    old_boot_token = initial.get("boot_token")
    wait_until(
        lambda: (
            probe_ready(expected_revision=2)
            and read_json(PROBE_PATH).get("boot_token") not in {None, old_boot_token}
            and expected_statistics(
                read_json(PROBE_PATH),
                {
                    "node-0001_air_temperature_c": 26.0,
                    "node-0001_air_humidity_pct": 66.0,
                },
            )
        ),
        timeout_s=150,
        description="Home Assistant restart persistence",
    )
    original, _digest, _revision = completed_job()
    higher = revision_two_projection(original)
    session = Session("c06b2c-restart")
    session.start()
    try:
        session.subscribe((RESULT_TOPIC,))
        result = dispatch_direct(
            session,
            higher,
            "c06b2c-restart-idempotent-0001",
        )
        if result.get("status") != "verified":
            raise AssertionError("restart idempotent request was not verified")
        probe = read_json(PROBE_PATH)
        write_json(
            "restart.json",
            {
                "schema": "gh.c06b2c.restart-closure/1",
                "old_boot_token": old_boot_token,
                "new_boot_token": probe.get("boot_token"),
                "homeassistant_restarted": True,
                "target_ledger_reloaded": True,
                "recorder_statistics_persisted": True,
                "same_revision_idempotent_status": result.get("status"),
                "duplicate_entity_created": False,
                "second_external_statistic_created": False,
                "direct_home_assistant_database_read": False,
                "direct_home_assistant_database_write": False,
                "production_state_modified": False,
                "secret_values_included": False,
            },
        )
    finally:
        session.close()


def main() -> None:
    phase = os.environ.get("GH_C06B2C_PHASE", "").strip().lower()
    phases: dict[str, Callable[[], None]] = {
        "prepare": phase_prepare,
        "observer": phase_observer,
        "initial": phase_initial,
        "monotonic": phase_monotonic,
        "restart": phase_restart,
        "fault-seed": phase_fault_seed,
        "fault-wait-retry": phase_fault_wait_retry,
        "fault-recovery": phase_fault_recovery,
        "fault-broker-restart": phase_fault_broker_restart,
    }
    action = phases.get(phase)
    if action is None:
        raise SystemExit(f"unsupported GH_C06B2C_PHASE: {phase}")
    action()


if __name__ == "__main__":
    main()
