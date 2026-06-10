"""ODE solver, forecasting, and threshold detection."""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d

from .grammar import ASTNode, BINARY_OPS, UNARY_OPS


# ---------------------------------------------------------------------------
# ODE Evaluation
# ---------------------------------------------------------------------------

def build_ode_rhs(
    equation: ASTNode,
    variable_names: List[str],
    target: str,
):
    """Build a numerical RHS function from an AST equation.

    The equation should represent d(target)/dt = f(...)
    """
    from sympy import Symbol, lambdify

    var_dict = {v: Symbol(v) for v in variable_names}
    var_dict["t"] = Symbol("t")
    expr = equation.to_sympy(var_dict)

    sympy_vars = [var_dict[v] for v in variable_names]
    func = lambdify(sympy_vars, expr, modules=["numpy", "math"])

    target_idx = variable_names.index(target) if target in variable_names else 0

    def rhs(t, y):
        """RHS for solve_ivp: y is the state vector."""
        state = {v: y[i] for i, v in enumerate(variable_names)}
        args = [state[v] for v in variable_names]
        try:
            dydt = float(func(*args))
            if math.isnan(dydt) or math.isinf(dydt):
                dydt = 0.0
        except Exception:
            dydt = 0.0

        dy = [0.0] * len(variable_names)
        dy[target_idx] = dydt
        return dy

    return rhs


def solve_ode(
    equation: ASTNode,
    variable_names: List[str],
    target: str,
    initial_conditions: Dict[str, float],
    t_span: Tuple[float, float],
    t_step: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Solve the ODE system numerically.

    Returns:
        t: time points
        y: solution array (n_variables x n_points)
    """
    y0 = [initial_conditions.get(v, 0.0) for v in variable_names]
    t_eval = np.arange(t_span[0], t_span[1] + t_step, t_step)
    if len(t_eval) == 0:
        t_eval = np.array([t_span[0], t_span[1]])

    rhs = build_ode_rhs(equation, variable_names, target)

    sol = solve_ivp(
        rhs,
        t_span,
        y0,
        t_eval=t_eval,
        method="RK45",
        rtol=1e-6,
        atol=1e-9,
        max_step=t_step * 2,
    )

    if not sol.success:
        # Fallback: simple Euler integration
        return _euler_solve(rhs, y0, t_eval, len(variable_names))

    return sol.t, sol.y


def _euler_solve(rhs, y0, t_eval, n_vars):
    """Fallback Euler integration."""
    y = np.zeros((n_vars, len(t_eval)))
    y[:, 0] = y0
    for i in range(1, len(t_eval)):
        dt = t_eval[i] - t_eval[i - 1]
        dydt = np.array(rhs(t_eval[i - 1], y[:, i - 1]))
        y[:, i] = y[:, i - 1] + np.array(dydt) * dt
    return t_eval, y


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------


def forecast(
    equation: ASTNode,
    variable_names: List[str],
    target: str,
    initial_conditions: Dict[str, float],
    horizon_minutes: int = 15,
    time_step_minutes: float = 1.0,
    noise_std: float = 0.05,
) -> List[ForecastPoint]:
    """Generate forecast with confidence intervals.

    Uses Monte Carlo perturbation for CI estimation.
    """
    t, y = solve_ode(
        equation,
        variable_names,
        target,
        initial_conditions,
        t_span=(0, horizon_minutes),
        t_step=time_step_minutes,
    )

    target_idx = variable_names.index(target) if target in variable_names else 0
    base_trajectory = y[target_idx]

    # Compute confidence intervals via noise perturbation
    n_mc = 20
    mc_results = []
    for _ in range(n_mc):
        perturbed_ic = {}
        for v, val in initial_conditions.items():
            perturbed_ic[v] = val * (1 + np.random.normal(0, noise_std))
        try:
            _, y_pert = solve_ode(
                equation,
                variable_names,
                target,
                perturbed_ic,
                t_span=(0, horizon_minutes),
                t_step=time_step_minutes,
            )
            mc_results.append(y_pert[target_idx])
        except Exception:
            mc_results.append(base_trajectory)

    mc_array = np.array(mc_results)
    lower = np.percentile(mc_array, 5, axis=0)
    upper = np.percentile(mc_array, 95, axis=0)

    points = []
    for i in range(len(t)):
        points.append({
            "time_minutes": float(t[i]),
            "value": float(base_trajectory[i]),
            "lower_ci": float(lower[i]),
            "upper_ci": float(upper[i]),
        })

    return points


# ---------------------------------------------------------------------------
# Threshold detection
# ---------------------------------------------------------------------------

def detect_threshold_breach(
    trajectory,
    threshold: float,
    threshold_variable: Optional[str] = None,
) -> Tuple[bool, Optional[float]]:
    """Detect if and when trajectory crosses the threshold.

    Returns:
        (breached, time_to_breach_minutes)
    """
    for i, pt in enumerate(trajectory):
        val = pt["value"] if isinstance(pt, dict) else pt.value
        if val >= threshold:
            if i == 0:
                return True, 0.0
            prev = trajectory[i - 1]
            prev_val = prev["value"] if isinstance(prev, dict) else prev.value
            prev_time = prev["time_minutes"] if isinstance(prev, dict) else prev.time_minutes
            pt_time = pt["time_minutes"] if isinstance(pt, dict) else pt.time_minutes
            frac = (threshold - prev_val) / (val - prev_val + 1e-12)
            breach_time = prev_time + frac * (pt_time - prev_time)
            return True, breach_time

    return False, None


# ---------------------------------------------------------------------------
# Steady-state estimation
# ---------------------------------------------------------------------------

def estimate_steady_state(
    trajectory,
    window: int = 10,
) -> float:
    """Estimate steady-state value from tail of trajectory."""
    if len(trajectory) < window:
        if trajectory:
            pt = trajectory[-1]
            return pt["value"] if isinstance(pt, dict) else pt.value
        return 0.0

    tail = [pt["value"] if isinstance(pt, dict) else pt.value for pt in trajectory[-window:]]
    return float(np.mean(tail))
