"""High-level orchestrator that ties discovery, forecasting, etc. together."""
from __future__ import annotations

import json
import uuid
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .grammar import ASTNode, Grammar, complexity, simplify_ast
from .gp_engine import GPEngine
from .pareto import compute_pareto_frontier, select_best_equation, ParetoPoint
from .ode_solver import solve_ode, forecast, detect_threshold_breach, estimate_steady_state
from .explanation import explain_anomaly
from .simulation import simulate_scenario
from .data_generator import generate_data, SYSTEMS
from .models import (
    DiscoverRequest,
    DiscoverResponse,
    DiscoverStatus,
    ForecastRequest,
    ForecastResult,
    ForecastPoint,
    ExplanationRequest,
    ExplanationResult,
    SimulateRequest,
    SimulateResult,
)

# In-memory job store (for demo; production would use a database)
_jobs: Dict[str, DiscoverStatus] = {}


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def run_discovery(request: DiscoverRequest) -> DiscoverResponse:
    """Start an equation discovery job."""
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = DiscoverStatus(job_id=job_id, status="running", progress=0.0)

    # Load data
    if request.csv_data:
        from io import StringIO
        df = pd.read_csv(StringIO(request.csv_data))
    elif request.csv_path:
        df = pd.read_csv(request.csv_path)
    elif request.system_type:
        df = generate_data(request.system_type.value, seed=42)
    else:
        _jobs[job_id].status = "failed"
        _jobs[job_id].error = "No data source provided"
        return DiscoverResponse(job_id=job_id, status="failed")

    # Auto-detect variables
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if request.target not in numeric_cols:
        if "queue_depth" in numeric_cols:
            request.target = "queue_depth"
        elif numeric_cols:
            request.target = numeric_cols[0]

    variable_names = [c for c in numeric_cols if c != "t"]
    if "t" not in df.columns:
        df["t"] = np.arange(len(df)) * 1.0

    target_idx = variable_names.index(request.target) if request.target in variable_names else 0

    # Prepare X, y
    X = df[variable_names].values
    y = df[request.target].values

    # Run GP
    grammar = Grammar(
        variables=variable_names,
        target=request.target,
        max_depth=request.max_depth,
    )

    engine = GPEngine(
        grammar=grammar,
        population_size=request.population_size,
        max_generations=request.max_generations,
    )

    results = engine.run(
        X=X,
        y=y,
        variable_names=variable_names,
        target_idx=target_idx,
        callback=lambda gen, mse, tree: _update_job(job_id, gen / request.max_generations, mse, tree, variable_names),
    )

    # Compute Pareto frontier
    frontier = compute_pareto_frontier(results, variable_names)

    _jobs[job_id].status = "completed"
    _jobs[job_id].progress = 1.0
    _jobs[job_id].pareto_front = [
        {"complexity": p.comp, "mse": p.mse, "latex": p.latex, "equation_id": p.equation_id}
        for p in frontier
    ]

    if frontier:
        best = select_best_equation(frontier)
        _jobs[job_id].best_equation = {
            "id": best.equation_id,
            "latex": best.latex,
            "complexity": best.comp,
            "mse": best.mse,
            "variables": variable_names,
            "target": request.target,
        }

    return DiscoverResponse(job_id=job_id, status="completed")


def _update_job(job_id: str, progress: float, mse: float, tree: ASTNode, variables: List[str]):
    if job_id in _jobs:
        _jobs[job_id].progress = progress


def get_job_status(job_id: str) -> DiscoverStatus:
    if job_id not in _jobs:
        raise ValueError(f"Job {job_id} not found")
    return _jobs[job_id]


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

def run_forecast(request: ForecastRequest) -> ForecastResult:
    """Run forecast on an equation."""
    from sympy import Symbol, parse_expr
    from sympy.parsing.sympy_parser import standard_transformations, implicit_multiplication_application

    # Parse equation from LaTeX (simplified: parse as sympy string)
    var_names = list(request.initial_conditions.keys())
    if "t" not in var_names:
        var_names.append("t")

    var_dict = {v: Symbol(v) for v in var_names}
    transformations = standard_transformations + (implicit_multiplication_application,)

    try:
        expr = parse_expr(request.equation, local_dict=var_dict, transformations=transformations)
    except Exception:
        # Try treating as a simple expression
        expr = parse_expr(request.equation, local_dict=var_dict)

    # Build AST from sympy expression
    from .grammar import _sympy_to_ast
    ast = _sympy_to_ast(expr, var_names)

    trajectory = forecast(
        ast,
        var_names,
        request.initial_conditions.get("queue_depth", list(request.initial_conditions.keys())[0]),
        request.initial_conditions,
        horizon_minutes=request.horizon_minutes,
        time_step_minutes=request.time_step_minutes,
    )

    threshold_breach = False
    time_to_breach = None
    if request.threshold is not None:
        threshold_breach, time_to_breach = detect_threshold_breach(
            trajectory, request.threshold, request.threshold_variable
        )

    peak = max(pt["value"] for pt in trajectory) if trajectory else 0
    steady = estimate_steady_state(trajectory)

    return ForecastResult(
        trajectory=trajectory,
        threshold_breach=threshold_breach,
        time_to_breach_minutes=time_to_breach,
        peak_value=round(peak, 2),
        steady_state_value=round(steady, 2),
    )


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------

def run_explanation(request: ExplanationRequest) -> ExplanationResult:
    """Run explanation on an anomaly."""
    from sympy import Symbol, parse_expr
    from sympy.parsing.sympy_parser import standard_transformations, implicit_multiplication_application

    var_names = list(request.actual.keys())
    if "t" not in var_names:
        var_names.append("t")

    var_dict = {v: Symbol(v) for v in var_names}
    transformations = standard_transformations + (implicit_multiplication_application,)
    expr = parse_expr(request.equation, local_dict=var_dict, transformations=transformations)

    from .grammar import _sympy_to_ast
    target = [v for v in request.actual.keys() if v != "t"][0] if request.actual else "queue_depth"
    ast = _sympy_to_ast(expr, var_names)

    return explain_anomaly(
        equation=ast,
        variable_names=var_names,
        target=target,
        actual=request.actual,
        predicted=request.predicted,
    )


# ---------------------------------------------------------------------------
# Simulate
# ---------------------------------------------------------------------------

def run_simulation(request: SimulateRequest) -> SimulateResult:
    """Run what-if simulation."""
    from sympy import Symbol, parse_expr
    from sympy.parsing.sympy_parser import standard_transformations, implicit_multiplication_application

    var_names = list(request.initial_conditions.keys())
    if "t" not in var_names:
        var_names.append("t")

    var_dict = {v: Symbol(v) for v in var_names}
    transformations = standard_transformations + (implicit_multiplication_application,)
    expr = parse_expr(request.equation, local_dict=var_dict, transformations=transformations)

    from .grammar import _sympy_to_ast
    target = [v for v in request.initial_conditions.keys() if v != "t"][0] if request.initial_conditions else "queue_depth"
    ast = _sympy_to_ast(expr, var_names)

    return simulate_scenario(
        equation=ast,
        variable_names=var_names,
        target=target,
        parameter_changes=request.parameter_changes,
        initial_conditions=request.initial_conditions,
        horizon_minutes=request.horizon_minutes,
        time_step_minutes=request.time_step_minutes,
    )


# ---------------------------------------------------------------------------
# Get all equations
# ---------------------------------------------------------------------------

def list_equations() -> List[Dict]:
    """List all discovered equations from completed jobs."""
    equations = []
    for job_id, status in _jobs.items():
        if status.best_equation:
            eq = status.best_equation.copy()
            eq["job_id"] = job_id
            equations.append(eq)
    return equations


def get_equation(equation_id: str) -> Optional[Dict]:
    """Get a specific equation by ID."""
    for job_id, status in _jobs.items():
        if status.best_equation and status.best_equation.get("id") == equation_id:
            eq = status.best_equation.copy()
            eq["job_id"] = job_id
            return eq
    return None
