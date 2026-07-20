from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from lightcoder.evaluation import (
    EvaluationError,
    evaluation_summary,
    load_attempts,
    restore_attempt,
    submit_evaluation,
)


def git(workspace: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def initialize_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    git(workspace, "init", "-q")
    git(workspace, "config", "user.name", "Test")
    git(workspace, "config", "user.email", "test@example.com")
    (workspace / "score.txt").write_text("1\n", encoding="utf-8")
    git(workspace, "add", ".")
    git(workspace, "commit", "-q", "-m", "seed")
    evaluator = workspace / ".lightcoder-eval"
    evaluator.mkdir()
    (evaluator / "evaluate.py").write_text(
        """import json
from pathlib import Path

score = int(Path("score.txt").read_text())
print(json.dumps({"metrics": {"partial": score}, "test_points": [{"name": "score"}]}))
""",
        encoding="utf-8",
    )
    (evaluator / "metrics.toml").write_text(
        """primary = "partial"
timeout_seconds = 30

[metrics.partial]
direction = "maximize"
""",
        encoding="utf-8",
    )
    return workspace


def test_managed_evaluation_versions_compares_and_restores(tmp_path: Path) -> None:
    workspace = initialize_workspace(tmp_path)
    store = tmp_path / "store"

    first = submit_evaluation(workspace, store=store, message="baseline")
    assert first["status"] == "completed"
    assert first["metrics"]["partial"] == 1
    assert first["comparison"]["classification"] == "baseline"

    (workspace / "score.txt").write_text("2\n", encoding="utf-8")
    second = submit_evaluation(workspace, store=store, message="improve")
    assert second["evaluator_hash"] == first["evaluator_hash"]
    assert second["comparison"]["classification"] == "improved"
    assert second["comparison"]["best_before"] == first["id"]

    evaluator = workspace / ".lightcoder-eval" / "evaluate.py"
    evaluator.write_text(evaluator.read_text(encoding="utf-8") + "# revised metric\n")
    (workspace / "score.txt").write_text("3\n", encoding="utf-8")
    third = submit_evaluation(workspace, store=store, message="new evaluator")
    assert third["evaluator_hash"] != second["evaluator_hash"]
    assert third["comparison"]["classification"] == "baseline"

    summary = evaluation_summary(workspace, store)
    assert summary["attempts"] == 3
    assert summary["latest"]["id"] == third["id"]
    assert summary["best_comparable"]["id"] == third["id"]

    restored = restore_attempt(workspace, first["id"], store=store)
    assert restored["commit"] == first["commit"]
    assert (workspace / "score.txt").read_text(encoding="utf-8") == "1\n"
    assert "# revised metric" not in evaluator.read_text(encoding="utf-8")


def test_failed_evaluator_is_recorded(tmp_path: Path) -> None:
    workspace = initialize_workspace(tmp_path)
    store = tmp_path / "store"
    (workspace / ".lightcoder-eval" / "evaluate.py").write_text(
        "raise RuntimeError('broken evaluator')\n", encoding="utf-8"
    )

    attempt = submit_evaluation(workspace, store=store)

    assert attempt["status"] == "failed"
    assert attempt["return_code"] != 0
    assert load_attempts(store)[0]["id"] == attempt["id"]
    assert "broken evaluator" in Path(attempt["log"]).read_text(encoding="utf-8")


def test_runtime_state_is_not_committed_with_solution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = initialize_workspace(tmp_path)
    runtime_state = workspace / ".lightcoder"
    runtime_state.mkdir()
    (runtime_state / "transcript.jsonl").write_text("secret runtime state\n")
    monkeypatch.setenv("LIGHTCODER_STATE_ROOT", str(runtime_state))

    attempt = submit_evaluation(workspace, store=tmp_path / "store")

    committed = git(workspace, "ls-tree", "-r", "--name-only", attempt["commit"])
    assert ".lightcoder-eval/evaluate.py" in committed
    assert ".lightcoder/transcript.jsonl" not in committed


def test_attempt_captures_available_agent_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = initialize_workspace(tmp_path)
    state_root = tmp_path / "runtime"
    run_dir = state_root / "runs" / "run-test"
    run_dir.mkdir(parents=True)
    (run_dir / "state.json").write_text(
        json.dumps({"counters": {"model_calls": 2}, "episodes": [{}, {}]}),
        encoding="utf-8",
    )
    (run_dir / "transcript.jsonl").write_text(
        json.dumps(
            {
                "role": "assistant",
                "metadata": {"usage": {"prompt_tokens": 11, "total_tokens": 13}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LIGHTCODER_STATE_ROOT", str(state_root))
    monkeypatch.setenv("LIGHTCODER_RUN_ID", "run-test")
    monkeypatch.setenv("LIGHTCODER_MODEL", "test-model")

    attempt = submit_evaluation(workspace, store=tmp_path / "store")

    assert attempt["agent"]["run_id"] == "run-test"
    assert attempt["agent"]["model"] == "test-model"
    assert attempt["agent"]["model_calls"] == 2
    assert attempt["agent"]["context_episodes"] == 2
    assert attempt["agent"]["token_usage"]["total_tokens"] == 13


def test_checkout_refuses_to_overwrite_dirty_workspace(tmp_path: Path) -> None:
    workspace = initialize_workspace(tmp_path)
    store = tmp_path / "store"
    attempt = submit_evaluation(workspace, store=store)
    (workspace / "score.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(EvaluationError, match="uncommitted changes"):
        restore_attempt(workspace, attempt["id"], store=store)


def test_first_explicit_eval_initializes_missing_git_repository(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "score.txt").write_text("4\n", encoding="utf-8")
    evaluator = workspace / ".lightcoder-eval"
    evaluator.mkdir()
    (evaluator / "evaluate.py").write_text(
        """import json
from pathlib import Path
print(json.dumps({"metrics": {"partial": int(Path("score.txt").read_text())}}))
""",
        encoding="utf-8",
    )
    (evaluator / "metrics.toml").write_text(
        'primary = "partial"\n[metrics.partial]\ndirection = "maximize"\n',
        encoding="utf-8",
    )

    attempt = submit_evaluation(workspace, store=tmp_path / "store")

    assert attempt["status"] == "completed"
    assert attempt["metrics"]["partial"] == 4
    assert (workspace / ".git").is_dir()
