"""FastAPI REST API for EquationX — 8 endpoints."""
from __future__ import annotations

import time
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .models import (
    DiscoverRequest,
    DiscoverResponse,
    DiscoverStatus,
    ForecastRequest,
    ForecastResult,
    ExplanationRequest,
    ExplanationResult,
    SimulateRequest,
    SimulateResult,
    HealthResponse,
)
from .orchestrator import (
    run_discovery,
    get_job_status,
    run_forecast,
    run_explanation,
    run_simulation,
    list_equations,
    get_equation,
)

_start_time = time.time()


def create_app() -> FastAPI:
    app = FastAPI(
        title="EquationX",
        description="AI Scientist for Infrastructure — discovers mathematical laws governing your systems",
        version=__version__,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # 1. POST /discover
    # ------------------------------------------------------------------
    @app.post("/discover", response_model=DiscoverResponse)
    async def discover(request: DiscoverRequest):
        try:
            result = run_discovery(request)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------------------
    # 2. GET /discover/{id}/status
    # ------------------------------------------------------------------
    @app.get("/discover/{job_id}/status", response_model=DiscoverStatus)
    async def discover_status(job_id: str):
        try:
            return get_job_status(job_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    # ------------------------------------------------------------------
    # 3. GET /equations
    # ------------------------------------------------------------------
    @app.get("/equations")
    async def equations():
        return list_equations()

    # ------------------------------------------------------------------
    # 4. GET /equations/{id}
    # ------------------------------------------------------------------
    @app.get("/equations/{equation_id}")
    async def equation_detail(equation_id: str):
        eq = get_equation(equation_id)
        if eq is None:
            raise HTTPException(status_code=404, detail="Equation not found")
        return eq

    # ------------------------------------------------------------------
    # 5. POST /forecast
    # ------------------------------------------------------------------
    @app.post("/forecast", response_model=ForecastResult)
    async def forecast_endpoint(request: ForecastRequest):
        try:
            return run_forecast(request)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------------------
    # 6. POST /explain
    # ------------------------------------------------------------------
    @app.post("/explain", response_model=ExplanationResult)
    async def explain_endpoint(request: ExplanationRequest):
        try:
            return run_explanation(request)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------------------
    # 7. POST /simulate
    # ------------------------------------------------------------------
    @app.post("/simulate", response_model=SimulateResult)
    async def simulate_endpoint(request: SimulateRequest):
        try:
            return run_simulation(request)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------------------
    # 8. GET /health
    # ------------------------------------------------------------------
    @app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(
            status="ok",
            version=__version__,
            uptime_seconds=round(time.time() - _start_time, 2),
        )

    return app
