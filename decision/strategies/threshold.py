"""
decision/strategies/threshold.py
Threshold-based strategy: sends to edge if edge CPU < threshold AND
task size is small; otherwise falls back to cloud.
This represents conventional static-rule offloading.
"""
from __future__ import annotations
from core.task import Task
from core.node import Node
from core.network_model import NetworkModel


class ThresholdStrategy:
    CPU_THRESHOLD  = 0.75   # edge CPU utilization threshold
    SIZE_THRESHOLD = 512.0  # KB — large tasks go to cloud

    def __init__(self, nodes: dict[str, Node], network: NetworkModel) -> None:
        self.nodes   = nodes
        self.network = network
        self._edge_ids = [nid for nid, n in nodes.items() if n.node_type.value == "edge"]

    def decide(self, task: Task) -> str:
        # Check best edge node
        best_edge = min(self._edge_ids, key=lambda nid: self.nodes[nid].queue_length)
        edge_util = self.nodes[best_edge].cpu_utilization

        if edge_util < self.CPU_THRESHOLD and task.size_kb < self.SIZE_THRESHOLD:
            task.decision_reason = (
                f"Threshold → {best_edge} "
                f"(cpu={edge_util:.2f}<{self.CPU_THRESHOLD}, "
                f"size={task.size_kb:.0f}<{self.SIZE_THRESHOLD})"
            )
            return best_edge
        else:
            task.decision_reason = (
                f"Threshold → cloud "
                f"(cpu={edge_util:.2f}, size={task.size_kb:.0f})"
            )
            return "cloud"
