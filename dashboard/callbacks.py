"""
dashboard/callbacks.py
Dash callback definitions for the modern EdgeCare AI simulator.
Handles:
  - Tab switching between Layman, Research, and Brain modes
  - Simulation controls (Start, Stop, Code Blue Surge, Wi-Fi Glitch)
  - Live chart rendering, layman narrative event stream, and decision brain meters
"""
from __future__ import annotations
import uuid
import threading
from collections import deque, defaultdict
from typing import Any

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, no_update, html
from dash.exceptions import PreventUpdate

from core.simulation_engine import SimulationEngine, SimConfig
from core.task_generator    import WorkloadConfig
from telemetry.database     import TelemetryDB
from telemetry.collector    import TelemetryCollector
from dashboard.medical_scenario import generate_eli5_narration

# ── Shared state (module-level) ──────────────────────────────────────
_engine    : SimulationEngine | None = None
_collector : TelemetryCollector | None = None
_db        : TelemetryDB | None = None
_sim_thread: threading.Thread | None = None

# Rolling data for charts (in-memory for speed)
_latency_history  : deque = deque(maxlen=300)
_throughput_window: deque = deque(maxlen=60)   # tasks completed per tick
_last_completed   : int   = 0
_fault_active     : bool  = False

DARK_LAYOUT = dict(
    paper_bgcolor="#111726",
    plot_bgcolor ="#0b0f19",
    font         =dict(color="#94a3b8", family="Plus Jakarta Sans, sans-serif", size=10),
    margin       =dict(l=35, r=10, t=10, b=25),
    legend       =dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10, color="#cbd5e1")),
    xaxis        =dict(gridcolor="#1e293b", zerolinecolor="#1e293b"),
    yaxis        =dict(gridcolor="#1e293b", zerolinecolor="#1e293b"),
)

NODE_COLORS = {"edge_1": "#38bdf8", "edge_2": "#10b981", "cloud": "#a855f7"}


def register_callbacks(app) -> None:
    """Register all Dash callbacks with the given app instance."""

    # ── 1. Tab Navigation Switcher ──────────────────────────────────
    @app.callback(
        Output("tab-layman-content",   "style"),
        Output("tab-research-content", "style"),
        Output("tab-brain-content",    "style"),
        Input("main-tabs", "active_tab"),
    )
    def switch_tabs(active_tab: str):
        show = {"display": "block"}
        hide = {"display": "none"}
        if active_tab == "tab-research":
            return hide, show, hide
        elif active_tab == "tab-brain":
            return hide, hide, show
        return show, hide, hide

    # ── 2. Slider Value Live Labels ─────────────────────────────────
    @app.callback(
        Output("rate-val-display",  "children"),
        Output("speed-val-display", "children"),
        Input("rate-slider",  "value"),
        Input("speed-slider", "value"),
    )
    def update_slider_labels(rate_val, speed_val):
        return f"{rate_val:.1f} tasks/s", f"{int(speed_val)}x"

    # ── 3. Start / Stop / Burst / Fault Controls ────────────────────
    @app.callback(
        Output("sim-state",          "data"),
        Output("live-interval",      "disabled"),
        Output("status-bar",         "children"),
        Output("header-pulse",       "className"),
        Output("header-status-text", "children"),
        Input("btn-start",  "n_clicks"),
        Input("btn-stop",   "n_clicks"),
        Input("btn-burst",  "n_clicks"),
        Input("btn-fault",  "n_clicks"),
        State("sim-state",        "data"),
        State("strategy-selector","value"),
        State("workload-selector","value"),
        State("rate-slider",      "value"),
        State("speed-slider",     "value"),
        prevent_initial_call=True,
    )
    def control_simulation(n_start, n_stop, n_burst, n_fault,
                           state, strategy, pattern, rate, speed):
        global _engine, _collector, _db, _sim_thread, _latency_history
        global _throughput_window, _last_completed, _fault_active

        triggered = ctx.triggered_id

        if triggered == "btn-start":
            if _engine:
                _engine.stop()
            if _sim_thread and _sim_thread.is_alive():
                _sim_thread.join(timeout=1)

            _latency_history.clear()
            _throughput_window.clear()
            _last_completed = 0
            _fault_active   = False

            run_id   = str(uuid.uuid4())[:8]
            scenario = f"{pattern}_{strategy}"

            _db        = TelemetryDB("results/simulation.db")
            _collector = TelemetryCollector(_db, scenario=scenario, run_id=run_id, strategy=strategy)

            cfg = SimConfig(
                duration_s   = 600.0,
                sim_speed    = float(speed),
                strategy     = strategy,
                scenario_name= scenario,
                run_id       = run_id,
                workload     = WorkloadConfig(pattern=pattern, base_rate=float(rate)),
            )
            _engine = SimulationEngine(
                cfg,
                telemetry_cb    = _collector.on_snapshot,
                task_complete_cb= _collector.on_task_complete,
            )
            _sim_thread = _engine.run_async()

            new_state = {"running": True, "run_id": run_id, "strategy": strategy}
            msg = f"🟢 Simulation Active - Run ID: {run_id} | Strategy: {strategy} | Pattern: {pattern}"
            return new_state, False, msg, "status-pulse green", "Simulating Live Traffic"

        elif triggered == "btn-stop":
            if _engine:
                _engine.stop()
            _fault_active = False
            return (
                {**state, "running": False},
                True,
                "⏹ Simulation Stopped. Ready for new run.",
                "status-pulse yellow",
                "Engine Idle",
            )

        elif triggered == "btn-burst":
            if _engine and state.get("running"):
                _engine.generator.inject_burst(size=25)
                return (
                    no_update,
                    no_update,
                    "🚨 CODE BLUE SURGE: Sudden batch of 25 emergency patient tasks injected!",
                    "status-pulse yellow",
                    "Emergency Surge Active",
                )
            raise PreventUpdate

        elif triggered == "btn-fault":
            if _engine and state.get("running"):
                _fault_active = True
                _engine.network.inject_fault("edge_1", extra_latency_ms=150, bw_factor=0.1)
                _engine.network.inject_fault("edge_2", extra_latency_ms=120, bw_factor=0.15)

                def _clear():
                    global _fault_active
                    if _engine:
                        _engine.network.clear_fault("edge_1")
                        _engine.network.clear_fault("edge_2")
                    _fault_active = False

                threading.Timer(10.0, _clear).start()
                return (
                    no_update,
                    no_update,
                    "⚡ WI-FI GLITCH: Hospital Ward link latency spiked to 150ms! Auto-recovering in 10s...",
                    "status-pulse red",
                    "Link Degradation Fault Active",
                )
            raise PreventUpdate

        raise PreventUpdate

    # ── 4. Comprehensive Telemetry & UI Updates ─────────────────────
    @app.callback(
        # Research mode outputs
        Output("latency-chart",        "figure"),
        Output("cpu-chart",            "figure"),
        Output("routing-pie",          "figure"),
        Output("queue-chart",          "figure"),
        Output("throughput-chart",     "figure"),
        Output("decision-trace",       "children"),
        Output("tasks-total",          "children"),
        Output("tasks-completed",      "children"),
        Output("tasks-dropped",        "children"),
        Output("avg-latency",          "children"),
        Output("p95-latency",          "children"),
        Output("sla-rate",             "children"),
        Output("sim-time-display",     "children"),
        # Layman mode outputs
        Output("layman-feed-container","children"),
        Output("layman-safe-pct",      "children"),
        Output("layman-breach-count",  "children"),
        Output("layman-routing-pie",   "figure"),
        Output("topology-link-status", "children"),
        Output("topology-link-status", "className"),
        Output("edge1-metrics-badge",  "children"),
        Output("edge2-metrics-badge",  "children"),
        Output("cloud-metrics-badge",  "children"),
        Output("edge1-pulse",          "className"),
        Output("edge2-pulse",          "className"),
        Output("device-output-badge",  "children"),
        # Decision Brain outputs
        Output("meter-latency",        "value"),
        Output("meter-latency-val",    "children"),
        Output("meter-bandwidth",      "value"),
        Output("meter-bandwidth-val",  "children"),
        Output("meter-cpu",            "value"),
        Output("meter-cpu-val",        "children"),
        Output("meter-queue",          "value"),
        Output("meter-queue-val",      "children"),
        Output("meter-size",           "value"),
        Output("meter-size-val",       "children"),
        Output("meter-complexity",     "value"),
        Output("meter-complexity-val", "children"),
        Output("brain-score-display",  "children"),
        Output("brain-decision-badge", "children"),
        Input("live-interval", "n_intervals"),
        State("sim-state",     "data"),
        prevent_initial_call=True,
    )
    def update_all_views(n_intervals, state):
        global _last_completed, _fault_active

        if not _collector or not state.get("running"):
            raise PreventUpdate

        kpis      = _collector.live_kpis()
        snapshots = _collector.latest_snapshots(60)
        tasks     = _collector.latest_tasks(50)

        # Accumulate latency
        for t in tasks:
            if t.get("total_latency_ms") and t.get("total_latency_ms") > 0:
                _latency_history.append({
                    "time"   : t.get("completed_at", 0),
                    "latency": t["total_latency_ms"],
                    "node"   : t.get("assigned_node", "?"),
                })

        # Throughput
        cur_completed = kpis["completed"]
        delta = cur_completed - _last_completed
        _last_completed = cur_completed
        _throughput_window.append(delta)

        sim_time = snapshots[-1]["sim_time"] if snapshots else 0.0

        # Build figures
        lat_fig     = _build_latency_chart()
        cpu_fig     = _build_cpu_chart(snapshots)
        routing_fig = _build_routing_pie(tasks)
        queue_fig   = _build_queue_chart(snapshots)
        thpt_fig    = _build_throughput_chart()
        raw_trace   = _build_decision_trace(tasks)

        # Layman feed
        layman_feed = [generate_eli5_narration(t) for t in reversed(tasks[-15:])]
        if not layman_feed:
            layman_feed = [html.Div("Generating patient tasks...", className="text-secondary small fst-italic p-2 text-center")]

        safe_pct = f"{(1.0 - kpis.get('sla_violation_rate', 0.0)) * 100:.1f}%"
        breach_cnt = f"{kpis.get('sla_violated', 0)}"

        # Topology indicators
        latest_nodes = snapshots[-1].get("nodes", {}) if snapshots else {}
        e1_cpu = latest_nodes.get("edge_1", {}).get("cpu_utilization", 0.0) * 100
        e1_q   = latest_nodes.get("edge_1", {}).get("queue_length", 0)
        e2_cpu = latest_nodes.get("edge_2", {}).get("cpu_utilization", 0.0) * 100
        e2_q   = latest_nodes.get("edge_2", {}).get("queue_length", 0)
        c_cpu  = latest_nodes.get("cloud", {}).get("cpu_utilization", 0.0) * 100

        e1_badge = f"Queue: {e1_q} | CPU: {e1_cpu:.1f}%"
        e2_badge = f"Queue: {e2_q} | CPU: {e2_cpu:.1f}%"
        c_badge  = f"CPU: {c_cpu:.1f}% (16 Cores)"

        if _fault_active:
            link_text = "⚡ 150 ms (DEGRADED)"
            link_class = "small font-mono text-danger fw-bold"
            e1_pulse = "status-pulse red"
            e2_pulse = "status-pulse red"
            dev_badge = [dbc.Badge("Wi-Fi Glitch Active", color="danger")]
        else:
            link_text = "~6 ms (Pristine Wi-Fi)"
            link_class = "small font-mono text-success fw-bold"
            e1_pulse = "status-pulse yellow" if e1_cpu > 70 else "status-pulse green"
            e2_pulse = "status-pulse yellow" if e2_cpu > 70 else "status-pulse green"
            dev_badge = [dbc.Badge("50+ Devices Active", color="success")]

        # Brain meters from latest task
        last_task = tasks[-1] if tasks else {}
        t_score = last_task.get("offload_score", 0.0) or 0.0
        t_lat   = 150.0 if _fault_active else 8.0
        t_bw    = 20.0  if _fault_active else 180.0
        t_size  = last_task.get("size_kb", 80.0)
        t_cplx  = last_task.get("complexity", 4.0)

        # Score display
        score_str = f"{t_score:.2f}"
        if t_score < 0.5:
            badge = [dbc.Badge("Target: Local Ward Edge Server", color="success", className="px-3 py-1")]
        else:
            badge = [dbc.Badge("Target: Regional Cloud Cluster", color="primary", className="px-3 py-1")]

        return (
            # Research mode
            lat_fig, cpu_fig, routing_fig, queue_fig, thpt_fig, raw_trace,
            f"{kpis.get('total_tasks', 0)}",
            f"{kpis.get('completed', 0)}",
            f"{kpis.get('dropped', 0)}",
            f"{kpis.get('avg_latency_ms', 0.0):.1f} ms",
            f"{kpis.get('p95_latency_ms', 0.0):.1f} ms",
            f"{kpis.get('sla_violation_rate', 0.0)*100:.1f}%",
            f"{sim_time:.1f} s",
            # Layman mode
            layman_feed, safe_pct, breach_cnt, routing_fig,
            link_text, link_class,
            e1_badge, e2_badge, c_badge,
            e1_pulse, e2_pulse, dev_badge,
            # Brain meters
            min(100, int(t_lat / 2.0)), f"{t_lat:.1f} ms",
            min(100, int(t_bw / 2.0)),  f"{t_bw:.1f} Mbps",
            min(100, int(e1_cpu)),       f"{e1_cpu:.1f}%",
            min(100, e1_q * 10),         f"{e1_q} tasks",
            min(100, int(t_size / 20.0)),f"{t_size:.1f} KB",
            min(100, int(t_cplx * 10)),  f"{t_cplx:.1f}/10",
            score_str, badge,
        )


# ── Chart builders ──────────────────────────────────────────────────

def _build_latency_chart() -> go.Figure:
    if not _latency_history:
        return _empty_figure("Waiting for live data...")
    data = list(_latency_history)
    by_node: dict[str, dict] = defaultdict(lambda: {"x": [], "y": []})
    for d in data:
        node = d["node"]
        by_node[node]["x"].append(d["time"])
        by_node[node]["y"].append(d["latency"])

    fig = go.Figure()
    for node, vals in by_node.items():
        fig.add_trace(go.Scattergl(
            x=vals["x"], y=vals["y"],
            mode="lines", name=node,
            line=dict(color=NODE_COLORS.get(node, "#94a3b8"), width=2),
        ))
    fig.update_layout(**DARK_LAYOUT, yaxis_title="Latency (ms)", xaxis_title="Sim Time (s)")
    return fig


def _build_cpu_chart(snapshots: list[dict]) -> go.Figure:
    if not snapshots:
        return _empty_figure("Waiting for node telemetry...")
    by_node: dict[str, dict] = defaultdict(lambda: {"x": [], "y": []})
    for snap in snapshots:
        t = snap["sim_time"]
        for nid, ns in snap.get("nodes", {}).items():
            by_node[nid]["x"].append(t)
            by_node[nid]["y"].append(ns.get("cpu_utilization", 0) * 100)

    fig = go.Figure()
    for node, vals in by_node.items():
        color = NODE_COLORS.get(node, "#94a3b8")
        fig.add_trace(go.Scattergl(
            x=vals["x"], y=vals["y"],
            mode="lines", name=node, fill="tozeroy",
            line=dict(color=color, width=1.5),
            fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.15)",
        ))
    fig.update_layout(**DARK_LAYOUT, yaxis_title="CPU Load (%)", yaxis_range=[0, 100])
    return fig


def _build_routing_pie(tasks: list[dict]) -> go.Figure:
    counts: dict[str, int] = defaultdict(int)
    for t in tasks:
        node = t.get("assigned_node") or "unknown"
        counts[node] += 1
    if not counts:
        return _empty_figure("No tasks routed yet")
    labels = list(counts.keys())
    values = list(counts.values())
    colors = [NODE_COLORS.get(l, "#94a3b8") for l in labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color="#0a0d14", width=2)),
        hole=0.55, textfont=dict(size=11, family="Plus Jakarta Sans"),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94a3b8", family="Plus Jakarta Sans", size=10),
        margin=dict(l=5, r=5, t=5, b=5),
        legend=dict(orientation="h", y=-0.1, font=dict(size=9)),
    )
    return fig


def _build_queue_chart(snapshots: list[dict]) -> go.Figure:
    if not snapshots:
        return _empty_figure("Waiting for queue snapshots...")
    by_node: dict[str, dict] = defaultdict(lambda: {"x": [], "y": []})
    for snap in snapshots:
        t = snap["sim_time"]
        for nid, ns in snap.get("nodes", {}).items():
            by_node[nid]["x"].append(t)
            by_node[nid]["y"].append(ns.get("queue_length", 0))

    fig = go.Figure()
    for node, vals in by_node.items():
        fig.add_trace(go.Scattergl(
            x=vals["x"], y=vals["y"],
            mode="lines", name=node,
            line=dict(color=NODE_COLORS.get(node, "#94a3b8"), width=1.8),
        ))
    fig.update_layout(**DARK_LAYOUT, yaxis_title="Tasks Queued")
    return fig


def _build_throughput_chart() -> go.Figure:
    vals = list(_throughput_window)
    if not vals:
        return _empty_figure("Waiting for throughput window...")
    fig = go.Figure(go.Bar(
        y=vals,
        marker=dict(color="#38bdf8", line=dict(color="rgba(56, 189, 248, 0.5)", width=1)),
        name="Tasks/tick",
    ))
    fig.update_layout(**DARK_LAYOUT, yaxis_title="Completed / Tick", xaxis_title="Recent Ticks")
    return fig


def _build_decision_trace(tasks: list[dict]) -> list:
    lines = []
    for t in reversed(tasks[-20:]):
        reason = t.get("decision_reason", "")
        node   = t.get("assigned_node", "?")
        lat    = t.get("total_latency_ms", 0)
        color  = NODE_COLORS.get(node, "#94a3b8")
        sla    = " ⚠️SLA" if t.get("sla_violated") else ""
        lines.append(
            html.Div(
                f"[{t.get('task_id','?')}] {reason} | lat={lat:.1f}ms{sla}",
                style={"color": color, "marginBottom": "3px"},
            )
        )
    return lines or [html.Div("Waiting for tasks...", className="text-secondary")]


def create_empty_fig(msg: str = "") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor="#111726",
        plot_bgcolor="#0b0f19",
        font=dict(color="#94a3b8", family="Plus Jakarta Sans, sans-serif", size=11),
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[dict(text=msg, x=0.5, y=0.5, showarrow=False,
                          font=dict(color="#64748b", size=12, family="Plus Jakarta Sans"))],
    )
    return fig


_empty_figure = create_empty_fig
