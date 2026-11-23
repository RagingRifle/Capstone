"""
decision/fuzzy_rules.py
Fuzzy Logic membership functions and rule base for the adaptive engine.

Input variables
---------------
  latency_ms      : Network latency to edge (0–200 ms)
  bandwidth_mbps  : Available bandwidth (0–500 Mbps)
  edge_cpu        : Edge CPU utilization (0–1)
  cloud_cpu       : Cloud CPU utilization (0–1)
  task_size_kb    : Task data size (0–2048 KB)
  task_complexity : CPU complexity (0–10)
  queue_len       : Edge queue length (0–50)

Output variable
---------------
  offload_score   : 0 = run on edge, 1 = offload to cloud  (0–1)
"""
from __future__ import annotations
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl


def build_fuzzy_system() -> ctrl.ControlSystemSimulation:
    """
    Construct and return a ready-to-use fuzzy control system simulation.
    """

    # ── Universe of discourse ──────────────────────────────────────────
    latency      = ctrl.Antecedent(np.arange(0, 201, 1),    "latency_ms")
    bandwidth    = ctrl.Antecedent(np.arange(0, 501, 1),    "bandwidth_mbps")
    edge_cpu     = ctrl.Antecedent(np.arange(0, 1.01, 0.01),"edge_cpu")
    task_size    = ctrl.Antecedent(np.arange(0, 2049, 1),   "task_size_kb")
    complexity   = ctrl.Antecedent(np.arange(0, 10.1, 0.1), "task_complexity")
    queue_len    = ctrl.Antecedent(np.arange(0, 51, 1),     "queue_len")

    offload      = ctrl.Consequent(np.arange(0, 1.01, 0.01),"offload_score")

    # ── Membership functions ──────────────────────────────────────────
    # Latency: low / medium / high
    latency["low"]    = fuzz.trimf(latency.universe,   [0,   0,  20])
    latency["medium"] = fuzz.trimf(latency.universe,   [10,  40,  80])
    latency["high"]   = fuzz.trimf(latency.universe,   [40, 100, 200])

    # Bandwidth: low / medium / high
    bandwidth["low"]    = fuzz.trimf(bandwidth.universe, [0,   0,  100])
    bandwidth["medium"] = fuzz.trimf(bandwidth.universe, [50,  200, 350])
    bandwidth["high"]   = fuzz.trimf(bandwidth.universe, [250, 500, 500])

    # Edge CPU utilization: low / medium / high / critical
    edge_cpu["low"]      = fuzz.trimf(edge_cpu.universe, [0,   0,   0.4])
    edge_cpu["medium"]   = fuzz.trimf(edge_cpu.universe, [0.3, 0.55, 0.7])
    edge_cpu["high"]     = fuzz.trimf(edge_cpu.universe, [0.6, 0.8,  0.9])
    edge_cpu["critical"] = fuzz.trimf(edge_cpu.universe, [0.85,1.0,  1.0])

    # Task size: small / medium / large
    task_size["small"]  = fuzz.trimf(task_size.universe, [0,    0,    256])
    task_size["medium"] = fuzz.trimf(task_size.universe, [128,  512, 1024])
    task_size["large"]  = fuzz.trimf(task_size.universe, [768, 2048, 2048])

    # Task complexity: low / medium / high
    complexity["low"]    = fuzz.trimf(complexity.universe, [0,   0,   4])
    complexity["medium"] = fuzz.trimf(complexity.universe, [2,   5,   7])
    complexity["high"]   = fuzz.trimf(complexity.universe, [6,  10,  10])

    # Queue length: short / moderate / long
    queue_len["short"]    = fuzz.trimf(queue_len.universe, [0,  0,  10])
    queue_len["moderate"] = fuzz.trimf(queue_len.universe, [5,  20,  35])
    queue_len["long"]     = fuzz.trimf(queue_len.universe, [25, 50,  50])

    # Offload score: stay_edge / borderline / prefer_cloud / cloud
    offload["edge"]         = fuzz.trimf(offload.universe, [0.0, 0.0, 0.25])
    offload["lean_edge"]    = fuzz.trimf(offload.universe, [0.1, 0.3, 0.5])
    offload["lean_cloud"]   = fuzz.trimf(offload.universe, [0.4, 0.6, 0.8])
    offload["cloud"]        = fuzz.trimf(offload.universe, [0.7, 1.0, 1.0])

    # ── Rule base ─────────────────────────────────────────────────────
    rules = [
        # R1: Edge not overloaded + low latency + small task → stay on edge
        ctrl.Rule(edge_cpu["low"]      & latency["low"]  & task_size["small"],   offload["edge"]),

        # R2: Edge not overloaded + medium conditions → lean edge
        ctrl.Rule(edge_cpu["low"]      & latency["medium"],                       offload["lean_edge"]),
        ctrl.Rule(edge_cpu["medium"]   & latency["low"]  & task_size["small"],   offload["lean_edge"]),

        # R3: Edge moderately loaded + bandwidth OK + medium task → lean cloud
        ctrl.Rule(edge_cpu["medium"]   & task_size["medium"],                     offload["lean_cloud"]),
        ctrl.Rule(edge_cpu["medium"]   & queue_len["moderate"],                   offload["lean_cloud"]),

        # R4: Edge high load → cloud
        ctrl.Rule(edge_cpu["high"],                                               offload["cloud"]),
        ctrl.Rule(edge_cpu["critical"],                                           offload["cloud"]),

        # R5: Long queue → cloud regardless
        ctrl.Rule(queue_len["long"],                                              offload["cloud"]),

        # R6: High network latency to edge → favour cloud
        ctrl.Rule(latency["high"],                                                offload["cloud"]),

        # R7: Large task + medium latency → cloud (avoid edge saturation)
        ctrl.Rule(task_size["large"]   & latency["medium"],                      offload["cloud"]),
        ctrl.Rule(task_size["large"]   & edge_cpu["medium"],                     offload["cloud"]),

        # R8: High complexity + edge loaded → cloud
        ctrl.Rule(complexity["high"]   & edge_cpu["medium"],                     offload["lean_cloud"]),
        ctrl.Rule(complexity["high"]   & edge_cpu["high"],                       offload["cloud"]),

        # R9: Low complexity + edge available → edge
        ctrl.Rule(complexity["low"]    & edge_cpu["low"],                        offload["edge"]),
        ctrl.Rule(complexity["low"]    & edge_cpu["medium"] & latency["low"],   offload["lean_edge"]),

        # R10: High bandwidth to edge + small task → edge (fast transfer)
        ctrl.Rule(bandwidth["high"]    & task_size["small"] & edge_cpu["low"],  offload["edge"]),

        # R11: Low bandwidth + large task → edge preferred (avoid slow cloud upload)
        ctrl.Rule(bandwidth["low"]     & task_size["large"],                     offload["lean_edge"]),

        # R12: Queue short + CPU low → edge
        ctrl.Rule(queue_len["short"]   & edge_cpu["low"],                        offload["edge"]),
    ]

    system = ctrl.ControlSystem(rules)
    return ctrl.ControlSystemSimulation(system)
