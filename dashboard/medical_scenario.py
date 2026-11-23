"""
dashboard/medical_scenario.py
Provides real-world Smart Hospital / Medical IoT scenario mappings,
layman-friendly ELI5 narrative explanations, and visual component helpers.
"""
from __future__ import annotations
import random
from dash import html
import dash_bootstrap_components as dbc

# Real-world medical task definitions
MEDICAL_DEVICE_CATALOG = {
    "latency_sensitive": {
        "title": "ICU Bedside ECG Monitor",
        "device_id": "ECG-ICU-04",
        "icon": "💓",
        "badge_color": "danger",
        "sla_target": "200 ms",
        "description": "Real-time cardiac arrhythmia spike detection. Must alert ward nurses instantly.",
        "danger_if_delayed": "Dangerous delay in cardiac arrest defibrillation response.",
    },
    "compute_intensive": {
        "title": "3D MRI / CT Brain Segmentation",
        "device_id": "MRI-RAD-02",
        "icon": "🩻",
        "badge_color": "primary",
        "sla_target": "800 ms",
        "description": "Multi-layer deep learning tumor boundary identification requiring intensive GPU/CPU power.",
        "danger_if_delayed": "Surgical navigation assistance stalls during active procedure.",
    },
    "data_intensive": {
        "title": "Robotic Surgery 4K Endoscope",
        "device_id": "SURG-BOT-01",
        "icon": "📹",
        "badge_color": "warning",
        "sla_target": "500 ms",
        "description": "Continuous high-bitrate video stream requiring wide bandwidth links.",
        "danger_if_delayed": "Video frame stutter during precision laparoscopic surgery.",
    },
    "batch": {
        "title": "EHR Vitals & Lab Sync",
        "device_id": "EHR-SYNC-99",
        "icon": "📋",
        "badge_color": "info",
        "sla_target": "1500 ms",
        "description": "Periodic patient blood pressure, SpO2, and temperature trend archival.",
        "danger_if_delayed": "Minor delay in non-emergency historical chart updates.",
    },
}

NODE_NAMES_HUMAN = {
    "edge_1": "🏥 Ward Edge Server (Local ICU)",
    "edge_2": "🏢 Hospital Floor Edge Server",
    "cloud":  "☁️ Regional Healthcare Cloud Cluster",
}


def get_medical_metadata(task_type: str, task_id: str) -> dict:
    """Return clinical metadata for a simulated task."""
    base = MEDICAL_DEVICE_CATALOG.get(task_type, MEDICAL_DEVICE_CATALOG["latency_sensitive"])
    # Pseudo-random patient ID based on task_id
    patient_num = (abs(hash(task_id)) % 88) + 101
    return {
        **base,
        "patient_name": f"Patient #{patient_num}",
    }


def generate_eli5_narration(task: dict) -> html.Div:
    """
    Generate an engaging, layman-understandable explanation of what the system
    decided, why it made that choice, and what it means for patient safety.
    """
    t_type = task.get("task_type", "latency_sensitive")
    t_id   = task.get("task_id", "???")
    node   = task.get("assigned_node", "edge_1")
    lat    = task.get("total_latency_ms", 0.0)
    sla_violated = task.get("sla_violated", False)
    meta   = get_medical_metadata(t_type, t_id)
    node_name = NODE_NAMES_HUMAN.get(node, node)

    # Narrative generation based on routing logic
    if node in ["edge_1", "edge_2"]:
        if lat < 60:
            outcome = "⚡ Blazing Fast Local Execution!"
            story = (
                f"The local {node_name} had free processing power and pristine local Wi-Fi. "
                f"{meta['patient_name']}'s {meta['title']} was handled in just {lat:.1f}ms without "
                f"wasting time travelling over the public internet."
            )
            border_color = "#10b981"
            status_badge = dbc.Badge("Safe & Local", color="success", className="ms-2")
        else:
            outcome = "⚠️ Mild Local Queue Delay"
            story = (
                f"{meta['patient_name']}'s request ran on {node_name} but encountered queue contention "
                f"taking {lat:.1f}ms."
            )
            border_color = "#f59e0b"
            status_badge = dbc.Badge("Queued Local", color="warning", className="ms-2")
    else: # Cloud
        if t_type == "compute_intensive":
            outcome = "☁️ Offloaded to Heavy Cloud Cores"
            story = (
                f"{meta['title']} has intense compute requirements. The system intelligently diverted it "
                f"to the 16-core cloud data center ({lat:.1f}ms), keeping local hospital edge cores free "
                f"for critical cardiac monitors."
            )
            border_color = "#38bdf8"
            status_badge = dbc.Badge("Heavy Compute Cloud", color="primary", className="ms-2")
        elif "Adaptive" in (task.get("decision_reason") or "") and "lat=" in (task.get("decision_reason") or ""):
            outcome = "🛡️ Network Degraded — Cloud Failover Saved It!"
            story = (
                f"Hospital Wi-Fi or local links experienced degradation. Rather than letting {meta['patient_name']}'s "
                f"data get stuck in local network latency, the engine bypassed the edge straight to Cloud."
            )
            border_color = "#a855f7"
            status_badge = dbc.Badge("Link Failover", color="purple", className="ms-2")
        else:
            outcome = "☁️ Routed to Cloud Cluster"
            story = (
                f"{meta['patient_name']}'s {meta['title']} was processed by the regional cloud cluster "
                f"in {lat:.1f}ms."
            )
            border_color = "#94a3b8"
            status_badge = dbc.Badge("Cloud Processed", color="secondary", className="ms-2")

    if sla_violated:
        outcome = "🚨 Deadline Delayed"
        story += f" Warning: Exceeded critical deadline of {meta['sla_target']}."
        border_color = "#f43f5e"
        status_badge = dbc.Badge("SLA Breached", color="danger", className="ms-2")

    return html.Div(
        className="p-2 mb-2 rounded-3",
        style={
            "backgroundColor": "rgba(22, 29, 45, 0.75)",
            "borderLeft": f"4px solid {border_color}",
            "borderTop": "1px solid rgba(255,255,255,0.05)",
            "borderRight": "1px solid rgba(255,255,255,0.05)",
            "borderBottom": "1px solid rgba(255,255,255,0.05)",
        },
        children=[
            html.Div([
                html.Span(f"{meta['icon']} {meta['title']}", className="fw-bold text-white small"),
                html.Span(f" • {meta['patient_name']}", className="text-secondary small ms-1"),
                status_badge,
                html.Span(f"{lat:.1f} ms", className="float-end fw-bold font-mono small", style={"color": border_color}),
            ], className="mb-1"),
            html.Div(outcome, className="fw-semibold small", style={"color": border_color, "fontSize": "0.8rem"}),
            html.Div(story, className="text-muted", style={"fontSize": "0.75rem", "lineHeight": "1.3"}),
        ]
    )


def build_hospital_devices_grid() -> dbc.Row:
    """Build the showcase row of 4 real-world IoT hospital devices."""
    cols = []
    for t_key, dev in MEDICAL_DEVICE_CATALOG.items():
        col = dbc.Col(
            html.Div(
                className="medical-card h-100",
                children=[
                    html.Div([
                        html.Span(dev["icon"], style={"fontSize": "1.8rem"}, className="me-2"),
                        html.Span(dev["title"], className="fw-bold text-white", style={"fontSize": "0.95rem"}),
                    ], className="d-flex align-items-center mb-2"),
                    html.Div([
                        dbc.Badge(dev["device_id"], color="dark", className="me-1 font-mono text-secondary"),
                        dbc.Badge(f"Target: {dev['sla_target']}", color=dev["badge_color"], className="fw-normal"),
                    ], className="mb-2"),
                    html.Div(dev["description"], className="text-muted small mb-2", style={"fontSize": "0.78rem"}),
                    html.Div([
                        html.Span("⚠️ Risk: ", className="text-warning small fw-bold"),
                        html.Span(dev["danger_if_delayed"], className="text-secondary small", style={"fontSize": "0.72rem"}),
                    ], className="p-2 rounded bg-black bg-opacity-25"),
                ],
            ),
            width=3,
        )
        cols.append(col)
    return dbc.Row(cols, className="g-2 mb-3")
