"""
core/task.py
Defines the Task dataclass — the fundamental unit of work in the simulation.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    PENDING   = "pending"
    QUEUED    = "queued"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    DROPPED   = "dropped"


class TaskType(str, Enum):
    COMPUTE_INTENSIVE = "compute_intensive"   # High CPU, low data
    DATA_INTENSIVE    = "data_intensive"      # Low CPU, high data transfer
    LATENCY_SENSITIVE = "latency_sensitive"   # Small, must be fast
    BATCH             = "batch"               # Large, deadline-flexible


@dataclass
class Task:
    """
    A single computational task to be offloaded.

    Attributes
    ----------
    task_id        : Unique identifier
    task_type      : Category of workload
    size_kb        : Input data size in KB (affects transfer time)
    complexity     : CPU cycles required (1–10 scale, maps to processing time)
    deadline_ms    : Maximum allowed end-to-end latency (ms)
    created_at     : SimPy simulation time when task arrived
    priority       : 1 (low) – 5 (high)
    """
    task_id      : str       = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_type    : TaskType  = TaskType.COMPUTE_INTENSIVE
    size_kb      : float     = 100.0
    complexity   : float     = 5.0       # 1–10
    deadline_ms  : float     = 500.0
    created_at   : float     = 0.0
    priority     : int       = 3         # 1–5

    # Filled in during execution
    queued_at      : float | None = None
    started_at     : float | None = None
    completed_at   : float | None = None
    assigned_node  : str   | None = None
    strategy_used  : str   | None = None
    status         : TaskStatus   = TaskStatus.PENDING

    # Decision engine metadata
    offload_score  : float | None = None   # Fuzzy score that drove the decision
    decision_reason: str  | None = None    # Human-readable reason

    @property
    def transfer_time_ms(self) -> float:
        """Placeholder — actual value set by NetworkModel."""
        return 0.0

    @property
    def queue_wait_ms(self) -> float:
        if self.queued_at is not None and self.started_at is not None:
            return (self.started_at - self.queued_at) * 1000
        return 0.0

    @property
    def execution_time_ms(self) -> float:
        if self.started_at is not None and self.completed_at is not None:
            return (self.completed_at - self.started_at) * 1000
        return 0.0

    @property
    def total_latency_ms(self) -> float:
        if self.created_at is not None and self.completed_at is not None:
            return (self.completed_at - self.created_at) * 1000
        return 0.0

    @property
    def sla_violated(self) -> bool:
        return self.total_latency_ms > self.deadline_ms

    def to_dict(self) -> dict:
        return {
            "task_id"        : self.task_id,
            "task_type"      : self.task_type.value,
            "size_kb"        : self.size_kb,
            "complexity"     : self.complexity,
            "deadline_ms"    : self.deadline_ms,
            "priority"       : self.priority,
            "created_at"     : self.created_at,
            "queued_at"      : self.queued_at,
            "started_at"     : self.started_at,
            "completed_at"   : self.completed_at,
            "assigned_node"  : self.assigned_node,
            "strategy_used"  : self.strategy_used,
            "status"         : self.status.value,
            "queue_wait_ms"  : self.queue_wait_ms,
            "execution_time_ms": self.execution_time_ms,
            "total_latency_ms" : self.total_latency_ms,
            "sla_violated"   : self.sla_violated,
            "offload_score"  : self.offload_score,
            "decision_reason": self.decision_reason,
        }
