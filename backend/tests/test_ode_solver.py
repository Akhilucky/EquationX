"""Tests for ODE solver and forecasting."""
import pytest
import numpy as np
from equationx.grammar import ASTNode
from equationx.ode_solver import (
    solve_ode,
    forecast,
    detect_threshold_breach,
    estimate_steady_state,
    build_ode_rhs,
)


def _make_linear_eq():
    """d(x)/dt = 2 - 0.5*x => approaches steady state at x=4"""
    return ASTNode(
        op="-",
        children=[
            ASTNode(value=2.0),
            ASTNode(op="*", children=[ASTNode(value=0.5), ASTNode(value="x")]),
        ],
    )


class TestODESolver:
    def test_solve_linear(self):
        eq = _make_linear_eq()
        t, y = solve_ode(eq, ["x"], "x", {"x": 0.0}, (0, 20), t_step=1.0)
        assert len(t) > 0
        assert len(y) == 1
        # x should approach 4 (steady state: 2 - 0.5*x = 0 => x = 4)
        assert abs(y[0][-1] - 4.0) < 0.5

    def test_solve_constant(self):
        eq = ASTNode(value=0.0)
        t, y = solve_ode(eq, ["x"], "x", {"x": 5.0}, (0, 10), t_step=1.0)
        # d(x)/dt = 0 => x stays constant
        assert abs(y[0][-1] - 5.0) < 0.1


class TestForecast:
    def test_forecast_returns_points(self):
        eq = _make_linear_eq()
        trajectory = forecast(eq, ["x"], "x", {"x": 0.0}, horizon_minutes=10, time_step_minutes=1.0)
        assert len(trajectory) > 0
        assert trajectory[0]["time_minutes"] == 0.0
        assert trajectory[-1]["time_minutes"] <= 10.0

    def test_forecast_has_ci(self):
        eq = _make_linear_eq()
        trajectory = forecast(eq, ["x"], "x", {"x": 0.0}, horizon_minutes=5, time_step_minutes=1.0)
        for pt in trajectory:
            assert pt["lower_ci"] <= pt["value"] <= pt["upper_ci"]


class TestThreshold:
    def test_breach_detected(self):
        trajectory = [
            {"time_minutes": 0, "value": 10, "lower_ci": 10, "upper_ci": 10},
            {"time_minutes": 1, "value": 50, "lower_ci": 50, "upper_ci": 50},
            {"time_minutes": 2, "value": 100, "lower_ci": 100, "upper_ci": 100},
        ]
        breached, ttb = detect_threshold_breach(trajectory, 80)
        assert breached
        assert ttb is not None
        assert 1.0 <= ttb <= 2.0

    def test_no_breach(self):
        trajectory = [
            {"time_minutes": 0, "value": 10, "lower_ci": 10, "upper_ci": 10},
            {"time_minutes": 1, "value": 20, "lower_ci": 20, "upper_ci": 20},
        ]
        breached, ttb = detect_threshold_breach(trajectory, 100)
        assert not breached
        assert ttb is None


class TestSteadyState:
    def test_constant_trajectory(self):
        trajectory = [
            {"time_minutes": i, "value": 42.0, "lower_ci": 42.0, "upper_ci": 42.0}
            for i in range(20)
        ]
        ss = estimate_steady_state(trajectory)
        assert abs(ss - 42.0) < 0.1
