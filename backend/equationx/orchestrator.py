"""High-level orchestrator with async execution, persistence, and LLM agent."""
from __future__ import annotations

import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .agent import LLMAgent
from .data_generator import generate_data
from .database import (
    get_equation as db_get_equation,
)
from .database import (
    get_job_status_from_db,
    init_db,
    save_equation,
    save_job_status,
)
from .database import (
    list_equations as db_list_equations,
)
from .explanation import explain_anomaly
from .gp_engine import GPEngine
from .grammar import ASTNode, Grammar
from .logging_config import get_logger
from .models import (
    DiscoverRequest,
    DiscoverResponse,
    ExplanationRequest,
    ExplanationResult,
    ForecastRequest,
    ForecastResult,
    SimulateRequest,
    SimulateResult,
)
from .observability import (
    ACTIVE_JOBS,
    DISCOVERIES_TOTAL,
    DISCOVERY_DURATION,
    EQUATIONS_DISCOVERED,
    track_duration,
)
from .ode_solver import detect_threshold_breach, estimate_steady_state, forecast
from .pareto import compute_pareto_frontier, select_best_equation
from .simulation import simulate_scenario

logger = get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)
_jobs: Dict[str, Dict[str, Any]] = {}
_agent: Optional[LLMAgent] = None

_has_intialized_db = False


def _ensure_db():
    global _has_intialized_db
    if not _has_intialized_db:
        init_db()
        _has_intialized_db = True


def get_agent() -> LLMAgent:
    global _agent
    if _agent is None:
        _agent = LLMAgent()
    return _agent


def run_discovery(request: DiscoverRequest) -> DiscoverResponse:
    """Start equation discovery synchronously (runs in thread pool)."""
    _ensure_db()
    job_id = str(uuid.uuid4())[:8]
    ACTIVE_JOBS.inc()

    _jobs[job_id] = {
        "job_id": job_id,
        "status": "running",
        "progress": 0.0,
        "pareto_front": [],
        "best_equation": None,
        "error": None,
    }
    save_job_status(job_id, "running")

    try:
        _run_discovery_internal(job_id, request)
        DISCOVERIES_TOTAL.labels(status="success").inc()
    except Exception as e:
        logger.exception(f"Discovery job {job_id} failed")
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)
        save_job_status(job_id, "failed", error=str(e))
        DISCOVERIES_TOTAL.labels(status="failed").inc()
    finally:
        ACTIVE_JOBS.dec()

    return DiscoverResponse(job_id=job_id, status=_jobs[job_id]["status"])


def _run_discovery_internal(job_id: str, request: DiscoverRequest):
    """Internal synchronous discovery execution."""

    if request.csv_data:
        from io import StringIO
        df = pd.read_csv(StringIO(request.csv_data))
    elif request.csv_path:
        df = pd.read_csv(request.csv_path)
    elif request.system_type:
        df = generate_data(request.system_type.value, seed=42)
    else:
        raise ValueError("No data source provided")

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if request.target not in numeric_cols:
        if numeric_cols:
            request.target = numeric_cols[0]

    variable_names = [c for c in numeric_cols if c != "t"]
    if "t" not in df.columns:
        df["t"] = np.arange(len(df)) * 1.0

    # Use LLM agent to suggest variable roles if available
    agent = get_agent()
    if agent.api_key:
        try:
            sample = df[variable_names].head(3).to_dict(orient="list")
            suggestion = agent.suggest_variables(variable_names, sample)
            if suggestion.get("target") in variable_names:
                request.target = suggestion["target"]
                logger.info(f"LLM suggested target: {request.target}")
        except Exception as e:
            logger.warning(f"LLM suggestion failed: {e}")

    target_idx = variable_names.index(request.target) if request.target in variable_names else 0
    X = df[variable_names].values
    y = df[request.target].values

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

    def _callback(gen: int, mse: float, tree: ASTNode):
        _jobs[job_id]["progress"] = (gen + 1) / request.max_generations
        save_job_status(job_id, "running", _jobs[job_id]["progress"])

    start_time = time.time()
    results = engine.run(
        X=X, y=y,
        variable_names=variable_names,
        target_idx=target_idx,
        callback=_callback,
    )
    duration = time.time() - start_time
    DISCOVERY_DURATION.observe(duration)
    logger.info(f"Discovery {job_id} completed in {duration:.1f}s, found {len(results)} candidates")

    frontier = compute_pareto_frontier(results, variable_names)

    pareto_dicts = [
        {"complexity": p.comp, "mse": p.mse, "latex": p.latex, "equation_id": p.equation_id}
        for p in frontier
    ]

    best_eq = None
    if frontier:
        best = select_best_equation(frontier)
        best_eq = {
            "id": best.equation_id,
            "latex": best.latex,
            "complexity": best.comp,
            "mse": best.mse,
            "variables": variable_names,
            "target": request.target,
        }
        # Persist to database
        save_equation(
            eq_id=best.equation_id, job_id=job_id,
            latex=best.latex, complexity=best.comp, mse=best.mse,
            variables=variable_names, target=request.target,
            system_type=request.system_type.value if request.system_type else None,
            pareto_front=pareto_dicts,
        )
        EQUATIONS_DISCOVERED.set(len(db_list_equations()))

        # Generate LLM explanation for best equation
        if agent.api_key:
            try:
                explanation = agent.explain_equation(
                    best.latex, variable_names, request.target, best.mse
                )
                best_eq["llm_explanation"] = explanation
            except Exception:
                pass

    _jobs[job_id].update({
        "status": "completed",
        "progress": 1.0,
        "pareto_front": pareto_dicts,
        "best_equation": best_eq,
    })
    save_job_status(job_id, "completed", progress=1.0)


def get_job_status(job_id: str) -> Dict[str, Any]:
    if job_id not in _jobs:
        db_status = get_job_status_from_db(job_id)
        if db_status:
            return db_status
        raise ValueError(f"Job {job_id} not found")
    return _jobs[job_id]


async def run_discovery_async(request: DiscoverRequest) -> DiscoverResponse:
    """Run discovery in a background thread (non-blocking)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, run_discovery, request)


@track_duration(DISCOVERY_DURATION)
def run_forecast(request: ForecastRequest) -> ForecastResult:
    """Run forecast on an equation."""
    _ensure_db()
    from sympy import Symbol, parse_expr
    from sympy.parsing.sympy_parser import (
        implicit_multiplication_application,
        standard_transformations,
    )

    var_names = list(request.initial_conditions.keys())
    if "t" not in var_names:
        var_names.append("t")

    var_dict = {v: Symbol(v) for v in var_names}
    transformations = standard_transformations + (implicit_multiplication_application,)

    try:
        expr = parse_expr(request.equation, local_dict=var_dict, transformations=transformations)
    except Exception:
        expr = parse_expr(request.equation, local_dict=var_dict)

    from .grammar import _sympy_to_ast
    target = [v for v in var_names if v != "t"][0] if var_names else "value"
    ast = _sympy_to_ast(expr, var_names)

    trajectory = forecast(
        ast, var_names, target, request.initial_conditions,
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


def run_explanation(request: ExplanationRequest) -> ExplanationResult:
    """Run explanation on an anomaly."""
    _ensure_db()
    from sympy import Symbol, parse_expr
    from sympy.parsing.sympy_parser import (
        implicit_multiplication_application,
        standard_transformations,
    )

    var_names = list(request.actual.keys())
    if "t" not in var_names:
        var_names.append("t")

    var_dict = {v: Symbol(v) for v in var_names}
    transformations = standard_transformations + (implicit_multiplication_application,)
    expr = parse_expr(request.equation, local_dict=var_dict, transformations=transformations)

    from .grammar import _sympy_to_ast
    target = [v for v in request.actual.keys() if v != "t"][0] if request.actual else "value"
    ast = _sympy_to_ast(expr, var_names)

    result = explain_anomaly(
        equation=ast, variable_names=var_names, target=target,
        actual=request.actual, predicted=request.predicted,
    )

    # Enhance with LLM if available
    agent = get_agent()
    if agent.api_key:
        try:
            factors_dict = [
                {"variable": f.variable, "actual": f.actual_value,
                 "expected": f.expected_value, "impact_pct": f.impact_pct}
                for f in result.contributing_factors
            ]
            enhanced = agent.enhanced_explain_anomaly(
                request.equation, request.actual,
                result.predicted_value, factors_dict,
            )
            result.summary = f"{result.summary} Root cause: {enhanced.get('root_cause', '')}"
            result.recommendation = enhanced.get("action", result.recommendation)
        except Exception as e:
            logger.warning(f"LLM enhancement failed: {e}")

    return result


def run_simulation(request: SimulateRequest) -> SimulateResult:
    """Run what-if simulation."""
    _ensure_db()
    from sympy import Symbol, parse_expr
    from sympy.parsing.sympy_parser import (
        implicit_multiplication_application,
        standard_transformations,
    )

    var_names = list(request.initial_conditions.keys())
    if "t" not in var_names:
        var_names.append("t")

    var_dict = {v: Symbol(v) for v in var_names}
    transformations = standard_transformations + (implicit_multiplication_application,)
    expr = parse_expr(request.equation, local_dict=var_dict, transformations=transformations)

    from .grammar import _sympy_to_ast
    target = (
        [v for v in request.initial_conditions.keys() if v != "t"][0]
        if request.initial_conditions else "value"
    )
    ast = _sympy_to_ast(expr, var_names)

    return simulate_scenario(
        equation=ast, variable_names=var_names, target=target,
        parameter_changes=request.parameter_changes,
        initial_conditions=request.initial_conditions,
        horizon_minutes=request.horizon_minutes,
        time_step_minutes=request.time_step_minutes,
    )


def list_all_equations() -> List[Dict]:
    _ensure_db()
    return db_list_equations()


def get_equation_by_id(equation_id: str) -> Optional[Dict]:
    _ensure_db()
    return db_get_equation(equation_id)
