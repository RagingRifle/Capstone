"""
decision/strategies/edge_only.py
Baseline strategy: always route tasks to the least-loaded edge node.
"""
from __future__ import annotations
from core.task import Task
from core.node import Node
from core.network_model import NetworkModel


class EdgeOnlyStrategy:
    def __init__(self, nodes: dict[str, Node], network: NetworkModel) -> None:
        self.nodes   = nodes
        self.network = network
        self._edge_ids = [nid for nid, n in nodes.items() if n.node_type.value == "edge"]

    def decide(self, task: Task) -> str:
        # Pick edge node with shortest queue
        best = min(self._edge_ids, key=lambda nid: self.nodes[nid].queue_length)
        task.decision_reason = f"EdgeOnly → {best}"
        return best
