"""In-process worker queue / job metrics (exportable to sample dashboards)."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class QueueMetrics:
    enqueued: int = 0
    started: int = 0
    succeeded: int = 0
    failed: int = 0
    dead_lettered: int = 0
    recovered: int = 0
    depth_estimate: int = 0


class WorkerMetrics:
    """Process-local counters — suitable for offline tests and sample dashboards."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_queue: dict[str, QueueMetrics] = {}

    def _q(self, queue: str) -> QueueMetrics:
        if queue not in self._by_queue:
            self._by_queue[queue] = QueueMetrics()
        return self._by_queue[queue]

    def record_enqueue(self, queue: str = "default") -> None:
        with self._lock:
            q = self._q(queue)
            q.enqueued += 1
            q.depth_estimate += 1

    def record_start(self, queue: str = "default") -> None:
        with self._lock:
            q = self._q(queue)
            q.started += 1
            q.depth_estimate = max(0, q.depth_estimate - 1)

    def record_success(self, queue: str = "default") -> None:
        with self._lock:
            self._q(queue).succeeded += 1

    def record_failure(self, queue: str = "default") -> None:
        with self._lock:
            self._q(queue).failed += 1

    def record_dead_letter(self, queue: str = "default") -> None:
        with self._lock:
            self._q(queue).dead_lettered += 1

    def record_recovery(self, queue: str = "default") -> None:
        with self._lock:
            self._q(queue).recovered += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {name: asdict(m) for name, m in self._by_queue.items()}

    def reset(self) -> None:
        with self._lock:
            self._by_queue.clear()


_metrics = WorkerMetrics()


def get_worker_metrics() -> WorkerMetrics:
    return _metrics
