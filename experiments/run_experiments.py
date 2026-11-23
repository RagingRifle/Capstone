"""
experiments/run_experiments.py
Batch runner: executes all 4 strategies × 4 scenarios = 16 simulation runs.
All results are saved to SQLite and exported as CSV for the research paper.

Usage:
    python experiments/run_experiments.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
import yaml
import json
import time
from pathlib import Path
from rich.console import Console
from rich.table   import Table
from rich.progress import track

from core.simulation_engine import SimulationEngine, SimConfig
from core.task_generator    import WorkloadConfig
from telemetry.database     import TelemetryDB
from telemetry.collector    import TelemetryCollector

console = Console()

STRATEGIES = ["edge_only", "cloud_only", "threshold", "adaptive"]
SCENARIO_DIR = Path(__file__).parent / "scenarios"
RESULTS_DIR  = Path("results")


def load_scenario(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def run_single(scenario_cfg: dict, strategy: str, db: TelemetryDB) -> dict:
    """Run one simulation and return result dict."""
    run_id   = str(uuid.uuid4())[:8]
    sc       = scenario_cfg
    net      = sc.get("network", {})
    nodes    = sc.get("nodes", {})
    sim_cfg  = sc.get("simulation", {})
    wl       = sc.get("workload", {})

    workload = WorkloadConfig(
        pattern          = wl.get("pattern", "poisson"),
        base_rate        = wl.get("base_rate", 3.0),
        burst_size       = wl.get("burst_size", 30),
        burst_interval_s = wl.get("burst_interval_s", 20.0),
        ramp_start_rate  = wl.get("ramp_start_rate", 0.5),
        ramp_end_rate    = wl.get("ramp_end_rate", 10.0),
        ramp_duration_s  = wl.get("ramp_duration_s", 60.0),
        size_kb_range    = tuple(wl.get("size_kb_range", [50, 1024])),
        complexity_range = tuple(wl.get("complexity_range", [1, 8])),
        deadline_ms_range= tuple(wl.get("deadline_ms_range", [200, 1500])),
    )

    scenario_name = f"{sc['name']}_{strategy}"

    cfg = SimConfig(
        duration_s       = sim_cfg.get("duration_s", 120),
        sim_speed        = 0,   # max speed for batch runs
        strategy         = strategy,
        scenario_name    = scenario_name,
        run_id           = run_id,
        workload         = workload,
        edge1_latency_ms = net.get("edge1_latency_ms", 5),
        edge1_bw_mbps    = net.get("edge1_bw_mbps", 200),
        edge2_latency_ms = net.get("edge2_latency_ms", 8),
        edge2_bw_mbps    = net.get("edge2_bw_mbps", 150),
        cloud_latency_ms = net.get("cloud_latency_ms", 80),
        cloud_bw_mbps    = net.get("cloud_bw_mbps", 1000),
        edge1_cores      = nodes.get("edge1_cores", 4),
        edge1_speed_ghz  = nodes.get("edge1_speed_ghz", 2.0),
        edge2_cores      = nodes.get("edge2_cores", 4),
        edge2_speed_ghz  = nodes.get("edge2_speed_ghz", 2.2),
        cloud_cores      = nodes.get("cloud_cores", 16),
        cloud_speed_ghz  = nodes.get("cloud_speed_ghz", 3.5),
    )

    collector = TelemetryCollector(db, scenario_name, run_id, strategy)

    engine = SimulationEngine(
        cfg,
        telemetry_cb    = collector.on_snapshot,
        task_complete_cb= collector.on_task_complete,
    )

    t0 = time.time()
    engine.run()
    elapsed = time.time() - t0

    results = engine.get_results()
    results["run_id"]  = run_id
    results["wall_time_s"] = round(elapsed, 2)

    # Persist
    for task in engine.completed_tasks + engine.dropped_tasks:
        db.insert_task(task, scenario_name, run_id)
    db.insert_run_result(results)

    return results


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    db = TelemetryDB(str(RESULTS_DIR / "simulation.db"))

    scenario_files = sorted(SCENARIO_DIR.glob("scenario_*.yaml"))
    total_runs = len(scenario_files) * len(STRATEGIES)

    console.print(f"\n[bold cyan]>> Starting batch experiments[/bold cyan]")
    console.print(f"   Scenarios : {len(scenario_files)}")
    console.print(f"   Strategies: {len(STRATEGIES)}")
    console.print(f"   Total runs: {total_runs}\n")

    all_results = []

    for sc_path in scenario_files:
        sc_cfg = load_scenario(sc_path)
        console.print(f"\n[bold yellow]Scenario: {sc_cfg['name']}[/bold yellow]  -- {sc_cfg.get('description','')}")

        for strategy in STRATEGIES:
            console.print(f"  Running [{strategy}]...", end=" ")
            try:
                result = run_single(sc_cfg, strategy, db)
                all_results.append(result)
                console.print(
                    f"[green]OK[/green] "
                    f"tasks={result['tasks_completed']}, "
                    f"lat={result['avg_latency_ms']:.1f}ms, "
                    f"SLA={result['sla_violation_rate']*100:.1f}%, "
                    f"wall={result['wall_time_s']}s"
                )
            except Exception as e:
                console.print(f"[red]ERROR: {e}[/red]")

    # Export CSVs
    paths = db.export_csv(str(RESULTS_DIR))
    console.print(f"\n[bold green]** All runs complete. CSVs exported:[/bold green]")
    for k, v in paths.items():
        console.print(f"   {k}: {v}")

    # Print summary table
    _print_summary(all_results)
    db.close()


def _print_summary(results: list[dict]) -> None:
    table = Table(title="\nResults Summary", style="bold", header_style="bold cyan")
    table.add_column("Scenario",  style="yellow")
    table.add_column("Strategy",  style="cyan")
    table.add_column("Completed", justify="right")
    table.add_column("Avg Lat",   justify="right")
    table.add_column("p95 Lat",   justify="right")
    table.add_column("SLA Viol",  justify="right")
    table.add_column("Thrput",    justify="right")

    for r in results:
        table.add_row(
            r.get("scenario","?"),
            r.get("strategy","?"),
            str(r.get("tasks_completed",0)),
            f"{r.get('avg_latency_ms',0):.1f} ms",
            f"{r.get('p95_latency_ms',0):.1f} ms",
            f"{r.get('sla_violation_rate',0)*100:.1f}%",
            f"{r.get('throughput_per_s',0):.2f}/s",
        )
    console.print(table)


if __name__ == "__main__":
    main()
