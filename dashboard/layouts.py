"""
dashboard/layouts.py
Defines the modern, glassmorphic layout for the Adaptive Edge-Cloud Simulator.
Includes:
  - Top header and control bar
  - Dual perspective tabs:
      1. 🏥 Smart Hospital IoT Ward (Layman-friendly real-world mode)
      2. 🔬 Engineering & Research Lab (Deep technical analytics)
      3. 🧠 Fuzzy Decision Brain (Live rule and inference inspector)
"""
from __future__ import annotations
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import dcc, html
from dashboard.medical_scenario import build_hospital_devices_grid


def create_empty_fig(msg: str = "Ready. Click ▶ Start to run.") -> go.Figure:
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



def build_layout() -> html.Div:
    return html.Div(
        className="px-4 py-3",
        style={"backgroundColor": "#0a0d14", "minHeight": "100vh"},
        children=[

            # ── Top Brand Header ──────────────────────────────────────────
            dbc.Row(className="mb-3 align-items-center", children=[
                dbc.Col([
                    html.Div([
                        html.Span("🏥 ", style={"fontSize": "1.8rem"}),
                        html.Span("EdgeCare AI", className="fw-extrabold text-white fs-4 me-2"),
                        dbc.Badge("v2.0 Adaptive Simulator", color="primary", className="me-2 fw-normal"),
                        dbc.Badge("IoT Medical & Research", color="info", className="fw-normal"),
                    ], className="d-flex align-items-center"),
                    html.Div(
                        "Autonomous Edge-Cloud Task Placement using Real-Time Network Sensing & Fuzzy Logic",
                        className="text-secondary small mt-1",
                    ),
                ], width=7),

                dbc.Col([
                    html.Div([
                        html.Span(className="status-pulse green me-2", id="header-pulse"),
                        html.Span("Engine Ready", id="header-status-text", className="fw-semibold text-white small me-3"),
                        html.Span("Sim Time: ", className="text-secondary small me-1"),
                        html.Span("0.0 s", id="sim-time-display", className="text-info font-mono fw-bold fs-5"),
                    ], className="d-flex align-items-center justify-content-end"),
                ], width=5),
            ]),

            # ── Global Control Console ────────────────────────────────────
            dbc.Card(className="glass-panel mb-3 p-3", children=[
                dbc.Row(className="align-items-center g-3", children=[
                    dbc.Col([
                        html.Label("Decision Strategy", className="text-secondary small fw-semibold mb-1"),
                        dcc.Dropdown(
                            id="strategy-selector",
                            options=[
                                {"label": "🧠 Adaptive (Fuzzy + Override)", "value": "adaptive"},
                                {"label": "⚖️ Static Threshold",          "value": "threshold"},
                                {"label": "📡 Edge Only (No Cloud)",       "value": "edge_only"},
                                {"label": "☁️ Cloud Only (No Edge)",       "value": "cloud_only"},
                            ],
                            value="adaptive",
                            clearable=False,
                            style={"backgroundColor": "#161d2d", "color": "#f1f5f9"},
                        ),
                    ], width=3),

                    dbc.Col([
                        html.Label("Workload Pattern", className="text-secondary small fw-semibold mb-1"),
                        dcc.Dropdown(
                            id="workload-selector",
                            options=[
                                {"label": "🌊 Poisson (Steady Patient Stream)",  "value": "poisson"},
                                {"label": "💥 Burst Spikes (Code Blue Surge)",    "value": "burst"},
                                {"label": "📈 Ramp Up (Shift Change Rush)",       "value": "ramp"},
                                {"label": "🔀 Mixed Multi-Pattern",               "value": "mixed"},
                            ],
                            value="poisson",
                            clearable=False,
                            style={"backgroundColor": "#161d2d", "color": "#f1f5f9"},
                        ),
                    ], width=3),

                    dbc.Col([
                        html.Div([
                            html.Label("Traffic Arrival Rate", className="text-secondary small fw-semibold mb-1"),
                            html.Span(id="rate-val-display", className="text-info small float-end font-mono"),
                        ]),
                        dcc.Slider(
                            id="rate-slider", min=0.5, max=15, step=0.5, value=3.0,
                            marks={0.5: "0.5", 5: "5", 10: "10", 15: "15 t/s"},
                            tooltip={"placement": "bottom", "always_visible": False},
                        ),
                    ], width=2),

                    dbc.Col([
                        html.Div([
                            html.Label("Simulation Speed", className="text-secondary small fw-semibold mb-1"),
                            html.Span(id="speed-val-display", className="text-info small float-end font-mono"),
                        ]),
                        dcc.Slider(
                            id="speed-slider", min=1, max=50, step=1, value=10,
                            marks={1: "1x", 10: "10x", 25: "25x", 50: "50x"},
                            tooltip={"placement": "bottom", "always_visible": False},
                        ),
                    ], width=2),

                    dbc.Col([
                        dbc.ButtonGroup([
                            dbc.Button("▶ Start", id="btn-start", color="success", className="btn-action-glow me-1"),
                            dbc.Button("⏹ Stop",  id="btn-stop",  color="danger",  className="btn-action-glow"),
                        ], className="w-100 mb-1"),
                        dbc.ButtonGroup([
                            dbc.Button("🚨 Code Blue Surge", id="btn-burst", color="warning", size="sm", className="btn-action-glow me-1", style={"fontSize": "0.72rem"}),
                            dbc.Button("⚡ Wi-Fi Glitch", id="btn-fault", color="secondary", size="sm", className="btn-action-glow", style={"fontSize": "0.72rem"}),
                        ], className="w-100"),
                    ], width=2),
                ]),
            ]),

            # ── Main Tabs: Layman Mode vs Research Lab vs Decision Brain ──
            dbc.Tabs(
                id="main-tabs",
                active_tab="tab-layman",
                className="custom-nav-tabs mb-3 border-0",
                children=[
                    dbc.Tab(
                        label="🏥 Smart Hospital IoT Ward (Layman Mode)",
                        tab_id="tab-layman",
                        tab_style={"cursor": "pointer"},
                    ),
                    dbc.Tab(
                        label="🔬 Engineering & Research Lab (Scientist Mode)",
                        tab_id="tab-research",
                        tab_style={"cursor": "pointer"},
                    ),
                    dbc.Tab(
                        label="🧠 Fuzzy Decision Brain (Live Rule Inspector)",
                        tab_id="tab-brain",
                        tab_style={"cursor": "pointer"},
                    ),
                ],
            ),

            # ── Tab Content Containers (Persistent DOM for zero-flicker live charts) ──
            html.Div(id="tab-layman-content",   children=build_layman_tab_layout(),   style={"display": "block"}),
            html.Div(id="tab-research-content", children=build_research_tab_layout(), style={"display": "none"}),
            html.Div(id="tab-brain-content",    children=build_brain_tab_layout(),    style={"display": "none"}),

            # ── Persistent Status Bar ─────────────────────────────────────
            dbc.Row(className="mt-3", children=[
                dbc.Col(
                    html.Div(
                        id="status-bar",
                        className="text-secondary small font-mono py-1 px-3 rounded glass-panel",
                        children="Ready. Click ▶ Start to run the live simulator.",
                    ),
                    width=12,
                ),
            ]),

            # ── Hidden State & Intervals ──────────────────────────────────
            dcc.Store(id="sim-state", data={"running": False, "run_id": "", "strategy": "adaptive"}),
            dcc.Interval(id="live-interval", interval=800, n_intervals=0, disabled=True),
        ],
    )


# ── Tab 1: Layman Hospital Layout ──────────────────────────────────────────

def build_layman_tab_layout() -> html.Div:
    return html.Div([

        # ── Real-World Devices Row ──
        html.Div([
            html.H5("Active Medical IoT Devices in Hospital", className="text-white fw-bold mb-1"),
            html.P(
                "In a connected hospital, different IoT instruments have vastly different computational needs. "
                "The simulator continuously decides whether each device's data should execute on local ward edge servers or in the cloud.",
                className="text-muted small mb-3",
            ),
            build_hospital_devices_grid(),
        ]),

        # ── Visual Hospital Network Flow Topology ──
        dbc.Card(className="glass-panel mb-3 p-3", children=[
            html.H6("Hospital Edge-Cloud Flow Topology & Active Node Health", className="text-white fw-bold mb-3"),
            dbc.Row(className="align-items-center text-center g-2", children=[

                # Column 1: Hospital Devices
                dbc.Col([
                    html.Div(className="topology-node h-100", children=[
                        html.Div("🏥 Hospital Floor", className="text-muted small fw-bold"),
                        html.Div("50+ IoT Medical Devices", className="fw-bold text-white fs-6 mt-1"),
                        html.Div("Streaming ECG, MRI, Vitals", className="text-secondary small mt-1", style={"fontSize": "0.75rem"}),
                        html.Div(id="device-output-badge", className="mt-2", children=[
                            dbc.Badge("Normal Stream", color="info", className="fw-normal"),
                        ]),
                    ]),
                ], width=3),

                # Arrow 1
                dbc.Col([
                    html.Div("─────▶", className="text-secondary fw-bold fs-5"),
                    html.Div("Local Wi-Fi / 5G", className="text-muted small", style={"fontSize": "0.7rem"}),
                    html.Div(id="topology-link-status", className="small font-mono text-success", children="~5 ms latency"),
                ], width=1),

                # Column 2: Edge Nodes
                dbc.Col([
                    dbc.Row([
                        dbc.Col(html.Div(className="topology-node mb-2", id="edge1-node-box", children=[
                            html.Div([
                                html.Span(className="status-pulse green me-1", id="edge1-pulse"),
                                html.Span("Ward Edge 1 (ICU)", className="text-white fw-bold small"),
                            ]),
                            html.Div("4 Cores @ 2.0 GHz", className="text-muted small", style={"fontSize": "0.7rem"}),
                            html.Div(id="edge1-metrics-badge", className="mt-1 small text-info", children="Queue: 0 | CPU: 0%"),
                        ]), width=12),
                        dbc.Col(html.Div(className="topology-node", id="edge2-node-box", children=[
                            html.Div([
                                html.Span(className="status-pulse green me-1", id="edge2-pulse"),
                                html.Span("Ward Edge 2 (Surgical)", className="text-white fw-bold small"),
                            ]),
                            html.Div("4 Cores @ 2.2 GHz", className="text-muted small", style={"fontSize": "0.7rem"}),
                            html.Div(id="edge2-metrics-badge", className="mt-1 small text-info", children="Queue: 0 | CPU: 0%"),
                        ]), width=12),
                    ]),
                ], width=4),

                # Arrow 2
                dbc.Col([
                    html.Div("─────▶", className="text-secondary fw-bold fs-5"),
                    html.Div("Hospital WAN Uplink", className="text-muted small", style={"fontSize": "0.7rem"}),
                    html.Div("~80 ms WAN RTT", className="small font-mono text-info"),
                ], width=1),

                # Column 3: Cloud Cluster
                dbc.Col([
                    html.Div(className="topology-node h-100", id="cloud-node-box", children=[
                        html.Div("☁️ Regional Health Cloud", className="text-muted small fw-bold"),
                        html.Div("16 High-Speed Cores", className="fw-bold text-white fs-6 mt-1"),
                        html.Div("Heavy AI Deep Learning", className="text-secondary small mt-1", style={"fontSize": "0.75rem"}),
                        html.Div(id="cloud-metrics-badge", className="mt-2 text-info small", children="CPU: 0%"),
                    ]),
                ], width=3),
            ]),
        ]),

        # ── Live Layman Feed & Safety Metrics ──
        dbc.Row(className="g-3", children=[
            # Left: Plain English Event Feed
            dbc.Col(dbc.Card(className="glass-panel h-100 p-3", children=[
                html.Div([
                    html.H6("🩺 Live Patient & Device Incident Feed (Explain-Like-I'm-5)", className="text-white fw-bold mb-1"),
                    html.P("Human-readable explanations of why the AI made each decision in real time.", className="text-muted small mb-2"),
                ]),
                html.Div(id="layman-feed-container", className="ticker-scroll", style={"minHeight": "240px"}, children=[
                    html.Div("Waiting for simulation to start... Click ▶ Start to begin generating patient vitals.", className="text-secondary small fst-italic p-3 text-center"),
                ]),
            ]), width=7),

            # Right: Patient Safety Scorecard
            dbc.Col(dbc.Card(className="glass-panel h-100 p-3", children=[
                html.H6("🛡️ Patient Safety & SLA Scorecard", className="text-white fw-bold mb-3"),
                dbc.Row(className="g-2 text-center mb-3", children=[
                    dbc.Col(html.Div(className="p-2 rounded bg-black bg-opacity-25", children=[
                        html.Div("Critical Alarms Kept", className="text-muted small", style={"fontSize": "0.7rem"}),
                        html.Div("100%", id="layman-safe-pct", className="text-success fw-bold fs-4"),
                    ]), width=6),
                    dbc.Col(html.Div(className="p-2 rounded bg-black bg-opacity-25", children=[
                        html.Div("Dangerous Delays", className="text-muted small", style={"fontSize": "0.7rem"}),
                        html.Div("0", id="layman-breach-count", className="text-danger fw-bold fs-4"),
                    ]), width=6),
                ]),
                html.Div("Live Task Placement Shares", className="text-secondary small fw-bold mb-1"),
                dcc.Graph(id="layman-routing-pie", figure=create_empty_fig("No routing shares yet"), style={"height": "180px"}, config={"displayModeBar": False}),
            ]), width=5),
        ]),
    ])


# ── Tab 2: Scientific Research Lab Layout ──────────────────────────────────

def build_research_tab_layout() -> html.Div:
    return html.Div([

        # ── KPI Cards Row ──
        dbc.Row(className="mb-3 g-2", children=[
            dbc.Col(_kpi_card("tasks-total",     "Tasks Generated",  "0",    "#38bdf8", "📦"), width=2),
            dbc.Col(_kpi_card("tasks-completed", "Completed",        "0",    "#10b981", "✅"), width=2),
            dbc.Col(_kpi_card("tasks-dropped",   "Dropped Tasks",    "0",    "#f43f5e", "❌"), width=2),
            dbc.Col(_kpi_card("avg-latency",     "Avg Latency",      "0 ms", "#a855f7", "⏱️"), width=2),
            dbc.Col(_kpi_card("p95-latency",     "p95 Latency",      "0 ms", "#f59e0b", "📈"), width=2),
            dbc.Col(_kpi_card("sla-rate",        "SLA Violation %",  "0%",   "#f43f5e", "⚠️"), width=2),
        ]),

        # ── Main Charts Row ──
        dbc.Row(className="mb-3 g-2", children=[
            dbc.Col(dbc.Card(className="glass-panel p-2", children=[
                html.Div("📊 End-to-End Latency Over Time (ms)", className="text-white small fw-bold px-2 py-1"),
                dcc.Graph(id="latency-chart", figure=create_empty_fig("Latency history appears here upon start"), style={"height": "250px"}, config={"displayModeBar": False}),
            ]), width=6),

            dbc.Col(dbc.Card(className="glass-panel p-2", children=[
                html.Div("🖥️ CPU Utilization per Compute Host (%)", className="text-white small fw-bold px-2 py-1"),
                dcc.Graph(id="cpu-chart", figure=create_empty_fig("CPU telemetry appears here upon start"), style={"height": "250px"}, config={"displayModeBar": False}),
            ]), width=3),

            dbc.Col(dbc.Card(className="glass-panel p-2", children=[
                html.Div("🎯 Offloading Destination Shares", className="text-white small fw-bold px-2 py-1"),
                dcc.Graph(id="routing-pie", figure=create_empty_fig("Routing shares appear here upon start"), style={"height": "250px"}, config={"displayModeBar": False}),
            ]), width=3),
        ]),

        # ── Second Charts Row ──
        dbc.Row(className="mb-3 g-2", children=[
            dbc.Col(dbc.Card(className="glass-panel p-2", children=[
                html.Div("📥 Host Queue Backlogs (Tasks Waiting)", className="text-white small fw-bold px-2 py-1"),
                dcc.Graph(id="queue-chart", figure=create_empty_fig("Queue backlogs appear here upon start"), style={"height": "220px"}, config={"displayModeBar": False}),
            ]), width=4),

            dbc.Col(dbc.Card(className="glass-panel p-2", children=[
                html.Div("⚡ Completion Throughput (tasks/sec)", className="text-white small fw-bold px-2 py-1"),
                dcc.Graph(id="throughput-chart", figure=create_empty_fig("Throughput appears here upon start"), style={"height": "220px"}, config={"displayModeBar": False}),
            ]), width=4),

            dbc.Col(dbc.Card(className="glass-panel p-2", children=[
                html.Div("🔍 Raw Decision Engine Trace", className="text-white small fw-bold px-2 py-1"),
                html.Div(id="decision-trace", className="ticker-scroll font-mono p-2", style={"maxHeight": "220px", "fontSize": "0.7rem"}),
            ]), width=4),
        ]),
    ])


# ── Tab 3: Fuzzy Decision Brain Inspector Layout ───────────────────────────

def build_brain_tab_layout() -> html.Div:
    return html.Div([
        dbc.Row(className="g-3", children=[
            # Left: Fuzzy Antecedent Meters
            dbc.Col(dbc.Card(className="glass-panel p-3 h-100", children=[
                html.H6("🧠 Live Multi-Parameter Sensing Inputs", className="text-white fw-bold mb-2"),
                html.P("The 6 real-time variables fed into the Mamdani Fuzzy Inference Engine for each task.", className="text-muted small mb-3"),

                _meter_row("Link Latency (ms)", "meter-latency", "0.0 ms", "#38bdf8"),
                _meter_row("Effective Bandwidth (Mbps)", "meter-bandwidth", "0.0 Mbps", "#10b981"),
                _meter_row("Edge CPU Strain (%)", "meter-cpu", "0.0%", "#f59e0b"),
                _meter_row("Queue Backlog (Tasks)", "meter-queue", "0", "#f43f5e"),
                _meter_row("Task Payload Size (KB)", "meter-size", "0.0 KB", "#a855f7"),
                _meter_row("Compute Complexity (1-10)", "meter-complexity", "0.0", "#e2e8f0"),
            ]), width=6),

            # Right: Defuzzified Offload Score & Rules Inspector
            dbc.Col(dbc.Card(className="glass-panel p-3 h-100", children=[
                html.H6("🎯 Defuzzified Offload Score & Override Layer", className="text-white fw-bold mb-2"),
                html.P("Scores below 0.50 favor local Edge; scores >= 0.50 divert to Cloud.", className="text-muted small mb-3"),

                # Big Score Gauge Box
                html.Div(className="p-3 mb-3 rounded-3 text-center bg-black bg-opacity-30 border border-secondary border-opacity-25", children=[
                    html.Div("Current Calculated Offload Index", className="text-muted small mb-1"),
                    html.Div("0.00", id="brain-score-display", className="fw-extrabold fs-1 font-mono text-info"),
                    html.Div(id="brain-decision-badge", className="mt-1", children=[
                        dbc.Badge("Waiting for tasks", color="secondary"),
                    ]),
                ]),

                html.H6("Active Rule Logic & Physics Overrides", className="text-white fw-bold small mb-2"),
                html.Div(className="p-2 rounded bg-black bg-opacity-25 text-muted small font-mono", style={"fontSize": "0.75rem", "lineHeight": "1.5"}, children=[
                    html.Div("• R1: If CPU low AND Latency low AND Size small -> Route Edge (0.15)"),
                    html.Div("• R4: If CPU high (>75%) -> Overflow to Cloud (0.85)"),
                    html.Div("• R6: If Edge Latency high (>60ms) -> Strong Cloud Bias (0.75)"),
                    html.Div("• Hard Override: If Edge Latency > 1.3x Cloud Latency -> Force Cloud (0.72)"),
                ]),
            ]), width=6),
        ]),
    ])


def _kpi_card(elem_id: str, label: str, initial: str, color: str, icon: str = "") -> dbc.Card:
    return dbc.Card(
        className="glass-panel",
        style={"borderLeft": f"3px solid {color}"},
        children=[
            dbc.CardBody(className="py-2 px-3", children=[
                html.Div([
                    html.Span(icon, className="me-1 small"),
                    html.Span(label, className="text-secondary small fw-semibold"),
                ]),
                html.Div(initial, id=elem_id, className="fw-bold mt-1 font-mono",
                         style={"fontSize": "1.35rem", "color": color}),
            ]),
        ],
    )


def _meter_row(label: str, elem_id: str, initial_val: str, color: str) -> html.Div:
    return html.Div(className="mb-2", children=[
        html.Div([
            html.Span(label, className="text-secondary small"),
            html.Span(initial_val, id=f"{elem_id}-val", className="float-end font-mono text-white small"),
        ]),
        dbc.Progress(id=elem_id, value=0, max=100, color="info", className="mt-1", style={"height": "6px", "backgroundColor": "#161d2d"}),
    ])
