from __future__ import annotations

from pathlib import Path

import pytest

from lightcoder.models import RunState, StateValidationError, WorkItem
from lightcoder.store import StateConflictError, StateStore


def test_work_graph_rejects_cycles(tmp_path: Path) -> None:
    state = RunState.create("cycle", tmp_path)
    state.work_items = [
        WorkItem("A", "A", "first", dependencies=["B"]),
        WorkItem("B", "B", "second", dependencies=["A"]),
    ]
    with pytest.raises(StateValidationError, match="cycle"):
        state.validate()


def test_ready_selection_respects_dependencies(tmp_path: Path) -> None:
    state = RunState.create("ordered", tmp_path)
    state.work_items = [
        WorkItem("A", "A", "first"),
        WorkItem("B", "B", "second", dependencies=["A"]),
    ]
    assert state.next_ready_item().id == "A"  # type: ignore[union-attr]
    state.work_item("A").status = "accepted"  # type: ignore[union-attr]
    assert state.next_ready_item().id == "B"  # type: ignore[union-attr]


def test_state_store_uses_optimistic_revisions(tmp_path: Path) -> None:
    state = RunState.create("persistent", tmp_path / "workspace")
    (tmp_path / "workspace").mkdir()
    store = StateStore.create(tmp_path / "state", state)
    first = store.load()
    stale = store.load()
    store.commit(first, expected_revision=0)
    with pytest.raises(StateConflictError):
        store.commit(stale, expected_revision=0)
