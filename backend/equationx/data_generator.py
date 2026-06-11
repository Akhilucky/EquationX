"""Synthetic data generator for 4 infrastructure system types."""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# System definitions (ground-truth ODEs)
# ---------------------------------------------------------------------------

SYSTEMS = {
    "queue": {
        "variables": ["queue_depth", "arrival_rate", "service_rate", "t"],
        "target": "queue_depth",
        "equation_latex": (
            r"\frac{d(queue)}{dt} = arrival\_rate - "
            r"service\_rate \cdot \frac{queue}{K + queue}"
        ),
        "description": "Queue system with saturation (Michaelis-Menten)",
    },
    "cpu": {
        "variables": ["cpu_usage", "load", "t"],
        "target": "cpu_usage",
        "equation_latex": r"\frac{d(c)}{dt} = \alpha \cdot (load - c) - \beta \cdot c",
        "description": "CPU autoscaling with decay",
    },
    "db_connections": {
        "variables": ["connections", "t"],
        "target": "connections",
        "equation_latex": r"\frac{d(conn)}{dt} = \lambda - \mu \cdot conn",
        "description": "DB connection pool dynamics",
    },
    "cache": {
        "variables": ["hit_rate", "t"],
        "target": "hit_rate",
        "equation_latex": r"\frac{d(hit)}{dt} = \gamma \cdot (1 - hit) - \delta \cdot hit",
        "description": "Cache utilization dynamics",
    },
}


def generate_queue_data(
    n_points: int = 500,
    dt: float = 1.0,
    noise_pct: float = 0.05,
    seed: Optional[int] = None,
) -> pd.DataFrame:
    """Generate queue system data.

    d(q)/dt = arrival_rate - service_rate * q / (K + q)
    """
    if seed is not None:
        np.random.seed(seed)

    K = 100.0  # saturation constant
    q = np.zeros(n_points)
    q[0] = 10.0

    # Time-varying arrival rate (sine wave + noise)
    t = np.arange(n_points) * dt
    arrival_rate = 8.0 + 2.0 * np.sin(2 * np.pi * t / 200) + np.random.normal(0, 0.3, n_points)
    arrival_rate = np.clip(arrival_rate, 0, 20)

    # Time-varying service rate
    service_rate = 1.2 + 0.1 * np.cos(2 * np.pi * t / 300) + np.random.normal(0, 0.05, n_points)
    service_rate = np.clip(service_rate, 0.5, 3.0)

    for i in range(1, n_points):
        dqdt = arrival_rate[i] - service_rate[i] * q[i - 1] / (K + q[i - 1])
        q[i] = q[i - 1] + dqdt * dt
        q[i] = max(0, q[i])

    # Add noise
    q_noisy = q + np.random.normal(0, q * noise_pct)

    return pd.DataFrame({
        "t": t,
        "queue_depth": q_noisy,
        "arrival_rate": arrival_rate,
        "service_rate": service_rate,
    })


def generate_cpu_data(
    n_points: int = 500,
    dt: float = 1.0,
    noise_pct: float = 0.05,
    seed: Optional[int] = None,
) -> pd.DataFrame:
    """Generate CPU autoscaling data.

    d(c)/dt = α*(load - c) - β*c
    """
    if seed is not None:
        np.random.seed(seed)

    alpha = 0.8
    beta = 0.3
    c = np.zeros(n_points)
    c[0] = 50.0

    t = np.arange(n_points) * dt
    load = 60.0 + 15.0 * np.sin(2 * np.pi * t / 250) + np.random.normal(0, 2, n_points)
    load = np.clip(load, 0, 100)

    for i in range(1, n_points):
        dcdt = alpha * (load[i] - c[i - 1]) - beta * c[i - 1]
        c[i] = c[i - 1] + dcdt * dt
        c[i] = max(0, min(100, c[i]))

    c_noisy = c + np.random.normal(0, c * noise_pct)

    return pd.DataFrame({
        "t": t,
        "cpu_usage": c_noisy,
        "load": load,
    })


def generate_db_data(
    n_points: int = 500,
    dt: float = 1.0,
    noise_pct: float = 0.05,
    seed: Optional[int] = None,
) -> pd.DataFrame:
    """Generate DB connection pool data.

    d(conn)/dt = λ - μ*conn
    """
    if seed is not None:
        np.random.seed(seed)

    lam = 5.0
    mu = 0.1
    conn = np.zeros(n_points)
    conn[0] = 10.0

    t = np.arange(n_points) * dt
    # Vary lambda with load pattern
    lam_t = lam + 2.0 * np.sin(2 * np.pi * t / 180) + np.random.normal(0, 0.2, n_points)
    lam_t = np.clip(lam_t, 1, 15)

    for i in range(1, n_points):
        dcdt = lam_t[i] - mu * conn[i - 1]
        conn[i] = conn[i - 1] + dcdt * dt
        conn[i] = max(0, conn[i])

    conn_noisy = conn + np.random.normal(0, conn * noise_pct)

    return pd.DataFrame({
        "t": t,
        "connections": conn_noisy,
    })


def generate_cache_data(
    n_points: int = 500,
    dt: float = 1.0,
    noise_pct: float = 0.05,
    seed: Optional[int] = None,
) -> pd.DataFrame:
    """Generate cache utilization data.

    d(hit)/dt = γ*(1 - hit) - δ*hit
    """
    if seed is not None:
        np.random.seed(seed)

    gamma = 0.6
    delta = 0.05
    hit = np.zeros(n_points)
    hit[0] = 0.3

    t = np.arange(n_points) * dt
    # Vary gamma (cache warming effect)
    gamma_t = gamma + 0.1 * np.sin(2 * np.pi * t / 150) + np.random.normal(0, 0.02, n_points)
    gamma_t = np.clip(gamma_t, 0.1, 1.0)

    for i in range(1, n_points):
        dhdt = gamma_t[i] * (1 - hit[i - 1]) - delta * hit[i - 1]
        hit[i] = hit[i - 1] + dhdt * dt
        hit[i] = max(0, min(1, hit[i]))

    hit_noisy = hit + np.random.normal(0, hit * noise_pct)
    hit_noisy = np.clip(hit_noisy, 0, 1)

    return pd.DataFrame({
        "t": t,
        "hit_rate": hit_noisy,
    })


# ---------------------------------------------------------------------------
# Unified generator
# ---------------------------------------------------------------------------

GENERATORS = {
    "queue": generate_queue_data,
    "cpu": generate_cpu_data,
    "db_connections": generate_db_data,
    "cache": generate_cache_data,
}


def generate_data(
    system_type: str,
    n_points: int = 500,
    dt: float = 1.0,
    noise_pct: float = 0.05,
    seed: Optional[int] = None,
) -> pd.DataFrame:
    """Generate data for a given system type."""
    if system_type not in GENERATORS:
        choices = list(GENERATORS.keys())
        raise ValueError(
            f"Unknown system type: {system_type}. Choose from: {choices}"
        )
    return GENERATORS[system_type](n_points=n_points, dt=dt, noise_pct=noise_pct, seed=seed)


def generate_all(seed: Optional[int] = None) -> Dict[str, pd.DataFrame]:
    """Generate data for all 4 system types."""
    return {name: gen(seed=seed) for name, gen in GENERATORS.items()}


def get_system_info(system_type: str) -> Dict:
    """Get metadata about a system type."""
    return SYSTEMS.get(system_type, {})
