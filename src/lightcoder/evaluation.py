from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path
from typing import Any

from .models import utc_now


EVALUATOR_DIRNAME = ".lightcoder-eval"
EVALUATOR_FILENAME = "evaluate.py"
METRICS_FILENAME = "metrics.toml"
CAPTURED_INPUTS_DIRNAME = ".lightcoder-eval-inputs"


class EvaluationError(ValueError):
    pass


def adopt_evaluator(
    workspace: Path,
    source: Path,
    *,
    primary: str,
    direction: str = "maximize",
    arguments: list[str] | None = None,
    timeout_seconds: float = 600,
) -> Path:
    """Adopt a working metric script without requiring a contract rewrite."""
    workspace = workspace.expanduser().resolve()
    source = source.expanduser()
    if not source.is_absolute():
        source = workspace / source
    source = source.resolve()
    if not source.is_file():
        raise EvaluationError(f"evaluator script does not exist: {source}")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", primary):
        raise EvaluationError("primary metric must be a simple name")
    if direction not in {"maximize", "minimize"}:
        raise EvaluationError("direction must be maximize or minimize")
    if timeout_seconds <= 0:
        raise EvaluationError("timeout must be positive")

    destination = workspace / EVALUATOR_DIRNAME
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / EVALUATOR_FILENAME
    if source != target:
        shutil.copy2(source, target)

    portable_arguments = [
        _portable_workspace_argument(workspace, value, index=index)
        for index, value in enumerate(arguments or [])
    ]
    command = [sys.executable, f"{EVALUATOR_DIRNAME}/{EVALUATOR_FILENAME}"]
    command.extend(portable_arguments)
    metrics = destination / METRICS_FILENAME
    metrics.write_text(
        "\n".join(
            [
                f"primary = {json.dumps(primary)}",
                f"timeout_seconds = {float(timeout_seconds):g}",
                f"command = {json.dumps(command)}",
                "",
                f"[metrics.{primary}]",
                f"direction = {json.dumps(direction)}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return destination


def evaluation_store(workspace: Path, configured: Path | None = None) -> Path:
    if configured is not None:
        return configured.expanduser().resolve()
    from_environment = os.getenv("LIGHTCODER_EVAL_STORE", "").strip()
    if from_environment:
        return Path(from_environment).expanduser().resolve()
    try:
        git_dir = _git_path(workspace, "rev-parse", "--git-dir")
    except EvaluationError:
        return (workspace.expanduser().resolve() / ".lightcoder" / "evaluations")
    path = Path(git_dir)
    if not path.is_absolute():
        path = _repo_root(workspace) / path
    return (path / "lightcoder-eval").resolve()


def submit_evaluation(
    workspace: Path,
    *,
    store: Path | None = None,
    message: str = "",
    state_root: Path | None = None,
    run_id: str = "",
    model: str = "",
) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    source_dir = workspace / EVALUATOR_DIRNAME
    _load_metric_config(source_dir)
    destination = evaluation_store(workspace, store)
    attempts = load_attempts(destination)
    attempt_id = f"A{len(attempts) + 1:04d}"
    started = time.monotonic()
    snapshot_path = ""
    workspace_hash = ""

    if shutil.which("git"):
        repo = _repo_root(workspace, initialize=True)
        commit = _commit_workspace(
            repo,
            message or "managed evaluation",
            excluded_paths=[state_root] if state_root is not None else None,
        )
        relative_workspace = workspace.relative_to(repo)
        relative_evaluator = source_dir.relative_to(repo)
        with tempfile.TemporaryDirectory(prefix="lightcoder-eval-") as temporary:
            checkout = Path(temporary) / "worktree"
            _git(repo, "worktree", "add", "--detach", "--force", str(checkout), commit)
            try:
                snapshot_workspace = checkout / relative_workspace
                snapshot_evaluator = checkout / relative_evaluator
                config = _load_metric_config(snapshot_evaluator)
                evaluator_hash = _hash_directory(snapshot_evaluator)
                execution = _run_evaluator(
                    snapshot_workspace, snapshot_evaluator, config
                )
            finally:
                _git(
                    repo,
                    "worktree",
                    "remove",
                    "--force",
                    str(checkout),
                    check=False,
                )
        version_backend = "git"
        solution = commit[:12]
    else:
        snapshot_workspace = destination / "snapshots" / attempt_id / "workspace"
        exclusions = [destination]
        if state_root is not None:
            exclusions.append(state_root)
        _copy_workspace_snapshot(workspace, snapshot_workspace, exclusions)
        snapshot_evaluator = snapshot_workspace / EVALUATOR_DIRNAME
        config = _load_metric_config(snapshot_evaluator)
        evaluator_hash = _hash_directory(snapshot_evaluator)
        workspace_hash = _hash_directory(snapshot_workspace)
        execution = _run_evaluator(snapshot_workspace, snapshot_evaluator, config)
        commit = f"snapshot-{workspace_hash}"
        solution = workspace_hash[:12]
        snapshot_path = str(snapshot_workspace)
        version_backend = "snapshot"

    duration = time.monotonic() - started
    primary = str(config["primary"])
    direction = str(config["metrics"][primary]["direction"])
    record: dict[str, Any] = {
        "id": attempt_id,
        "created_at": utc_now(),
        "message": message.strip(),
        "commit": commit,
        "solution": solution,
        "version_backend": version_backend,
        "workspace_hash": workspace_hash,
        "snapshot": snapshot_path,
        "evaluator_hash": evaluator_hash,
        "evaluator": f"E-{evaluator_hash[:8]}",
        "primary_metric": primary,
        "direction": direction,
        "status": execution["status"],
        "duration_seconds": round(duration, 6),
        "metrics": execution.get("metrics", {}),
        "test_points": execution.get("test_points", []),
        "return_code": execution.get("return_code"),
        "error": execution.get("error", ""),
        "comparison": {},
        "agent": _active_agent_metadata(
            state_root=state_root,
            run_id=run_id,
            model=model,
        ),
    }
    if record["status"] == "completed":
        record["comparison"] = _comparison(record, attempts)

    destination.mkdir(parents=True, exist_ok=True)
    log_path = destination / "logs" / f"{attempt_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(str(execution.get("log", "")), encoding="utf-8")
    record["log"] = str(log_path)
    _append_jsonl(destination / "attempts.jsonl", record)
    return record


def load_attempts(store: Path) -> list[dict[str, Any]]:
    path = store.expanduser().resolve() / "attempts.jsonl"
    if not path.is_file():
        return []
    values: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("id"):
            values.append(value)
    return values


def find_attempt(store: Path, attempt_id: str) -> dict[str, Any]:
    normalized = attempt_id.strip().upper()
    for attempt in load_attempts(store):
        if str(attempt.get("id", "")).upper() == normalized:
            return attempt
    raise EvaluationError(f"unknown evaluation attempt: {attempt_id}")


def restore_attempt(
    workspace: Path,
    attempt_id: str,
    *,
    store: Path | None = None,
    excluded_paths: list[Path] | None = None,
) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    destination = evaluation_store(workspace, store)
    attempt = find_attempt(destination, attempt_id)
    if attempt.get("version_backend") == "snapshot":
        snapshot = Path(str(attempt.get("snapshot", "")))
        if not snapshot.is_dir():
            raise EvaluationError(f"snapshot is missing for {attempt_id}: {snapshot}")
        exclusions = [destination]
        exclusions.extend(excluded_paths or [])
        latest = load_attempts(destination)[-1]
        expected = str(latest.get("workspace_hash", ""))
        if expected and _hash_workspace(workspace, exclusions) != expected:
            raise EvaluationError(
                "workspace has uncommitted changes; run `lightcoder eval` before restore"
            )
        _restore_workspace_snapshot(workspace, snapshot, exclusions)
        return attempt

    repo = _repo_root(workspace)
    pathspecs = ["."]
    for excluded in excluded_paths or []:
        try:
            relative = excluded.expanduser().resolve().relative_to(repo)
        except ValueError:
            continue
        if relative.parts:
            pathspecs.append(f":(exclude){relative.as_posix()}/**")
    dirty = _git(repo, "status", "--porcelain", "--", *pathspecs).stdout.strip()
    if dirty:
        raise EvaluationError(
            "workspace has uncommitted changes; run `lightcoder eval`, commit them, "
            "or clean them before checkout"
        )
    commit = str(attempt["commit"])
    _git(
        repo,
        "restore",
        "--source",
        commit,
        "--staged",
        "--worktree",
        "--",
        *pathspecs,
    )
    return attempt


def evaluation_summary(workspace: Path, store: Path | None = None) -> dict[str, Any]:
    try:
        attempts = load_attempts(evaluation_store(workspace, store))
    except (EvaluationError, OSError):
        return {"attempts": 0}
    completed = [item for item in attempts if item.get("status") == "completed"]
    summary: dict[str, Any] = {"attempts": len(attempts)}
    if not completed:
        return summary
    latest = completed[-1]
    comparable = [
        item
        for item in completed
        if item.get("evaluator_hash") == latest.get("evaluator_hash")
        and item.get("primary_metric") == latest.get("primary_metric")
        and item.get("direction") == latest.get("direction")
    ]
    best = _best_attempt(comparable, str(latest["primary_metric"]), str(latest["direction"]))
    summary.update(
        {
            "latest": _compact_attempt(latest),
            "best_comparable": _compact_attempt(best) if best else None,
        }
    )
    return summary


def format_attempt(record: dict[str, Any]) -> str:
    if record.get("status") != "completed":
        return (
            f"{record['id']} failed under {record['evaluator']}: "
            f"{record.get('error', 'evaluation failed')}\n"
            f"commit={record['solution']} log={record.get('log', '')}"
        )
    primary = str(record["primary_metric"])
    value = record["metrics"][primary]
    comparison = record.get("comparison", {})
    detail = str(comparison.get("summary", "first comparable result"))
    return (
        f"{record['id']} completed: {primary}={value} ({record['evaluator']})\n"
        f"comparison: {detail}\n"
        f"commit={record['solution']} duration={record['duration_seconds']:.2f}s"
    )


def format_log(attempts: list[dict[str, Any]]) -> str:
    if not attempts:
        return "No managed evaluation attempts."
    rows = ["ID     SOLUTION      EVALUATOR   STATUS      PRIMARY"]
    for item in attempts:
        primary = str(item.get("primary_metric", ""))
        metrics = item.get("metrics", {})
        value = metrics.get(primary, "-") if isinstance(metrics, dict) else "-"
        rows.append(
            f"{str(item.get('id', '')):<6} "
            f"{str(item.get('solution', '')):<13} "
            f"{str(item.get('evaluator', '')):<11} "
            f"{str(item.get('status', '')):<11} "
            f"{primary}={value}"
        )
    return "\n".join(rows)


def _load_metric_config(directory: Path) -> dict[str, Any]:
    evaluator = directory / EVALUATOR_FILENAME
    metrics_path = directory / METRICS_FILENAME
    missing = [str(path) for path in (evaluator, metrics_path) if not path.is_file()]
    if missing:
        raise EvaluationError(
            "managed evaluator is not configured; create "
            f"{directory / EVALUATOR_FILENAME} and {directory / METRICS_FILENAME}. "
            "Run `lightcoder eval --help` for the contract."
        )
    try:
        config = tomllib.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise EvaluationError(f"invalid {metrics_path}: {error}") from error
    primary = config.get("primary")
    metrics = config.get("metrics")
    if not isinstance(primary, str) or not isinstance(metrics, dict):
        raise EvaluationError("metrics.toml requires `primary` and `[metrics.<name>]`")
    definition = metrics.get(primary)
    if not isinstance(definition, dict) or definition.get("direction") not in {
        "maximize",
        "minimize",
    }:
        raise EvaluationError(
            "the primary metric requires direction = \"maximize\" or \"minimize\""
        )
    timeout = config.get("timeout_seconds", 600)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise EvaluationError("timeout_seconds must be a positive number")
    command = config.get("command")
    if command is not None and (
        not isinstance(command, list)
        or not command
        or not all(isinstance(item, str) and item for item in command)
    ):
        raise EvaluationError("command must be a non-empty array of strings")
    return config


def _run_evaluator(
    workspace: Path, evaluator_dir: Path, config: dict[str, Any]
) -> dict[str, Any]:
    configured_command = config.get("command")
    command = (
        list(configured_command)
        if isinstance(configured_command, list)
        else [sys.executable, str(evaluator_dir / EVALUATOR_FILENAME)]
    )
    environment = os.environ.copy()
    environment["LIGHTCODER_EVAL_WORKSPACE"] = str(workspace)
    try:
        result = subprocess.run(
            command,
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            timeout=float(config.get("timeout_seconds", 600)),
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else error.stdout or ""
        stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else error.stderr or ""
        return {
            "status": "failed",
            "return_code": 124,
            "error": f"evaluator timed out after {config.get('timeout_seconds', 600)}s",
            "log": _combined_log(stdout, stderr),
        }
    log = _combined_log(result.stdout, result.stderr)
    if result.returncode != 0:
        return {
            "status": "failed",
            "return_code": result.returncode,
            "error": f"evaluator exited with code {result.returncode}",
            "log": log,
        }
    try:
        normalized, test_points = _parse_evaluator_output(result.stdout, config)
    except (KeyError, json.JSONDecodeError, EvaluationError) as error:
        return {
            "status": "failed",
            "return_code": result.returncode,
            "error": str(error),
            "log": log,
        }
    return {
        "status": "completed",
        "return_code": result.returncode,
        "metrics": normalized,
        "test_points": test_points,
        "log": log,
    }


def _commit_workspace(
    repo: Path,
    message: str,
    *,
    excluded_paths: list[Path | None] | None = None,
) -> str:
    pathspecs = ["."]
    configured_exclusions = [
        path.expanduser().resolve()
        for path in (excluded_paths or [])
        if path is not None
    ]
    state_root = os.getenv("LIGHTCODER_STATE_ROOT", "").strip()
    if state_root and not configured_exclusions:
        configured_exclusions.append(Path(state_root).expanduser().resolve())
    for excluded in configured_exclusions:
        try:
            relative_state = excluded.relative_to(repo)
        except ValueError:
            continue
        if relative_state.parts:
            pathspecs.append(f":(exclude){relative_state.as_posix()}/**")
    _git(repo, "add", "-A", "--", *pathspecs)
    staged = _git(repo, "diff", "--cached", "--quiet", check=False)
    if staged.returncode not in {0, 1}:
        raise EvaluationError(staged.stderr.strip() or "git diff --cached failed")
    if staged.returncode == 1:
        committed = _git(
            repo,
            "-c",
            "user.name=LightCoder",
            "-c",
            "user.email=lightcoder@local",
            "commit",
            "--no-verify",
            "-m",
            f"lightcoder eval: {message}",
            check=False,
        )
        if committed.returncode != 0:
            raise EvaluationError(committed.stderr.strip() or committed.stdout.strip())
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _comparison(record: dict[str, Any], attempts: list[dict[str, Any]]) -> dict[str, Any]:
    comparable = [
        item
        for item in attempts
        if item.get("status") == "completed"
        and item.get("evaluator_hash") == record.get("evaluator_hash")
        and item.get("primary_metric") == record.get("primary_metric")
        and item.get("direction") == record.get("direction")
    ]
    if not comparable:
        return {"classification": "baseline", "summary": "first result under this evaluator"}
    primary = str(record["primary_metric"])
    direction = str(record["direction"])
    best = _best_attempt(comparable, primary, direction)
    assert best is not None
    old = float(best["metrics"][primary])
    new = float(record["metrics"][primary])
    delta = new - old
    improved = new > old if direction == "maximize" else new < old
    equal = new == old
    classification = "equal" if equal else "improved" if improved else "regressed"
    return {
        "classification": classification,
        "best_before": best["id"],
        "best_value": old,
        "delta": delta,
        "summary": f"{classification} vs {best['id']}: {old} -> {new} (delta {delta:+g})",
    }


def _best_attempt(
    attempts: list[dict[str, Any]], primary: str, direction: str
) -> dict[str, Any] | None:
    usable = [
        item
        for item in attempts
        if isinstance(item.get("metrics"), dict)
        and isinstance(item["metrics"].get(primary), (int, float))
    ]
    if not usable:
        return None
    return (max if direction == "maximize" else min)(
        usable, key=lambda item: float(item["metrics"][primary])
    )


def _compact_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
    primary = str(attempt.get("primary_metric", ""))
    metrics = attempt.get("metrics", {})
    return {
        "id": attempt.get("id"),
        "solution": attempt.get("solution"),
        "evaluator": attempt.get("evaluator"),
        "primary_metric": primary,
        "value": metrics.get(primary) if isinstance(metrics, dict) else None,
    }


def _active_agent_metadata(
    *,
    state_root: Path | None = None,
    run_id: str = "",
    model: str = "",
) -> dict[str, Any]:
    run_id = run_id.strip() or os.getenv("LIGHTCODER_RUN_ID", "").strip()
    model = model.strip() or os.getenv("LIGHTCODER_MODEL", "").strip()
    metadata: dict[str, Any] = {
        key: value
        for key, value in {
            "run_id": run_id,
            "model": model,
        }.items()
        if value
    }
    state_root_value = (
        state_root.expanduser().resolve()
        if state_root is not None
        else Path(os.getenv("LIGHTCODER_STATE_ROOT", "")).expanduser()
        if os.getenv("LIGHTCODER_STATE_ROOT", "").strip()
        else None
    )
    if state_root_value is None or not run_id:
        return metadata
    run_dir = state_root_value / "runs" / run_id
    state_path = run_dir / "state.json"
    transcript_path = run_dir / "transcript.jsonl"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    usage: dict[str, int] = {}
    model_responses = 0
    try:
        transcript_lines = transcript_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    except OSError:
        transcript_lines = []
    for line in transcript_lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if value.get("role") != "assistant":
            continue
        model_responses += 1
        response_usage = value.get("metadata", {}).get("usage", {})
        if not isinstance(response_usage, dict):
            continue
        for name, amount in response_usage.items():
            if isinstance(amount, int):
                usage[str(name)] = usage.get(str(name), 0) + amount
    counters = state.get("counters", {}) if isinstance(state, dict) else {}
    metadata.update(
        {
            "model_calls": max(int(counters.get("model_calls", 0)), model_responses),
            "token_usage": dict(sorted(usage.items())),
            "context_episodes": len(state.get("episodes", []))
            if isinstance(state, dict)
            else 0,
        }
    )
    return metadata


def _last_json_object(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise EvaluationError("the last non-empty output line must be a JSON object")
        return value
    raise EvaluationError("evaluator produced no JSON output")


def _parse_evaluator_output(
    stdout: str, config: dict[str, Any]
) -> tuple[dict[str, int | float], list[Any]]:
    try:
        payload = _last_json_object(stdout)
    except (json.JSONDecodeError, EvaluationError):
        return _parse_metric_lines(stdout, config), []
    metrics = payload["metrics"]
    if not isinstance(metrics, dict):
        raise EvaluationError("evaluator output `metrics` must be an object")
    normalized: dict[str, int | float] = {}
    for name, value in metrics.items():
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            raise EvaluationError(f"metric {name!r} must be numeric")
        normalized[str(name)] = value
    primary = str(config["primary"])
    if primary not in normalized:
        raise EvaluationError(f"evaluator did not return primary metric {primary!r}")
    test_points = payload.get("test_points", [])
    if not isinstance(test_points, list):
        raise EvaluationError("evaluator output `test_points` must be a list")
    return normalized, test_points


def _parse_metric_lines(
    stdout: str, config: dict[str, Any]
) -> dict[str, int | float]:
    normalized: dict[str, int | float] = {}
    for match in re.finditer(
        r"(?mi)^\s*([a-z][a-z0-9_-]{0,31})\s*[:=]\s*"
        r"(-?(?:\d+(?:\.\d*)?|\.\d+))\s*%?\s*$",
        stdout,
    ):
        normalized[match.group(1)] = float(match.group(2))
    primary = str(config["primary"])
    if primary not in normalized:
        raise EvaluationError(
            "evaluator must print JSON or a line like "
            f"`{primary}=0.5` for the primary metric"
        )
    return normalized


def _portable_workspace_argument(
    workspace: Path, value: str, *, index: int
) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        return value
    try:
        return path.resolve().relative_to(workspace).as_posix()
    except ValueError:
        if not path.is_file():
            return value
        # Agents commonly stage candidate artifacts under /tmp.  Capture those
        # files at a stable argument-position path so the candidate commit is
        # reproducible while the evaluator contract hash remains comparable.
        destination = workspace / CAPTURED_INPUTS_DIRNAME
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / f"arg-{index:02d}{path.suffix}"
        shutil.copy2(path, target)
        return target.relative_to(workspace).as_posix()


def _hash_directory(directory: Path) -> str:
    return _hash_workspace(directory, [])


def _hash_workspace(directory: Path, excluded_paths: list[Path]) -> str:
    hasher = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        if _path_is_excluded(path, excluded_paths):
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        hasher.update(str(path.relative_to(directory)).encode())
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def _copy_workspace_snapshot(
    workspace: Path, destination: Path, excluded_paths: list[Path]
) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    excluded = [path.expanduser().resolve() for path in excluded_paths]

    def ignore(directory: str, names: list[str]) -> set[str]:
        current = Path(directory)
        ignored: set[str] = set()
        for name in names:
            candidate = (current / name).resolve()
            if (
                name in {".git", "__pycache__", ".pytest_cache", ".mypy_cache"}
                or candidate.suffix == ".pyc"
                or _path_is_excluded(candidate, excluded)
            ):
                ignored.add(name)
        return ignored

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(workspace, destination, symlinks=True, ignore=ignore)


def _restore_workspace_snapshot(
    workspace: Path, snapshot: Path, excluded_paths: list[Path]
) -> None:
    protected_names = {".git"}
    for excluded in excluded_paths:
        try:
            relative = excluded.expanduser().resolve().relative_to(workspace)
        except ValueError:
            continue
        if relative.parts:
            protected_names.add(relative.parts[0])
    for child in workspace.iterdir():
        if child.name in protected_names:
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in snapshot.iterdir():
        target = workspace / child.name
        if child.name in protected_names:
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.copytree(child, target, symlinks=True, dirs_exist_ok=True)
        elif child.is_symlink():
            target.symlink_to(os.readlink(child))
        else:
            shutil.copy2(child, target)


def _path_is_excluded(path: Path, excluded_paths: list[Path]) -> bool:
    resolved = path.expanduser().resolve()
    for excluded in excluded_paths:
        target = excluded.expanduser().resolve()
        if resolved == target or target in resolved.parents:
            return True
    return False


def _combined_log(stdout: str, stderr: str) -> str:
    return f"STDOUT\n{stdout}\nSTDERR\n{stderr}".rstrip() + "\n"


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _repo_root(workspace: Path, *, initialize: bool = False) -> Path:
    try:
        root = _git_path(workspace, "rev-parse", "--show-toplevel")
    except EvaluationError:
        if not initialize:
            raise
        initialized = subprocess.run(
            ["git", "init", "-q"], cwd=workspace, capture_output=True, text=True
        )
        if initialized.returncode != 0:
            raise EvaluationError(
                initialized.stderr.strip() or "could not initialize Git workspace"
            )
        root = _git_path(workspace, "rev-parse", "--show-toplevel")
    return Path(root).resolve()


def _git_path(workspace: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments], cwd=workspace, capture_output=True, text=True
        )
    except FileNotFoundError as error:
        raise EvaluationError("managed evaluation Git backend is unavailable") from error
    if result.returncode != 0:
        raise EvaluationError(
            result.stderr.strip() or "managed evaluation requires a Git repository"
        )
    return result.stdout.strip()


def _git(
    repo: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *arguments], cwd=repo, capture_output=True, text=True
    )
    if check and result.returncode != 0:
        raise EvaluationError(result.stderr.strip() or result.stdout.strip())
    return result
