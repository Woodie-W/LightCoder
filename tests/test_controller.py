from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from lightcoder.controller import RunController, native_tool_schemas
from lightcoder.evaluation import load_attempts, submit_evaluation
from lightcoder.model import ModelError, ModelResponse, PermanentModelError
from lightcoder.models import TaskProfile, WorkItem
from lightcoder.reporting import build_run_report
from lightcoder.tools import ToolResult

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
    transcript = [
        json.loads(line)
        for line in controller.store.transcript_path.read_text().splitlines()
    ]
    assert transcript[state.episodes[0].transcript_end - 1]["role"] == "tool"


def test_managed_evaluation_is_optional_and_reminds_after_first_local_test(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "optional evaluation",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()
    messages = controller.context.build_messages(
        state, "Use tools", core_skill="profile-task"
    )
    assert "OPTIONAL MANAGED EVALUATION" in messages[0].content

    controller._execute_tool(
        state,
        {
            "action": "run",
            "command": "python -m pytest --version",
            "cwd": ".",
        },
    )

    config = state.runtime_config["managed_evaluation"]
    assert config["local_check_hint_shown"] is True
    transcript = controller.store.transcript_path.read_text(encoding="utf-8")
    assert "This was a local check" in transcript

    plain_workspace = tmp_path / "plain-workspace"
    plain_workspace.mkdir()
    plain = RunController.create(
        "plain run",
        plain_workspace,
        ScriptedModel([]),
        state_root=tmp_path / "plain-state",
        skills_root=skills_root,
    )
    plain_state = plain.store.load()
    plain_messages = plain.context.build_messages(
        plain_state, "Use tools", core_skill="profile-task"
    )
    assert "OPTIONAL MANAGED EVALUATION" not in plain_messages[0].content


def test_managed_evaluation_native_tool_adopts_and_records_baseline(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    (workspace / "eval_align.py").write_text(
        "print('S3 = 0.248294')\n", encoding="utf-8"
    )
    controller = RunController.create(
        "optimize a score",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"

    enabled_names = {
        item["function"]["name"]
        for item in native_tool_schemas(
            "long_horizon_work", managed_evaluation=True
        )
    }
    plain_names = {
        item["function"]["name"]
        for item in native_tool_schemas("long_horizon_work")
    }
    assert "managed_eval" in enabled_names
    assert "managed_eval" not in plain_names
    decision_names = {
        item["function"]["name"]
        for item in native_tool_schemas(
            "long_horizon_work",
            managed_evaluation=True,
            managed_evaluation_decision=True,
        )
    }
    assert decision_names == {"managed_eval", "skip_managed_eval"}

    result = controller._execute_managed_evaluation(
        state,
        {
            "action": "managed_eval",
            "script": "eval_align.py",
            "primary": "S3",
            "message": "baseline",
        },
    )

    assert result.success
    assert "S3=0.248294" in result.output
    assert state.runtime_config["managed_evaluation"]["successful_evaluator_runs"] == 0
    store = Path(state.runtime_config["managed_evaluation"]["store"])
    assert load_attempts(store)[0]["metrics"]["S3"] == pytest.approx(0.248294)
    assert build_run_report(controller.store)["managed_evaluation"]["attempts"] == 1


def test_invalid_managed_candidate_is_recorded_but_not_successful_evidence(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "evaluate.py").write_text(
        "print('{\"valid\": false, \"metrics\": {\"partial\": 1}}')\n",
        encoding="utf-8",
    )
    controller = RunController.create(
        "reject invalid candidate",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"

    result = controller._execute_managed_evaluation(
        state,
        {
            "action": "managed_eval",
            "script": "evaluate.py",
            "primary": "partial",
        },
    )

    assert result.success is False
    assert result.exit_code == 0
    assert result.data["attempt"]["valid"] is False
    assert state.runtime_config["managed_evaluation"]["decision_pending"] is False


def test_managed_evaluation_history_restore_and_embedded_state_isolation(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    (workspace / "score.txt").write_text("1\n", encoding="utf-8")
    (workspace / "evaluate.py").write_text(
        "from pathlib import Path\n"
        "print(f'S3={Path(\"score.txt\").read_text().strip()}')\n",
        encoding="utf-8",
    )
    state_root = workspace / "runtime-state"
    controller = RunController.create(
        "optimize a score",
        workspace,
        ScriptedModel([]),
        state_root=state_root,
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"

    controller._execute_tool(
        state,
        {
            "action": "managed_eval",
            "operation": "submit",
            "script": "evaluate.py",
            "primary": "S3",
            "message": "one",
        },
    )
    first_evidence = controller.store.evidence_by_id([state.evidence_ids[-1]])[0]
    assert first_evidence.workspace_revision == controller.tools.workspace_revision()
    tracked = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "runtime-state/" not in tracked

    (workspace / "score.txt").write_text("2\n", encoding="utf-8")
    second = controller._execute_managed_evaluation(
        state,
        {"action": "managed_eval", "operation": "submit", "message": "two"},
    )
    assert "S3=2.0" in second.output
    history = controller._execute_managed_evaluation(
        state, {"action": "managed_eval", "operation": "history"}
    )
    assert history.success
    assert "A0001" in history.output and "A0002" in history.output
    restored = controller._execute_managed_evaluation(
        state,
        {
            "action": "managed_eval",
            "operation": "restore",
            "attempt_id": "A0001",
        },
    )
    assert restored.success
    assert (workspace / "score.txt").read_text(encoding="utf-8") == "1\n"


def test_background_evaluator_counts_once_when_poll_observes_completion(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "evaluate.py").write_text(
        "print('S3=0.2')\n", encoding="utf-8"
    )
    controller = RunController.create(
        "optimize a score",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"
    controller._execute_tool(
        state,
        {
            "action": "write",
            "path": "evaluate.py",
            "content": "print('S3=0.2')\n",
            "rationale": "numeric evaluator",
        },
    )

    command_ids: list[str] = []
    for _ in range(2):
        before = {item["id"] for item in controller.commands.recover()}
        controller._execute_tool(
            state,
            {"action": "start", "command": "python evaluate.py", "cwd": "."},
        )
        created = [
            item for item in controller.commands.recover() if item["id"] not in before
        ]
        assert len(created) == 1
        command_id = created[0]["id"]
        command_ids.append(command_id)
        for _poll in range(50):
            controller._execute_tool(
                state, {"action": "poll", "command_id": command_id}
            )
            metadata = controller.commands.describe(command_id)
            if metadata.get("status") == "exited":
                controller._refresh_waiting_jobs(state)
                break
        else:
            pytest.fail("background evaluator did not finish")

    config = state.runtime_config["managed_evaluation"]
    assert config["successful_evaluator_runs"] == 2
    assert config["decision_pending"] is True
    assert config["observed_evaluator_command_ids"] == command_ids

    controller._execute_tool(
        state, {"action": "poll", "command_id": command_ids[-1]}
    )
    assert config["successful_evaluator_runs"] == 2


def test_failed_background_evaluator_is_not_counted(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "evaluate.py").write_text(
        "print('S3=0.9')\nraise SystemExit(7)\n", encoding="utf-8"
    )
    controller = RunController.create(
        "reject failed scores",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"
    state.runtime_config["managed_evaluation"]["candidate_evaluator_path"] = (
        "evaluate.py"
    )
    controller._execute_tool(
        state, {"action": "start", "command": "python evaluate.py", "cwd": "."}
    )
    command_id = controller.commands.recover()[0]["id"]
    deadline = time.monotonic() + 2
    while True:
        controller._execute_tool(
            state, {"action": "poll", "command_id": command_id}
        )
        result = controller.commands.describe(command_id)
        if result.get("status") == "exited":
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)

    config = state.runtime_config["managed_evaluation"]
    assert result["exit_code"] == 7
    assert config["successful_evaluator_runs"] == 0
    assert config["decision_pending"] is False


def test_poll_keeps_service_interactive_and_explicit_wait_avoids_model_calls(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "wait for computation",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"
    controller._execute_tool(
        state,
        {
            "action": "start",
            "command": "sleep 0.5; printf finished",
            "cwd": ".",
            "timeout_seconds": 2,
        },
    )
    command_id = controller.commands.recover()[0]["id"]
    controller._execute_tool(
        state, {"action": "poll", "command_id": command_id}
    )
    assert state.status != "waiting"
    controller._execute_tool(
        state,
        {"action": "run", "command": "printf interactive", "cwd": "."},
    )
    assert "interactive" in controller.store.evidence_by_id(
        [state.evidence_ids[-1]]
    )[0].summary
    tool_names = {
        item["function"]["name"]
        for item in native_tool_schemas("long_horizon_work")
    }
    assert "wait" in tool_names
    controller._apply_action(
        state,
        {
            "action": "wait",
            "command_id": command_id,
            "reason": "no independent work remains",
        },
    )
    assert state.status == "waiting"
    assert controller._refresh_waiting_jobs(state) is True
    assert state.status == "waiting"
    assert state.counters.get("model_calls", 0) == 0

    time.sleep(0.6)
    assert controller._refresh_waiting_jobs(state) is False
    assert state.counters.get("model_calls", 0) == 0
    assert "waiting_command_ids" not in state.runtime_config
    evidence = controller.store.evidence_by_id([state.evidence_ids[-1]])[0]
    assert "finished" in evidence.summary
    events = controller.store.events_path.read_text(encoding="utf-8")
    assert "controller-managed waiting poll" not in events
    assert "managed_jobs_running" in events


def test_explicit_wait_periodically_returns_control_for_a_live_service(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "recover from a mistaken service wait",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"
    started = controller.commands.start("sleep 10")
    controller._apply_action(
        state,
        {
            "action": "wait",
            "command_id": started.background_id,
            "reason": "mistakenly treated service as computation",
        },
    )
    state.runtime_config["waiting_review_at"] = "2000-01-01T00:00:00+00:00"

    assert controller._refresh_waiting_jobs(state) is False
    assert "waiting_command_ids" not in state.runtime_config
    assert controller.commands.poll(started.background_id).data["status"] == "running"
    controller.commands.terminate(started.background_id, grace_seconds=0.1)


def test_candidate_path_detection_accepts_saving_progressive(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    candidate = workspace / "result.align"
    candidate.write_text("a\tb\n", encoding="utf-8")
    controller = RunController.create(
        "save a candidate",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )

    assert controller._reported_candidate_paths(
        f"Saving to {candidate}...\nDone.", "."
    ) == [str(candidate)]


def test_adoption_command_does_not_guess_among_multiple_metrics() -> None:
    command = RunController._evaluator_adoption_command(
        ["python3", "/opt/score_golden.py", "binary", "golden.jsonl"],
        candidate_name="",
        output="Total: 10, Passed: 4, Failed: 6\nPass rate: 0.4\n",
    )
    assert "--primary PRIMARY_METRIC" in command
    assert "--primary Total" not in command

    single = RunController._evaluator_adoption_command(
        ["python3", "evaluate.py"], candidate_name="", output="S3=0.5\n"
    )
    assert "--primary S3" in single


def test_submitted_candidate_rechecks_do_not_retrigger_until_candidate_changes(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "optimize a score",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"
    controller._execute_tool(
        state,
        {
            "action": "write",
            "path": "evaluate.py",
            "content": "print('S3=0.1')\n",
            "rationale": "numeric evaluator",
        },
    )
    for _ in range(2):
        controller._execute_tool(
            state, {"action": "run", "command": "python evaluate.py", "cwd": "."}
        )
    config = state.runtime_config["managed_evaluation"]
    assert config["decision_pending"] is True

    controller._execute_tool(
        state,
        {
            "action": "managed_eval",
            "operation": "submit",
            "script": "evaluate.py",
            "primary": "S3",
        },
    )
    assert config["decision_pending"] is False
    assert config["successful_evaluator_runs"] == 0

    for _ in range(2):
        controller._execute_tool(
            state, {"action": "run", "command": "python evaluate.py", "cwd": "."}
        )
    assert config["successful_evaluator_runs"] == 0
    assert config["decision_pending"] is False

    controller._execute_tool(
        state,
        {
            "action": "write",
            "path": "evaluate.py",
            "content": "print('S3=0.2')\n",
            "rationale": "revise numeric evaluator",
        },
    )
    for _ in range(2):
        controller._execute_tool(
            state, {"action": "run", "command": "python evaluate.py", "cwd": "."}
        )
    assert config["successful_evaluator_runs"] == 2
    assert config["decision_pending"] is True
    events = controller.store.events_path.read_text(encoding="utf-8")
    assert "managed_evaluator_repeat_ignored" in events


@pytest.mark.parametrize(
    ("write_action", "run_command"),
    [
        (
            {
                "action": "write",
                "path": "eval_align.py",
                "content": "print('S3=0.1')\n",
            },
            "python eval_align.py",
        ),
        (
            {
                "action": "write",
                "path": "quality.py",
                "content": "print('S3=0.1')\n",
                "rationale": "Create a pure Python metric calculator",
            },
            "python quality.py",
        ),
    ],
)
def test_managed_evaluation_reminds_after_authored_evaluator_runs(
    tmp_path: Path,
    skills_root: Path,
    write_action: dict[str, object],
    run_command: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    controller = RunController.create(
        "optimize a score",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()

    controller._execute_tool(state, write_action)
    assert not state.runtime_config["managed_evaluation"]["local_check_hint_shown"]
    controller._execute_tool(
        state,
        {"action": "run", "command": run_command, "cwd": "."},
    )
    assert not state.runtime_config["managed_evaluation"]["local_check_hint_shown"]
    controller._execute_tool(
        state,
        {"action": "run", "command": run_command, "cwd": "."},
    )

    assert state.runtime_config["managed_evaluation"]["local_check_hint_shown"]
    assert state.runtime_config["managed_evaluation"]["decision_pending"]
    pending_context = controller.context.build_messages(
        state, "Use tools", core_skill="execute-work-item"
    )[-1].content
    assert '"decision_pending": true' in pending_context
    assert '"unmanaged_numeric_runs": 2' in pending_context
    transcript = controller.store.transcript_path.read_text(encoding="utf-8")
    assert "repeated numeric evaluation" in transcript
    assert "lightcoder eval --adopt" in transcript
    events = controller.store.events_path.read_text(encoding="utf-8")
    assert '"signal": "evaluator_script"' in events
    assert "managed_evaluator_detected" in events


def test_reading_evaluator_does_not_execute_it_and_skip_deduplicates_run(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "inspect then run a scorer",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"
    controller._execute_tool(
        state,
        {
            "action": "write",
            "path": "score_golden.py",
            "content": "print('Pass rate: 0.5431')\n",
            "rationale": "Create scoring script",
        },
    )
    config = state.runtime_config["managed_evaluation"]

    for _ in range(2):
        controller._execute_tool(
            state,
            {
                "action": "run",
                "command": "cat score_golden.py",
                "cwd": ".",
                "rationale": "Check the scorer source",
            },
        )
    assert config["successful_evaluator_runs"] == 0
    assert config["decision_pending"] is False

    for _ in range(2):
        controller._execute_tool(
            state,
            {
                "action": "run",
                "command": "python3 score_golden.py 2>&1 | tail -30",
                "cwd": ".",
            },
        )
    assert config["successful_evaluator_runs"] == 2
    assert config["decision_pending"] is True

    controller._apply_action(
        state,
        {"action": "skip_managed_eval", "reason": "not comparable yet"},
    )
    for _ in range(2):
        controller._execute_tool(
            state,
            {
                "action": "run",
                "command": "python3 score_golden.py 2>&1 | tail -30",
                "cwd": ".",
            },
        )
    assert config["successful_evaluator_runs"] == 0
    assert config["decision_pending"] is False

    (workspace / "candidate.txt").write_text("changed\n", encoding="utf-8")
    for _ in range(2):
        controller._execute_tool(
            state,
            {
                "action": "run",
                "command": "python3 score_golden.py 2>&1 | tail -30",
                "cwd": ".",
            },
        )
    assert config["successful_evaluator_runs"] == 2
    assert config["decision_pending"] is True


def test_generic_evaluation_utility_is_not_misclassified_as_evaluator(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "optimize a score",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()
    controller._execute_tool(
        state,
        {
            "action": "write",
            "path": "graph_utils.py",
            "content": "def compute_score(): return 0\n",
            "rationale": "Build graph loading and evaluation utilities",
        },
    )
    assert "candidate_evaluator_path" not in state.runtime_config["managed_evaluation"]
    assert "managed_evaluator_detected" not in controller.store.events_path.read_text(
        encoding="utf-8"
    )


def test_managed_evaluation_reminds_after_solver_reports_metric(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solver.py").write_text(
        "print('S3: 0.104172')\n", encoding="utf-8"
    )
    controller = RunController.create(
        "optimize a score",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()

    controller._execute_tool(
        state,
        {
            "action": "run",
            "command": "python solver.py",
            "cwd": ".",
            "rationale": "Test greedy alignment baseline",
        },
    )

    assert state.runtime_config["managed_evaluation"]["local_check_hint_shown"]
    transcript = controller.store.transcript_path.read_text(encoding="utf-8")
    assert "reported a numeric metric" in transcript
    events = controller.store.events_path.read_text(encoding="utf-8")
    assert '"signal": "local_metric"' in events


def test_managed_evaluation_gates_candidate_metric_after_reference_run(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "eval.py").write_text(
        "print('S3=0.18')\nprint('NC=0.31')\n", encoding="utf-8"
    )
    (workspace / "solver.py").write_text(
        "from pathlib import Path\n"
        "Path('/tmp/candidate.align').write_text('candidate\\n')\n"
        "print('Final S3: 0.202510, Ea: 7148, E2_aligned: 26382')\n"
        "print('Writing alignment to /tmp/candidate.align...')\n",
        encoding="utf-8",
    )
    controller = RunController.create(
        "optimize a score",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"
    controller._execute_tool(
        state,
        {
            "action": "write",
            "path": "eval.py",
            "content": "print('S3=0.18')\nprint('NC=0.31')\n",
            "rationale": "Create evaluation script",
        },
    )
    controller._execute_tool(
        state, {"action": "run", "command": "python eval.py", "cwd": "."}
    )
    controller._execute_tool(
        state,
        {
            "action": "run",
            "command": "python -c \"print('S3=0.03, Ea=2, E2a=5')\"",
            "cwd": ".",
            "rationale": "Test an in-memory diagnostic",
        },
    )
    assert state.runtime_config["managed_evaluation"]["decision_pending"] is False
    assert state.runtime_config["managed_evaluation"]["local_check_hint_shown"] is False
    controller._execute_tool(
        state,
        {
            "action": "run",
            "command": "python solver.py",
            "cwd": ".",
            "rationale": "Quick test of candidate alignment",
        },
    )

    config = state.runtime_config["managed_evaluation"]
    assert config["decision_pending"] is True
    assert config["successful_evaluator_runs"] == 1
    events = controller.store.events_path.read_text(encoding="utf-8")
    assert '"signal": "candidate_metric"' in events
    assert '"candidate_artifacts": ["/tmp/candidate.align"]' in events
    transcript = controller.store.transcript_path.read_text(encoding="utf-8")
    assert "Candidate-producing command" in transcript

    with pytest.raises(ValueError, match="only managed_eval or skip_managed_eval"):
        controller._apply_action(
            state,
            {"action": "run", "command": "true", "cwd": "."},
        )
    assert config["decision_pending"] is True

    controller._apply_action(
        state,
        {
            "action": "skip_managed_eval",
            "reason": "this Candidate is not reproducible",
        },
    )
    assert config["decision_pending"] is False
    assert config["declined"] is False
    controller._execute_tool(
        state,
        {
            "action": "run",
            "command": "python solver.py",
            "cwd": ".",
            "rationale": "Quick test of candidate alignment",
        },
    )
    assert config["decision_pending"] is False

    (workspace / "solver.py").write_text(
        (workspace / "solver.py").read_text(encoding="utf-8").replace(
            "candidate\\n", "changed candidate\\n"
        ),
        encoding="utf-8",
    )
    controller._execute_tool(
        state,
        {
            "action": "run",
            "command": "python solver.py",
            "cwd": ".",
            "rationale": "Quick test of changed candidate alignment",
        },
    )
    assert config["decision_pending"] is True
    events = controller.store.events_path.read_text(encoding="utf-8")
    assert '"kind": "managed_evaluation_skipped"' in events

    result = controller._execute_managed_evaluation(
        state,
        {
            "action": "managed_eval",
            "operation": "submit",
            "script": "eval.py",
            "primary": "S3",
            "arguments": ["/tmp/candidate.align"],
        },
    )
    assert result.success
    attempt = result.data["attempt"]
    assert attempt["metrics"] == {"NC": 0.31, "S3": 0.18}
    assert config["decision_pending"] is False

    controller._execute_tool(
        state,
        {
            "action": "run",
            "command": "python eval.py /tmp/candidate.align",
            "cwd": ".",
        },
    )
    assert config["successful_evaluator_runs"] == 0
    assert config["decision_pending"] is False

    Path("/tmp/candidate.align").write_text("third candidate\n", encoding="utf-8")
    controller._execute_tool(
        state,
        {
            "action": "run",
            "command": "python eval.py /tmp/candidate.align",
            "cwd": ".",
        },
    )
    assert config["successful_evaluator_runs"] == 1


def test_background_candidate_metric_is_gated_after_completion(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    candidate_path = (workspace / "candidate.align").resolve()
    (workspace / "eval.py").write_text("print('S3=0.18')\n", encoding="utf-8")
    (workspace / "solver.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(candidate_path)!r}).write_text('candidate\\n')\n"
        "print('Final S3 = 0.23, NC = 0.07')\n"
        f"print('Saved to {candidate_path}')\n",
        encoding="utf-8",
    )
    controller = RunController.create(
        "optimize a score",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"
    controller._execute_tool(
        state,
        {
            "action": "write",
            "path": "eval.py",
            "content": "print('S3=0.18')\n",
            "rationale": "Create evaluation script",
        },
    )
    controller._execute_tool(
        state, {"action": "run", "command": "python eval.py", "cwd": "."}
    )
    before = {item["id"] for item in controller.commands.recover()}
    controller._execute_tool(
        state,
        {"action": "start", "command": "python solver.py", "cwd": "."},
    )
    created = [
        item for item in controller.commands.recover() if item["id"] not in before
    ]
    assert len(created) == 1
    command_id = created[0]["id"]
    for _ in range(100):
        controller._execute_tool(
            state,
            {"action": "poll", "command_id": command_id},
        )
        if controller.commands.describe(command_id)["status"] == "exited":
            controller._refresh_waiting_jobs(state)
            break
    else:
        pytest.fail("background Candidate did not finish")

    config = state.runtime_config["managed_evaluation"]
    assert config["decision_pending"] is True
    assert config["pending_candidate_artifacts"] == [str(candidate_path)]
    events = controller.store.events_path.read_text(encoding="utf-8")
    assert '"signal": "candidate_metric"' in events


def test_metric_names_accept_multiple_assignments_on_one_line() -> None:
    assert RunController._metric_names("S3=0.248294 NC=1.000000\n") == [
        "S3",
        "NC",
    ]
    assert RunController._metric_names("Pass rate: 0.5431\n") == ["Pass_rate"]


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


def test_multi_hour_deadline_uses_flat_flow_even_if_model_profiles_short(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "official multi-hour task",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.deadline.wall_time_seconds = 18_000

    controller._apply_action(
        state,
        {
            "action": "profile_task",
            "profile": {
                "execution_regime": "standard",
                "primary_playbook": "generalist",
                "estimated_horizon": "short",
                "validation_cost": "low",
                "rationale": "model guessed short",
            },
        },
    )

    assert state.phase == "long_horizon_work"
    assert state.profile.execution_regime == "long_horizon"  # type: ignore[union-attr]
    assert state.profile.estimated_horizon == "multi_hour"  # type: ignore[union-attr]


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


def test_profile_aliases_route_long_horizon_tasks_without_plan_fallback() -> None:
    normalized = RunController._normalize_profile(
        {
            "profile": "optimization",
            "horizon": "long_horizon",
            "rationale": "multi-hour measured search",
        }
    )
    assert normalized["execution_regime"] == "long_horizon"
    assert normalized["primary_playbook"] == "optimization"
    assert normalized["estimated_horizon"] == "multi_hour"


def test_rejected_native_tool_call_gets_a_tool_response(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "native protocol recovery",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    controller._record_rejected_tool_call(
        state,
        {"action": "unknown_tool", "_tool_call_id": "call_bad"},
        "tool is unavailable",
    )
    message = json.loads(controller.store.transcript_path.read_text().splitlines()[-1])
    assert message["role"] == "tool"
    assert message["metadata"]["tool_call_id"] == "call_bad"
    assert json.loads(message["content"])["success"] is False


def test_final_delivery_stops_managed_jobs(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "final cleanup", workspace, ScriptedModel([]), state_root=tmp_path / "state", skills_root=skills_root
    )
    state = controller.store.load()
    started = controller.commands.start("sleep 30")
    assert started.success
    state.phase = "deliver"
    state.final["verification"] = {"evidence_ids": ["ev-placeholder"]}
    controller._apply_action(
        state,
        {
            "action": "final_delivery",
            "summary": "done",
            "tests": [],
            "changed_files": [],
            "risks": [],
        },
    )
    assert controller.commands.poll(started.background_id).data["status"] == "terminated"


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
    assert "TOOL POLICY" in flat_prompt
    assert "start/poll/logs/stop" in flat_prompt
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


def test_deadline_restores_best_explicitly_valid_managed_attempt(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact = workspace / "result.align"
    score = workspace / "score.txt"
    valid = workspace / "valid.txt"
    artifact.write_text("best\n", encoding="utf-8")
    score.write_text("10\n", encoding="utf-8")
    valid.write_text("true\n", encoding="utf-8")
    evaluator = workspace / ".lightcoder-eval"
    evaluator.mkdir()
    (evaluator / "evaluate.py").write_text(
        "import json\nfrom pathlib import Path\n"
        "print(json.dumps({'valid': Path('valid.txt').read_text().strip() == 'true', "
        "'metrics': {'score': int(Path('score.txt').read_text())}}))\n",
        encoding="utf-8",
    )
    (evaluator / "metrics.toml").write_text(
        'primary = "score"\n[metrics.score]\ndirection = "maximize"\n',
        encoding="utf-8",
    )
    controller = RunController.create(
        "preserve best valid result",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
        managed_evaluation=True,
    )
    state = controller.store.load()
    store = Path(state.runtime_config["managed_evaluation"]["store"])
    first = submit_evaluation(
        workspace, store=store, state_root=controller.store.root
    )
    assert first["valid"] is True

    artifact.write_text("invalid-high-score\n", encoding="utf-8")
    score.write_text("100\n", encoding="utf-8")
    valid.write_text("false\n", encoding="utf-8")
    invalid = submit_evaluation(
        workspace, store=store, state_root=controller.store.root
    )
    assert invalid["valid"] is False
    artifact.write_text("unfinished\n", encoding="utf-8")

    state.deadline.wall_time_seconds = 1
    controller._deadline_elapsed_base = 2
    assert controller._deadline_transition(state) is True
    assert artifact.read_text(encoding="utf-8") == "best\n"
    events = controller.store.events_path.read_text(encoding="utf-8")
    assert '"kind": "managed_evaluation_best_restored"' in events
    assert f'"attempt_id": "{first["id"]}"' in events


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


def test_multi_hour_deadline_reserves_fixed_finalization_window(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "leave time for final state",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.deadline.wall_time_seconds = 3_600
    controller._deadline_elapsed_base = 3_569
    assert controller._deadline_transition(state) is False

    controller._deadline_elapsed_base = 3_570
    assert controller._deadline_transition(state) is True
    assert state.final["limit"]["configured_seconds"] == 3_600
    assert state.final["limit"]["work_seconds"] == 3_570


def test_foreground_run_uses_remaining_task_time_without_fixed_cap(
    tmp_path: Path, skills_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "run a long foreground command",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"
    state.deadline.wall_time_seconds = 3_600
    controller._deadline_elapsed_base = 10
    observed: dict[str, float | None] = {}

    def fake_run(command: str, **kwargs: object) -> ToolResult:
        observed["timeout_seconds"] = kwargs.get("timeout_seconds")  # type: ignore[assignment]
        return ToolResult("run", "cmd-test", True, 0.0, output="ok", exit_code=0)

    monkeypatch.setattr(controller.commands, "run", fake_run)
    controller._execute_tool(
        state,
        {"action": "run", "command": "long-command", "cwd": "."},
    )

    timeout = observed["timeout_seconds"]
    assert timeout is not None
    assert 3_500 < timeout < 3_600


def test_automatic_mutation_check_uses_remaining_work_time(
    tmp_path: Path, skills_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = RunController.create(
        "bound automatic checks",
        workspace,
        ScriptedModel([]),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.store.load()
    state.phase = "long_horizon_work"
    state.deadline.wall_time_seconds = 3_600
    controller._deadline_elapsed_base = 3_565
    observed: dict[str, float | None] = {}

    def fake_run(command: str, **kwargs: object) -> ToolResult:
        observed["timeout_seconds"] = kwargs.get("timeout_seconds")  # type: ignore[assignment]
        return ToolResult("run", "cmd-check", True, 0.0, output="ok", exit_code=0)

    monkeypatch.setattr(controller.commands, "run", fake_run)
    controller._execute_tool(
        state, {"action": "write", "path": "module.py", "content": "value = 1\n"}
    )

    timeout = observed["timeout_seconds"]
    assert timeout is not None
    assert 0 < timeout <= 5


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


def test_permanent_model_failure_stops_without_exponential_retries(
    tmp_path: Path, skills_root: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    class RejectedModel:
        model = "rejected"

        def complete(self, messages, *, timeout_seconds=None, tools=None):
            raise PermanentModelError("model HTTP 400: invalid tool history")

    controller = RunController.create(
        "reject invalid requests",
        workspace,
        RejectedModel(),
        state_root=tmp_path / "state",
        skills_root=skills_root,
    )
    state = controller.step()

    assert state.status == "failed_infra"
    assert not state.retry_at
    assert state.counters["model_calls"] == 1


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
