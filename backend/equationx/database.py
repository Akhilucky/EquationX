"""Persistent equation store using SQLite."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any

_db_path: Path = Path.home() / ".equationx" / "equations.db"
_local = threading.local()


def _get_connection() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(_db_path))
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db(path: Optional[str] = None):
    global _db_path
    if path:
        _db_path = Path(path)
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS equations (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            latex TEXT NOT NULL,
            complexity INTEGER NOT NULL,
            mse REAL NOT NULL,
            variables TEXT NOT NULL,
            target TEXT NOT NULL,
            system_type TEXT,
            pareto_front TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'running',
            progress REAL DEFAULT 0.0,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS forecast_results (
            id TEXT PRIMARY KEY,
            equation_id TEXT,
            horizon_minutes INTEGER,
            trajectory TEXT,
            threshold_breach INTEGER,
            time_to_breach REAL,
            peak_value REAL,
            steady_state REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (equation_id) REFERENCES equations(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            key_hash TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def save_equation(
    eq_id: str, job_id: str, latex: str, complexity: int, mse: float,
    variables: List[str], target: str, system_type: Optional[str] = None,
    pareto_front: Optional[List[Dict]] = None,
):
    conn = _get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO equations
           (id, job_id, latex, complexity, mse, variables, target, system_type, pareto_front)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (eq_id, job_id, latex, complexity, mse, json.dumps(variables),
         target, system_type, json.dumps(pareto_front) if pareto_front else None),
    )
    conn.commit()


def list_equations() -> List[Dict[str, Any]]:
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM equations ORDER BY created_at DESC"
    ).fetchall()
    result = []
    for row in rows:
        eq = dict(row)
        eq["variables"] = json.loads(eq["variables"])
        if eq.get("pareto_front"):
            eq["pareto_front"] = json.loads(eq["pareto_front"])
        result.append(eq)
    return result


def get_equation(eq_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    row = conn.execute(
        "SELECT * FROM equations WHERE id = ?", (eq_id,)
    ).fetchone()
    if row is None:
        return None
    eq = dict(row)
    eq["variables"] = json.loads(eq["variables"])
    if eq.get("pareto_front"):
        eq["pareto_front"] = json.loads(eq["pareto_front"])
    return eq


def save_job_status(job_id: str, status: str, progress: float = 0.0, error: Optional[str] = None):
    conn = _get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO jobs (job_id, status, progress, error, updated_at)
           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
        (job_id, status, progress, error),
    )
    conn.commit()


def get_job_status_from_db(job_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    row = conn.execute(
        "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
    ).fetchone()
    return dict(row) if row else None


def save_api_key(key_hash: str, name: str):
    conn = _get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO api_keys (key_hash, name) VALUES (?, ?)",
        (key_hash, name),
    )
    conn.commit()


def validate_api_key(key_hash: str) -> bool:
    conn = _get_connection()
    row = conn.execute(
        "SELECT 1 FROM api_keys WHERE key_hash = ? AND is_active = 1",
        (key_hash,),
    ).fetchone()
    return row is not None
