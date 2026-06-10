"""Explanation engine: detect deviations and identify root causes."""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from .grammar import ASTNode
from .ode_solver import solve_ode
from .models import FactorContribution, ExplanationResult


def explain_anomaly(
    equation: ASTNode,
    variable_names: List[str],
    target: str,
    actual: Dict[str, float],
    predicted: Optional[Dict[str, float]] = None,
    baseline_conditions: Optional[Dict[str, float]] = None,
) -> ExplanationResult:
    """Explain why actual differs from predicted.

    Args:
        equation: The discovered ODE equation.
        variable_names: All variable names.
        target: Target variable being predicted.
        actual: Actual observed values of all variables.
        predicted: Expected/predicted values (if None, computed from equation).
        baseline_conditions: Baseline conditions for comparison.

    Returns:
        ExplanationResult with summary, factors, and recommendation.
    """
    from sympy import Symbol

    var_dict = {v: Symbol(v) for v in variable_names}
    var_dict["t"] = Symbol("t")
    expr = equation.to_sympy(var_dict)

    # Compute predicted value for target
    sympy_vars = [var_dict[v] for v in variable_names]
    func = __import__("sympy").lambdify(sympy_vars, expr, modules=["numpy", "math"])

    actual_args = [actual.get(v, 0.0) for v in variable_names]
    try:
        predicted_value = float(func(*actual_args))
    except Exception:
        predicted_value = 0.0

    actual_value = actual.get(target, 0.0)
    deviation = actual_value - predicted_value

    # Analyze each variable's contribution to deviation
    factors = []
    if baseline_conditions is None:
        if predicted is not None:
            baseline_conditions = {v: np.mean([actual.get(v, 0.0), predicted.get(v, actual.get(v, 0.0))]) for v in variable_names}
        else:
            baseline_conditions = {v: actual.get(v, 0.0) for v in variable_names}

    for v in variable_names:
        if v == target:
            continue
        actual_v = actual.get(v, 0.0)
        expected_v = baseline_conditions.get(v, actual_v)

        if expected_v == 0:
            continue

        # Compute partial effect: change target when varying this variable
        perturbed_args = list(actual_args)
        v_idx = variable_names.index(v)
        perturbed_args[v_idx] = expected_v
        try:
            perturbed_val = float(func(*perturbed_args))
        except Exception:
            continue

        impact = perturbed_val - predicted_value
        pct = (impact / (abs(predicted_value) + 1e-10)) * 100

        direction = "above" if actual_v > expected_v else "below" if actual_v < expected_v else "neutral"

        factors.append(
            FactorContribution(
                variable=v,
                actual_value=actual_v,
                expected_value=expected_v,
                impact_pct=round(pct, 1),
                direction=direction,
            )
        )

    # Sort by impact magnitude
    factors.sort(key=lambda f: abs(f.impact_pct), reverse=True)

    # Generate summary
    top_factor = factors[0] if factors else None
    if deviation > 0:
        summary = f"{target} is at {actual_value:.1f} when expected {predicted_value:.1f} ({abs(deviation):.1f} above)."
    elif deviation < 0:
        summary = f"{target} is at {actual_value:.1f} when expected {predicted_value:.1f} ({abs(deviation):.1f} below)."
    else:
        summary = f"{target} is at expected value {actual_value:.1f}."

    if top_factor:
        summary += f" {top_factor.variable} ({top_factor.actual_value:.1f}) is {abs(top_factor.impact_pct):.0f}% {top_factor.direction} normal."

    # Generate recommendation
    recommendation = _generate_recommendation(target, deviation, factors)

    return ExplanationResult(
        summary=summary,
        predicted_value=round(predicted_value, 2),
        actual_value=round(actual_value, 2),
        deviation=round(deviation, 2),
        contributing_factors=factors,
        recommendation=recommendation,
    )


def _generate_recommendation(
    target: str,
    deviation: float,
    factors: List[FactorContribution],
) -> str:
    """Generate actionable recommendation based on analysis."""
    if abs(deviation) < 0.01:
        return "System is operating as expected. No action needed."

    top = factors[0] if factors else None
    if "queue" in target.lower():
        if deviation > 0:
            if top and "arrival" in top.variable.lower():
                return "Arrival rate is elevated. Consider rate-limiting or scaling up service capacity."
            elif top and "service" in top.variable.lower():
                return "Service rate is below normal. Scale up service instances or reduce workload."
            else:
                return "Queue is higher than expected. Review workload and capacity."
        else:
            return "Queue is lower than expected. System may be over-provisioned."
    elif "cpu" in target.lower() or "c" in target.lower():
        if deviation > 0:
            return "CPU usage is higher than expected. Consider scaling up or optimizing workload."
        else:
            return "CPU usage is lower than expected. Consider reducing allocated resources."
    elif "conn" in target.lower():
        if deviation > 0:
            return "Database connections are higher than expected. Check for connection leaks or scale pool."
        else:
            return "Database connections are lower than expected. Pool may be over-provisioned."
    elif "hit" in target.lower() or "cache" in target.lower():
        if deviation > 0:
            return "Cache hit rate is lower than expected. Review cache eviction policy or increase cache size."
        else:
            return "Cache is performing better than expected."

    return f"Investigate factors contributing to {target} deviation."
