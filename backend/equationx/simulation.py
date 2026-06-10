"""Simulation module: parameter modification and trajectory prediction."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from .grammar import ASTNode
from .ode_solver import (
    solve_ode,
    forecast,
    detect_threshold_breach,
    estimate_steady_state,
)
from .models import SimulateResult


def simulate_scenario(
    equation: ASTNode,
    variable_names: List[str],
    target: str,
    parameter_changes: Dict[str, float],
    initial_conditions: Dict[str, float],
    horizon_minutes: int = 60,
    time_step_minutes: float = 1.0,
    threshold: Optional[float] = None,
) -> SimulateResult:
    """Run a what-if simulation with modified parameters.

    Args:
        equation: The discovered ODE.
        variable_names: All variable names.
        target: Target variable.
        parameter_changes: Dict of variable -> new value (replaces in initial conditions).
        initial_conditions: Base initial conditions.
        horizon_minutes: How far to simulate.
        time_step_minutes: Time step.
        threshold: Optional threshold to check.

    Returns:
        SimulateResult with baseline, modified trajectories, and analysis.
    """
    # Baseline trajectory
    base_t, base_y = solve_ode(
        equation,
        variable_names,
        target,
        initial_conditions,
        t_span=(0, horizon_minutes),
        t_step=time_step_minutes,
    )

    target_idx = variable_names.index(target) if target in variable_names else 0
    base_vals = base_y[target_idx]

    # Modified trajectory
    modified_ic = dict(initial_conditions)
    modified_ic.update(parameter_changes)

    mod_t, mod_y = solve_ode(
        equation,
        variable_names,
        target,
        modified_ic,
        t_span=(0, horizon_minutes),
        t_step=time_step_minutes,
    )
    mod_vals = mod_y[target_idx]

    # Convert to dicts
    base_trajectory = [
        {
            "time_minutes": float(base_t[i]),
            "value": float(base_vals[i]),
            "lower_ci": float(base_vals[i]),
            "upper_ci": float(base_vals[i]),
        }
        for i in range(len(base_t))
    ]

    modified_trajectory = [
        {
            "time_minutes": float(mod_t[i]),
            "value": float(mod_vals[i]),
            "lower_ci": float(mod_vals[i]),
            "upper_ci": float(mod_vals[i]),
        }
        for i in range(len(mod_t))
    ]

    # Analysis
    peak_value = float(np.max(mod_vals))
    steady_state = estimate_steady_state(modified_trajectory)

    # Time to stabilize: when std of last N points < 1% of mean
    time_to_stabilize = _compute_stabilize_time(mod_vals, time_step_minutes, horizon_minutes)

    # Threshold check
    breached = False
    if threshold is not None:
        breached, _ = detect_threshold_breach(modified_trajectory, threshold)

    # Recommendation
    recommendation = _generate_simulation_recommendation(
        target, parameter_changes, peak_value, steady_state, breached, threshold
    )

    return SimulateResult(
        baseline_trajectory=base_trajectory,
        modified_trajectory=modified_trajectory,
        peak_value=round(peak_value, 2),
        steady_state_value=round(steady_state, 2),
        time_to_stabilize_minutes=round(time_to_stabilize, 1),
        threshold_breach=breached,
        recommendation=recommendation,
    )


def _compute_stabilize_time(values: np.ndarray, step: float, horizon: float) -> float:
    """Estimate time to stabilize based on variance in a sliding window."""
    window = max(5, len(values) // 5)
    if len(values) < window:
        return horizon

    for i in range(len(values) - window):
        segment = values[i : i + window]
        mean = np.mean(segment)
        std = np.std(segment)
        if abs(mean) > 1e-6 and std / abs(mean) < 0.01:
            return i * step
        elif std < 0.1:
            return i * step

    return horizon


def _generate_simulation_recommendation(
    target: str,
    changes: Dict[str, float],
    peak: float,
    steady: float,
    breached: bool,
    threshold: Optional[float],
) -> str:
    """Generate recommendation from simulation results."""
    changes_desc = ", ".join(f"{k}={v}" for k, v in changes.items())

    if breached and threshold:
        return (
            f"With {changes_desc}, {target} peaks at {peak:.1f} and stabilizes at {steady:.1f}. "
            f"Threshold ({threshold}) still breached. Further changes needed."
        )
    elif not breached and threshold:
        return (
            f"With {changes_desc}, {target} peaks at {peak:.1f} and stabilizes at {steady:.1f}. "
            f"No threshold breach. This configuration is viable."
        )
    else:
        return (
            f"With {changes_desc}, {target} peaks at {peak:.1f} and stabilizes at {steady:.1f}. "
            f"System stabilizes in {_compute_stabilize_time_str(steady, peak)}."
        )


def _compute_stabilize_time_str(steady: float, peak: float) -> str:
    ratio = abs(peak - steady) / (abs(steady) + 1e-10)
    if ratio < 0.1:
        return "minutes"
    elif ratio < 0.5:
        return "tens of minutes"
    else:
        return "over an hour"
