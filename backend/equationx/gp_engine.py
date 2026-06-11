"""High-performance genetic programming engine using DEAP + scipy optimization."""
from __future__ import annotations

import math
import random
from typing import Callable, List, Optional, Tuple

import numpy as np
from deap import base, creator

from .grammar import ASTNode, Grammar, complexity

try:
    from scipy.optimize import minimize
    _HAS_SCIPY_OPT = True
except ImportError:
    _HAS_SCIPY_OPT = False


if not hasattr(creator, "FitnessMin"):
    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
if not hasattr(creator, "Individual"):
    creator.create("Individual", list, fitness=creator.FitnessMin)


def _find_constants(tree: ASTNode) -> List[int]:
    """Return paths to all constant nodes in the tree."""
    paths = []

    def _walk(node: ASTNode, path: List[int]):
        if node.op is None and isinstance(node.value, (int, float)):
            paths.append(path[:])
        for i, child in enumerate(node.children):
            _walk(child, path + [i])

    _walk(tree, [])
    return paths


def _set_constant(tree: ASTNode, path: List[int], value: float):
    """Set a constant at a given path in the tree."""
    node = tree
    for idx in path:
        node = node.children[idx]
    node.value = round(value, 6)


def _get_constants_vec(tree: ASTNode) -> List[float]:
    """Extract all constants as a flat vector."""
    vals = []

    def _walk(node: ASTNode):
        if node.op is None and isinstance(node.value, (int, float)):
            vals.append(float(node.value))
        for child in node.children:
            _walk(child)

    _walk(tree)
    return vals


def _optimize_constants(
    tree: ASTNode,
    grammar: Grammar,
    X: np.ndarray,
    y: np.ndarray,
    variable_names: List[str],
) -> ASTNode:
    """Optimize numeric constants in the tree using scipy BFGS."""
    if not _HAS_SCIPY_OPT:
        return tree

    const_paths = _find_constants(tree)
    if not const_paths:
        return tree

    opt_tree = _deep_copy_tree(tree)
    import sympy

    def _make_func(params):
        t = _deep_copy_tree(opt_tree)
        for path, val in zip(const_paths, params):
            _set_constant(t, path, val)
        var_dict = {v: sympy.Symbol(v) for v in variable_names}
        var_dict["t"] = sympy.Symbol("t")
        try:
            expr = t.to_sympy(var_dict)
            sympy_vars = [var_dict[v] for v in variable_names]
            f = sympy.lambdify(sympy_vars, expr, modules=["numpy", "math"])
            preds = np.array([float(f(*row)) for row in X])
            preds = np.nan_to_num(preds, nan=0.0, posinf=1e10, neginf=-1e10)
            return float(np.mean((preds - y) ** 2))
        except Exception:
            return 1e10

    init = _get_constants_vec(opt_tree)
    if not init:
        return tree

    try:
        res = minimize(_make_func, init, method="BFGS", options={"maxiter": 50, "disp": False})
        if res.fun < _make_func(init):
            for path, val in zip(const_paths, res.x):
                _set_constant(opt_tree, path, val)
    except Exception:
        pass

    return opt_tree


def _deep_copy_tree(node: ASTNode) -> ASTNode:
    """Deep copy an ASTNode tree."""
    if node.op is None:
        return ASTNode(value=node.value)
    new = ASTNode(op=node.op, children=[_deep_copy_tree(c) for c in node.children],
                  is_derivative=node.is_derivative, deriv_var=node.deriv_var,
                  deriv_order=node.deriv_order)
    return new


def _random_expression(grammar: Grammar, max_depth: int = None) -> ASTNode:
    """Generate a random expression tree."""
    if max_depth is None:
        max_depth = grammar.max_depth
    return grammar.random_tree(max_depth=max_depth)


def _crossover_trees(parent1: ASTNode, parent2: ASTNode) -> Tuple[ASTNode, ASTNode]:
    """Subtree crossover: swap a random subtree between two parents."""
    p1 = _deep_copy_tree(parent1)
    p2 = _deep_copy_tree(parent2)

    def _random_subtree(node: ASTNode) -> Optional[ASTNode]:
        if node.op is None:
            return node
        if random.random() < 0.3:
            return node
        if node.children:
            return _random_subtree(random.choice(node.children))
        return node

    def _replace_subtree(root: ASTNode, target: ASTNode, replacement: ASTNode) -> ASTNode:
        if root is target:
            return _deep_copy_tree(replacement)
        new = _deep_copy_tree(root)
        for i, child in enumerate(new.children):
            new.children[i] = _replace_subtree(child, target, replacement)
        return new

    s1 = _random_subtree(p1)
    s2 = _random_subtree(p2)

    try:
        child1 = _replace_subtree(p1, s1, s2)
        child2 = _replace_subtree(p2, s2, s1)
        return child1, child2
    except RecursionError:
        return p1, p2


def _mutate_tree(tree: ASTNode, grammar: Grammar) -> ASTNode:
    """Subtree mutation: replace a random subtree with a new random one."""
    t = _deep_copy_tree(tree)

    def _mutate_node(node: ASTNode, depth: int = 0) -> ASTNode:
        if node.op is None:
            if random.random() < 0.3:
                return grammar.random_tree(max_depth=min(3, grammar.max_depth))
            return node
        if random.random() < 0.2:
            return grammar.random_tree(max_depth=min(3, grammar.max_depth))
        new = _deep_copy_tree(node)
        for i, child in enumerate(new.children):
            new.children[i] = _mutate_node(child, depth + 1)
        return new

    return _mutate_node(t)


def _eval_individual_ast(
    tree: ASTNode,
    grammar: Grammar,
    X: np.ndarray,
    y: np.ndarray,
    variable_names: List[str],
    target_idx: int,
) -> Tuple[float]:
    """Evaluate an AST tree against data and return (score,)."""
    try:
        import sympy
        var_dict = {v: sympy.Symbol(v) for v in variable_names}
        var_dict["t"] = sympy.Symbol("t")
        expr = tree.to_sympy(var_dict)

        sympy_vars = [var_dict[v] for v in variable_names]
        func = sympy.lambdify(sympy_vars, expr, modules=["numpy", "math"])

        predictions = []
        for row in X:
            try:
                val = float(func(*row))
                if math.isnan(val) or math.isinf(val):
                    return (1e10,)
                predictions.append(val)
            except Exception:
                return (1e10,)

        predictions = np.array(predictions)
        mse = float(np.mean((predictions - y) ** 2))
        comp = complexity(tree)
        score = mse + 0.001 * comp
        return (max(1e-12, score),)
    except Exception:
        return (1e10,)


class GPEngine:
    """High-performance genetic programming engine for symbolic regression."""

    def __init__(
        self,
        grammar: Grammar,
        population_size: int = 200,
        max_generations: int = 100,
        crossover_prob: float = 0.8,
        mutation_prob: float = 0.3,
        tournament_size: int = 7,
        hall_of_fame_size: int = 50,
        optimize_constants: bool = True,
    ):
        self.grammar = grammar
        self.pop_size = population_size
        self.max_gen = max_generations
        self.cx_prob = crossover_prob
        self.mut_prob = mutation_prob
        self.tourn_size = tournament_size
        self.hof_size = hall_of_fame_size
        self.optimize_constants = optimize_constants

    def run(
        self,
        X: np.ndarray,
        y: np.ndarray,
        variable_names: List[str],
        target_idx: int,
        callback: Optional[Callable[[int, float, ASTNode], None]] = None,
    ) -> List[Tuple[ASTNode, float, int]]:
        """Run GP and return Pareto-optimal equations."""

        # Create initial population
        pop = []
        for _ in range(self.pop_size):
            tree = _random_expression(self.grammar)
            pop.append(tree)

        hof = []
        best_mse = float("inf")

        for gen in range(self.max_gen):
            # Evaluate
            fitnesses = []
            for tree in pop:
                fit = _eval_individual_ast(
                    tree, self.grammar, X, y, variable_names, target_idx
                )
                fitnesses.append(fit[0])

            # Track best
            gen_best = min(fitnesses)
            if gen_best < best_mse:
                best_mse = gen_best
                best_tree = pop[fitnesses.index(gen_best)]
                if self.optimize_constants:
                    best_tree = _optimize_constants(
                        best_tree, self.grammar, X, y, variable_names
                    )
                hof.append((_deep_copy_tree(best_tree), gen_best, complexity(best_tree)))
                hof = sorted(hof, key=lambda x: x[1])[:self.hof_size]

            if callback:
                callback(gen, gen_best, pop[fitnesses.index(gen_best)])

            # Selection (tournament)
            selected = []
            for _ in range(self.pop_size):
                tourn = random.sample(list(zip(pop, fitnesses)), min(self.tourn_size, len(pop)))
                winner = min(tourn, key=lambda x: x[1])
                selected.append(winner[0])

            # Crossover & mutation
            offspring = []
            for i in range(0, len(selected), 2):
                p1 = selected[i]
                p2 = selected[(i + 1) % len(selected)]
                if random.random() < self.cx_prob:
                    c1, c2 = _crossover_trees(p1, p2)
                else:
                    c1, c2 = _deep_copy_tree(p1), _deep_copy_tree(p2)
                if random.random() < self.mut_prob:
                    c1 = _mutate_tree(c1, self.grammar)
                if random.random() < self.mut_prob:
                    c2 = _mutate_tree(c2, self.grammar)
                offspring.extend([c1, c2])

            pop = offspring[:self.pop_size]

        # Constant optimization on final hall of fame
        if self.optimize_constants:
            optimized_hof = []
            for tree, mse_val, comp in hof:
                opt_tree = _optimize_constants(tree, self.grammar, X, y, variable_names)
                new_fit = _eval_individual_ast(
                    opt_tree, self.grammar, X, y, variable_names, target_idx
                )[0]
                optimized_hof.append((opt_tree, new_fit, complexity(opt_tree)))
            hof = optimized_hof

        hof.sort(key=lambda x: x[1])
        return hof
