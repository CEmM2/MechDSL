"""Tests for forward type propagation and BinOp resolution."""

from algo2code.algo_parser import parse_algorithm
from algo2code.ast_nodes import BinOp, Branch, VarType
from algo2code.type_inference import infer_types


class TestTypeInference:
    def test_dot_product(self, pcg_latex):
        algo = parse_algorithm(pcg_latex)
        infer_types(algo)
        # rho = r^T z should be scalar
        rho_assign = algo.body[3]
        assert rho_assign.value.inferred_type == VarType.SCALAR

    def test_matvec(self, pcg_latex):
        algo = parse_algorithm(pcg_latex)
        infer_types(algo)
        # r = b - A·x : RHS should be vector
        r_assign = algo.body[0]
        rhs = r_assign.value
        assert rhs.inferred_type == VarType.VECTOR

    def test_norm_is_scalar(self, pcg_latex):
        algo = parse_algorithm(pcg_latex)
        infer_types(algo)
        # Find the If condition: ||r|| < tol
        for_body = algo.body[4].body
        if_stmt = next(s for s in for_body if isinstance(s, Branch))
        cond = if_stmt.condition
        assert isinstance(cond, BinOp)
        assert cond.left.inferred_type == VarType.SCALAR  # norm result
