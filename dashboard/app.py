"""
dashboard/app.py
Entry point for the live simulation dashboard.
Run:  python dashboard/app.py
Then open:  http://localhost:8050
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dash
import dash_bootstrap_components as dbc
from dashboard.layouts   import build_layout
from dashboard.callbacks import register_callbacks

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    title="EdgeCare AI - Adaptive Edge-Cloud Simulator",
    update_title=None,
    suppress_callback_exceptions=True,
)

app.layout = build_layout()
register_callbacks(app)

if __name__ == "__main__":
    print("\n>> Starting Edge-Cloud Offloading Simulator Dashboard")
    print("   Open your browser at: http://localhost:8050\n")
    app.run(debug=False, port=8050, threaded=True)
