"""
analysis/generate_figures.py
Reads results from SQLite/CSV and generates publication-quality figures
for the IEEE research paper.

Output: results/figures/*.png  (300 DPI, IEEE column width compatible)

Usage:
    python analysis/generate_figures.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from pathlib import Path

DB_PATH  = "results/simulation.db"
FIG_DIR  = Path("results/figures")
DPI      = 300

# IEEE two-column width ≈ 3.5 in; full-page ≈ 7.16 in
COL_W  = 3.5
PAGE_W = 7.16

STRATEGY_COLORS = {
    "edge_only" : "#58a6ff",
    "cloud_only": "#d2a8ff",
    "threshold" : "#ffa657",
    "adaptive"  : "#3fb950",
}
STRATEGY_LABELS = {
    "edge_only" : "Edge-Only",
    "cloud_only": "Cloud-Only",
    "threshold" : "Threshold",
    "adaptive"  : "Adaptive (Fuzzy)",
}

sns.set_theme(style="whitegrid", font_scale=0.85)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    results = pd.read_sql_query("SELECT * FROM run_results", conn)
    tasks   = pd.read_sql_query("SELECT * FROM tasks WHERE status='completed'", conn)
    conn.close()
    return results, tasks


def fig1_avg_latency_bar(results: pd.DataFrame) -> None:
    """Bar chart: Average latency per strategy per scenario."""
    fig, ax = plt.subplots(figsize=(PAGE_W, 3.0))
    scenarios  = results["scenario"].str.split("_").str[0].unique()
    strategies = results["strategy"].unique()
    x     = np.arange(len(scenarios))
    width = 0.18

    for i, strat in enumerate(strategies):
        sub = results[results["strategy"] == strat]
        vals = []
        for sc in scenarios:
            row = sub[sub["scenario"].str.startswith(sc)]
            vals.append(row["avg_latency_ms"].values[0] if len(row) else 0)
        ax.bar(x + i * width, vals, width, label=STRATEGY_LABELS.get(strat, strat),
               color=STRATEGY_COLORS.get(strat, "#888"), alpha=0.85, edgecolor="white", linewidth=0.5)

    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels([s.capitalize() for s in scenarios])
    ax.set_ylabel("Average Latency (ms)")
    ax.set_xlabel("Scenario")
    ax.set_title("Fig. 1 — Average Task Latency by Strategy and Scenario")
    ax.legend(framealpha=0.3)
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    plt.tight_layout()
    _save("fig1_avg_latency.png")


def fig2_sla_violation_bar(results: pd.DataFrame) -> None:
    """Bar chart: SLA violation rate per strategy per scenario."""
    fig, ax = plt.subplots(figsize=(PAGE_W, 3.0))
    scenarios  = results["scenario"].str.split("_").str[0].unique()
    strategies = results["strategy"].unique()
    x     = np.arange(len(scenarios))
    width = 0.18

    for i, strat in enumerate(strategies):
        sub = results[results["strategy"] == strat]
        vals = []
        for sc in scenarios:
            row = sub[sub["scenario"].str.startswith(sc)]
            vals.append(row["sla_violation_rate"].values[0] * 100 if len(row) else 0)
        ax.bar(x + i * width, vals, width, label=STRATEGY_LABELS.get(strat, strat),
               color=STRATEGY_COLORS.get(strat, "#888"), alpha=0.85, edgecolor="white", linewidth=0.5)

    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels([s.capitalize() for s in scenarios])
    ax.set_ylabel("SLA Violation Rate (%)")
    ax.set_xlabel("Scenario")
    ax.set_title("Fig. 2 — SLA Violation Rate by Strategy and Scenario")
    ax.legend(framealpha=0.3)
    plt.tight_layout()
    _save("fig2_sla_violations.png")


def fig3_cdf_latency(tasks: pd.DataFrame) -> None:
    """CDF of task latency for each strategy (normal scenario only)."""
    fig, ax = plt.subplots(figsize=(COL_W * 1.5, 3.0))
    sub = tasks[tasks["scenario"].str.startswith("normal")]

    for strat in sub["strategy_used"].unique():
        lats = sub[sub["strategy_used"] == strat]["total_latency_ms"].dropna()
        if len(lats) == 0:
            continue
        sorted_lats = np.sort(lats)
        cdf = np.arange(1, len(sorted_lats) + 1) / len(sorted_lats)
        ax.plot(sorted_lats, cdf,
                label=STRATEGY_LABELS.get(strat, strat),
                color=STRATEGY_COLORS.get(strat, "#888"),
                linewidth=1.8)

    ax.axvline(x=500, color="red", linestyle="--", alpha=0.6, linewidth=1, label="SLA = 500 ms")
    ax.set_xlabel("Task Latency (ms)")
    ax.set_ylabel("CDF")
    ax.set_title("Fig. 3 — Latency CDF (Normal Scenario)")
    ax.legend(framealpha=0.3, fontsize=8)
    ax.set_xlim(left=0)
    ax.set_ylim(0, 1.05)
    plt.tight_layout()
    _save("fig3_cdf_latency.png")


def fig4_throughput_bar(results: pd.DataFrame) -> None:
    """Grouped bar: throughput per strategy."""
    fig, ax = plt.subplots(figsize=(COL_W * 1.5, 3.0))
    sub = results.groupby("strategy")["throughput_per_s"].mean().reset_index()
    colors = [STRATEGY_COLORS.get(s, "#888") for s in sub["strategy"]]
    bars = ax.bar(
        [STRATEGY_LABELS.get(s, s) for s in sub["strategy"]],
        sub["throughput_per_s"],
        color=colors, edgecolor="white", linewidth=0.5, alpha=0.9,
    )
    ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=8)
    ax.set_ylabel("Avg Throughput (tasks/s)")
    ax.set_title("Fig. 4 — Average Throughput by Strategy")
    plt.tight_layout()
    _save("fig4_throughput.png")


def fig5_energy_bar(results: pd.DataFrame) -> None:
    """Grouped bar: energy proxy by strategy."""
    fig, ax = plt.subplots(figsize=(COL_W * 1.5, 3.0))
    sub = results.groupby("strategy")["total_energy_j"].mean().reset_index()
    colors = [STRATEGY_COLORS.get(s, "#888") for s in sub["strategy"]]
    bars = ax.bar(
        [STRATEGY_LABELS.get(s, s) for s in sub["strategy"]],
        sub["total_energy_j"],
        color=colors, edgecolor="white", linewidth=0.5, alpha=0.9,
    )
    ax.bar_label(bars, fmt="%.1f J", padding=3, fontsize=8)
    ax.set_ylabel("Energy Proxy (J)")
    ax.set_title("Fig. 5 — Energy Consumption Proxy by Strategy")
    plt.tight_layout()
    _save("fig5_energy.png")


def fig6_heatmap(results: pd.DataFrame) -> None:
    """Heatmap: avg latency [scenario × strategy]."""
    pivot = results.copy()
    pivot["sc_short"] = pivot["scenario"].str.split("_").str[0].str.capitalize()
    pivot["strat_label"] = pivot["strategy"].map(STRATEGY_LABELS)
    matrix = pivot.pivot_table(index="sc_short", columns="strat_label", values="avg_latency_ms")

    fig, ax = plt.subplots(figsize=(COL_W * 1.6, 2.8))
    sns.heatmap(
        matrix, annot=True, fmt=".0f", cmap="YlOrRd", ax=ax,
        linewidths=0.5, linecolor="white",
        cbar_kws={"label": "Avg Latency (ms)"},
    )
    ax.set_title("Fig. 6 — Latency Heatmap (Scenario × Strategy)")
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.tight_layout()
    _save("fig6_heatmap.png")


def _save(fname: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / fname
    plt.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Saved {path}")


def main() -> None:
    print("\n>> Generating IEEE paper figures from results database...")
    if not Path(DB_PATH).exists():
        print(f"  [!] Database not found at {DB_PATH}")
        print("  Run experiments first:  python experiments/run_experiments.py")
        return

    results, tasks = load_data()
    if results.empty:
        print("  [!] No results found. Run experiments first.")
        return

    print(f"  Loaded {len(results)} run results, {len(tasks)} completed tasks.\n")

    fig1_avg_latency_bar(results)
    fig2_sla_violation_bar(results)
    fig3_cdf_latency(tasks)
    fig4_throughput_bar(results)
    fig5_energy_bar(results)
    fig6_heatmap(results)

    print(f"\n[DONE] All figures saved to {FIG_DIR}/")


if __name__ == "__main__":
    main()
