"""
core/task_generator.py
Generates tasks using configurable arrival patterns:
  - Poisson  : Steady-state random arrivals (λ tasks/sec)
  - Burst    : Sudden spike of tasks arriving in a short window
  - Ramp     : Gradually increasing arrival rate
  - Mixed    : Cycles through multiple patterns

Task properties (size, complexity, type, deadline) are sampled
from distributions matching the scenario configuration.
"""
from __future__ import annotations
import random
import simpy
from dataclasses import dataclass
from typing import Callable, Generator
from core.task import Task, TaskType


@dataclass
class WorkloadConfig:
    """Parameters controlling the workload shape for a simulation run."""
    pattern          : str   = "poisson"    # poisson | burst | ramp | mixed
    base_rate        : float = 2.0          # tasks/second (Poisson λ)
    burst_size       : int   = 30           # tasks in a burst event
    burst_interval_s : float = 20.0         # seconds between burst events
    ramp_start_rate  : float = 0.5          # tasks/sec at ramp start
    ramp_end_rate    : float = 10.0         # tasks/sec at ramp end
    ramp_duration_s  : float = 60.0         # seconds to ramp over

    # Task property distributions
    size_kb_range    : tuple[float, float] = (10.0, 2048.0)
    complexity_range : tuple[float, float] = (1.0, 10.0)
    deadline_ms_range: tuple[float, float] = (100.0, 2000.0)
    priority_weights : list[float]         = None   # weights for priorities 1–5

    def __post_init__(self):
        if self.priority_weights is None:
            self.priority_weights = [0.1, 0.2, 0.4, 0.2, 0.1]


class TaskGenerator:
    """
    SimPy process that continuously generates tasks and passes them
    to a callback (usually the decision engine / scheduler).

    Parameters
    ----------
    env        : SimPy Environment
    config     : WorkloadConfig
    on_task_fn : Callable[[Task], None] — called for each generated task
    """

    TASK_TYPE_WEIGHTS = {
        TaskType.COMPUTE_INTENSIVE : 0.35,
        TaskType.DATA_INTENSIVE    : 0.25,
        TaskType.LATENCY_SENSITIVE : 0.25,
        TaskType.BATCH             : 0.15,
    }

    def __init__(
        self,
        env       : simpy.Environment,
        config    : WorkloadConfig,
        on_task_fn: Callable[[Task], None],
    ) -> None:
        self.env        = env
        self.config     = config
        self.on_task_fn = on_task_fn
        self.tasks_generated = 0
        self._running   = True

        # Start the generator process
        self._process = env.process(self._run())

    # ------------------------------------------------------------------
    # Public control
    # ------------------------------------------------------------------

    def stop(self) -> None:
        self._running = False

    def inject_burst(self, size: int | None = None) -> None:
        """Manually inject a burst event (callable from dashboard)."""
        n = size or self.config.burst_size
        for _ in range(n):
            task = self._make_task()
            self.on_task_fn(task)
            self.tasks_generated += 1

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> Generator:
        pattern = self.config.pattern
        if pattern == "poisson":
            yield from self._poisson()
        elif pattern == "burst":
            yield from self._burst()
        elif pattern == "ramp":
            yield from self._ramp()
        elif pattern == "mixed":
            yield from self._mixed()
        else:
            raise ValueError(f"Unknown workload pattern: {pattern}")

    def _poisson(self) -> Generator:
        """Exponential inter-arrival times → Poisson process."""
        rate = self.config.base_rate
        while self._running:
            inter_arrival = random.expovariate(rate)
            yield self.env.timeout(inter_arrival)
            self._emit()

    def _burst(self) -> Generator:
        """Steady low rate with periodic burst spikes."""
        low_rate = max(self.config.base_rate * 0.3, 0.1)
        while self._running:
            # Normal period
            burst_in = self.config.burst_interval_s * random.uniform(0.8, 1.2)
            end_time = self.env.now + burst_in
            while self._running and self.env.now < end_time:
                inter = random.expovariate(low_rate)
                yield self.env.timeout(inter)
                self._emit()

            # Burst period — emit burst_size tasks quickly
            if self._running:
                for _ in range(self.config.burst_size):
                    yield self.env.timeout(random.uniform(0.01, 0.1))
                    self._emit()

    def _ramp(self) -> Generator:
        """Linearly increasing arrival rate over ramp_duration_s."""
        start  = self.config.ramp_start_rate
        end    = self.config.ramp_end_rate
        dur    = self.config.ramp_duration_s
        t0     = self.env.now
        while self._running:
            elapsed = self.env.now - t0
            frac    = min(elapsed / dur, 1.0)
            rate    = start + (end - start) * frac
            inter   = random.expovariate(max(rate, 0.01))
            yield self.env.timeout(inter)
            self._emit()

    def _mixed(self) -> Generator:
        """Cycle: 30s poisson → 10s burst → 30s ramp → repeat."""
        phases = [
            ("poisson", 30),
            ("burst",   10),
            ("ramp",    30),
        ]
        while self._running:
            for phase, duration in phases:
                self.config.pattern = phase
                end = self.env.now + duration
                sub = self.env.process(self._run_until(phase, end))
                yield sub
            self.config.pattern = "mixed"

    def _run_until(self, pattern: str, end_time: float) -> Generator:
        rate = self.config.base_rate
        while self._running and self.env.now < end_time:
            inter = random.expovariate(rate)
            yield self.env.timeout(inter)
            if self.env.now < end_time:
                self._emit()

    def _emit(self) -> None:
        task = self._make_task()
        self.on_task_fn(task)
        self.tasks_generated += 1

    def _make_task(self) -> Task:
        cfg = self.config
        task_type = random.choices(
            list(self.TASK_TYPE_WEIGHTS.keys()),
            weights=list(self.TASK_TYPE_WEIGHTS.values()),
        )[0]

        # Latency-sensitive tasks are always small & have tight deadlines
        if task_type == TaskType.LATENCY_SENSITIVE:
            size_kb    = random.uniform(10, 100)
            complexity = random.uniform(1, 3)
            deadline   = random.uniform(100, 300)
        elif task_type == TaskType.DATA_INTENSIVE:
            size_kb    = random.uniform(500, cfg.size_kb_range[1])
            complexity = random.uniform(1, 5)
            deadline   = random.uniform(300, cfg.deadline_ms_range[1])
        elif task_type == TaskType.BATCH:
            size_kb    = random.uniform(*cfg.size_kb_range)
            complexity = random.uniform(5, 10)
            deadline   = random.uniform(1000, cfg.deadline_ms_range[1])
        else:
            size_kb    = random.uniform(*cfg.size_kb_range)
            complexity = random.uniform(*cfg.complexity_range)
            deadline   = random.uniform(*cfg.deadline_ms_range)

        priority = random.choices(range(1, 6), weights=cfg.priority_weights)[0]

        return Task(
            task_type   = task_type,
            size_kb     = round(size_kb, 2),
            complexity  = round(complexity, 2),
            deadline_ms = round(deadline, 1),
            created_at  = self.env.now,
            priority    = priority,
        )
