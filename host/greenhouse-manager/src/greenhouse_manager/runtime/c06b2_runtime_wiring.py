from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass

from .c06b2_mqtt_rpc_adapter import (
    MqttProjectionRpcAdapter,
    PahoProjectionRpcTransport,
)
from .config import Settings
from .history_projection_runner import ProjectionRunner
from .history_projection_store import ProjectionStore
from .mqtt_service import ManagerMqttService

_LOGGER = logging.getLogger(__name__)
_MANAGER_RUNTIME_ENV = "GH_C06B2_RUNTIME_ENABLED"


def manager_c06b2_runtime_enabled() -> bool:
    """Return the explicit Manager runtime switch; disabled is the frozen default."""

    raw = os.getenv(_MANAGER_RUNTIME_ENV)
    if raw is None:
        return False
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{_MANAGER_RUNTIME_ENV} must be a boolean value")


@dataclass(slots=True)
class ProjectionRuntimeHealth:
    iteration_count: int = 0
    completed_count: int = 0
    retry_count: int = 0
    blocked_count: int = 0
    stale_count: int = 0
    failure_count: int = 0
    last_failure_type: str | None = None


class ManagerProjectionRuntimeWorker:
    """One background ProjectionRunner loop, active only after explicit opt-in."""

    def __init__(
        self,
        *,
        runner: ProjectionRunner,
        close_callback: Callable[[], None],
        idle_sleep_seconds: float = 2.0,
        error_sleep_seconds: float = 5.0,
    ) -> None:
        if idle_sleep_seconds <= 0 or error_sleep_seconds <= 0:
            raise ValueError("worker sleep intervals must be positive")
        self.runner = runner
        self._close_callback = close_callback
        self._idle_sleep_seconds = idle_sleep_seconds
        self._error_sleep_seconds = error_sleep_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.health = ProjectionRuntimeHealth()

    @property
    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.is_alive:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="c06b2-projection-runtime",
            daemon=True,
        )
        self._thread.start()

    def _sleep(self, seconds: float) -> None:
        self._stop.wait(seconds)

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    result = self.runner.run_once()
                    self.health.iteration_count += 1
                    if result.status == "completed":
                        self.health.completed_count += 1
                    elif result.status == "retry":
                        self.health.retry_count += 1
                    elif result.status == "blocked":
                        self.health.blocked_count += 1
                    elif result.status == "stale":
                        self.health.stale_count += 1
                    if result.status == "idle":
                        self._sleep(self._idle_sleep_seconds)
                except Exception as exc:  # noqa: BLE001 - keep durable jobs retryable
                    self.health.failure_count += 1
                    self.health.last_failure_type = type(exc).__name__
                    _LOGGER.exception("C06-B2 projection worker iteration failed")
                    self._sleep(self._error_sleep_seconds)
        finally:
            self._close_callback()

    def stop(self, timeout: float = 15.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout)
        if thread is not None and thread.is_alive():
            _LOGGER.error("C06-B2 projection worker did not stop within timeout")


def _build_projection_worker(settings: Settings) -> ManagerProjectionRuntimeWorker:
    store = ProjectionStore(settings.history_db_path)
    transport = PahoProjectionRpcTransport(
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        client_id=f"{settings.mqtt_client_id}-c06b2",
        result_topic=(
            f"gh/v1/{settings.system_id}/ingress/homeassistant/history/projection/result"
        ),
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        tls_enabled=settings.mqtt_tls,
        ca_file=settings.mqtt_ca_file,
    )
    adapter = MqttProjectionRpcAdapter(
        system_id=settings.system_id,
        transport=transport,
        timeout_seconds=25.0,
    )
    runner = ProjectionRunner(
        store=store,
        adapter=adapter,
        worker_id=f"{settings.mqtt_client_id}-c06b2",
        lease_seconds=45,
        adapter_timeout_seconds=30,
    )

    closed = False
    close_lock = threading.Lock()

    def close() -> None:
        nonlocal closed
        with close_lock:
            if closed:
                return
            closed = True
        try:
            adapter.stop()
        finally:
            store.close()

    return ManagerProjectionRuntimeWorker(runner=runner, close_callback=close)


def run_manager_service(
    settings: Settings,
    *,
    service_factory: Callable[[Settings], ManagerMqttService] = ManagerMqttService,
    worker_factory: Callable[[Settings], ManagerProjectionRuntimeWorker] = _build_projection_worker,
) -> None:
    """Run the existing Manager, with C06-B2B wiring disabled unless explicitly enabled."""

    service = service_factory(settings)
    if not manager_c06b2_runtime_enabled():
        service.run()
        return

    worker = worker_factory(settings)
    _LOGGER.warning(
        "C06-B2 Manager runtime explicitly enabled system_id=%s",
        settings.system_id,
    )
    worker.start()
    try:
        service.run()
    finally:
        worker.stop()
