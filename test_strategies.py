from core.simulation_engine import SimulationEngine, SimConfig
from core.task_generator import WorkloadConfig

strategies = ['edge_only', 'cloud_only', 'threshold', 'adaptive']

print(f"\n{'Strategy':<14} {'Tasks':>6} {'Avg Lat':>10} {'p95 Lat':>10} {'SLA%':>6} {'Distribution'}")
print("-" * 75)

for strategy in strategies:
    cfg = SimConfig(
        duration_s=10,
        sim_speed=0,
        strategy=strategy,
        workload=WorkloadConfig(base_rate=3.0),
    )
    e = SimulationEngine(cfg)
    e.run()
    r = e.get_results()
    dist = r.get('node_distribution', {})
    dist_str = "  ".join(f"{k}:{v}" for k, v in dist.items())
    print(
        f"{strategy:<14} {r['tasks_completed']:>6}  "
        f"{r['avg_latency_ms']:>9.1f}ms  "
        f"{r['p95_latency_ms']:>9.1f}ms  "
        f"{r['sla_violation_rate']*100:>5.1f}%  {dist_str}"
    )

print("\nAll strategies OK.")
