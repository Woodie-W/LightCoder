from __future__ import annotations

import json
from pathlib import Path

import pytest

from lightcoder.controller import RunController
from lightcoder.model import ModelError, ModelResponse
from lightcoder.models import TaskProfile, WorkItem
from lightcoder.reporting import build_run_report

from conftest import CompletingModel, ScriptedModel


def test_controller_completes_full_single_agent_flow(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    model = CompletingModel(workspace)
    controller = RunController.create(
        "create marker",
        workspace,
        model,
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.run(max_cycles=30)
    assert state.status == "completed"
    assert state.phase == "done"
    assert state.work_item("W1").status == "accepted"  # type: ignore[union-attr]
    assert state.final["verification"]["evidence_ids"]
    assert model.calls == state.counters["model_calls"]
    report = build_run_report(controller.store)
    assert report["mandatory_accepted"] == 1
    assert report["commands_passed"] == 2
    assert report["context_episodes"] == 2
    assert report["context_rotations"] == 1


def test_long_horizon_uses_flat_flow_without_work_items(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "long marker",
        workspace,
        CompletingModel(workspace, regime="long_horizon"),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.run(max_cycles=30)
    assert state.status == "completed"
    assert state.phase == "done"
    assert state.work_items == []
    assert state.active_work_item_id is None
    assert build_run_report(controller.store)["control_mode"] == "flat"
    events = controller.store.events_path.read_text(encoding="utf-8")
    assert "flat_long_horizon_started" in events


def test_optimization_profile_always_requires_best_artifact(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    model = ScriptedModel(
        [
            {
                "action": "profile_task",
                "profile": {
                    "execution_regime": "long_horizon",
                    "primary_playbook": "optimization",
                    "estimated_horizon": "multi_hour",
                    "validation_cost": "low",
                    "supports_partial_progress": True,
                    "requires_best_artifact": False,
                    "rationale": "model omitted best-artifact discipline",
                },
            }
        ]
    )
    controller = RunController.create(
        "optimize an artifact",
        workspace,
        model,
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )

    state = controller.run(max_cycles=1)

    assert state.profile is not None
    assert state.profile.primary_playbook == "optimization"
    assert state.profile.requires_best_artifact is True


def test_long_horizon_bypasses_plan_generation(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    model = ScriptedModel(
        [
            {
                "action": "profile_task",
                "profile": {
                    "execution_regime": "long_horizon",
                    "primary_playbook": "optimization",
                    "estimated_horizon": "multi_hour",
                    "validation_cost": "high",
                    "supports_partial_progress": True,
                    "requires_best_artifact": True,
                    "rationale": "multiple scoreable artifacts",
                },
            },
            {
                "action": "run",
                "command": "true",
                "rationale": "start direct execution",
            },
        ]
    )
    controller = RunController.create(
        "optimize two alignment files",
        workspace,
        model,
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )

    state = controller.run(max_cycles=2)

    assert state.phase == "long_horizon_work"
    assert state.work_items == []
    assert state.active_work_item_id is None
    assert len(model.messages) == 2
    flat_prompt = "\n".join(message.content for message in model.messages[1])
    assert '"action":"begin_final_verification"' in flat_prompt
    assert '"action":"start"' in flat_prompt
    assert "Return set_plan" not in flat_prompt
    events = controller.store.events_path.read_text(encoding="utf-8")
    assert "flat_long_horizon_started" in events


def test_run_rejects_legacy_background_flag(tmp_path: Path, skills_root: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "tool protocol",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"
    with pytest.raises(ValueError, match="use start"):
        controller._execute_tool(
            state,
            {"action": "run", "command": "sleep 1", "background": True},
        )


def test_run_rejects_obvious_persistent_server(tmp_path: Path, skills_root: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "tool protocol",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"
    with pytest.raises(ValueError, match="use start"):
        controller._execute_tool(
            state,
            {"action": "run", "command": "python -m uvicorn app:app"},
        )


def test_optimization_deadline_restores_last_accepted_checkpoint(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact = workspace / "best.align"
    artifact.write_text("accepted-best\n", encoding="utf-8")
    controller = RunController.create(
        "optimize best.align",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.profile = TaskProfile(
        execution_regime="long_horizon",
        primary_playbook="optimization",
        estimated_horizon="multi_hour",
        requires_best_artifact=True,
    )
    with pytest.raises(ValueError, match="evidence id"):
        controller._checkpoint(
            state,
            {
                "restore_notes": "unvalidated",
                "metric_name": "score",
                "metric_value": 1.0,
                "metric_direction": "maximize",
                "artifact_paths": ["best.align"],
            },
        )
    controller._execute_tool(
        state,
        {"action": "bash", "command": "test -f best.align", "cwd": "."},
    )
    controller._checkpoint(
        state,
        {
            "restore_notes": "accepted best",
            "metric_name": "score",
            "metric_value": 1.0,
            "metric_direction": "maximize",
            "evidence_ids": [state.evidence_ids[-1]],
            "artifact_paths": ["best.align"],
        },
    )
    artifact.write_text("unfinished-losing-candidate\n", encoding="utf-8")
    state.deadline.started_at = "2000-01-01T00:00:00+00:00"
    state.deadline.wall_time_seconds = 60

    # A stale or backward-adjusted wall clock cannot trigger the deadline.
    assert controller._deadline_transition(state) is False
    controller._deadline_elapsed_base = 61

    assert controller._deadline_transition(state) is True
    assert state.status == "paused_limit"
    assert artifact.read_text(encoding="utf-8") == "accepted-best\n"
    assert "best_checkpoint_restored" in controller.store.events_path.read_text(
        encoding="utf-8"
    )


def test_non_improving_checkpoint_does_not_replace_best(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact = workspace / "candidate.txt"
    artifact.write_text("best\n", encoding="utf-8")
    controller = RunController.create(
        "maximize candidate score",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.profile = TaskProfile(
        execution_regime="long_horizon",
        primary_playbook="optimization",
        estimated_horizon="multi_hour",
        requires_best_artifact=True,
    )

    controller._execute_tool(
        state,
        {"action": "bash", "command": "test -f candidate.txt", "cwd": "."},
    )
    controller._checkpoint(
        state,
        {
            "restore_notes": "score ten",
            "metric_name": "score",
            "metric_value": 10,
            "metric_direction": "maximize",
            "evidence_ids": [state.evidence_ids[-1]],
            "artifact_paths": ["candidate.txt"],
        },
    )
    best_id = state.best_checkpoint_id

    artifact.write_text("worse\n", encoding="utf-8")
    controller._execute_tool(
        state,
        {"action": "bash", "command": "test -f candidate.txt", "cwd": "."},
    )
    controller._checkpoint(
        state,
        {
            "restore_notes": "score nine",
            "metric_name": "score",
            "metric_value": 9,
            "metric_direction": "maximize",
            "evidence_ids": [state.evidence_ids[-1]],
            "artifact_paths": ["candidate.txt"],
        },
    )

    assert state.best_checkpoint_id == best_id
    controller._restore_best_checkpoint_at_deadline(state)
    assert artifact.read_text(encoding="utf-8") == "best\n"
    assert "checkpoint_retained_not_promoted" in (
        controller.store.events_path.read_text(encoding="utf-8")
    )


def test_hard_deadline_terminates_background_commands(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "stop background work at deadline",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    command = controller.commands.run("sleep 30", background=True)
    state.deadline.wall_time_seconds = 1
    controller._deadline_elapsed_base = 2

    assert controller._deadline_transition(state) is True
    metadata = {
        item["id"]: item for item in controller.commands.recover()
    }
    assert metadata[command.background_id]["status"] == "terminated"
    assert state.final["limit"]["terminated_command_ids"] == [
        command.background_id
    ]


def test_controller_does_not_reserve_a_fixed_hardening_fraction(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "continue useful work until the hard deadline",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"
    state.deadline.wall_time_seconds = 100
    controller._deadline_elapsed_base = 99

    assert controller._deadline_transition(state) is False
    assert state.phase == "long_horizon_work"


def test_mutation_evidence_cannot_accept_work_item(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    model = ScriptedModel(
        [
            {
                "action": "profile_task",
                "profile": {
                    "execution_regime": "standard",
                    "primary_playbook": "generalist",
                    "estimated_horizon": "short",
                    "validation_cost": "low",
                    "supports_partial_progress": True,
                    "requires_best_artifact": False,
                    "rationale": "local",
                },
            },
            {
                "action": "set_plan",
                "work_items": [
                    {
                        "id": "W1",
                        "title": "Marker",
                        "description": "Create marker",
                        "kind": "capability",
                        "playbook": "generalist",
                        "dependencies": [],
                        "mandatory": True,
                        "acceptance": ["test -f marker.txt"],
                        "verification_commands": ["test -f marker.txt"],
                    }
                ],
            },
            {"action": "write", "path": "marker.txt", "content": "ok\n"},
            {"action": "begin_verification"},
            {
                "action": "accept_work_item",
                "evidence_ids": ["missing"],
                "summary": "not evidence",
            },
        ]
    )
    controller = RunController.create(
        "marker",
        workspace,
        model,
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.run(max_cycles=7)
    assert state.status == "running"
    assert state.work_item("W1").status == "verifying"  # type: ignore[union-attr]
    assert state.counters["invalid_actions"] == 1


def test_batch_executes_multiple_tools_in_one_model_turn(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    model = ScriptedModel(
        [
            {
                "action": "profile_task",
                "profile": {
                    "execution_regime": "standard",
                    "primary_playbook": "generalist",
                    "estimated_horizon": "short",
                    "validation_cost": "low",
                    "supports_partial_progress": True,
                    "requires_best_artifact": False,
                    "rationale": "local",
                },
            },
            {
                "action": "set_plan",
                "work_items": [
                    {
                        "id": "W1",
                        "title": "Batch",
                        "description": "Create two files",
                        "kind": "capability",
                        "playbook": "generalist",
                        "dependencies": [],
                        "mandatory": True,
                        "acceptance": ["files exist"],
                        "verification_commands": ["test -f a.txt && test -f b.txt"],
                    }
                ],
            },
            {
                "action": "batch",
                "actions": [
                    {"action": "write", "path": "a.txt", "content": "a\n"},
                    {"action": "write", "path": "b.txt", "content": "b\n"},
                ],
                "rationale": "independent writes",
            },
        ]
    )
    controller = RunController.create(
        "batch files",
        workspace,
        model,
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    controller.run(max_cycles=4)
    assert (workspace / "a.txt").read_text() == "a\n"
    assert (workspace / "b.txt").read_text() == "b\n"
    assert len(model.messages) == 3


def test_batch_accepts_provider_batched_actions_alias(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    model = ScriptedModel(
        [
            {
                "action": "profile_task",
                "profile": {
                    "execution_regime": "standard",
                    "primary_playbook": "generalist",
                    "estimated_horizon": "short",
                    "validation_cost": "low",
                    "supports_partial_progress": True,
                    "requires_best_artifact": False,
                    "rationale": "local",
                },
            },
            {
                "action": "set_plan",
                "work_items": [
                    {
                        "id": "W1",
                        "title": "Alias",
                        "description": "Create an artifact",
                        "mandatory": True,
                        "acceptance": ["file exists"],
                        "verification_commands": ["test -f alias.txt"],
                    }
                ],
            },
            {
                "action": "batch",
                "batched_actions": [
                    {"action": "write", "path": "alias.txt", "content": "ok\n"}
                ],
            },
        ]
    )
    controller = RunController.create(
        "batch alias",
        workspace,
        model,
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    controller.run(max_cycles=4)
    assert (workspace / "alias.txt").read_text() == "ok\n"


def test_repeated_mutation_requires_command_feedback(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    model = ScriptedModel(
        [
            {
                "action": "profile_task",
                "profile": {
                    "execution_regime": "standard",
                    "primary_playbook": "generalist",
                    "estimated_horizon": "short",
                    "validation_cost": "low",
                    "supports_partial_progress": True,
                    "requires_best_artifact": False,
                    "rationale": "local",
                },
            },
            {
                "action": "set_plan",
                "work_items": [
                    {
                        "id": "W1",
                        "title": "Feedback loop",
                        "description": "Create and validate an artifact",
                        "mandatory": True,
                        "acceptance": ["file exists"],
                        "verification_commands": ["test -f artifact.txt"],
                    }
                ],
            },
            {"action": "write", "path": "artifact.txt", "content": "first\n"},
            {"action": "write", "path": "artifact.txt", "content": "second\n"},
        ]
    )
    controller = RunController.create(
        "mutation feedback",
        workspace,
        model,
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.run(max_cycles=5)
    assert (workspace / "artifact.txt").read_text() == "first\n"
    assert state.counters["invalid_actions"] == 1
    assert "focused bash check" in controller.store.transcript_path.read_text()


def test_command_feedback_allows_followup_mutation(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    model = ScriptedModel(
        [
            {
                "action": "profile_task",
                "profile": {
                    "execution_regime": "standard",
                    "primary_playbook": "generalist",
                    "estimated_horizon": "short",
                    "validation_cost": "low",
                    "supports_partial_progress": True,
                    "requires_best_artifact": False,
                    "rationale": "local",
                },
            },
            {
                "action": "set_plan",
                "work_items": [
                    {
                        "id": "W1",
                        "title": "Feedback loop",
                        "description": "Create and validate an artifact",
                        "mandatory": True,
                        "acceptance": ["file exists"],
                        "verification_commands": ["test -f artifact.txt"],
                    }
                ],
            },
            {"action": "write", "path": "artifact.txt", "content": "first\n"},
            {"action": "bash", "command": "test -f artifact.txt"},
            {"action": "write", "path": "artifact.txt", "content": "second\n"},
        ]
    )
    controller = RunController.create(
        "mutation feedback",
        workspace,
        model,
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.run(max_cycles=6)
    assert (workspace / "artifact.txt").read_text() == "second\n"
    assert state.counters.get("invalid_actions", 0) == 0


def test_repeated_absolute_path_mutation_requires_feedback(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "absolute mutation feedback",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.work_items = [
        WorkItem(
            id="W1",
            title="Artifact",
            description="Create artifact",
            status="running",
            acceptance=["exists"],
            verification_commands=["test -f artifact.txt"],
        )
    ]
    state.active_work_item_id = "W1"
    controller._execute_tool(
        state,
        {"action": "write", "path": str(workspace / "artifact.txt"), "content": "one"},
    )
    try:
        controller._execute_tool(
            state,
            {"action": "write", "path": str(workspace / "artifact.txt"), "content": "two"},
        )
    except ValueError as error:
        assert "focused bash check" in str(error)
    else:
        raise AssertionError("absolute path should use the same mutation gate")


def test_duplicate_complete_read_is_rejected(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "artifact.txt").write_text("one\ntwo\n")
    controller = RunController.create(
        "read once",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.work_items = [
        WorkItem(
            id="W1",
            title="Artifact",
            description="Inspect artifact",
            status="running",
            acceptance=["inspected"],
            verification_commands=["true"],
        )
    ]
    state.active_work_item_id = "W1"
    action = {"action": "read", "path": str(workspace / "artifact.txt")}
    controller._execute_tool(state, action)
    try:
        controller._execute_tool(state, action)
    except ValueError as error:
        assert "already read completely" in str(error)
    else:
        raise AssertionError("duplicate complete read should be rejected")


def test_write_without_content_is_rejected_before_mutation(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "do not write empty",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    try:
        controller._execute_tool(
            state,
            {"action": "write", "path": "artifact.txt", "content_omitted_chars": 50},
        )
    except ValueError as error:
        assert "explicit string content" in str(error)
    else:
        raise AssertionError("write without content must be rejected")
    assert not (workspace / "artifact.txt").exists()


def test_batch_continues_after_one_duplicate_read_is_rejected(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "seen.txt").write_text("seen\n")
    (workspace / "new.txt").write_text("new\n")
    controller = RunController.create(
        "partial batch",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.phase = "standard_work"
    state.work_items = [
        WorkItem(
            id="W1",
            title="Inspect",
            description="Inspect files",
            status="running",
            acceptance=["inspected"],
            verification_commands=["true"],
        )
    ]
    state.active_work_item_id = "W1"
    controller._execute_tool(state, {"action": "read", "path": "seen.txt"})
    controller._apply_action(
        state,
        {
            "action": "batch",
            "actions": [
                {"action": "read", "path": "seen.txt"},
                {"action": "read", "path": "new.txt"},
            ],
        },
    )
    evidence = controller.store.evidence_by_id(state.work_item("W1").evidence_ids)
    assert any(item.data.get("path") == "new.txt" for item in evidence)
    assert "skipped rejected batch children" in controller.store.transcript_path.read_text()


def test_python_mutation_runs_automatic_compile_and_allows_followup_edit(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "automatic syntax check",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.work_items = [
        WorkItem(
            id="W1",
            title="Module",
            description="Create module",
            status="running",
            acceptance=["compiles"],
            verification_commands=["python3 -m py_compile module.py"],
        )
    ]
    state.active_work_item_id = "W1"
    controller._execute_tool(
        state,
        {"action": "write", "path": "module.py", "content": "value = 1\n"},
    )
    controller._execute_tool(
        state,
        {
            "action": "edit",
            "path": "module.py",
            "old": "value = 1",
            "new": "value = 2",
        },
    )
    evidence = controller.store.evidence_by_id(state.work_item("W1").evidence_ids)
    checks = [item for item in evidence if item.command == "python3 -m py_compile module.py"]
    assert len(checks) == 2
    assert all(item.exit_code == 0 for item in checks)


def test_controller_runs_exact_acceptance_command_without_model_round_trip(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    model = ScriptedModel(
        [
            {
                "action": "profile_task",
                "profile": {
                    "execution_regime": "standard",
                    "primary_playbook": "generalist",
                    "estimated_horizon": "short",
                    "validation_cost": "low",
                    "supports_partial_progress": True,
                    "requires_best_artifact": False,
                    "rationale": "local",
                },
            },
            {
                "action": "set_plan",
                "work_items": [
                    {
                        "id": "W1",
                        "title": "Marker",
                        "description": "Create marker",
                        "kind": "capability",
                        "playbook": "generalist",
                        "dependencies": [],
                        "mandatory": True,
                        "acceptance": ["marker exists"],
                        "verification_commands": ["test -f marker.txt"],
                    }
                ],
            },
            {"action": "write", "path": "marker.txt", "content": "ok\n"},
            {"action": "begin_verification", "rationale": "ready"},
        ]
    )
    controller = RunController.create(
        "marker",
        workspace,
        model,
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.run(max_cycles=6)
    evidence = controller.store.evidence()
    assert state.work_item("W1").status == "verifying"  # type: ignore[union-attr]
    assert any(item.command == "test -f marker.txt" for item in evidence)
    assert len(model.messages) == 4


def test_rejections_do_not_trigger_attempt_limit(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    class RejectingModel:
        model = "rejecting"

        def complete(self, messages, *, timeout_seconds=None):
            prompt = "\n".join(message.content for message in messages)
            if "Return profile_task:" in prompt:
                action = {
                    "action": "profile_task",
                    "profile": {
                        "execution_regime": "standard",
                        "primary_playbook": "generalist",
                        "estimated_horizon": "short",
                        "validation_cost": "low",
                        "supports_partial_progress": True,
                        "requires_best_artifact": False,
                        "rationale": "local",
                    },
                }
            elif "Return set_plan" in prompt:
                action = {
                    "action": "set_plan",
                    "work_items": [
                        {
                            "id": "W1",
                            "title": "Explore",
                            "description": "Resolve behavior",
                            "kind": "capability",
                            "playbook": "generalist",
                            "dependencies": [],
                            "mandatory": True,
                            "acceptance": ["true"],
                            "verification_commands": ["true"],
                        }
                    ],
                }
            else:
                action = {
                    "action": "reject_work_item",
                    "evidence_ids": [],
                    "failure_signature": "hypothesis falsified",
                    "next_strategy": "inspect another boundary",
                }
            return ModelResponse(json.dumps(action))

    controller = RunController.create(
        "keep diagnosing",
        workspace,
        RejectingModel(),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.run(max_cycles=20)
    item = state.work_item("W1")
    assert state.status == "running"
    assert item.attempt_count >= 8  # type: ignore[union-attr]
    assert len(item.failure_signatures) >= 8  # type: ignore[union-attr]


def test_model_failures_schedule_backoff_without_terminating(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    class FailingModel:
        model = "offline"

        def complete(self, messages, *, timeout_seconds=None):
            raise ModelError("temporary outage")

    controller = RunController.create(
        "survive outage",
        workspace,
        FailingModel(),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.step()
    assert state.status == "running"
    assert state.retry_at
    assert state.counters["model_calls"] == 1
    assert state.counters["consecutive_model_errors"] == 1


def test_ablation_configuration_changes_mechanism_and_persists(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "ablation marker",
        workspace,
        CompletingModel(workspace, regime="long_horizon"),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        ablations=["standard-only", "no-handoffs"],
    )
    state = controller.run(max_cycles=30)
    assert state.status == "completed"
    assert state.profile.execution_regime == "standard"  # type: ignore[union-attr]
    assert state.runtime_config["ablations"] == ["no-handoffs", "standard-only"]
    assert state.best_checkpoint_id is None
    assert len(state.episodes) == 2
    assert not list(controller.store.handoffs_dir.glob("*.json"))
    assert build_run_report(controller.store)["ablations"] == [
        "no-handoffs",
        "standard-only",
    ]
