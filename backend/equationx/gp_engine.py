"""Genetic programming engine for equation discovery using DEAP."""
from __future__ import annotations

import copy
import math
import random
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from deap import base, creator, tools, algorithms

from .grammar import ASTNode, BINARY_OPS, UNARY_OPS, Grammar, complexity


# ---------------------------------------------------------------------------
# Creator (DEAP)
# ---------------------------------------------------------------------------

if not hasattr(creator, "FitnessMin"):
    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
if not hasattr(creator, "Individual"):
    creator.create("Individual", list, fitness=creator.FitnessMin)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _eval_individual(
    individual: List[int],
    grammar: Grammar,
    X: np.ndarray,
    y: np.ndarray,
    variable_names: List[str],
    target_idx: int,
) -> Tuple[float]:
    """Evaluate an individual (encoded as node list) against data."""
    try:
        tree = _decode_individual(individual, grammar)
        var_dict = {v: __import__("sympy").Symbol(v) for v in variable_names}
        var_dict["t"] = __import__("sympy").Symbol("t")
        expr = tree.to_sympy(var_dict)

        # Convert to numerical function
        sympy_vars = [var_dict[v] for v in variable_names]
        func = __import__("sympy").lambdify(sympy_vars, expr, modules=["numpy", "math"])

        # Evaluate on data
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
        # Combine MSE with complexity penalty
        score = mse + 0.001 * comp
        return (score,)
    except Exception:
        return (1e10,)


# ---------------------------------------------------------------------------
# Individual encoding / decoding
# ---------------------------------------------------------------------------

def _encode_tree(tree: ASTNode) -> List[int]:
    """Flatten AST into a list of integers for DEAP."""
    nodes = []
    _flatten(tree, nodes)
    return nodes


def _flatten(node: ASTNode, out: List[int]):
    if node.op is None:
        out.append(0)  # terminal marker
        if isinstance(node.value, (int, float)):
            out.append(1)  # constant
            out.append(int(node.value * 1000))
        else:
            out.append(0)  # variable
            out.append(hash(str(node.value)) % 100)
    else:
        op_list = list(BINARY_OPS.keys()) + list(UNARY_OPS.keys())
        idx = op_list.index(node.op) + 2 if node.op in op_list else 1
        out.append(idx)
        out.append(len(node.children))
        for c in node.children:
            _flatten(c, out)


def _decode_individual(individual: List[int], grammar: Grammar) -> ASTNode:
    """Decode a flat integer list back into an ASTNode."""
    pos = [0]

    def _read() -> ASTNode:
        if pos[0] >= len(individual):
            return grammar.random_terminal()

        marker = individual[pos[0]]
        pos[0] += 1

        if marker == 0:  # terminal
            is_const = individual[pos[0]] if pos[0] < len(individual) else 0
            pos[0] += 1
            val = individual[pos[0]] if pos[0] < len(individual) else 0
            pos[0] += 1
            if is_const == 1:
                return ASTNode(value=val / 1000.0)
            else:
                var_idx = val % len(grammar.all_vars)
                return ASTNode(value=grammar.all_vars[var_idx])
        else:
            op_list = list(BINARY_OPS.keys()) + list(UNARY_OPS.keys())
            if marker - 2 < len(op_list):
                op_name = op_list[marker - 2]
            else:
                op_name = "+"
            n_children = individual[pos[0]] if pos[0] < len(individual) else 2
            pos[0] += 1
            children = [_read() for _ in range(max(1, min(n_children, 3)))]
            return ASTNode(op=op_name, children=children)

    return _read()


# ---------------------------------------------------------------------------
# GP Engine
# ---------------------------------------------------------------------------

class GPEngine:
    """Genetic programming engine for symbolic regression."""

    def __init__(
        self,
        grammar: Grammar,
        population_size: int = 200,
        max_generations: int = 100,
        crossover_prob: float = 0.7,
        mutation_prob: float = 0.2,
        tournament_size: int = 5,
    ):
        self.grammar = grammar
        self.pop_size = population_size
        self.max_gen = max_generations
        self.cx_prob = crossover_prob
        self.mut_prob = mutation_prob
        self.tourn_size = tournament_size

        self.toolbox = base.Toolbox()
        self._setup_toolbox()

    def _setup_toolbox(self):
        self.toolbox.register("individual", self._random_individual)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)
        self.toolbox.register("select", tools.selTournament, tournsize=self.tourn_size)
        self.toolbox.register("mate", self._crossover)
        self.toolbox.register("mutate", self._mutate)

    def _random_individual(self):
        tree = self.grammar.random_tree()
        return creator.Individual(_encode_tree(tree))

    def _crossover(self, ind1, ind2):
        """Subtree crossover."""
        # Find a subtree in each and swap
        try:
            tree1 = _decode_individual(list(ind1), self.grammar)
            tree2 = _decode_individual(list(ind2), self.grammar)
            # Simple: swap random subtrees by re-encoding
            cxpoint = random.randint(1, min(len(ind1), len(ind2)) - 1)
            ind1[cxpoint:], ind2[cxpoint:] = ind2[cxpoint:], ind1[cxpoint:]
        except Exception:
            pass
        return ind1, ind2

    def _mutate(self, ind):
        """Point mutation or subtree mutation."""
        try:
            if random.random() < 0.5:
                # point mutation
                idx = random.randint(0, len(ind) - 1)
                ind[idx] = random.randint(0, max(ind) if ind else 10)
            else:
                # subtree mutation: replace part with new random tree
                tree = self.grammar.random_tree(max_depth=3)
                new_part = _encode_tree(tree)
                point = random.randint(0, len(ind) - 1)
                ind[point:point + 1] = new_part
        except Exception:
            pass
        return (ind,)

    def run(
        self,
        X: np.ndarray,
        y: np.ndarray,
        variable_names: List[str],
        target_idx: int,
        callback: Optional[Callable[[int, float, ASTNode], None]] = None,
    ) -> List[Tuple[ASTNode, float, int]]:
        """Run GP and return Pareto-optimal equations."""
        self.toolbox.register(
            "evaluate",
            _eval_individual,
            grammar=self.grammar,
            X=X,
            y=y,
            variable_names=variable_names,
            target_idx=target_idx,
        )

        pop = self.toolbox.population(n=self.pop_size)
        hof = tools.ParetoFront()

        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", np.mean)
        stats.register("min", np.min)

        pop, logbook = algorithms.eaMuPlusLambda(
            pop,
            self.toolbox,
            mu=self.pop_size,
            lambda_=self.pop_size,
            cxpb=self.cx_prob,
            mutpb=self.mut_prob,
            ngen=self.max_gen,
            stats=stats,
            halloffame=hof,
            verbose=False,
        )

        # Convert hall of fame to (ASTNode, mse, complexity)
        results = []
        seen = set()
        for ind in hof:
            try:
                tree = _decode_individual(list(ind), self.grammar)
                comp = complexity(tree)
                mse = ind.fitness.values[0] if ind.fitness.valid else 1e10
                key = str(tree)
                if key not in seen and mse < 1e9:
                    seen.add(key)
                    results.append((tree, mse, comp))
            except Exception:
                continue

        # Sort by MSE for Pareto frontier
        results.sort(key=lambda x: x[1])

        if callback and results:
            best = results[0]
            callback(self.max_gen, best[1], best[0])

        return results
