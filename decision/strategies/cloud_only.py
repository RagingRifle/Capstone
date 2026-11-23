"""
decision/strategies/cloud_only.py
Baseline strategy: always route tasks to the cloud node.
"""
from __future__ import annotations
from core.task import Task
from core.node import Node
from core.network_model import NetworkModel


class CloudOnlyStrategy:
    def __init__(self, nodes: dict[str, Node], network: NetworkModel) -> None:
        self.nodes   = nodes
        self.network = network

    def decide(self, task: Task) -> str:
        task.decision_reason = "CloudOnly → cloud"
        return "cloud"
