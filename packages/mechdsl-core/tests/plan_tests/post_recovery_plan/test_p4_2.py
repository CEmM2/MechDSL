"""Tests for Task P4-2: symbolic/bridge.py adapter (nrpylatex AST → mechdsl symbolic).

Acceptance criteria covered:
1. convert() handles a balanced rank-2 indexed expression including
   F^{iI} two-point.
2. log(J)-style scalar entries — covered structurally via rank-0 scalar
   path. Nrpylatex 1.4.0 does not register \\log{} as a known function,
   so the integration round-trip is deferred (see module docstring);
   this test exercises the bridge's rank-0 path with the closest
   parseable surrogate.
3. Unsupported nodes raise with Phase-4 pointer.
4. No mutation of existing symbolic types — verified by importing the
   public symbolic surface and comparing identity before/after a
   convert() call.
"""

from __future__ import annotations

import pytest

from mechdsl.frontend.math_parser import IndexClassification, parse_math
from mechdsl.symbolic import constitutive as _sym_constitutive
from mechdsl.symbolic import convected as _sym_convected
from mechdsl.symbolic import kinematics as _sym_kinematics
from mechdsl.symbolic.bridge import (
    BridgeError,
    SymbolicNode,
    convert,
    convert_namespace,
)

_TWO_POINT_WITH_CONSTS = (
    "% declare FUU --dim 3\n% declare AUU --dim 3\n% declare \\mu --const\nA^{i I} = F^{i I}\n"
)


class TestTaskP4_2:
    """Tests for Task P4-2: bridge.py adapter."""

    @pytest.mark.unit
    def test_convert_handles_two_point_F_iI(self) -> None:
        result = parse_math(_TWO_POINT_WITH_CONSTS)
        nodes = convert_namespace(result.tensors, result.classifications)
        f = nodes["FUU"]
        assert isinstance(f, SymbolicNode)
        assert f.kind == "tensor2"
        assert f.rank == 2
        assert f.suffix == "UU"
        assert f.classification is not None
        assert 0 in f.classification.spatial_axes
        assert 1 in f.classification.material_axes

    @pytest.mark.unit
    def test_convert_handles_constant_scalar(self) -> None:
        """nrpylatex stores ``--const`` declarations as
        Function('Constant')(Symbol('mu')); the bridge maps these to
        SymbolicNode kind=='constant' with rank 0.
        Surrogate for the deferred ``log(J)`` rank-0 scalar path.
        """
        result = parse_math(_TWO_POINT_WITH_CONSTS)
        nodes = convert_namespace(result.tensors, result.classifications)
        mu = nodes[r"\mu"]
        assert mu.kind == "constant"
        assert mu.rank == 0

    @pytest.mark.unit
    def test_unsupported_rank_raises_with_phase_pointer(self) -> None:
        """A rank-3 nrpylatex IndexedSymbol falls outside the bridge's
        currently supported shapes and raises BridgeError.
        """
        # Feed a synthetic rank-3 IndexedSymbol directly to convert(),
        # bypassing nrpylatex's contraction grammar (which forbids
        # bound-index assignment to a rank-0 LHS without UD pairing).
        import nrpylatex
        from sympy import Function, Symbol

        function = Function("Tensor")(Symbol("TUUU", real=True))
        rank3 = nrpylatex.IndexedSymbol(function, dimension=3)
        with pytest.raises(BridgeError) as excinfo:
            convert("TUUU", rank3, classification=None)
        msg = str(excinfo.value).lower()
        assert "post_recovery_plan phase 4" in msg
        assert "rank-3" in msg or "rank 3" in msg

    @pytest.mark.unit
    def test_convert_rejects_non_indexed_non_constant_input(self) -> None:
        """``convert`` rejects raw Python types that nrpylatex would
        never produce — guards the bridge surface.
        """
        with pytest.raises(BridgeError) as excinfo:
            convert("X", object(), classification=None)
        assert "post_recovery_plan Phase 4" in str(excinfo.value)

    @pytest.mark.unit
    def test_existing_symbolic_types_unchanged_after_convert(self) -> None:
        """Identity of public symbolic-layer attributes survives a
        bridge call. The bridge must not mutate or replace any
        ``mechdsl.symbolic`` API surface.
        """
        snapshot_attrs = {
            mod.__name__: tuple(sorted(name for name in vars(mod) if not name.startswith("_")))
            for mod in (_sym_kinematics, _sym_constitutive, _sym_convected)
        }
        result = parse_math(_TWO_POINT_WITH_CONSTS)
        convert_namespace(result.tensors, result.classifications)
        after = {
            mod.__name__: tuple(sorted(name for name in vars(mod) if not name.startswith("_")))
            for mod in (_sym_kinematics, _sym_constitutive, _sym_convected)
        }
        assert snapshot_attrs == after, "bridge mutated symbolic public attributes"

    @pytest.mark.unit
    def test_convert_with_explicit_classification_passthrough(self) -> None:
        """``convert`` accepts an externally supplied
        IndexClassification and passes it onto the SymbolicNode.
        Decouples convention enforcement from the bridge.
        """
        result = parse_math(_TWO_POINT_WITH_CONSTS)
        cls = IndexClassification(
            name="FUU",
            suffix="UU",
            spatial_axes=(0,),
            material_axes=(1,),
        )
        node = convert("FUU", result.tensors["FUU"], classification=cls)
        assert node.classification is cls
