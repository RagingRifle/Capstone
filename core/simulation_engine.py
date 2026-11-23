"""
core/simulation_engine.py
Central orchestrator. Wires together: environment, nodes, network model,
task generator, decision engine, and telemetry collector.

Usage
-----
    from core.simulation_engine import SimulationEngine, SimConfig
    engine = SimulationEngine(SimConfig(...))
    engine.run()
    results = engine.get_results()
"""
from __future__ import annotations
import simpy
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from core.task        import Task, TaskStatus
from core.node        import Node, NodeConfig, NodeType
from core.network_model import NetworkModel, LinkProfile
from core.task_generator import TaskGenerator, WorkloadConfig


@dataclass
class SimConfig:
    """Top-level configuration for a simulation run."""
    # Simulation time
    duration_s       : float = 120.0
    sim_speed        : float = 1.0         # 1.0 = real-time, 10.0 = 10× faster, 0 = max speed

    # Workload
    workload         : WorkloadConfig = field(default_factory=WorkloadConfig)

    # Strategy
    strategy         : str  = "adaptive"   # edge_only | cloud_only | threshold | adaptive

    # Network links — defaults tuned for realistic MEC scenario
    edge1_latency_ms : float = 5.0
    edge1_bw_mbps    : float = 200.0
    edge2_latency_ms : float = 8.0
    edge2_bw_mbps    : float = 150.0
    cloud_latency_ms : float = 80.0
    cloud_bw_mbps    : float = 1000.0

    # Node hardware
    edge1_cores      : int   = 4
    edge1_speed_ghz  : float = 2.0
    edge2_cores      : int   = 4
    edge2_speed_ghz  : float = 2.2
    cloud_cores      : int   = 16
    cloud_speed_ghz  : float = 3.5

    # Experiment metadata
    scenario_name    : str  = "default"
    run_id           : str  = ""


class SimulationEngine:
    """
    Discrete-event simulation engine.

    Attributes (available after run())
    -----------
    completed_tasks  : list[Task]   — all tasks that finished
    dropped_tasks    : list[Task]   — tasks dropped due to queue overflow
    """

    def __init__(
        self,
        config          : SimConfig,
        telemetry_cb    : Callable[[dict], None] | None = None,
        task_complete_cb: Callable[[Task],  None] | None = None,
    ) -> None:
        self.config           = config
        self.telemetry_cb     = telemetry_cb     # called periodically with node snapshots
        self.task_complete_cb = task_complete_cb  # called when each task finishes

        self.completed_tasks  : list[Task] = []
        self.dropped_tasks    : list[Task] = []
        self.all_tasks        : list[Task] = []

        self._stop_event = threading.Event()
        self._env        = simpy.Environment()

        self._setup()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup(self) -> None:
        cfg = self.config
        env = self._env

        # --- Nodes ---
        self.nodes: dict[str, Node] = {
            "edge_1": Node(NodeConfig("edge_1", NodeType.EDGE,  cfg.edge1_cores, cfg.edge1_speed_ghz), env),
            "edge_2": Node(NodeConfig("edge_2", NodeType.EDGE,  cfg.edge2_cores, cfg.edge2_speed_ghz), env),
            "cloud" : Node(NodeConfig("cloud",  NodeType.CLOUD, cfg.cloud_cores, cfg.cloud_speed_ghz), env),
        }

        # --- Network Model ---
        self.network = NetworkModel()
        self.network.add_link("edge_1", LinkProfile(cfg.edge1_latency_ms, cfg.edge1_bw_mbps, jitter_ms=1.0))
        self.network.add_link("edge_2", LinkProfile(cfg.edge2_latency_ms, cfg.edge2_bw_mbps, jitter_ms=1.5))
        self.network.add_link("cloud",  LinkProfile(cfg.cloud_latency_ms, cfg.cloud_bw_mbps, jitter_ms=10.0))

        # --- Decision Engine ---
        self._decision_engine = self._build_decision_engine()

        # --- Task Generator ---
        self.generator = TaskGenerator(env, cfg.workload, self._on_task_arrival)

        # --- Telemetry ticker ---
        env.process(self._telemetry_ticker())

    def _build_decision_engine(self):
        strategy = self.config.strategy
        if strategy == "edge_only":
            from decision.strategies.edge_only import EdgeOnlyStrategy
            return EdgeOnlyStrategy(self.nodes, self.network)
        elif strategy == "cloud_only":
            from decision.strategies.cloud_only import CloudOnlyStrategy
            return CloudOnlyStrategy(self.nodes, self.network)
        elif strategy == "threshold":
            from decision.strategies.threshold import ThresholdStrategy
            return ThresholdStrategy(self.nodes, self.network)
        elif strategy == "adaptive":
            from decision.adaptive_engine import AdaptiveEngine
            return AdaptiveEngine(self.nodes, self.network)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_task_arrival(self, task: Task) -> None:
        """Called by TaskGenerator for each new task."""
        self.all_tasks.append(task)
        task.strategy_used = self.config.strategy

        # Decision engine selects node
        node_id = self._decision_engine.decide(task)
        node    = self.nodes[node_id]

        # Add network transfer overhead to task creation time conceptually
        # (we simulate it as a timeout before task starts on node)
        self._env.process(self._dispatch(task, node))

    def _dispatch(self, task: Task, node: Node):
        """SimPy process: simulate network transfer then execute on node."""
        transfer_ms = self.network.total_offload_overhead_ms(node.node_id, task.size_kb)
        yield self._env.timeout(transfer_ms / 1000.0)   # convert ms → s

        yield self._env.process(node.execute(task))

        if task.status == TaskStatus.COMPLETED:
            self.completed_tasks.append(task)
        elif task.status == TaskStatus.DROPPED:
            self.dropped_tasks.append(task)

        if self.task_complete_cb:
            self.task_complete_cb(task)

    def _telemetry_ticker(self):
        """Emit node snapshots every 0.5 sim-seconds."""
        while True:
            yield self._env.timeout(0.5)
            if self.telemetry_cb:
                snapshot = {
                    "sim_time" : self._env.now,
                    "nodes"    : {nid: n.snapshot() for nid, n in self.nodes.items()},
                    "network"  : self.network.snapshot(),
                    "tasks_total"    : len(self.all_tasks),
                    "tasks_completed": len(self.completed_tasks),
                    "tasks_dropped"  : len(self.dropped_tasks),
                }
                self.telemetry_cb(snapshot)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Run the simulation synchronously until duration_s elapses.
        Set sim_speed=0 to run at maximum speed (no real-time pacing).
        """
        cfg      = self.config
        env      = self._env
        end_time = cfg.duration_s

        if cfg.sim_speed == 0:
            # Max speed — no real-time pacing
            env.run(until=end_time)
        else:
            # Real-time paced — advance in small steps
            step_s      = 0.1                        # sim-time step (s)
            wall_step   = step_s / cfg.sim_speed     # real-time equivalent
            sim_target  = 0.0

            while env.now < end_time and not self._stop_event.is_set():
                sim_target += step_s
                env.run(until=min(sim_target, end_time))
                time.sleep(wall_step)

    def run_async(self) -> threading.Thread:
        """Run the simulation in a background thread. Returns the thread."""
        t = threading.Thread(target=self.run, daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._stop_event.set()
        self.generator.stop()

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def get_results(self) -> dict:
        """Compute summary statistics over completed tasks."""
        import numpy as np
        tasks = self.completed_tasks
        if not tasks:
            return {"error": "No completed tasks"}

        latencies = [t.total_latency_ms  for t in tasks]
        exec_times = [t.execution_time_ms for t in tasks]
        sla_viol  = [t for t in tasks if t.sla_violated]
        node_dist = {}
        for t in tasks:
            node_dist[t.assigned_node] = node_dist.get(t.assigned_node, 0) + 1

        duration = self.config.duration_s
        return {
            "scenario"         : self.config.scenario_name,
            "strategy"         : self.config.strategy,
            "duration_s"       : duration,
            "tasks_generated"  : len(self.all_tasks),
            "tasks_completed"  : len(tasks),
            "tasks_dropped"    : len(self.dropped_tasks),
            "task_completion_rate": len(tasks) / max(len(self.all_tasks), 1),
            "throughput_per_s" : len(tasks) / duration,
            "avg_latency_ms"   : np.mean(latencies),
            "p50_latency_ms"   : np.percentile(latencies, 50),
            "p95_latency_ms"   : np.percentile(latencies, 95),
            "p99_latency_ms"   : np.percentile(latencies, 99),
            "std_latency_ms"   : np.std(latencies),
            "avg_exec_time_ms" : np.mean(exec_times),
            "sla_violations"   : len(sla_viol),
            "sla_violation_rate": len(sla_viol) / max(len(tasks), 1),
            "node_distribution": node_dist,
            "total_energy_j"   : sum(n.total_energy for n in self.nodes.values()),
            "cpu_utilization"  : {nid: n.cpu_utilization for nid, n in self.nodes.items()},
        }
