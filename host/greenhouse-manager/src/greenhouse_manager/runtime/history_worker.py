from __future__ import annotations

import logging
import queue
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from .history_replay import HistoryReplayProcessor, HistoryReplayResult

_LOGGER = logging.getLogger(__name__)

HistorySubmitStatus = Literal[
    "queued",
    "queue_full",
    "rate_limited",
    "rate_state_full",
]


@dataclass(frozen=True, slots=True)
class HistoryWorkItem:
    node_id: str
    topic: str
    payload: bytes
    retained: bool
    node_allowed: bool
    received_at: datetime


@dataclass(frozen=True, slots=True)
class HistoryWorkerHealth:
    running: bool
    failure_count: int
    last_failure_stage: str | None
    last_failure_type: str | None


@dataclass(slots=True)
class _RateState:
    recent: deque[float]
    last_seen: float


class HistoryReplayWorker:
    """Bounded host worker that keeps historical SQLite work off the MQTT callback."""

    def __init__(
        self,
        *,
        processor: HistoryReplayProcessor,
        on_result: Callable[[HistoryReplayResult], None],
        queue_capacity: int = 64,
        max_pages_per_minute: int = 60,
        rate_state_capacity: int = 1_024,
        rate_state_ttl_s: int = 3_600,
        prune_interval_s: int = 300,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not 1 <= queue_capacity <= 1_024:
            raise ValueError("queue_capacity must be between 1 and 1024")
        if not 1 <= max_pages_per_minute <= 600:
            raise ValueError("max_pages_per_minute must be between 1 and 600")
        if not 1 <= rate_state_capacity <= 65_536:
            raise ValueError("rate_state_capacity must be between 1 and 65536")
        if not 1 <= rate_state_ttl_s <= 86_400:
            raise ValueError("rate_state_ttl_s must be between 1 and 86400")
        if not 30 <= prune_interval_s <= 86_400:
            raise ValueError("prune_interval_s must be between 30 and 86400")
        self.processor = processor
        self.on_result = on_result
        self.max_pages_per_minute = max_pages_per_minute
        self.rate_state_capacity = rate_state_capacity
        self.rate_state_ttl_s = rate_state_ttl_s
        self.prune_interval_s = prune_interval_s
        self._monotonic = monotonic
        self._queue: queue.Queue[HistoryWorkItem] = queue.Queue(maxsize=queue_capacity)
        self._rate_lock = threading.Lock()
        self._rate_states: OrderedDict[str, _RateState] = OrderedDict()
        self._health_lock = threading.Lock()
        self._failure_count = 0
        self._last_failure_stage: str | None = None
        self._last_failure_type: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._next_prune = self._monotonic() + self.prune_interval_s

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()

    @property
    def rate_state_count(self) -> int:
        with self._rate_lock:
            return len(self._rate_states)

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def health(self) -> HistoryWorkerHealth:
        with self._health_lock:
            return HistoryWorkerHealth(
                running=self.is_alive,
                failure_count=self._failure_count,
                last_failure_stage=self._last_failure_stage,
                last_failure_type=self._last_failure_type,
            )

    def _record_failure(self, stage: str, error: Exception) -> None:
        with self._health_lock:
            self._failure_count += 1
            self._last_failure_stage = stage
            self._last_failure_type = type(error).__name__
        _LOGGER.error(
            "C-06 history worker failure stage=%s error=%s",
            stage,
            type(error).__name__,
            exc_info=True,
        )

    def _purge_rate_states_locked(self, now: float) -> None:
        cutoff = now - self.rate_state_ttl_s
        while self._rate_states:
            node_id, state = next(iter(self._rate_states.items()))
            if state.last_seen > cutoff:
                break
            del self._rate_states[node_id]

    def submit(self, item: HistoryWorkItem) -> HistorySubmitStatus:
        now = self._monotonic()
        with self._rate_lock:
            self._purge_rate_states_locked(now)
            state = self._rate_states.get(item.node_id)
            if state is not None:
                cutoff = now - 60.0
                while state.recent and state.recent[0] <= cutoff:
                    state.recent.popleft()
                if len(state.recent) >= self.max_pages_per_minute:
                    state.last_seen = now
                    self._rate_states.move_to_end(item.node_id)
                    return "rate_limited"
            elif len(self._rate_states) >= self.rate_state_capacity:
                return "rate_state_full"

            try:
                self._queue.put_nowait(item)
            except queue.Full:
                return "queue_full"

            if state is None:
                state = _RateState(recent=deque(), last_seen=now)
                self._rate_states[item.node_id] = state
            state.recent.append(now)
            state.last_seen = now
            self._rate_states.move_to_end(item.node_id)
            return "queued"

    def start(self) -> None:
        if self.is_alive:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="c06-history-worker",
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, timeout: float = 10.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is None:
            return
        thread.join(timeout=timeout)
        if not thread.is_alive():
            self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            timeout = max(0.1, min(1.0, self._next_prune - self._monotonic()))
            try:
                item = self._queue.get(timeout=timeout)
            except queue.Empty:
                self.run_maintenance()
                continue
            try:
                self._process(item)
            finally:
                self._queue.task_done()
            self.run_maintenance()

    def _dispatch_result(self, result: HistoryReplayResult) -> None:
        try:
            self.on_result(result)
        except Exception as error:
            self._record_failure("result_callback", error)

    def _process(self, item: HistoryWorkItem) -> HistoryReplayResult:
        try:
            result = self.processor.process(
                item.topic,
                item.payload,
                retained=item.retained,
                node_allowed=item.node_allowed,
                received_at=item.received_at,
            )
        except Exception as error:
            self._record_failure("page_processing", error)
            result = HistoryReplayResult(
                status="retry",
                node_id=item.node_id,
                reason=f"history worker processing failed: {type(error).__name__}",
            )
        self._dispatch_result(result)
        return result

    def process_one_for_test(self) -> HistoryReplayResult | None:
        try:
            item = self._queue.get_nowait()
        except queue.Empty:
            return None
        try:
            return self._process(item)
        finally:
            self._queue.task_done()

    def run_maintenance(
        self,
        *,
        now: datetime | None = None,
        force: bool = False,
    ) -> int:
        current = self._monotonic()
        if not force and current < self._next_prune:
            return 0
        self._next_prune = current + self.prune_interval_s
        try:
            return self.processor.store.prune(now=now or datetime.now(UTC))
        except Exception as error:
            self._record_failure("maintenance", error)
            return 0
