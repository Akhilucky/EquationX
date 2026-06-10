"""Pareto frontier computation for accuracy vs complexity trade-off."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .grammar import ASTNode, complexity


@dataclass
class ParetoPoint:
    """A point on the Pareto frontier."""
    equation: ASTNode
    mse: float
    comp: int
    latex: str
    equation_id: str

    def to_dict(self):
        return {
            "complexity": self.comp,
            "mse": self.mse,
            "latex": self.latex,
            "equation_id": self.equation_id,
        }


def compute_pareto_frontier(
    candidates: List[Tuple[ASTNode, float, int]],
    variables: List[str],
) -> List[ParetoPoint]:
    """Compute Pareto frontier from candidate equations.

    Args:
        candidates: List of (ASTNode, mse, complexity) tuples.
        variables: Variable names for LaTeX rendering.

    Returns:
        List of ParetoPoint sorted by complexity.
    """
    if not candidates:
        return []

    # Sort by complexity
    candidates.sort(key=lambda x: x[2])

    frontier: List[Tuple[ASTNode, float, int]] = []
    best_mse = float("inf")

    # Iterate from simplest to most complex
    for eq, mse, comp in candidates:
        if mse < best_mse:
            best_mse = mse
            frontier.append((eq, mse, comp))

    # Convert to ParetoPoints with LaTeX
    from sympy import Symbol, latex

    var_dict = {v: Symbol(v) for v in variables}
    var_dict["t"] = Symbol("t")

    points = []
    for i, (eq, mse, comp) in enumerate(frontier):
        try:
            expr = eq.to_sympy(var_dict)
            lt = latex(expr)
        except Exception:
            lt = str(eq)

        points.append(
            ParetoPoint(
                equation=eq,
                mse=mse,
                comp=comp,
                latex=lt,
                equation_id=f"eq_{i:04d}",
            )
        )

    return points


def select_best_equation(
    frontier: List[ParetoPoint],
    complexity_weight: float = 0.001,
) -> ParetoPoint:
    """Select the best equation using a weighted score.

    score = mse + complexity_weight * complexity
    """
    if not frontier:
        raise ValueError("Empty Pareto frontier")

    scored = [(p, p.mse + complexity_weight * p.comp) for p in frontier]
    scored.sort(key=lambda x: x[1])
    return scored[0][0]
