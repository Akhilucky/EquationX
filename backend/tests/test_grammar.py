"""Tests for grammar, AST, and parsing."""
import pytest
from equationx.grammar import ASTNode, Grammar, complexity, simplify_ast, BINARY_OPS, UNARY_OPS


class TestASTNode:
    def test_leaf_node(self):
        node = ASTNode(value=42)
        assert node.op is None
        assert node.value == 42
        assert node.children == []

    def test_binary_op(self):
        left = ASTNode(value="x")
        right = ASTNode(value="y")
        node = ASTNode(op="+", children=[left, right])
        assert node.op == "+"
        assert len(node.children) == 2

    def test_to_sympy_binary(self):
        from sympy import Symbol
        x, y = Symbol("x"), Symbol("y")
        variables = {"x": x, "y": y, "t": Symbol("t")}
        left = ASTNode(value="x")
        right = ASTNode(value="y")
        node = ASTNode(op="+", children=[left, right])
        expr = node.to_sympy(variables)
        assert expr == x + y

    def test_to_sympy_unary(self):
        from sympy import Symbol
        x = Symbol("x")
        variables = {"x": x, "t": Symbol("t")}
        child = ASTNode(value="x")
        node = ASTNode(op="exp", children=[child])
        expr = node.to_sympy(variables)
        assert expr == __import__("sympy").exp(x)

    def test_to_latex(self):
        from sympy import Symbol
        x, y = Symbol("x"), Symbol("y")
        variables = {"x": x, "y": y, "t": Symbol("t")}
        left = ASTNode(value="x")
        right = ASTNode(value="y")
        node = ASTNode(op="+", children=[left, right])
        latex = node.to_latex(variables)
        assert "x" in latex
        assert "y" in latex

    def test_complexity(self):
        leaf = ASTNode(value=1)
        assert complexity(leaf) == 1

        left = ASTNode(value="x")
        right = ASTNode(value="y")
        parent = ASTNode(op="+", children=[left, right])
        assert complexity(parent) == 3

    def test_repr(self):
        node = ASTNode(value="x")
        assert repr(node) == "x"


class TestGrammar:
    def test_random_terminal_returns_node(self):
        grammar = Grammar(variables=["x", "y"], target="x")
        for _ in range(20):
            term = grammar.random_terminal()
            assert isinstance(term, ASTNode)
            assert term.value is not None

    def test_random_tree(self):
        grammar = Grammar(variables=["x", "y"], target="x", max_depth=3)
        tree = grammar.random_tree()
        assert isinstance(tree, ASTNode)
        assert complexity(tree) >= 1

    def test_random_tree_full(self):
        grammar = Grammar(variables=["x"], target="x", max_depth=4)
        tree = grammar.random_tree(method="full")
        assert isinstance(tree, ASTNode)
