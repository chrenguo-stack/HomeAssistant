from __future__ import annotations

import queue
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from .history_replay import HistoryReplayProcessor, HistoryReplayResult

HistorySubmitStatus = Literal["queued", "queue_full", "rate_limited"]


@dataclass(frozen=True, slots=True)
class HistoryWorkItem:
    node_id: str
    topic: str
    payload: bytes
    retained: bool
    node_allowed: bool
    received_at: datetime


class HistoryReplayWorker:
    """Bounded host worker that keeps historical SQLite work off the MQTT callback."""

    def __init__(
        self,
        *,
        processor: HistoryReplayProcessor,
        on_result: Callable[[HistoryReplayResult], None],
        queue_capacity: int = 64,
        max_pages_per_minute: int = 60,
        prune_interval_s: int = 300,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not 1 <= queue_capacity <= 1_024:
            raise ValueError("queue_capacity must be between 1 and 1024")
        if not 1 <= max_pages_per_minute <= 600:
            raise ValueError("max_pages_per_minute must be between 1 and 600")
        if not 30 <= prune_interval_s <= 86_400:
            raise ValueError("prune_interval_s must be between 30 and 86400")
        self.processor = processor
        self.on_result = on_result
        self.max_pages_per_minute = max_pages_per_minute
        self.prune_interval_s = prune_interval_s
        self._monotonic = monotonic
        self._queue: queue.Queue[HistoryWorkItem] = queue.Queue(maxsize=queue_capacity)
        self._rate_lock = threading.Lock()
        self._recent: dict[str, deque[float]] = defaultdict(deque)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._next_prune = self._monotonic() + self.prune_interval_s

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()

    def submit(self, item: HistoryWorkItem) -> HistorySubmitStatus:
        now = self._monotonic()
        with self._rate_lock:
            recent = self._recent[item.node_id]
            cutoff = now - 60.0
            while recent and recent[0] <= cutoff:
                recent.popleft()
            if len(recent) >= self.max_pages_per_minute:
                return "rate_limited"
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                return "queue_full"
            recent.append(now)
            return "queued"

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
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
        if self._thread is not None:
            self._thread.join(timeout=timeout)
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

    def _process(self, item: HistoryWorkItem) -> HistoryReplayResult:
        result = self.processor.process(
            item.topic,
            item.payload,
            retained=item.retained,
            node_allowed=item.node_allowed,
            received_at=item.received_at,
        )
        self.on_result(result)
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
        pruned = self.processor.store.prune(now=now or datetime.now(UTC))
        self._next_prune = current + self.prune_interval_s
        return pruned
