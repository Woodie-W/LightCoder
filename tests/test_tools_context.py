from __future__ import annotations

import time
from pathlib import Path

from lightcoder.context import ContextManager
from lightcoder.models import Episode, RunState
from lightcoder.skills import SkillRegistry
from lightcoder.store import StateStore
from lightcoder.tools import CommandSupervisor, WorkspaceTools


def make_runtime(tmp_path: Path, skills_root: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = RunState.create("tools", workspace)
    store = StateStore.create(workspace / ".lightcoder", state)
    tools = WorkspaceTools(workspace, store)
    return state, store, tools, ContextManager(store, tools, SkillRegistry(skills_root))


def test_workspace_tools_enforce_paths_and_keep_metadata_out_of_revision(
    tmp_path: Path, skills_root: Path
) -> None:
    _, store, tools, _ = make_runtime(tmp_path, skills_root)
    assert not tools.write("../escape.txt", "bad").success
    assert not tools.write(".lightcoder/overwrite", "bad").success
    assert tools.write("inside.txt", "ok\n").success
    revision = tools.workspace_revision()
    store.append_event("metadata_changed")
    assert tools.workspace_revision() == revision


def test_command_timeout_terminates_process_group(
    tmp_path: Path, skills_root: Path
) -> None:
    _, _, tools, _ = make_runtime(tmp_path, skills_root)
    result = CommandSupervisor(tools).run("sleep 10", timeout_seconds=0.05)
    assert result.exit_code == 124
    assert "timed out" in result.output


def test_background_command_preserves_identity_log_and_exit_code(
    tmp_path: Path, skills_root: Path
) -> None:
    _, _, tools, _ = make_runtime(tmp_path, skills_root)
    supervisor = CommandSupervisor(tools)
    started = supervisor.run("sleep 0.05; printf finished", background=True)
    assert started.success
    assert started.data["pid"] > 0
    deadline = time.monotonic() + 2
    while True:
        result = supervisor.poll(started.background_id)
        if result.data.get("status") == "exited":
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)
    assert result.exit_code == 0
    assert "finished" in result.output


def test_context_rotation_creates_validated_handoff(
    tmp_path: Path, skills_root: Path
) -> None:
    state, store, tools, context = make_runtime(tmp_path, skills_root)
    state.episodes.append(Episode(0, state.created_at, None))
    store.append_transcript("assistant", '{"action":"read"}')
    handoff = context.rotate(state, reason="test", next_action="inspect disk")
    assert handoff["workspace_revision"] == tools.workspace_revision()
    assert len(state.episodes) == 2
    assert context.latest_handoff(state)["workspace_revision_matches"] is True  # type: ignore[index]
    assert (store.handoffs_dir / "0001.json").is_file()
    assert context._recent_transcript(state) == []
