"""Prometheus metrics and OpenTelemetry integration for EquationX."""
from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, Optional

from .logging_config import get_logger

logger = get_logger(__name__)

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
    _prometheus_available = True
except ImportError:
    _prometheus_available = False

    class _FakeMetric:
        def labels(self, **kwargs): return self
        def inc(self, amount=1): pass
        def observe(self, amount): pass
        def set(self, value): pass

    class _FakeRegistry:
        def Counter(self, *a, **kw): return _FakeMetric()
        def Histogram(self, *a, **kw): return _FakeMetric()
        def Gauge(self, *a, **kw): return _FakeMetric()

    Counter = Histogram = Gauge = _FakeMetric
    REGISTRY = _FakeRegistry()


DISCOVERY_DURATION = Histogram(
    "equationx_discovery_duration_seconds",
    "Time spent on equation discovery",
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)

FORECAST_DURATION = Histogram(
    "equationx_forecast_duration_seconds",
    "Time spent on forecasting",
    buckets=[0.1, 0.5, 1, 2, 5, 10],
)

DISCOVERIES_TOTAL = Counter(
    "equationx_discoveries_total",
    "Total number of discovery runs",
    ["status"],
)

FORECASTS_TOTAL = Counter(
    "equationx_forecasts_total",
    "Total number of forecasts",
    ["status"],
)

EQUATIONS_DISCOVERED = Gauge(
    "equationx_equations_discovered",
    "Number of equations discovered",
)

EXPLANATIONS_TOTAL = Counter(
    "equationx_explanations_total",
    "Total number of anomaly explanations",
    ["status"],
)

SIMULATIONS_TOTAL = Counter(
    "equationx_simulations_total",
    "Total number of simulations run",
    ["status"],
)

ACTIVE_JOBS = Gauge(
    "equationx_active_jobs",
    "Number of active discovery jobs",
)


def track_duration(metric: Histogram):
    """Decorator to track function duration in a Prometheus histogram."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                metric.observe(time.time() - start)
                return result
            except Exception as e:
                metric.observe(time.time() - start)
                raise
        return wrapper
    return decorator


def expose_metrics():
    """Return Prometheus metrics as text."""
    if not _prometheus_available:
        return "# Prometheus client not installed\n"
    return generate_latest(REGISTRY).decode("utf-8")
