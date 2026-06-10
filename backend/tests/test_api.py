"""Tests for REST API endpoints."""
import pytest
from fastapi.testclient import TestClient
from equationx.api import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestDiscoverEndpoint:
    def test_discover_with_system(self, client):
        response = client.post("/discover", json={
            "system_type": "queue",
            "target": "queue_depth",
            "max_generations": 5,
            "population_size": 10,
        })
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    def test_discover_status(self, client):
        # Start a job
        res = client.post("/discover", json={
            "system_type": "queue",
            "target": "queue_depth",
            "max_generations": 2,
            "population_size": 5,
        })
        job_id = res.json()["job_id"]

        response = client.get(f"/discover/{job_id}/status")
        assert response.status_code == 200

    def test_discover_status_not_found(self, client):
        response = client.get("/discover/nonexistent/status")
        assert response.status_code == 404


class TestEquationsEndpoint:
    def test_list_equations(self, client):
        response = client.get("/equations")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_equation_not_found(self, client):
        response = client.get("/equations/nonexistent")
        assert response.status_code == 404


class TestForecastEndpoint:
    def test_forecast(self, client):
        response = client.post("/forecast", json={
            "equation": "0.95 * arrival_rate - 1.21 * service_rate",
            "initial_conditions": {"queue_depth": 10, "arrival_rate": 8.0, "service_rate": 1.0},
            "horizon_minutes": 10,
        })
        assert response.status_code == 200
        data = response.json()
        assert "trajectory" in data
        assert "peak_value" in data

    def test_forecast_with_threshold(self, client):
        response = client.post("/forecast", json={
            "equation": "0.95 * arrival_rate - 1.21 * service_rate",
            "initial_conditions": {"queue_depth": 10, "arrival_rate": 8.0, "service_rate": 1.0},
            "horizon_minutes": 10,
            "threshold": 50,
        })
        assert response.status_code == 200
        assert "threshold_breach" in response.json()


class TestExplainEndpoint:
    def test_explain(self, client):
        response = client.post("/explain", json={
            "equation": "0.95 * arrival_rate - 1.21 * service_rate",
            "actual": {"queue_depth": 95, "arrival_rate": 12.4, "service_rate": 1.2},
        })
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "contributing_factors" in data
        assert "recommendation" in data


class TestSimulateEndpoint:
    def test_simulate(self, client):
        response = client.post("/simulate", json={
            "equation": "0.95 * arrival_rate - 1.21 * service_rate",
            "parameter_changes": {"service_rate": 2.0},
            "initial_conditions": {"queue_depth": 10, "arrival_rate": 8.0, "service_rate": 1.0},
            "horizon_minutes": 30,
        })
        assert response.status_code == 200
        data = response.json()
        assert "peak_value" in data
        assert "recommendation" in data
