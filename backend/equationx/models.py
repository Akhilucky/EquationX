"""Pydantic models for EquationX API and internal data."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SystemType(str, Enum):
    QUEUE = "queue"
    CPU = "cpu"
    DB_CONNECTIONS = "db_connections"
    CACHE = "cache"


# ---------------------------------------------------------------------------
# Equation / AST
# ---------------------------------------------------------------------------

class EquationNode(BaseModel):
    op: Optional[str] = None
    children: List["EquationNode"] = []
    value: Optional[Any] = None
    is_derivative: bool = False
    deriv_var: Optional[str] = None
    deriv_order: int = 1


class Equation(BaseModel):
    id: str
    latex: str
    complexity: int
    mse: float
    variables: List[str]
    target: str
    nodes: Optional[EquationNode] = None


class ParetoPoint(BaseModel):
    complexity: int
    mse: float
    latex: str
    equation_id: str


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class DiscoverRequest(BaseModel):
    csv_data: Optional[str] = None
    csv_path: Optional[str] = None
    target: str = "queue_depth"
    variables: Optional[List[str]] = None
    max_generations: int = 100
    population_size: int = 200
    max_depth: int = 6
    system_type: Optional[SystemType] = None


class DiscoverResponse(BaseModel):
    job_id: str
    status: str = "started"


class DiscoverStatus(BaseModel):
    job_id: str
    status: str  # running, completed, failed
    progress: float = 0.0
    pareto_front: List[ParetoPoint] = []
    best_equation: Optional[Equation] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------

class ForecastRequest(BaseModel):
    equation: str  # LaTeX or JSON of equation
    initial_conditions: Dict[str, float]
    horizon_minutes: int = 15
    threshold: Optional[float] = None
    threshold_variable: Optional[str] = None
    time_step_minutes: float = 1.0


class ForecastPoint(BaseModel):
    time_minutes: float
    value: float
    lower_ci: float
    upper_ci: float


class ForecastResult(BaseModel):
    trajectory: List[ForecastPoint]
    threshold_breach: bool
    time_to_breach_minutes: Optional[float] = None
    peak_value: float
    steady_state_value: Optional[float] = None


# ---------------------------------------------------------------------------
# Explanation
# ---------------------------------------------------------------------------

class ExplanationRequest(BaseModel):
    equation: str
    actual: Dict[str, float]
    predicted: Optional[Dict[str, float]] = None
    variables: Optional[List[str]] = None


class FactorContribution(BaseModel):
    variable: str
    actual_value: float
    expected_value: float
    impact_pct: float
    direction: str  # "above" or "below"


class ExplanationResult(BaseModel):
    summary: str
    predicted_value: float
    actual_value: float
    deviation: float
    contributing_factors: List[FactorContribution]
    recommendation: str


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

class SimulateRequest(BaseModel):
    equation: str
    parameter_changes: Dict[str, float]
    initial_conditions: Dict[str, float]
    horizon_minutes: int = 60
    time_step_minutes: float = 1.0


class SimulateResult(BaseModel):
    baseline_trajectory: List[ForecastPoint]
    modified_trajectory: List[ForecastPoint]
    peak_value: float
    steady_state_value: float
    time_to_stabilize_minutes: float
    threshold_breach: bool
    recommendation: str


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    uptime_seconds: float = 0.0
