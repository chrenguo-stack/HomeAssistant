from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime
from typing import Any

from greenhouse_manager.runtime.c06b2_ha_projection_protocol import (
    build_projection_result,
    parse_projection_request,
    projection_hash,
    projection_result_topic,
)
from greenhouse_manager.runtime.c06b2_mqtt_rpc_adapter import MqttProjectionRpcAdapter
from greenhouse_manager.runtime.c06b2_runtime_wiring import ManagerProjectionRuntimeWorker
from greenhouse_manager.runtime.history_projection_contract import (
    ProjectionBatch,
    ProjectionRunResult,
)

SYSTEM = "sys_fault"
NODE = "node_fault"
HOUR = "2026-08-06T00:00:00Z"
NOW = datetime(2026, 8, 6, 0, 30, tzinfo=UTC)
MEASUREMENT_KEYS = (
    "air_temperature_c",
    "air_humidity_pct",
    "co2_ppm",
    "illuminance_lx",
    "soil_temperature_c",
    "soil_moisture_pct",
    "soil_ec_us_cm",
    "vpd_kpa",
    "dew_point_c",
    "absolute_humidity_g_m3",
    "ppfd_umol_m2_s",
    "battery_v",
    "battery_pct",
)


def projection(revision: int) -> dict[str, Any]:
    item = {
        "measurement_key": "air_temperature_c",
        "entity_unique_id": f"{NODE}_air_temperature_c",
        "name": "空气温度",
        "unit_of_measurement": "°C",
        "device_class": "temperature",
        "unit_class_hint": "temperature",
        "state_class": "measurement",
        "mean_type": "arithmetic",
        "has_sum": False,
        "samples": 1,
        "mean": 20.0,
        "min": 20.0,
        "max": 20.0,
    }
    return {
        "schema": "gh.c06-hourly-projection/1",
        "idempotency_key": f"{NODE}|{HOUR}|v1",
        "node_id": NODE,
        "sample_hour": HOUR,
        "projection_version": 1,
        "revision": revision,
        "algorithm_version": 2,
        "quality_policy": "ok-only/1",
        "source_record_count": 1,
        "source_set_sha256": "a" * 64,
        "eligible_record_count": 1,
        "skipped_time_quality": 0,
        "series": [item],
        "audit": {
            key: {
                "present": int(key == "air_temperature_c"),
                "accepted": int(key == "air_temperature_c"),
                "excluded_quality": 0,
                "invalid_or_null": 0,
                "missing": int(key != "air_temperature_c"),
            }
            for key in MEASUREMENT_KEYS
        },
    }


def batch(revision: int) -> ProjectionBatch:
    payload = projection(revision)
    return ProjectionBatch(
        NODE,
        HOUR,
        1,
        revision,
        projection_hash(payload),
        payload,
    )


class FaultTransport:
    def __init__(self) -> None:
        self.on_message: Any = None
        self.on_connect: Any = None
        self.on_disconnect: Any = None
        self.hook: Any = None
        self.published: list[bytes] = []

    def set_callbacks(self, *, on_message: Any, on_connect: Any, on_disconnect: Any) -> None:
        self.on_message = on_message
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect

    def start(self) -> None:
        self.on_connect()

    def publish(self, *, topic: str, payload: bytes, qos: int, retain: bool) -> bool:
        assert qos == 1 and retain is False
        self.published.append(payload)
        if self.hook is not None:
            self.hook(topic, payload)
        return True

    def stop(self) -> None:
        return

    def emit(self, payload: bytes, *, topic: str | None = None) -> None:
        self.on_message(topic or projection_result_topic(SYSTEM), payload)


def verified_result(payload: bytes) -> dict[str, Any]:
    request = parse_projection_request(payload, expected_system_id=SYSTEM)
    return build_projection_result(
        request=request,
        status="verified",
        monotonic_revision_enforced=True,
        verified_at=NOW,
    ).as_document()


def test_rpc_ignores_misbound_duplicate_and_late_results() -> None:
    transport = FaultTransport()
    adapter = MqttProjectionRpcAdapter(
        system_id=SYSTEM,
        transport=transport,
        timeout_seconds=0.03,
        request_id_factory=lambda: "fault_request_0001",
        clock=lambda: NOW,
    )

    def respond(_topic: str, payload: bytes) -> None:
        valid = verified_result(payload)
        for key, value in (
            ("request_id", "wrong_request_0001"),
            ("system_id", "wrong_system"),
            ("revision", 99),
            ("projection_hash", "b" * 64),
        ):
            mismatch = dict(valid)
            mismatch[key] = value
            transport.emit(json.dumps(mismatch, separators=(",", ":")).encode())
        encoded = json.dumps(valid, separators=(",", ":")).encode()
        transport.emit(encoded)
        transport.emit(encoded)

    transport.hook = respond
    result = adapter.dispatch(batch(1))
    assert result.status == "verified"
    assert adapter.ignored_result_count == 5

    transport.hook = None
    timeout = adapter.dispatch(batch(2))
    assert timeout.code == "mqtt_rpc_timeout"
    transport.emit(
        json.dumps(verified_result(transport.published[-1]), separators=(",", ":")).encode()
    )
    assert adapter.ignored_result_count == 6


def test_rpc_stop_unblocks_pending_request_and_allows_clean_restart() -> None:
    transport = FaultTransport()
    request_ids = iter(("fault_stop_00001", "fault_restart_0001"))
    adapter = MqttProjectionRpcAdapter(
        system_id=SYSTEM,
        transport=transport,
        timeout_seconds=1.0,
        request_id_factory=lambda: next(request_ids),
        clock=lambda: NOW,
    )
    output: list[Any] = []
    thread = threading.Thread(target=lambda: output.append(adapter.dispatch(batch(1))))
    thread.start()
    deadline = time.monotonic() + 1.0
    while not transport.published and time.monotonic() < deadline:
        time.sleep(0.001)
    assert transport.published
    adapter.stop()
    thread.join(1)
    assert not thread.is_alive()
    assert output[0].code == "mqtt_transport_stopped"

    transport.hook = lambda _topic, payload: transport.emit(
        json.dumps(verified_result(payload), separators=(",", ":")).encode()
    )
    assert adapter.dispatch(batch(2)).status == "verified"


def test_runtime_worker_isolates_iteration_failure_and_continues() -> None:
    completed = threading.Event()
    closed = threading.Event()

    class Runner:
        calls = 0

        def run_once(self) -> ProjectionRunResult:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("injected fault")
            if self.calls == 2:
                completed.set()
                return ProjectionRunResult(status="completed")
            return ProjectionRunResult(status="idle")

    runner = Runner()
    worker = ManagerProjectionRuntimeWorker(
        runner=runner,  # type: ignore[arg-type]
        close_callback=closed.set,
        idle_sleep_seconds=0.001,
        error_sleep_seconds=0.001,
    )
    worker.start()
    assert completed.wait(1)
    assert worker.is_alive
    worker.stop(1)
    assert closed.wait(1)
    assert worker.health.failure_count == 1
    assert worker.health.last_failure_type == "RuntimeError"
    assert worker.health.completed_count == 1
