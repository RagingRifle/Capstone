"""
core/node.py
Simulates an Edge or Cloud compute node.
Tracks CPU utilization, queue length, energy proxy, and processes tasks
using SimPy resources for realistic concurrency.
"""
from __future__ import annotations
import simpy
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.task import Task


class NodeType(str, Enum):
    EDGE  = "edge"
    CLOUD = "cloud"


@dataclass
class NodeConfig:
    node_id      : str
    node_type    : NodeType
    cpu_cores    : int   = 4
    cpu_speed_ghz: float = 2.5      # GHz — affects processing time
    ram_gb       : float = 8.0
    queue_limit  : int   = 50       # Max tasks in queue before dropping
    energy_per_ghz: float = 10.0   # Watts per GHz (proxy for energy cost)


class Node:
    """
    A simulated compute node (edge or cloud).

    Processing model
    ----------------
    processing_time_s = (complexity * BASE_CYCLES) / (cpu_speed_ghz * 1e9)
    where BASE_CYCLES = 1e8 cycles per complexity unit.

    Each CPU core is modelled as a SimPy Resource slot.
    """

    BASE_CYCLES = 1e8   # cycles per complexity unit

    def __init__(self, config: NodeConfig, env: simpy.Environment) -> None:
        self.config   = config
        self.env      = env
        self.node_id  = config.node_id
        self.node_type = config.node_type

        # SimPy resource — limits concurrency to cpu_cores
        self._resource = simpy.Resource(env, capacity=config.cpu_cores)

        # Telemetry counters
        self.tasks_completed : int   = 0
        self.tasks_dropped   : int   = 0
        self.tasks_failed    : int   = 0
        self.total_energy    : float = 0.0   # Watt-seconds (joules proxy)
        self._queue_length_history: list[tuple[float, int]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def queue_length(self) -> int:
        """Current number of tasks waiting or being processed."""
        return len(self._resource.queue) + self._resource.count

    @property
    def cpu_utilization(self) -> float:
        """Fraction of cores currently busy [0.0, 1.0]."""
        return self._resource.count / self.config.cpu_cores

    @property
    def is_overloaded(self) -> bool:
        return self.queue_length >= self.config.queue_limit

    def processing_time_s(self, task: "Task") -> float:
        """Compute how long this node takes to process the task (seconds)."""
        cycles = task.complexity * self.BASE_CYCLES
        speed  = self.config.cpu_speed_ghz * 1e9
        base   = cycles / speed
        # Add slight variability ±5%
        return base * random.uniform(0.95, 1.05)

    def execute(self, task: "Task") -> simpy.events.ProcessGenerator:
        """
        SimPy process: acquire a CPU core, execute, release.
        Updates task timing fields in-place.
        Returns when task is complete.
        """
        from core.task import TaskStatus

        if self.is_overloaded:
            task.status = TaskStatus.DROPPED
            self.tasks_dropped += 1
            return

        task.queued_at = self.env.now
        self._log_queue()

        with self._resource.request() as req:
            yield req
            task.started_at    = self.env.now
            task.assigned_node = self.node_id
            task.status        = TaskStatus.RUNNING

            proc_time = self.processing_time_s(task)
            yield self.env.timeout(proc_time)

            task.completed_at = self.env.now
            task.status       = TaskStatus.COMPLETED
            self.tasks_completed += 1

            # Energy: power × time (simplified)
            power = self.config.cpu_speed_ghz * self.config.energy_per_ghz
            self.total_energy += power * proc_time

        self._log_queue()

    def _log_queue(self) -> None:
        self._queue_length_history.append((self.env.now, self.queue_length))

    def snapshot(self) -> dict:
        """Return current state for telemetry / dashboard."""
        return {
            "node_id"         : self.node_id,
            "node_type"       : self.node_type.value,
            "cpu_cores"       : self.config.cpu_cores,
            "cpu_utilization" : round(self.cpu_utilization, 4),
            "queue_length"    : self.queue_length,
            "tasks_completed" : self.tasks_completed,
            "tasks_dropped"   : self.tasks_dropped,
            "total_energy_j"  : round(self.total_energy, 4),
            "sim_time"        : self.env.now,
        }

    def reset_counters(self) -> None:
        self.tasks_completed = 0
        self.tasks_dropped   = 0
        self.tasks_failed    = 0
        self.total_energy    = 0.0
        self._queue_length_history.clear()
