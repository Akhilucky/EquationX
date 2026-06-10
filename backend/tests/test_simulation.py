"""Tests for simulation module."""
import pytest
from equationx.grammar import ASTNode
from equationx.simulation import simulate_scenario


def _make_equation():
    return ASTNode(
        op="-",
        children=[
            ASTNode(value="arrival_rate"),
            ASTNode(
                op="*",
                children=[
                    ASTNode(value="service_rate"),
                    ASTNode(
                        op="/",
                        children=[
                            ASTNode(value="q"),
                            ASTNode(
                                op="+",
                                children=[ASTNode(value=100.0), ASTNode(value="q")],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


class TestSimulation:
    def test_simulate_returns_result(self):
        eq = _make_equation()
        result = simulate_scenario(
            equation=eq,
            variable_names=["q", "arrival_rate", "service_rate"],
            target="q",
            parameter_changes={"service_rate": 2.0},
            initial_conditions={"q": 10, "arrival_rate": 8.0, "service_rate": 1.0},
            horizon_minutes=30,
            time_step_minutes=1.0,
        )
        assert result.peak_value >= 0
        assert result.steady_state_value >= 0
        assert result.time_to_stabilize_minutes >= 0
        assert result.recommendation

    def test_simulate_with_threshold(self):
        eq = _make_equation()
        result = simulate_scenario(
            equation=eq,
            variable_names=["q", "arrival_rate", "service_rate"],
            target="q",
            parameter_changes={"service_rate": 2.0},
            initial_conditions={"q": 10, "arrival_rate": 8.0, "service_rate": 1.0},
            horizon_minutes=30,
            time_step_minutes=1.0,
            threshold=50,
        )
        assert isinstance(result.threshold_breach, bool)

    def test_baseline_vs_modified(self):
        eq = _make_equation()
        result = simulate_scenario(
            equation=eq,
            variable_names=["q", "arrival_rate", "service_rate"],
            target="q",
            parameter_changes={"service_rate": 2.0},
            initial_conditions={"q": 10, "arrival_rate": 8.0, "service_rate": 1.0},
            horizon_minutes=30,
            time_step_minutes=1.0,
        )
        assert len(result.baseline_trajectory) > 0
        assert len(result.modified_trajectory) > 0
        assert len(result.baseline_trajectory) == len(result.modified_trajectory)
