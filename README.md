# Adaptive Edge–Cloud Task Offloading Simulator

A software-defined simulation framework for adaptive task offloading between edge and cloud nodes.

## Setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## Run

```bash
# Run the live dashboard
python dashboard/app.py

# Run batch experiments
python experiments/run_experiments.py

# Generate paper figures
python analysis/generate_figures.py
```

## Project Structure

```
capstone/
├── core/               # Simulation engine, tasks, nodes, network
├── decision/           # Adaptive engine + 4 strategies
├── telemetry/          # Metrics collection & SQLite storage
├── dashboard/          # Real-time Dash web UI
├── experiments/        # Scenario configs & batch runner
├── analysis/           # Statistical analysis & figure generation
└── results/            # Auto-generated outputs
```
