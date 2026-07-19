from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal


RunStatus = Literal[
    "new",
    "running",
    "waiting",
    "paused_limit",
    "completed",
    "failed_infra",
    "cancelled",
]
Phase = Literal[
    "recon",
    "plan",
    "standard_work",
    "long_horizon_work",
    "final_verify",
    "deliver",
    "done",
]
ExecutionRegime = Literal["standard", "long_horizon"]
Playbook = Literal[
    "repair", "feature", "project", "transformation", "optimization", "generalist"
]
WorkStatus = Literal[
    "pending", "ready", "running", "verifying", "accepted", "rejected", "blocked"
]

VALID_PHASES = {
    "recon",
    "plan",
    "standard_work",
    "long_horizon_work",
    "final_verify",
    "deliver",
    "done",
}
VALID_REGIMES = {"standard", "long_horizon"}
VALID_PLAYBOOKS = {
    "repair",
    "feature",
    "project",
    "transformation",
    "optimization",
    "generalist",
}
VALID_HORIZONS = {"short", "medium", "multi_hour"}
VALID_VALIDATION_COSTS = {"low", "medium", "high"}
VALID_WORK_KINDS = {
    "capability",
    "experiment",
    "integration",
    "verification",
    "hardening",
}
VALID_WORK_STATUSES = {
    "pending",
    "ready",
    "running",
    "verifying",
    "accepted",
    "rejected",
    "blocked",
}
VALID_RUN_STATUSES = {
    "new",
    "running",
    "waiting",
    "paused_limit",
    "completed",
    "failed_infra",
    "cancelled",
}

PLAYBOOK_ALIASES = {
    # Models occasionally use work-item kinds where a playbook is expected.
    "capability": "generalist",
    "experiment": "optimization",
    "hardening": "generalist",
    "integration": "project",
    "test": "generalist",
    "testing": "generalist",
    "verification": "generalist",
}


def normalize_playbook(value: Any) -> str:
    raw = str(value or "generalist")
    return PLAYBOOK_ALIASES.get(raw, raw)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class StateValidationError(ValueError):
    pass


@dataclass(slots=True)
class TaskProfile:
    execution_regime: ExecutionRegime = "standard"
    primary_playbook: Playbook = "generalist"
    estimated_horizon: str = "short"
    validation_cost: str = "low"
    supports_partial_progress: bool = True
    requires_best_artifact: bool = False
    rationale: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TaskProfile":
        profile = cls(
            execution_regime=str(value.get("execution_regime", "standard")),  # type: ignore[arg-type]
            primary_playbook=normalize_playbook(value.get("primary_playbook")),  # type: ignore[arg-type]
            estimated_horizon=str(value.get("estimated_horizon", "short")),
            validation_cost=str(value.get("validation_cost", "low")),
            supports_partial_progress=bool(
                value.get("supports_partial_progress", True)
            ),
            requires_best_artifact=bool(value.get("requires_best_artifact", False)),
            rationale=str(value.get("rationale", "")),
        )
        profile.validate()
        return profile

    def validate(self) -> None:
        if self.execution_regime not in VALID_REGIMES:
            raise StateValidationError(
                f"invalid execution regime: {self.execution_regime}"
            )
        if self.primary_playbook not in VALID_PLAYBOOKS:
            raise StateValidationError(f"invalid playbook: {self.primary_playbook}")
        if self.estimated_horizon not in VALID_HORIZONS:
            raise StateValidationError(
                f"invalid estimated horizon: {self.estimated_horizon}"
            )
        if self.validation_cost not in VALID_VALIDATION_COSTS:
            raise StateValidationError(
                f"invalid validation cost: {self.validation_cost}"
            )


@dataclass(slots=True)
class WorkItem:
    id: str
    title: str
    description: str
    kind: str = "capability"
    playbook: Playbook = "generalist"
    status: WorkStatus = "pending"
    dependencies: list[str] = field(default_factory=list)
    mandatory: bool = True
    acceptance: list[str] = field(default_factory=list)
    verification_commands: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    failure_signatures: list[str] = field(default_factory=list)
    attempt_count: int = 0

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "WorkItem":
        raw_kind = str(value.get("kind", "capability"))
        kind_aliases = {
            "generalist": "capability",
            "feature": "capability",
            "optimization": "experiment",
            "project": "integration",
            "repair": "capability",
            "test": "verification",
            "testing": "verification",
            "transformation": "capability",
        }
        item = cls(
            id=str(value.get("id") or new_id("work")),
            title=str(value.get("title", "")).strip(),
            description=str(value.get("description", "")).strip(),
            kind=kind_aliases.get(raw_kind, raw_kind),
            playbook=normalize_playbook(value.get("playbook")),  # type: ignore[arg-type]
            status=str(value.get("status", "pending")),  # type: ignore[arg-type]
            dependencies=[str(x) for x in value.get("dependencies", [])],
            mandatory=bool(value.get("mandatory", True)),
            acceptance=[str(x) for x in value.get("acceptance", []) if str(x).strip()],
            verification_commands=[
                str(x) for x in value.get("verification_commands", []) if str(x).strip()
            ],
            evidence_ids=[str(x) for x in value.get("evidence_ids", [])],
            failure_signatures=[str(x) for x in value.get("failure_signatures", [])],
            attempt_count=max(0, int(value.get("attempt_count", 0))),
        )
        item.validate()
        return item

    def validate(self) -> None:
        if not self.id or not self.title or not self.description:
            raise StateValidationError("work items require id, title, and description")
        if self.kind not in VALID_WORK_KINDS:
            raise StateValidationError(f"invalid work kind: {self.kind}")
        if self.playbook not in VALID_PLAYBOOKS:
            raise StateValidationError(f"invalid work playbook: {self.playbook}")
        if self.status not in VALID_WORK_STATUSES:
            raise StateValidationError(f"invalid work status: {self.status}")


@dataclass(slots=True)
class Evidence:
    id: str
    kind: str
    created_at: str
    work_item_id: str | None
    workspace_revision: str
    summary: str
    command: str = ""
    cwd: str = "."
    exit_code: int | None = None
    duration_seconds: float = 0.0
    raw_log: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Episode:
    generation: int
    started_at: str
    active_work_item_id: str | None
    token_estimate: int = 0
    ended_at: str = ""
    end_reason: str = ""
    handoff_path: str = ""
    transcript_start: int = 0
    transcript_end: int = 0


@dataclass(slots=True)
class Checkpoint:
    id: str
    created_at: str
    workspace_revision: str
    changed_files: list[str]
    accepted_work_items: list[str]
    evidence_ids: list[str]
    restore_notes: str
    base_revision: str = ""
    snapshot_path: str = ""
    metric_name: str = ""
    metric_value: float | None = None
    metric_direction: str = ""
    validation_evidence_ids: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Deadline:
    started_at: str = field(default_factory=utc_now)
    wall_time_seconds: float = 0.0
    # Retained for state-file compatibility. The controller no longer takes a
    # fixed fraction of task time away from implementation for forced hardening.
    harden_fraction: float = 0.0


@dataclass(slots=True)
class RunState:
    schema_version: int
    revision: int
    run_id: str
    objective: str
    workspace: str
    status: RunStatus = "new"
    phase: Phase = "recon"
    profile: TaskProfile | None = None
    work_items: list[WorkItem] = field(default_factory=list)
    active_work_item_id: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    episodes: list[Episode] = field(default_factory=list)
    best_checkpoint_id: str | None = None
    deadline: Deadline = field(default_factory=Deadline)
    runtime_config: dict[str, Any] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    retry_at: str = ""
    final: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        objective: str,
        workspace: Path,
        *,
        run_id: str | None = None,
        wall_time_seconds: float = 0.0,
        runtime_config: dict[str, Any] | None = None,
    ) -> "RunState":
        objective = objective.strip()
        if not objective:
            raise StateValidationError("objective must not be empty")
        return cls(
            schema_version=1,
            revision=0,
            run_id=run_id or new_id("run"),
            objective=objective,
            workspace=str(workspace.resolve()),
            deadline=Deadline(wall_time_seconds=max(0.0, wall_time_seconds)),
            runtime_config=dict(runtime_config or {}),
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RunState":
        profile_value = value.get("profile")
        state = cls(
            schema_version=int(value.get("schema_version", 1)),
            revision=int(value.get("revision", 0)),
            run_id=str(value["run_id"]),
            objective=str(value["objective"]),
            workspace=str(value["workspace"]),
            status=str(value.get("status", "new")),  # type: ignore[arg-type]
            phase=str(value.get("phase", "recon")),  # type: ignore[arg-type]
            profile=TaskProfile.from_dict(profile_value)
            if isinstance(profile_value, dict)
            else None,
            work_items=[WorkItem.from_dict(x) for x in value.get("work_items", [])],
            active_work_item_id=value.get("active_work_item_id"),
            evidence_ids=[str(x) for x in value.get("evidence_ids", [])],
            episodes=[Episode(**x) for x in value.get("episodes", [])],
            best_checkpoint_id=value.get("best_checkpoint_id"),
            deadline=Deadline(**value.get("deadline", {})),
            runtime_config=dict(value.get("runtime_config", {})),
            counters={str(k): int(v) for k, v in value.get("counters", {}).items()},
            retry_at=str(value.get("retry_at", "")),
            final=dict(value.get("final", {})),
            created_at=str(value.get("created_at", utc_now())),
            updated_at=str(value.get("updated_at", utc_now())),
        )
        state.validate()
        return state

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        if self.schema_version != 1:
            raise StateValidationError(
                f"unsupported state schema: {self.schema_version}"
            )
        if self.status not in VALID_RUN_STATUSES:
            raise StateValidationError(f"invalid run status: {self.status}")
        if self.phase not in VALID_PHASES:
            raise StateValidationError(f"invalid phase: {self.phase}")
        ids = [item.id for item in self.work_items]
        if len(ids) != len(set(ids)):
            raise StateValidationError("work item ids must be unique")
        known = set(ids)
        for item in self.work_items:
            item.validate()
            missing = set(item.dependencies) - known
            if missing:
                raise StateValidationError(
                    f"work item {item.id} has unknown dependencies: {sorted(missing)}"
                )
        self._validate_acyclic()
        if (
            self.active_work_item_id is not None
            and self.active_work_item_id not in known
        ):
            raise StateValidationError("active work item does not exist")

    def _validate_acyclic(self) -> None:
        graph = {item.id: item.dependencies for item in self.work_items}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise StateValidationError(f"work graph contains a cycle at {node}")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)

    def work_item(self, work_item_id: str | None) -> WorkItem | None:
        return next((item for item in self.work_items if item.id == work_item_id), None)

    def refresh_ready_items(self) -> None:
        accepted = {item.id for item in self.work_items if item.status == "accepted"}
        for item in self.work_items:
            if (
                item.status in {"pending", "rejected"}
                and set(item.dependencies) <= accepted
            ):
                item.status = "ready"

    def next_ready_item(self) -> WorkItem | None:
        self.refresh_ready_items()
        return next((item for item in self.work_items if item.status == "ready"), None)

    def mandatory_complete(self) -> bool:
        return bool(self.work_items) and all(
            not item.mandatory or item.status == "accepted" for item in self.work_items
        )

    def stable_digest(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False).encode(
            "utf-8"
        )
        return hashlib.sha256(payload).hexdigest()
