"""Expression AST, grammar, and symbolic utilities for EquationX."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sympy import (
    Add,
    Derivative,
    Expr,
    Float,
    Function,
    Mul,
    Pow,
    S,
    Symbol,
    cos,
    exp,
    latex,
    log,
    simplify,
    sin,
    sqrt,
)
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

# ---------------------------------------------------------------------------
# Supported operators
# ---------------------------------------------------------------------------

BINARY_OPS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b if b != 0 else S.One,
}

UNARY_OPS = {
    "exp": exp,
    "log": log,
    "sin": sin,
    "cos": cos,
    "sqrt": sqrt,
}

TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
)


# ---------------------------------------------------------------------------
# AST Node
# ---------------------------------------------------------------------------

@dataclass
class ASTNode:
    """A node in the expression tree."""
    op: Optional[str] = None          # operator name or None for leaf
    children: List["ASTNode"] = None  # child nodes
    value: Optional[Any] = None       # numeric literal or variable name
    is_derivative: bool = False       # True if this node is d/dt
    deriv_var: Optional[str] = None   # variable being differentiated w.r.t.
    deriv_order: int = 1

    def __post_init__(self):
        if self.children is None:
            self.children = []

    # ------------------------------------------------------------------
    # Conversion to SymPy
    # ------------------------------------------------------------------

    def to_sympy(self, variables: Dict[str, Symbol]) -> Expr:
        """Convert AST node to a SymPy expression."""
        if self.op is None:
            # leaf
            if self.value is not None:
                try:
                    return Float(float(self.value))
                except (ValueError, TypeError):
                    name = str(self.value)
                    if name in variables:
                        return variables[name]
                    return Symbol(name)
            return S.Zero

        if self.is_derivative:
            inner = self.children[0].to_sympy(variables) if self.children else S.Zero
            t = variables.get(self.deriv_var, Symbol(self.deriv_var or "t"))
            return Derivative(inner, t, self.deriv_order)

        child_sympy = [c.to_sympy(variables) for c in self.children]

        if self.op in BINARY_OPS:
            result = child_sympy[0]
            for c in child_sympy[1:]:
                result = BINARY_OPS[self.op](result, c)
            return result

        if self.op in UNARY_OPS:
            return UNARY_OPS[self.op](child_sympy[0])

        raise ValueError(f"Unknown operator: {self.op}")

    # ------------------------------------------------------------------
    # String / LaTeX
    # ------------------------------------------------------------------

    def to_latex(self, variables: Dict[str, Symbol]) -> str:
        expr = self.to_sympy(variables)
        return latex(expr)

    def __repr__(self) -> str:
        if self.op is None:
            return str(self.value)
        args = ", ".join(repr(c) for c in self.children)
        return f"{self.op}({args})"


# ---------------------------------------------------------------------------
# Grammar helpers for GP
# ---------------------------------------------------------------------------

@dataclass
class Grammar:
    """Defines the search space for genetic programming."""
    variables: List[str]
    target: str
    operators: List[str] = None
    unary_ops: List[str] = None
    constants_range: tuple = (-2.0, 2.0)
    max_depth: int = 6

    def __post_init__(self):
        if self.operators is None:
            self.operators = list(BINARY_OPS.keys())
        if self.unary_ops is None:
            self.unary_ops = list(UNARY_OPS.keys())

    @property
    def all_vars(self) -> List[str]:
        return self.variables

    def random_terminal(self) -> ASTNode:
        """Return a random terminal node (variable or constant)."""
        if random.random() < 0.7:
            name = random.choice(self.all_vars)
            return ASTNode(value=name)
        else:
            const = random.uniform(*self.constants_range)
            return ASTNode(value=round(const, 3))

    def random_tree(self, max_depth: int = None, method="grow") -> ASTNode:
        """Generate a random expression tree using grow or full method."""
        if max_depth is None:
            max_depth = self.max_depth

        if max_depth <= 1 or (method == "grow" and random.random() < 0.3):
            return self.random_terminal()

        # choose operator
        if random.random() < 0.8 and self.operators:
            op = random.choice(self.operators)
            children = [self.random_tree(max_depth - 1, method) for _ in range(2)]
            return ASTNode(op=op, children=children)
        elif self.unary_ops:
            op = random.choice(self.unary_ops)
            child = self.random_tree(max_depth - 1, method)
            return ASTNode(op=op, children=[child])
        else:
            return self.random_terminal()


# ---------------------------------------------------------------------------
# Parsing from string
# ---------------------------------------------------------------------------

def parse_equation_string(eq_str: str, variables: List[str]) -> ASTNode:
    """Parse a string equation into an AST. Used for ground-truth in tests."""
    var_dict = {v: Symbol(v) for v in variables}
    var_dict["t"] = Symbol("t")
    expr = parse_expr(eq_str, local_dict=var_dict, transformations=TRANSFORMATIONS)
    return _sympy_to_ast(expr, variables)


def _sympy_to_ast(expr: Expr, variables: List[str]) -> ASTNode:
    """Convert a SymPy expression back to an ASTNode."""
    if expr.is_Symbol:
        return ASTNode(value=str(expr))
    if expr.is_number:
        return ASTNode(value=float(expr))
    if isinstance(expr, Derivative):
        inner = _sympy_to_ast(expr.args[0], variables)
        var = str(expr.variables[0])
        return ASTNode(
            is_derivative=True, children=[inner],
            deriv_var=var, deriv_order=expr.derivative_count,
        )
    if isinstance(expr, Add):
        children = [_sympy_to_ast(a, variables) for a in expr.args]
        result = children[0]
        for c in children[1:]:
            result = ASTNode(op="+", children=[result, c])
        return result
    if isinstance(expr, Mul):
        children = [_sympy_to_ast(a, variables) for a in expr.args]
        result = children[0]
        for c in children[1:]:
            result = ASTNode(op="*", children=[result, c])
        return result
    if isinstance(expr, Pow):
        base = _sympy_to_ast(expr.args[0], variables)
        exp_node = _sympy_to_ast(expr.args[1], variables)
        if exp_node.value == 0.5:
            return ASTNode(op="sqrt", children=[base])
        return ASTNode(op="pow", children=[base, exp_node])
    if isinstance(expr, Function):
        func_name = str(type(expr).__name__)
        children = [_sympy_to_ast(a, variables) for a in expr.args]
        return ASTNode(op=func_name, children=children)

    return ASTNode(value=str(expr))


# ---------------------------------------------------------------------------
# Simplification
# ---------------------------------------------------------------------------

def simplify_ast(node: ASTNode, variables: List[str]) -> ASTNode:
    """Simplify an AST by evaluating constant sub-expressions."""
    var_dict = {v: Symbol(v) for v in variables}
    var_dict["t"] = Symbol("t")
    try:
        expr = node.to_sympy(var_dict)
        simplified = simplify(expr)
        return _sympy_to_ast(simplified, variables)
    except Exception:
        return node


def complexity(node: ASTNode) -> int:
    """Compute the complexity (number of nodes) of an AST."""
    if node.op is None:
        return 1
    return 1 + sum(complexity(c) for c in node.children)
