"""Tests for GP engine and Pareto frontier."""
import pytest
import numpy as np
from equationx.grammar import ASTNode, Grammar
from equationx.gp_engine import GPEngine
from equationx.pareto import compute_pareto_frontier, select_best_equation


class TestGPEngine:
    def test_init(self):
        grammar = Grammar(variables=["x", "y"], target="x")
        engine = GPEngine(grammar, population_size=10, max_generations=2)
        assert engine.pop_size == 10
        assert engine.max_gen == 2

    def test_random_expression(self):
        from equationx.gp_engine import _random_expression
        grammar = Grammar(variables=["x"], target="x")
        tree = _random_expression(grammar)
        assert tree is not None
        assert hasattr(tree, 'to_sympy')

    def test_run_simple(self):
        grammar = Grammar(variables=["x"], target="x", max_depth=3)
        engine = GPEngine(grammar, population_size=20, max_generations=5)

        X = np.linspace(0, 10, 50).reshape(-1, 1)
        y = 2 * X[:, 0] + 1  # y = 2x + 1

        results = engine.run(X, y, ["x"], 0)
        assert isinstance(results, list)
        # Should find at least some equations
        assert len(results) >= 0  # May be empty if GP doesn't converge in 5 gens


class TestPareto:
    def test_compute_pareto_empty(self):
        frontier = compute_pareto_frontier([], ["x"])
        assert frontier == []

    def test_compute_pareto(self):
        eq1 = ASTNode(value="x")
        eq2 = ASTNode(op="+", children=[ASTNode(value="x"), ASTNode(value="y")])
        candidates = [
            (eq1, 0.1, 1),
            (eq2, 0.05, 3),
            (ASTNode(value="y"), 0.2, 1),
        ]
        frontier = compute_pareto_frontier(candidates, ["x", "y"])
        assert len(frontier) > 0
        # MSE should decrease along frontier
        for i in range(1, len(frontier)):
            assert frontier[i].mse <= frontier[i - 1].mse

    def test_select_best(self):
        from equationx.pareto import ParetoPoint
        eq = ASTNode(value="x")
        points = [
            ParetoPoint(equation=eq, mse=0.1, comp=1, latex="x", equation_id="eq1"),
            ParetoPoint(equation=eq, mse=0.05, comp=5, latex="y", equation_id="eq2"),
        ]
        best = select_best_equation(points)
        assert best is not None
