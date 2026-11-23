"""
telemetry/database.py
SQLite-backed storage for tasks and periodic node snapshots.
Provides methods for insertion, querying, and export.
"""
from __future__ import annotations
import sqlite3
import json
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from core.task import Task


DEFAULT_DB_PATH = "results/simulation.db"


class TelemetryDB:
    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn   = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")  # concurrent writes
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id          TEXT PRIMARY KEY,
                task_type        TEXT,
                size_kb          REAL,
                complexity       REAL,
                deadline_ms      REAL,
                priority         INTEGER,
                created_at       REAL,
                queued_at        REAL,
                started_at       REAL,
                completed_at     REAL,
                assigned_node    TEXT,
                strategy_used    TEXT,
                status           TEXT,
                queue_wait_ms    REAL,
                execution_time_ms REAL,
                total_latency_ms REAL,
                sla_violated     INTEGER,
                offload_score    REAL,
                decision_reason  TEXT,
                scenario         TEXT,
                run_id           TEXT,
                recorded_at      TEXT
            );

            CREATE TABLE IF NOT EXISTS node_snapshots (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                sim_time         REAL,
                node_id          TEXT,
                node_type        TEXT,
                cpu_utilization  REAL,
                queue_length     INTEGER,
                tasks_completed  INTEGER,
                total_energy_j   REAL,
                strategy         TEXT,
                scenario         TEXT,
                run_id           TEXT,
                recorded_at      TEXT
            );

            CREATE TABLE IF NOT EXISTS run_results (
                run_id           TEXT PRIMARY KEY,
                scenario         TEXT,
                strategy         TEXT,
                duration_s       REAL,
                tasks_generated  INTEGER,
                tasks_completed  INTEGER,
                tasks_dropped    INTEGER,
                task_completion_rate REAL,
                throughput_per_s REAL,
                avg_latency_ms   REAL,
                p50_latency_ms   REAL,
                p95_latency_ms   REAL,
                p99_latency_ms   REAL,
                std_latency_ms   REAL,
                sla_violations   INTEGER,
                sla_violation_rate REAL,
                total_energy_j   REAL,
                node_distribution TEXT,
                recorded_at      TEXT
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Inserts
    # ------------------------------------------------------------------

    def insert_task(self, task: Task, scenario: str = "", run_id: str = "") -> None:
        d = task.to_dict()
        self._conn.execute("""
            INSERT OR REPLACE INTO tasks VALUES (
                :task_id, :task_type, :size_kb, :complexity, :deadline_ms,
                :priority, :created_at, :queued_at, :started_at, :completed_at,
                :assigned_node, :strategy_used, :status, :queue_wait_ms,
                :execution_time_ms, :total_latency_ms, :sla_violated,
                :offload_score, :decision_reason, :scenario, :run_id, :recorded_at
            )
        """, {**d, "scenario": scenario, "run_id": run_id,
               "recorded_at": datetime.utcnow().isoformat()})
        self._conn.commit()

    def insert_snapshot(self, snapshot: dict, strategy: str = "", scenario: str = "", run_id: str = "") -> None:
        now = datetime.utcnow().isoformat()
        for node_id, ns in snapshot.get("nodes", {}).items():
            self._conn.execute("""
                INSERT INTO node_snapshots
                (sim_time, node_id, node_type, cpu_utilization, queue_length,
                 tasks_completed, total_energy_j, strategy, scenario, run_id, recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                snapshot["sim_time"],
                node_id,
                ns.get("node_type",""),
                ns.get("cpu_utilization", 0),
                ns.get("queue_length", 0),
                ns.get("tasks_completed", 0),
                ns.get("total_energy_j", 0),
                strategy, scenario, run_id, now
            ))
        self._conn.commit()

    def insert_run_result(self, results: dict) -> None:
        results["node_distribution"] = json.dumps(results.get("node_distribution", {}))
        results["recorded_at"] = datetime.utcnow().isoformat()
        self._conn.execute("""
            INSERT OR REPLACE INTO run_results VALUES (
                :run_id, :scenario, :strategy, :duration_s,
                :tasks_generated, :tasks_completed, :tasks_dropped,
                :task_completion_rate, :throughput_per_s,
                :avg_latency_ms, :p50_latency_ms, :p95_latency_ms,
                :p99_latency_ms, :std_latency_ms,
                :sla_violations, :sla_violation_rate,
                :total_energy_j, :node_distribution, :recorded_at
            )
        """, results)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Queries → DataFrames
    # ------------------------------------------------------------------

    def get_tasks_df(self, run_id: str = "") -> pd.DataFrame:
        q = "SELECT * FROM tasks"
        params = []
        if run_id:
            q += " WHERE run_id = ?"
            params.append(run_id)
        return pd.read_sql_query(q, self._conn, params=params)

    def get_snapshots_df(self, run_id: str = "", node_id: str = "") -> pd.DataFrame:
        q = "SELECT * FROM node_snapshots WHERE 1=1"
        params = []
        if run_id:
            q += " AND run_id = ?"
            params.append(run_id)
        if node_id:
            q += " AND node_id = ?"
            params.append(node_id)
        return pd.read_sql_query(q, self._conn, params=params)

    def get_results_df(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM run_results", self._conn)

    def recent_tasks(self, n: int = 100) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM tasks ORDER BY rowid DESC LIMIT ?", (n,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def recent_snapshots(self, n: int = 200) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM node_snapshots ORDER BY id DESC LIMIT ?", (n,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_csv(self, out_dir: str = "results") -> dict[str, str]:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        paths = {}
        for table, fname in [
            ("tasks",          "tasks.csv"),
            ("node_snapshots", "node_snapshots.csv"),
            ("run_results",    "run_results.csv"),
        ]:
            df   = pd.read_sql_query(f"SELECT * FROM {table}", self._conn)
            path = os.path.join(out_dir, fname)
            df.to_csv(path, index=False)
            paths[table] = path
        return paths

    def close(self) -> None:
        self._conn.close()
