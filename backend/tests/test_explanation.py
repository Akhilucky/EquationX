"""Tests for explanation engine."""
import pytest
from equationx.grammar import ASTNode
from equationx.explanation import explain_anomaly


def _make_equation():
    """d(q)/dt = arrival_rate - service_rate * q / (100 + q)"""
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


class TestExplanation:
    def test_explain_returns_result(self):
        eq = _make_equation()
        result = explain_anomaly(
            equation=eq,
            variable_names=["q", "arrival_rate", "service_rate"],
            target="q",
            actual={"q": 95, "arrival_rate": 12.4, "service_rate": 1.2},
        )
        assert result.summary
        assert isinstance(result.deviation, float)
        assert isinstance(result.contributing_factors, list)
        assert result.recommendation

    def test_explain_high_arrival(self):
        eq = _make_equation()
        result = explain_anomaly(
            equation=eq,
            variable_names=["q", "arrival_rate", "service_rate"],
            target="q",
            actual={"q": 95, "arrival_rate": 12.4, "service_rate": 1.2},
            baseline_conditions={"q": 50, "arrival_rate": 8.0, "service_rate": 1.2},
        )
        # arrival_rate is above normal
        arrival_factors = [f for f in result.contributing_factors if f.variable == "arrival_rate"]
        assert len(arrival_factors) > 0
        assert arrival_factors[0].direction == "above"

    def test_recommendation_generated(self):
        eq = _make_equation()
        result = explain_anomaly(
            equation=eq,
            variable_names=["q", "arrival_rate", "service_rate"],
            target="q",
            actual={"q": 95, "arrival_rate": 12.4, "service_rate": 1.2},
        )
        assert len(result.recommendation) > 0
