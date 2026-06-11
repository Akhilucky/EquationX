"""Data connectors for real-time observability platforms."""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from .logging_config import get_logger

logger = get_logger(__name__)


class PrometheusConnector:
    """Fetch time-series data from Prometheus for equation discovery."""

    def __init__(self, url: str = "http://localhost:9090"):
        self.url = url.rstrip("/")

    def query_range(
        self,
        query: str,
        start: str,
        end: str,
        step: str = "15s",
    ) -> pd.DataFrame:
        """Execute a Prometheus range query and return results as a DataFrame."""
        import httpx
        response = httpx.get(
            f"{self.url}/api/v1/query_range",
            params={"query": query, "start": start, "end": end, "step": step},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()["data"]["result"]

        rows = []
        for series in data:
            metric_name = series.get("metric", {}).get("__name__", "metric")
            for timestamp, value in series["values"]:
                rows.append({
                    "t": float(timestamp),
                    metric_name: float(value),
                    **{k: v for k, v in series.get("metric", {}).items()
                       if k != "__name__"},
                })

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df = df.groupby("t")[numeric_cols].mean().reset_index()
        df = df.sort_values("t")
        df["t"] = np.arange(len(df)) * 1.0  # Normalize time
        return df

    def list_metrics(self, filter_pattern: str = "") -> List[str]:
        """List available metrics matching a pattern."""
        import httpx
        response = httpx.get(
            f"{self.url}/api/v1/label/__name__/values",
            timeout=10,
        )
        response.raise_for_status()
        metrics = response.json()["data"]
        if filter_pattern:
            metrics = [m for m in metrics if filter_pattern in m]
        return metrics


class DatadogConnector:
    """Fetch data from Datadog API."""

    def __init__(self, api_key: str, app_key: str, site: str = "datadoghq.com"):
        self.api_key = api_key
        self.app_key = app_key
        self.base_url = f"https://api.{site}"

    def query_metrics(
        self,
        query: str,
        from_seconds: int,
        to_seconds: int,
    ) -> pd.DataFrame:
        """Query Datadog metrics."""
        import httpx
        response = httpx.get(
            f"{self.base_url}/api/v1/query",
            params={
                "query": query,
                "from": from_seconds,
                "to": to_seconds,
            },
            headers={
                "DD-API-KEY": self.api_key,
                "DD-APPLICATION-KEY": self.app_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        rows = []
        for series in data.get("series", []):
            metric = series.get("metric", "value")
            for point in series.get("pointlist", []):
                rows.append({
                    "t": float(point[0]),
                    metric: float(point[1]) if point[1] is not None else 0.0,
                })

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df = df.groupby("t")[numeric_cols].mean().reset_index()
        df = df.sort_values("t")
        df["t"] = np.arange(len(df)) * 1.0
        return df
