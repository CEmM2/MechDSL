"""Tests for the algpseudocode control-flow parser."""

from algo2code.algo_parser import parse_algorithm
from algo2code.ast_nodes import Assign, Branch, ForLoop, Return, VarType


class TestAlgoParser:
    def test_parses_name(self, pcg_latex):
        algo = parse_algorithm(pcg_latex)
        assert algo.name == "pcg"

    def test_parses_backend(self, pcg_latex):
        algo = parse_algorithm(pcg_latex)
        assert algo.backend == "taichi"

    def test_parses_args(self, pcg_latex):
        algo = parse_algorithm(pcg_latex)
        assert len(algo.args) == 6
        names = [n for n, _ in algo.args]
        assert "A" in names
        assert "b" in names

    def test_parses_type_directives(self, pcg_latex):
        algo = parse_algorithm(pcg_latex)
        assert algo.type_annotations["r"] == VarType.VECTOR
        assert algo.type_annotations["rho"] == VarType.SCALAR

    def test_body_structure(self, pcg_latex):
        algo = parse_algorithm(pcg_latex)
        # Should have: 4 assignments, 1 for loop, 1 return
        assert len(algo.body) == 6
        assert isinstance(algo.body[0], Assign)  # r = ...
        assert isinstance(algo.body[1], Assign)  # z = ...
        assert isinstance(algo.body[2], Assign)  # p = ...
        assert isinstance(algo.body[3], Assign)  # rho = ...
        assert isinstance(algo.body[4], ForLoop)
        assert isinstance(algo.body[5], Return)

    def test_for_loop(self, pcg_latex):
        algo = parse_algorithm(pcg_latex)
        for_stmt = algo.body[4]
        assert isinstance(for_stmt, ForLoop)
        assert for_stmt.var == "k"
        assert for_stmt.start == 0
        assert for_stmt.end_expr == "maxiter"

    def test_if_branch(self, pcg_latex):
        algo = parse_algorithm(pcg_latex)
        for_body = algo.body[4].body
        if_stmts = [s for s in for_body if isinstance(s, Branch)]
        assert len(if_stmts) == 1
        if_stmt = if_stmts[0]
        assert len(if_stmt.if_body) == 1
        assert isinstance(if_stmt.if_body[0], Return)

    def test_return_values(self, pcg_latex):
        algo = parse_algorithm(pcg_latex)
        ret = algo.body[5]
        assert isinstance(ret, Return)
        assert len(ret.values) == 2
