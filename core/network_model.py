"""
core/network_model.py
Simulates network conditions between a source (task generator) and each node.
Models: RTT latency, available bandwidth, packet loss, jitter.
All values are stochastic and can be perturbed for fault-injection scenarios.
"""
from __future__ import annotations
import random
import math
from dataclasses import dataclass, field


@dataclass
class LinkProfile:
    """
    Describes the network link characteristics to a specific node.

    Attributes
    ----------
    base_latency_ms    : Base one-way latency (ms)
    bandwidth_mbps     : Available bandwidth (Mbps)
    jitter_ms          : Max random jitter added per transmission (ms)
    packet_loss_rate   : Probability of packet loss [0, 1]
    """
    base_latency_ms  : float = 10.0
    bandwidth_mbps   : float = 100.0
    jitter_ms        : float = 2.0
    packet_loss_rate : float = 0.001

    # Fault injection state
    _fault_active    : bool  = field(default=False, repr=False)
    _fault_latency   : float = field(default=0.0,   repr=False)   # Extra ms when fault active
    _fault_bw_factor : float = field(default=1.0,   repr=False)   # BW multiplier during fault

    def inject_fault(self, extra_latency_ms: float = 200.0, bw_factor: float = 0.1) -> None:
        """Simulate a network fault: high latency, degraded bandwidth."""
        self._fault_active  = True
        self._fault_latency = extra_latency_ms
        self._fault_bw_factor = bw_factor

    def clear_fault(self) -> None:
        self._fault_active  = False
        self._fault_latency = 0.0
        self._fault_bw_factor = 1.0

    @property
    def effective_latency_ms(self) -> float:
        jitter = random.uniform(0, self.jitter_ms)
        base   = self.base_latency_ms + jitter
        if self._fault_active:
            base += self._fault_latency
        return base

    @property
    def effective_bandwidth_mbps(self) -> float:
        bw = self.bandwidth_mbps * self._fault_bw_factor
        # Add slight random fluctuation ±10%
        bw *= random.uniform(0.9, 1.1)
        return max(bw, 0.1)

    @property
    def rtt_ms(self) -> float:
        """Round-trip time = 2× one-way latency."""
        return self.effective_latency_ms * 2


class NetworkModel:
    """
    Holds link profiles for all nodes and computes transfer times.

    Usage
    -----
        net = NetworkModel()
        net.add_link("edge_1", LinkProfile(base_latency_ms=5, bandwidth_mbps=200))
        net.add_link("cloud",  LinkProfile(base_latency_ms=80, bandwidth_mbps=1000))

        transfer_ms = net.transfer_time_ms("edge_1", size_kb=512)
        latency_ms  = net.latency_ms("edge_1")
    """

    def __init__(self) -> None:
        self._links: dict[str, LinkProfile] = {}

    def add_link(self, node_id: str, profile: LinkProfile) -> None:
        self._links[node_id] = profile

    def get_link(self, node_id: str) -> LinkProfile:
        if node_id not in self._links:
            raise KeyError(f"No link profile for node '{node_id}'")
        return self._links[node_id]

    def latency_ms(self, node_id: str) -> float:
        """One-way latency to node (ms), including jitter and any active fault."""
        return self.get_link(node_id).effective_latency_ms

    def rtt_ms(self, node_id: str) -> float:
        """Round-trip time to node (ms)."""
        return self.get_link(node_id).rtt_ms

    def bandwidth_mbps(self, node_id: str) -> float:
        return self.get_link(node_id).effective_bandwidth_mbps

    def transfer_time_ms(self, node_id: str, size_kb: float) -> float:
        """
        Time to transfer `size_kb` kilobytes to the node (ms).
        transfer_time = (size_bytes / bandwidth_bytes_per_ms)
        """
        link = self.get_link(node_id)
        bandwidth_kbps = link.effective_bandwidth_mbps * 1000 / 8   # KB/s
        transfer_ms    = (size_kb / bandwidth_kbps) * 1000          # ms
        return transfer_ms + link.effective_latency_ms

    def total_offload_overhead_ms(self, node_id: str, size_kb: float) -> float:
        """
        Full overhead: upload + download RTT (approximated as upload×1.1 for ACK).
        """
        return self.transfer_time_ms(node_id, size_kb) * 1.1

    def has_packet_loss(self, node_id: str) -> bool:
        link = self.get_link(node_id)
        return random.random() < link.packet_loss_rate

    def inject_fault(self, node_id: str, extra_latency_ms: float = 200.0, bw_factor: float = 0.1) -> None:
        self.get_link(node_id).inject_fault(extra_latency_ms, bw_factor)

    def clear_fault(self, node_id: str) -> None:
        self.get_link(node_id).clear_fault()

    def snapshot(self) -> dict:
        """Return current network state for telemetry."""
        return {
            node_id: {
                "latency_ms"    : link.effective_latency_ms,
                "bandwidth_mbps": link.effective_bandwidth_mbps,
                "rtt_ms"        : link.rtt_ms,
                "fault_active"  : link._fault_active,
            }
            for node_id, link in self._links.items()
        }
