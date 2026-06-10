"""FastAPI REST API for EquationX — async, with auth & rate limiting."""
from __future__ import annotations

import asyncio
import hashlib
import os
import time
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from . import __version__
from .logging_config import setup_logging, get_logger
from .observability import expose_metrics
from .models import (
    DiscoverRequest, DiscoverResponse, DiscoverStatus,
    ForecastRequest, ForecastResult,
    ExplanationRequest, ExplanationResult,
    SimulateRequest, SimulateResult, HealthResponse,
)
from .orchestrator import (
    run_discovery_async, get_job_status,
    run_forecast, run_explanation, run_simulation,
    list_all_equations, get_equation_by_id,
)

logger = get_logger(__name__)

_start_time = time.time()

# Rate limiting state
_rate_limit_store: Dict[str, list] = {}
_RATE_LIMIT = int(os.environ.get("EQUATIONX_RATE_LIMIT", "60"))
_RATE_WINDOW = int(os.environ.get("EQUATIONX_RATE_WINDOW", "60"))
_API_KEY = os.environ.get("EQUATIONX_API_KEY", "")

setup_logging(os.environ.get("EQUATIONX_LOG_LEVEL", "INFO"))


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter."""

    async def dispatch(self, request: Request, call_next):
        if _RATE_LIMIT <= 0:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - _RATE_WINDOW

        if client_ip not in _rate_limit_store:
            _rate_limit_store[client_ip] = []
        _rate_limit_store[client_ip] = [
            t for t in _rate_limit_store[client_ip] if t > window_start
        ]

        if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {_RATE_LIMIT} requests per {_RATE_WINDOW}s.",
            )

        _rate_limit_store[client_ip].append(now)
        return await call_next(request)


async def verify_api_key(request: Request) -> None:
    """Optional API key authentication."""
    if not _API_KEY:
        return
    auth = request.headers.get("Authorization", "")
    key = auth.replace("Bearer ", "").strip()
    if not key or key != _API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Set EQUATIONX_API_KEY env var on server.",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"EquationX v{__version__} starting up")
    yield
    logger.info("EquationX shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="EquationX",
        description="AI Scientist for Infrastructure — discovers mathematical laws governing your systems",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("EQUATIONX_CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware)

    # ------------------------------------------------------------------
    # Prometheus metrics endpoint
    # ------------------------------------------------------------------
    @app.get("/metrics")
    async def metrics():
        return Response(content=expose_metrics(), media_type="text/plain")

    # ------------------------------------------------------------------
    # 1. POST /discover
    # ------------------------------------------------------------------
    @app.post("/discover", response_model=DiscoverResponse, dependencies=[Depends(verify_api_key)])
    async def discover(request: DiscoverRequest):
        try:
            return await run_discovery_async(request)
        except Exception as e:
            logger.exception("Discovery failed")
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------------------
    # 2. GET /discover/{job_id}/status
    # ------------------------------------------------------------------
    @app.get("/discover/{job_id}/status", response_model=DiscoverStatus, dependencies=[Depends(verify_api_key)])
    async def discover_status(job_id: str):
        try:
            status = get_job_status(job_id)
            if isinstance(status, dict):
                return DiscoverStatus(**status)
            return status
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    # ------------------------------------------------------------------
    # 3. GET /equations
    # ------------------------------------------------------------------
    @app.get("/equations", dependencies=[Depends(verify_api_key)])
    async def equations():
        return list_all_equations()

    # ------------------------------------------------------------------
    # 4. GET /equations/{equation_id}
    # ------------------------------------------------------------------
    @app.get("/equations/{equation_id}", dependencies=[Depends(verify_api_key)])
    async def equation_detail(equation_id: str):
        eq = get_equation_by_id(equation_id)
        if eq is None:
            raise HTTPException(status_code=404, detail="Equation not found")
        return eq

    # ------------------------------------------------------------------
    # 5. POST /forecast
    # ------------------------------------------------------------------
    @app.post("/forecast", response_model=ForecastResult, dependencies=[Depends(verify_api_key)])
    async def forecast_endpoint(request: ForecastRequest):
        try:
            return run_forecast(request)
        except Exception as e:
            logger.exception("Forecast failed")
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------------------
    # 6. POST /explain
    # ------------------------------------------------------------------
    @app.post("/explain", response_model=ExplanationResult, dependencies=[Depends(verify_api_key)])
    async def explain_endpoint(request: ExplanationRequest):
        try:
            return run_explanation(request)
        except Exception as e:
            logger.exception("Explanation failed")
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------------------
    # 7. POST /simulate
    # ------------------------------------------------------------------
    @app.post("/simulate", response_model=SimulateResult, dependencies=[Depends(verify_api_key)])
    async def simulate_endpoint(request: SimulateRequest):
        try:
            return run_simulation(request)
        except Exception as e:
            logger.exception("Simulation failed")
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
