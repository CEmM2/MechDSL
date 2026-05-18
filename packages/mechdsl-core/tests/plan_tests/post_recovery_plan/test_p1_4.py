"""Tests for Task P1-4: Emit f_ext init Taichi kernel from lowered Neumann BC."""

from __future__ import annotations

import ast

import pytest

from mechdsl.codegen.taichi_printer import (
    EmissionContext,
    NeumannKernelSpec,
    _sanitize_kernel_suffix,
    emit_neumann_f_ext_kernel,
)


@pytest.fixture
def spec_load_z1():
    return NeumannKernelSpec(
        bc_name="load",
        surface_tag="z1",
        per_node_force=(0.0, 0.0, -250.0),
    )


def _emit(spec: NeumannKernelSpec) -> tuple[str, str]:
    """Return (kernel_function_name, emitted_source)."""
    ctx = EmissionContext()
    name = emit_neumann_f_ext_kernel(ctx, spec)
    return name, ctx.get_source()


class TestTaskP1_4:
    """Tests for Task P1-4: Taichi @ti.kernel emission for f_ext from Neumann BC."""

    @pytest.mark.integration
    def test_emit_kernel_zeroes_outside_surface(self, spec_load_z1):
        """
        Acceptance criterion #1: emitted kernel zeroes f_ext globally then
        writes per-node force on tagged surface nodes only.
        """
        _, src = _emit(spec_load_z1)
        # Global zero loop must precede the surface-write loop.
        zero_idx = src.find("f_ext[i][d] = 0.0")
        write_idx = src.find("f_ext[nid][0]")
        assert 0 < zero_idx < write_idx, (
            f"zero-loop must precede surface-write loop; got zero@{zero_idx}, write@{write_idx}"
        )
        # Tagged-node assignment carries the per_node_force tuple values
        # (deterministic-format helper strips trailing zeros from round
        # numbers, so 250.0 emits as ``-250`` — Taichi coerces the int
        # literal to f64 at the assignment site).
        assert "f_ext[nid][2] = -250" in src

    @pytest.mark.integration
    def test_emitted_source_is_valid_python(self, spec_load_z1):
        """
        Acceptance criterion #2 (precondition): the emitted source must
        parse as Python — confirms the kernel signature and body are
        syntactically clean before any Taichi-side compile.
        """
        _, src = _emit(spec_load_z1)
        # Wrap in a dummy `import taichi as ti` + `n_nodes/f_ext` placeholders
        # so the parser sees the full surface (the kernel body refers to
        # `f_ext` which only exists in the full emitted file).
        parseable = ("import taichi as ti\nn_nodes = 0\nf_ext = []\n") + src
        ast.parse(parseable)

    @pytest.mark.integration
    def test_jit_budget_probe_under_kernel_limit(self, spec_load_z1):
        """
        Acceptance criterion #2: emitted kernel body line count stays well
        under the per-kernel JIT budget (≤ 2000 lines per @ti.kernel from
        .claude/CLAUDE.md). The Neumann emitter is fixed-size by design,
        so a tight upper bound (50 lines) is the right regression guard.
        """
        _, src = _emit(spec_load_z1)
        # Slice from "@ti.kernel" to next blank-blank delimiter (the emitter
        # writes two empty lines after the kernel).
        kernel_lines = []
        capturing = False
        for line in src.splitlines():
            if line.strip().startswith("@ti.kernel"):
                capturing = True
                continue
            if capturing:
                kernel_lines.append(line)
                if line == "" and kernel_lines and kernel_lines[-2:] == ["", ""]:
                    break
        assert len(kernel_lines) <= 50, (
            f"emitted kernel has {len(kernel_lines)} lines, expected ≤ 50 "
            "(generous bound vs the 2000-line per-kernel JIT cap)"
        )

    @pytest.mark.integration
    def test_kernel_callable_signature_stable(self, spec_load_z1):
        """
        Acceptance criterion #3: kernel name follows
        ``init_f_ext_from_neumann_<sanitized_bc_name>`` and signature
        accepts a 1-D int32 ndarray of surface node indices.
        """
        name, src = _emit(spec_load_z1)
        assert name == "init_f_ext_from_neumann_load"
        assert f"def {name}(surface_nodes: ti.types.ndarray(dtype=ti.i32, ndim=1)):" in src

    @pytest.mark.integration
    def test_kernel_docstring_mentions_surface_tag(self, spec_load_z1):
        """
        Emitted docstring documents the surface tag and per-node force —
        downstream readers can audit the emission without re-running the
        lowering pass.
        """
        _, src = _emit(spec_load_z1)
        assert "Surface tag: 'z1'" in src
        assert "Per-node force" in src

    @pytest.mark.integration
    def test_index_partitioning_rule(self, spec_load_z1):
        """
        Mesh indices (i over n_nodes, k over surface_nodes) use runtime
        ``range`` loops; spatial component (d) uses ``ti.static`` per the
        index-partitioning rule (.claude/CLAUDE.md).
        """
        _, src = _emit(spec_load_z1)
        assert "for i in range(n_nodes):" in src
        assert "for k in range(n_surface):" in src
        assert "for d in ti.static(range(3)):" in src

    @pytest.mark.integration
    def test_sanitize_kernel_suffix_handles_special_chars(self):
        """BC names with hyphens/dots get sanitised into valid identifiers."""
        assert _sanitize_kernel_suffix("load-top") == "load_top"
        assert _sanitize_kernel_suffix("load.0") == "load_0"
        assert _sanitize_kernel_suffix("123load") == "_123load"
        assert _sanitize_kernel_suffix("") == "bc"

    @pytest.mark.integration
    def test_multiple_specs_emit_distinct_kernels(self):
        """Two different BC specs produce two distinct kernels with
        independent names; surface tag and per-node force are independent
        per emission."""
        ctx = EmissionContext()
        n1 = emit_neumann_f_ext_kernel(
            ctx,
            NeumannKernelSpec(
                bc_name="load_top", surface_tag="z1", per_node_force=(0.0, 0.0, -100.0)
            ),
        )
        n2 = emit_neumann_f_ext_kernel(
            ctx,
            NeumannKernelSpec(
                bc_name="load_side", surface_tag="x1", per_node_force=(50.0, 0.0, 0.0)
            ),
        )
        src = ctx.get_source()
        assert n1 == "init_f_ext_from_neumann_load_top"
        assert n2 == "init_f_ext_from_neumann_load_side"
        assert n1 in src and n2 in src
        assert "f_ext[nid][2] = -100" in src
        assert "f_ext[nid][0] = 50" in src
