"""
telemetry/collector.py
Bridges the simulation engine callbacks → TelemetryDB.
Also maintains an in-memory rolling buffer for the live dashboard.
"""
from __future__ import annotations
import threading
from collections import deque
from core.task import Task
from telemetry.database import TelemetryDB


class TelemetryCollector:
    """
    Thread-safe collector that:
    - Receives task-complete callbacks from the simulation engine
    - Receives periodic node snapshot callbacks
    - Persists records to SQLite via TelemetryDB
    - Maintains rolling in-memory buffers for the live dashboard
    """

    BUFFER_SIZE = 1000   # max in-memory records

    def __init__(
        self,
        db       : TelemetryDB,
        scenario : str = "default",
        run_id   : str = "",
        strategy : str = "adaptive",
    ) -> None:
        self.db       = db
        self.scenario = scenario
        self.run_id   = run_id
        self.strategy = strategy
        self._lock    = threading.Lock()

        # In-memory rolling buffers (for dashboard)
        self.task_buffer     : deque[dict] = deque(maxlen=self.BUFFER_SIZE)
        self.snapshot_buffer : deque[dict] = deque(maxlen=self.BUFFER_SIZE)

        # Live KPI accumulators
        self._latencies   : list[float] = []
        self._sla_violated: int = 0
        self._total_tasks : int = 0
        self._completed   : int = 0
        self._dropped     : int = 0

    # ------------------------------------------------------------------
    # Callbacks (called by SimulationEngine)
    # ------------------------------------------------------------------

    def on_task_complete(self, task: Task) -> None:
        """Called for every task that finishes (completed or dropped)."""
        with self._lock:
            self.db.insert_task(task, self.scenario, self.run_id)
            self.task_buffer.append(task.to_dict())
            self._total_tasks += 1

            if task.status.value == "completed":
                self._completed += 1
                self._latencies.append(task.total_latency_ms)
                if task.sla_violated:
                    self._sla_violated += 1
            elif task.status.value == "dropped":
                self._dropped += 1

    def on_snapshot(self, snapshot: dict) -> None:
        """Called every 0.5 sim-seconds with node state."""
        with self._lock:
            self.db.insert_snapshot(snapshot, self.strategy, self.scenario, self.run_id)
            self.snapshot_buffer.append(snapshot)

    # ------------------------------------------------------------------
    # Live KPIs (read by dashboard without DB round-trip)
    # ------------------------------------------------------------------

    def live_kpis(self) -> dict:
        import numpy as np
        with self._lock:
            lats = self._latencies.copy()
        return {
            "total_tasks"     : self._total_tasks,
            "completed"       : self._completed,
            "dropped"         : self._dropped,
            "sla_violated"    : self._sla_violated,
            "avg_latency_ms"  : round(float(np.mean(lats)), 2)  if lats else 0,
            "p95_latency_ms"  : round(float(np.percentile(lats, 95)), 2) if lats else 0,
            "completion_rate" : round(self._completed / max(self._total_tasks, 1), 4),
            "sla_violation_rate": round(self._sla_violated / max(self._completed, 1), 4),
        }

    def latest_snapshots(self, n: int = 60) -> list[dict]:
        """Return last n snapshots for dashboard time-series charts."""
        with self._lock:
            return list(self.snapshot_buffer)[-n:]

    def latest_tasks(self, n: int = 50) -> list[dict]:
        with self._lock:
            return list(self.task_buffer)[-n:]
