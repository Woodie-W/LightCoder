from __future__ import annotations

import json
from pathlib import Path

from lightcoder.controller import RunController
from lightcoder.model import ModelError, ModelResponse
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


def test_long_horizon_acceptance_promotes_checkpoint_and_rotates_context(
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
    assert state.best_checkpoint_id
    assert len(state.episodes) >= 2
    checkpoint = controller.store.checkpoints_dir / f"{state.best_checkpoint_id}.json"
    assert checkpoint.is_file()
    checkpoint_value = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert checkpoint_value["snapshot_path"]
    assert (controller.store.run_dir / checkpoint_value["snapshot_path"]).is_file()


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
    state = controller.run(max_cycles=6)
    assert state.status == "running"
    assert state.work_item("W1").status == "verifying"  # type: ignore[union-attr]
    assert state.counters["invalid_actions"] == 1


def test_rejections_do_not_trigger_attempt_limit(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    class RejectingModel:
        model = "rejecting"

        def complete(self, messages):
            prompt = messages[1].content
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

        def complete(self, messages):
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
