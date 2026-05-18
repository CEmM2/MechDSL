"""Tests for mechdsl.solver.history_fields (Task P8.3).

Covers: registration, get/set, commit/rollback lifecycle, in-place
semantics, factory helper, and error paths.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.solver.history_fields import HistoryFields, create_j2_history

# -- 1. Initial state --------------------------------------------------------


class TestInitialState:
    """All fields zero right after creation."""

    def test_empty_after_init(self) -> None:
        h = HistoryFields()
        assert h.field_names == []

    def test_zero_after_register(self) -> None:
        h = HistoryFields()
        h.register("foo", (4, 3))
        np.testing.assert_array_equal(h.get_current("foo"), np.zeros((4, 3)))
        np.testing.assert_array_equal(h.get_old("foo"), np.zeros((4, 3)))


# -- 2. Register and get -----------------------------------------------------


class TestRegisterAndGet:
    """register → get_current / get_old return arrays with correct shape and dtype."""

    def test_shape(self) -> None:
        h = HistoryFields()
        h.register("bar", (2, 8, 6))
        assert h.get_current("bar").shape == (2, 8, 6)
        assert h.get_old("bar").shape == (2, 8, 6)

    def test_dtype_float64(self) -> None:
        h = HistoryFields()
        h.register("x", (5,))
        assert h.get_current("x").dtype == np.float64
        assert h.get_old("x").dtype == np.float64


# -- 3. set_current -----------------------------------------------------------


class TestSetCurrent:
    """set_current updates the current buffer."""

    def test_set_and_read_back(self) -> None:
        h = HistoryFields()
        h.register("s", (3,))
        vals = np.array([1.0, 2.0, 3.0])
        h.set_current("s", vals)
        np.testing.assert_array_equal(h.get_current("s"), vals)

    def test_set_does_not_affect_old(self) -> None:
        h = HistoryFields()
        h.register("s", (3,))
        h.set_current("s", np.ones(3))
        np.testing.assert_array_equal(h.get_old("s"), np.zeros(3))


# -- 4. Commit ---------------------------------------------------------------


class TestCommit:
    """After commit, old equals current."""

    def test_commit_copies_current_to_old(self) -> None:
        h = HistoryFields()
        h.register("a", (4,))
        h.set_current("a", np.arange(4, dtype=np.float64))
        h.commit()
        np.testing.assert_array_equal(h.get_old("a"), h.get_current("a"))


# -- 5. Rollback --------------------------------------------------------------


class TestRollback:
    """After rollback, current is restored to old."""

    def test_rollback_restores_current(self) -> None:
        h = HistoryFields()
        h.register("a", (3,))
        # old stays zero; set current to something
        h.set_current("a", np.array([10.0, 20.0, 30.0]))
        h.rollback()
        np.testing.assert_array_equal(h.get_current("a"), np.zeros(3))


# -- 6. Commit-modify-rollback -----------------------------------------------


class TestCommitModifyRollback:
    """Current is restored to the last committed value, not zero."""

    def test_cycle(self) -> None:
        h = HistoryFields()
        h.register("v", (2,))
        committed = np.array([5.0, 6.0])
        h.set_current("v", committed)
        h.commit()

        # Modify current further
        h.set_current("v", np.array([100.0, 200.0]))
        assert h.get_current("v")[0] == 100.0  # sanity

        h.rollback()
        np.testing.assert_array_equal(h.get_current("v"), committed)


# -- 7. Multiple fields -------------------------------------------------------


class TestMultipleFields:
    """commit / rollback affect ALL registered fields."""

    def test_commit_all(self) -> None:
        h = HistoryFields()
        h.register("x", (2,))
        h.register("y", (3,))
        h.set_current("x", np.ones(2))
        h.set_current("y", np.ones(3) * 7.0)
        h.commit()
        np.testing.assert_array_equal(h.get_old("x"), np.ones(2))
        np.testing.assert_array_equal(h.get_old("y"), np.ones(3) * 7.0)

    def test_rollback_all(self) -> None:
        h = HistoryFields()
        h.register("x", (2,))
        h.register("y", (3,))
        h.set_current("x", np.ones(2))
        h.set_current("y", np.ones(3) * 7.0)
        h.commit()

        h.set_current("x", np.array([99.0, 99.0]))
        h.set_current("y", np.array([99.0, 99.0, 99.0]))
        h.rollback()

        np.testing.assert_array_equal(h.get_current("x"), np.ones(2))
        np.testing.assert_array_equal(h.get_current("y"), np.ones(3) * 7.0)


# -- 8. Sequential cycles ----------------------------------------------------


class TestSequentialCycles:
    """commit, modify, commit, rollback → restores to last commit, not first."""

    def test_two_commits(self) -> None:
        h = HistoryFields()
        h.register("z", (2,))

        # First commit
        h.set_current("z", np.array([1.0, 2.0]))
        h.commit()

        # Second commit with different values
        h.set_current("z", np.array([10.0, 20.0]))
        h.commit()

        # Modify again
        h.set_current("z", np.array([999.0, 999.0]))

        # Rollback should restore to second commit
        h.rollback()
        np.testing.assert_array_equal(h.get_current("z"), np.array([10.0, 20.0]))


# -- 9. field_names -----------------------------------------------------------


class TestFieldNames:
    """field_names returns list of registered names."""

    def test_names(self) -> None:
        h = HistoryFields()
        h.register("alpha", (4,))
        h.register("beta", (4,))
        assert set(h.field_names) == {"alpha", "beta"}

    def test_empty(self) -> None:
        h = HistoryFields()
        assert h.field_names == []


# -- 10. __contains__ ---------------------------------------------------------


class TestContains:
    """``in`` operator works for registered / unregistered names."""

    def test_registered(self) -> None:
        h = HistoryFields()
        h.register("alpha", (4,))
        assert "alpha" in h

    def test_unregistered(self) -> None:
        h = HistoryFields()
        assert "nope" not in h


# -- 11. create_j2_history factory -------------------------------------------


class TestCreateJ2History:
    """Factory creates correct fields with correct shapes."""

    def test_fields_exist(self) -> None:
        h = create_j2_history(n_elem=10, n_qp=8)
        assert "alpha" in h
        assert "plastic_strain" in h

    def test_shapes(self) -> None:
        h = create_j2_history(n_elem=5, n_qp=4)
        assert h.get_current("alpha").shape == (5, 4)
        assert h.get_current("plastic_strain").shape == (5, 4, 6)

    def test_default_n_qp(self) -> None:
        h = create_j2_history(n_elem=3)
        assert h.get_current("alpha").shape == (3, 8)
        assert h.get_current("plastic_strain").shape == (3, 8, 6)


# -- 12. Unknown field raises KeyError ----------------------------------------


class TestUnknownFieldRaises:
    """Accessing an unregistered field raises KeyError."""

    def test_get_current_unknown(self) -> None:
        h = HistoryFields()
        with pytest.raises(KeyError):
            h.get_current("does_not_exist")

    def test_get_old_unknown(self) -> None:
        h = HistoryFields()
        with pytest.raises(KeyError):
            h.get_old("does_not_exist")

    def test_set_current_unknown(self) -> None:
        h = HistoryFields()
        with pytest.raises(KeyError):
            h.set_current("does_not_exist", np.zeros(3))


# -- 13. In-place semantics ---------------------------------------------------


class TestInPlaceSemantics:
    """set_current does not create a new array — views are preserved."""

    def test_view_preserved(self) -> None:
        h = HistoryFields()
        h.register("q", (4,))
        view = h.get_current("q")
        h.set_current("q", np.array([1.0, 2.0, 3.0, 4.0]))
        # The original view should reflect the update because set_current
        # uses ``[:] = value`` (in-place copy).
        np.testing.assert_array_equal(view, np.array([1.0, 2.0, 3.0, 4.0]))

    def test_same_object(self) -> None:
        h = HistoryFields()
        h.register("q", (4,))
        buf1 = h.get_current("q")
        h.set_current("q", np.ones(4))
        buf2 = h.get_current("q")
        assert buf1 is buf2  # same underlying array object
