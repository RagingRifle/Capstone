"""
decision/adaptive_engine.py
Adaptive task offloading decision engine.

Decision pipeline
-----------------
1. Sample current network & node conditions
2. Run Fuzzy Logic inference → offload_score ∈ [0, 1]
3. Apply weighted scoring correction (priority, deadline urgency)
4. Select target node:
     offload_score < 0.5  → best edge node
     offload_score ≥ 0.5  → cloud node
5. Tag task with score + human-readable reason
"""
from __future__ import annotations
import numpy as np
from typing import TYPE_CHECKING

from core.node          import Node
from core.network_model import NetworkModel
from core.task          import Task, TaskType

if TYPE_CHECKING:
    pass


FUZZY_AVAILABLE = True
try:
    from decision.fuzzy_rules import build_fuzzy_system
except ImportError:
    FUZZY_AVAILABLE = False


class AdaptiveEngine:
    """
    Fuzzy Logic + Weighted Scoring adaptive decision engine.

    Falls back to weighted scoring only if scikit-fuzzy is not installed.
    """

    # Priority bonus: tasks with higher priority get edge preference
    PRIORITY_WEIGHT = 0.05          # per priority level (1–5)

    # Deadline urgency: if remaining headroom < this, prefer fast edge
    URGENT_DEADLINE_MS = 200.0

    def __init__(self, nodes: dict[str, Node], network: NetworkModel) -> None:
        self.nodes   = nodes
        self.network = network
        self._edge_ids = [nid for nid, n in nodes.items() if n.node_type.value == "edge"]
        self._cloud_id = "cloud"

        # Build fuzzy system once — reuse per task
        if FUZZY_AVAILABLE:
            self._fuzzy_sim = build_fuzzy_system()
            self._use_fuzzy = True
        else:
            self._use_fuzzy = False

        # Track decision stats
        self.edge_decisions  = 0
        self.cloud_decisions = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decide(self, task: Task) -> str:
        """
        Returns the node_id that should execute this task.
        Also sets task.offload_score and task.decision_reason.
        """
        best_edge = min(self._edge_ids, key=lambda nid: self.nodes[nid].queue_length)
        edge_node = self.nodes[best_edge]

        # --- Gather inputs ---
        latency_ms   = self.network.latency_ms(best_edge)
        bandwidth    = self.network.bandwidth_mbps(best_edge)
        edge_cpu     = edge_node.cpu_utilization
        queue_len    = edge_node.queue_length
        task_size    = task.size_kb
        task_cplx    = task.complexity

        # --- Fuzzy inference ---
        if self._use_fuzzy:
            score = self._fuzzy_score(latency_ms, bandwidth, edge_cpu, task_size, task_cplx, queue_len)
        else:
            score = self._weighted_score(latency_ms, bandwidth, edge_cpu, task_size, task_cplx, queue_len)

        # --- Weighted corrections ---
        score = self._apply_corrections(score, task)

        # --- Hard override: severe latency conditions ---
        # When edge latency exceeds the cloud RTT, routing to edge is always
        # suboptimal regardless of CPU state. This is the key condition-awareness
        # that static threshold strategies cannot express.
        cloud_latency = self.network.latency_ms(self._cloud_id)
        if latency_ms > cloud_latency * 1.3:
            # Edge is significantly slower than cloud — force cloud
            score = max(score, 0.72)
        elif latency_ms > 60.0:
            # Moderately degraded edge — strong cloud bias
            score = max(score, 0.55)
        elif bandwidth < 30.0:
            # Very low bandwidth — large tasks will clog the edge link
            if task_size > 256:
                score = max(score, 0.60)

        # --- Select node ---
        task.offload_score = round(score, 4)

        if score < 0.5:
            # Favour edge
            self.edge_decisions += 1
            task.decision_reason = (
                f"Adaptive→{best_edge} "
                f"[score={score:.3f}, cpu={edge_cpu:.2f}, lat={latency_ms:.1f}ms, "
                f"q={queue_len}]"
            )
            return best_edge
        else:
            # Offload to cloud
            self.cloud_decisions += 1
            task.decision_reason = (
                f"Adaptive→cloud "
                f"[score={score:.3f}, cpu={edge_cpu:.2f}, lat={latency_ms:.1f}ms, "
                f"q={queue_len}]"
            )
            return self._cloud_id

    # ------------------------------------------------------------------
    # Scoring methods
    # ------------------------------------------------------------------

    def _fuzzy_score(
        self,
        latency_ms : float,
        bandwidth  : float,
        edge_cpu   : float,
        task_size  : float,
        complexity : float,
        queue_len  : int,
    ) -> float:
        """
        Run the scikit-fuzzy simulation and return offload_score ∈ [0, 1].
        Clamps inputs to universe bounds to avoid simulation errors.
        """
        sim = self._fuzzy_sim
        try:
            sim.input["latency_ms"]       = float(np.clip(latency_ms, 0, 200))
            sim.input["bandwidth_mbps"]   = float(np.clip(bandwidth,  0, 500))
            sim.input["edge_cpu"]         = float(np.clip(edge_cpu,   0, 1))
            sim.input["task_size_kb"]     = float(np.clip(task_size,  0, 2048))
            sim.input["task_complexity"]  = float(np.clip(complexity, 0, 10))
            sim.input["queue_len"]        = float(np.clip(queue_len,  0, 50))
            sim.compute()
            return float(np.clip(sim.output["offload_score"], 0, 1))
        except Exception:
            # Fuzzy inference failed (e.g. no rule fired) — fall back
            return self._weighted_score(latency_ms, bandwidth, edge_cpu, task_size, complexity, queue_len)

    def _weighted_score(
        self,
        latency_ms : float,
        bandwidth  : float,
        edge_cpu   : float,
        task_size  : float,
        complexity : float,
        queue_len  : int,
    ) -> float:
        """
        Deterministic weighted scoring fallback.
        Each sub-score ∈ [0, 1] where higher = more reason to use cloud.
        """
        # Normalize inputs
        lat_score  = np.clip(latency_ms / 200.0, 0, 1)        # high latency → cloud
        bw_score   = 1 - np.clip(bandwidth / 500.0, 0, 1)     # low BW → cloud
        cpu_score  = np.clip(edge_cpu, 0, 1)                   # high CPU → cloud
        size_score = np.clip(task_size / 2048.0, 0, 1)        # large task → cloud
        cplx_score = np.clip(complexity / 10.0, 0, 1)         # complex → cloud
        q_score    = np.clip(queue_len / 50.0, 0, 1)          # long queue → cloud

        weights = [0.25, 0.10, 0.30, 0.15, 0.10, 0.10]
        scores  = [lat_score, bw_score, cpu_score, size_score, cplx_score, q_score]
        return float(np.dot(weights, scores))

    def _apply_corrections(self, score: float, task: Task) -> float:
        """Apply priority and deadline-urgency corrections to raw score."""
        # High priority → prefer edge (lower score)
        priority_adj = -(task.priority - 3) * self.PRIORITY_WEIGHT
        score += priority_adj

        # Latency-sensitive tasks strongly prefer edge
        if task.task_type == TaskType.LATENCY_SENSITIVE:
            score -= 0.15

        # If deadline is very tight, prefer the lower-latency edge option
        if task.deadline_ms < self.URGENT_DEADLINE_MS:
            score -= 0.10

        return float(np.clip(score, 0, 1))

    def stats(self) -> dict:
        total = self.edge_decisions + self.cloud_decisions
        return {
            "edge_decisions"  : self.edge_decisions,
            "cloud_decisions" : self.cloud_decisions,
            "edge_pct"        : self.edge_decisions  / max(total, 1) * 100,
            "cloud_pct"       : self.cloud_decisions / max(total, 1) * 100,
        }
