from __future__ import annotations

import time
from pathlib import Path

from lightcoder.context import ContextManager
from lightcoder.controller import WORK_ACTIONS
from lightcoder.models import Episode, RunState
from lightcoder.models import Evidence
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
    (tools.workspace / "target" / "debug").mkdir(parents=True)
    (tools.workspace / "target" / "debug" / "generated").write_text("noise")
    assert tools.workspace_revision() == revision


def test_command_timeout_terminates_process_group(
    tmp_path: Path, skills_root: Path
) -> None:
    _, _, tools, _ = make_runtime(tmp_path, skills_root)
    result = CommandSupervisor(tools).run("sleep 10", timeout_seconds=0.05)
    assert result.exit_code == 124
    assert "timed out" in result.output


def test_edit_requires_an_unambiguous_exact_match(
    tmp_path: Path, skills_root: Path
) -> None:
    _, _, tools, _ = make_runtime(tmp_path, skills_root)
    assert tools.write("sample.txt", "one two two\n").success
    ambiguous = tools.edit("sample.txt", "two", "three")
    assert not ambiguous.success
    assert "matched 2 times" in ambiguous.output
    assert tools.edit("sample.txt", "two", "three", replace_all=True).success
    assert (tools.workspace / "sample.txt").read_text() == "one three three\n"


def test_background_command_preserves_identity_log_and_exit_code(
    tmp_path: Path, skills_root: Path
) -> None:
    _, _, tools, _ = make_runtime(tmp_path, skills_root)
    supervisor = CommandSupervisor(tools)
    started = supervisor.start("sleep 0.05; printf finished")
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


def test_run_does_not_hang_on_accidental_background_descendant(
    tmp_path: Path, skills_root: Path
) -> None:
    _, _, tools, _ = make_runtime(tmp_path, skills_root)
    result = CommandSupervisor(tools).run("sleep 10 &", timeout_seconds=1)
    assert result.exit_code == 125
    assert "Use the start action" in result.output


def test_command_output_can_be_read_by_line_after_context_truncation(
    tmp_path: Path, skills_root: Path
) -> None:
    _, _, tools, _ = make_runtime(tmp_path, skills_root)
    supervisor = CommandSupervisor(tools)
    result = supervisor.run(
        "for i in $(seq 1 40); do printf 'line-%s\\n' \"$i\"; done"
    )

    recovered = supervisor.read_output(result.call_id, start_line=21, max_lines=3)

    assert recovered.success
    assert "21: line-21" in recovered.output
    assert "23: line-23" in recovered.output
    assert "40 total lines" in recovered.output


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


def test_context_rotation_reserves_only_eight_thousand_tokens(
    tmp_path: Path, skills_root: Path
) -> None:
    _, _, _, context = make_runtime(tmp_path, skills_root)
    assert context.context_window_tokens == 128_000
    assert context.rotation_threshold_tokens == 120_000


def test_context_keeps_static_prefix_before_changing_state_and_compacts_writes(
    tmp_path: Path, skills_root: Path
) -> None:
    state, store, _, context = make_runtime(tmp_path, skills_root)
    state.objective = "stable task objective"
    store.append_transcript(
        "assistant",
        '{"action":"write","path":"large.txt","content":"'
        + ("x" * 20_000)
        + '"}',
    )
    messages = context.build_messages(
        state,
        WORK_ACTIONS,
        core_skill="execute-work-item",
        playbook="generalist",
    )
    assert "TASK OBJECTIVE\nstable task objective" in messages[0].content
    assert "TOOL POLICY" in messages[0].content
    assert messages[-1].content.startswith("CANONICAL RUN STATE")
    assert "stable task objective" not in messages[-1].content
    assert len(messages[-2].content) < 1_000
    assert "content_omitted_chars" in messages[-2].content


def test_next_prompt_preserves_previous_request_as_cacheable_prefix(
    tmp_path: Path, skills_root: Path
) -> None:
    state, store, _, context = make_runtime(tmp_path, skills_root)
    first = context.build_messages(
        state,
        WORK_ACTIONS,
        core_skill="execute-work-item",
        playbook="generalist",
    )
    store.append_transcript(
        "user", first[-1].content, kind="controller_context"
    )
    store.append_transcript("assistant", '{"action":"read","path":"README.md"}')
    second = context.build_messages(
        state,
        WORK_ACTIONS,
        core_skill="execute-work-item",
        playbook="generalist",
    )
    assert second[0].content == first[0].content
    assert second[1].content == first[1].content
    assert second[-1].content.startswith("CANONICAL RUN STATE")


def test_compacted_batch_history_keeps_valid_action_key(
    tmp_path: Path, skills_root: Path
) -> None:
    state, store, _, context = make_runtime(tmp_path, skills_root)
    store.append_transcript(
        "assistant",
        '{"action":"batch","actions":[{"action":"read","path":"a"}]}'
    )
    messages = context.build_messages(state, WORK_ACTIONS)
    assert "COMPLETED ACTION HISTORY" in messages[-2].content
    assert '"children": [{"type": "read"}]' in messages[-2].content
    assert '"action"' not in messages[-2].content
    assert "batched_actions" not in messages[-2].content


def test_latest_observation_is_not_truncated_to_short_state_summary(
    tmp_path: Path, skills_root: Path
) -> None:
    state, store, _, context = make_runtime(tmp_path, skills_root)
    marker = "tail-marker-visible-to-model"
    store.record_evidence(
        Evidence(
            id="ev-long-read",
            kind="observation",
            created_at=state.created_at,
            work_item_id=None,
            workspace_revision="rev",
            summary=("line\n" * 1_000) + marker,
            data={"success": True},
        )
    )
    messages = context.build_messages(state, WORK_ACTIONS)
    assert marker in messages[-1].content


def test_all_evidence_from_latest_model_call_remains_visible(
    tmp_path: Path, skills_root: Path
) -> None:
    state, store, _, context = make_runtime(tmp_path, skills_root)
    # The durable state can be rendered after the controller has advanced the
    # counter, while evidence still belongs to the action from call 7.
    state.counters["model_calls"] = 8
    markers = [f"batch-tail-{index}" for index in range(8)]
    for index, marker in enumerate(markers):
        store.record_evidence(
            Evidence(
                id=f"ev-batch-{index}",
                kind="observation",
                created_at=state.created_at,
                work_item_id=None,
                workspace_revision="rev",
                summary=("line\n" * 1_000) + marker,
                data={"success": True, "model_call": 7},
            )
        )
    messages = context.build_messages(state, WORK_ACTIONS)
    assert all(marker in messages[-1].content for marker in markers)
