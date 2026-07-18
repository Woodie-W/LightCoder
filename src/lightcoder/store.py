from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from .models import Checkpoint, Evidence, RunState, new_id, utc_now


class StateConflictError(RuntimeError):
    pass


class StateStore:
    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root.resolve()
        self.run_id = run_id
        self.run_dir = self.root / "runs" / run_id
        self.state_path = self.run_dir / "state.json"
        self.events_path = self.run_dir / "events.jsonl"
        self.evidence_path = self.run_dir / "evidence.jsonl"
        self.transcript_path = self.run_dir / "transcript.jsonl"
        self.handoffs_dir = self.run_dir / "handoffs"
        self.commands_dir = self.run_dir / "commands"
        self.checkpoints_dir = self.run_dir / "checkpoints"
        self.lock_path = self.run_dir / ".lease"
        self.event_sink: Callable[[dict[str, Any]], None] | None = None
        self._lease_depth = 0
        self._lease_handle: Any = None

    @classmethod
    def create(cls, root: Path, state: RunState) -> "StateStore":
        store = cls(root, state.run_id)
        store._ensure_dirs()
        if store.state_path.exists():
            raise FileExistsError(f"run already exists: {state.run_id}")
        state.validate()
        store._atomic_json(store.state_path, state.to_dict())
        store.append_event(
            "run_created", {"objective": state.objective, "workspace": state.workspace}
        )
        return store

    def _ensure_dirs(self) -> None:
        for path in (
            self.run_dir,
            self.handoffs_dir,
            self.commands_dir,
            self.checkpoints_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def lease(self) -> Iterator[None]:
        if self._lease_depth:
            self._lease_depth += 1
            try:
                yield
            finally:
                self._lease_depth -= 1
            return
        self._ensure_dirs()
        handle = self.lock_path.open("a+", encoding="utf-8")
        try:
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            except ImportError:
                pass
            self._lease_depth = 1
            self._lease_handle = handle
            yield
        finally:
            self._lease_depth = 0
            self._lease_handle = None
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except ImportError:
                pass
            handle.close()

    def load(self) -> RunState:
        if not self.state_path.is_file():
            raise FileNotFoundError(f"unknown run: {self.run_id}")
        return RunState.from_dict(
            json.loads(self.state_path.read_text(encoding="utf-8"))
        )

    def commit(self, state: RunState, *, expected_revision: int) -> RunState:
        with self.lease():
            current = self.load()
            if current.revision != expected_revision:
                raise StateConflictError(
                    f"state revision changed: expected {expected_revision}, found {current.revision}"
                )
            state.validate()
            state.revision = expected_revision + 1
            state.updated_at = utc_now()
            self._atomic_json(self.state_path, state.to_dict())
            return state

    def append_event(self, kind: str, data: dict[str, Any] | None = None) -> None:
        event = {
            "id": new_id("event"),
            "created_at": utc_now(),
            "kind": kind,
            "data": data or {},
        }
        self._append_jsonl(self.events_path, event)
        if self.event_sink:
            self.event_sink(event)

    def append_transcript(self, role: str, content: str, **metadata: Any) -> None:
        self._append_jsonl(
            self.transcript_path,
            {
                "created_at": utc_now(),
                "role": role,
                "content": content,
                "metadata": metadata,
            },
        )

    def transcript_line_count(self) -> int:
        if not self.transcript_path.is_file():
            return 0
        with self.transcript_path.open("rb") as handle:
            return sum(1 for _ in handle)

    def record_evidence(self, evidence: Evidence) -> None:
        self._append_jsonl(
            self.evidence_path,
            evidence.__dict__
            if hasattr(evidence, "__dict__")
            else {
                field: getattr(evidence, field)
                for field in evidence.__dataclass_fields__
            },
        )

    def evidence(self) -> list[Evidence]:
        if not self.evidence_path.is_file():
            return []
        values: list[Evidence] = []
        for line in self.evidence_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            try:
                values.append(Evidence(**json.loads(line)))
            except (json.JSONDecodeError, TypeError):
                continue
        return values

    def evidence_by_id(self, evidence_ids: list[str]) -> list[Evidence]:
        requested = set(evidence_ids)
        return [item for item in self.evidence() if item.id in requested]

    def write_handoff(self, generation: int, value: dict[str, Any]) -> Path:
        path = self.handoffs_dir / f"{generation:04d}.json"
        self._atomic_json(path, value)
        return path

    def write_checkpoint(self, checkpoint: Checkpoint) -> Path:
        path = self.checkpoints_dir / f"{checkpoint.id}.json"
        value = {
            field: getattr(checkpoint, field)
            for field in checkpoint.__dataclass_fields__
        }
        self._atomic_json(path, value)
        return path

    def command_log_path(self, command_id: str) -> Path:
        self._ensure_dirs()
        return self.commands_dir / f"{command_id}.log"

    def _append_jsonl(self, path: Path, value: dict[str, Any]) -> None:
        self._ensure_dirs()
        line = json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def _atomic_json(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            directory_fd = os.open(path.parent, os.O_DIRECTORY)
        except (AttributeError, OSError):
            return
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)


def default_state_root(workspace: Path) -> Path:
    return workspace.resolve() / ".lightcoder"


def discover_runs(root: Path) -> list[str]:
    runs = root.resolve() / "runs"
    if not runs.is_dir():
        return []
    return sorted(
        path.name for path in runs.iterdir() if (path / "state.json").is_file()
    )
