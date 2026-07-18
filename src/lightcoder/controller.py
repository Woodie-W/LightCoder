from __future__ import annotations

import time
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .agent import ActionError, CodingAgent
from .context import ContextManager
from .model import ModelClient, ModelError
from .models import (
    Checkpoint,
    Evidence,
    Episode,
    RunState,
    StateValidationError,
    TaskProfile,
    WorkItem,
    new_id,
    utc_now,
)
from .skills import SkillRegistry
from .store import StateStore, default_state_root
from .tools import CommandSupervisor, ToolResult, WorkspaceTools


PROFILE_ACTIONS = """Return profile_task:
{"action":"profile_task","profile":{"execution_regime":"standard|long_horizon","primary_playbook":"repair|feature|project|transformation|optimization|generalist","estimated_horizon":"short|medium|multi_hour","validation_cost":"low|medium|high","supports_partial_progress":true,"requires_best_artifact":false,"rationale":"observable routing reasons"}}"""

PLAN_ACTIONS = """Return set_plan with a dependency DAG:
{"action":"set_plan","work_items":[{"id":"W1","title":"...","description":"concrete outcome","kind":"capability|experiment|integration|verification|hardening","playbook":"repair|feature|project|transformation|optimization|generalist","dependencies":[],"mandatory":true,"acceptance":["concrete observable"],"verification_commands":["exact shell command that establishes acceptance"]}]}
Every mandatory item requires at least one verification command."""

WORK_ACTIONS = """Return exactly one action:
{"action":"bash","command":"...","cwd":".","timeout_seconds":1800,"background":false,"rationale":"..."}
{"action":"read","path":"...","start_line":1,"max_lines":400,"rationale":"..."}
{"action":"write","path":"...","content":"...","rationale":"..."}
{"action":"poll","command_id":"cmd-..."}
{"action":"terminate","command_id":"cmd-..."}
{"action":"begin_verification","rationale":"implementation is ready for its acceptance oracle"}
{"action":"accept_work_item","evidence_ids":["ev-..."],"summary":"why the acceptance criteria pass"}
{"action":"reject_work_item","evidence_ids":["ev-..."],"failure_signature":"specific observed failure","next_strategy":"materially different next approach"}
{"action":"revise_plan","work_items":[...],"rationale":"new evidence requiring decomposition change"}
{"action":"checkpoint","restore_notes":"how to recover this known-good state","metric_name":"","metric_value":null,"artifact_paths":[]}
{"action":"rotate_context","reason":"...","next_action":"..."}
{"action":"wait","reason":"specific external event","resume_hint":"how to determine it is ready"}
Do not accept an item without current-revision observational evidence. Use begin_verification before acceptance."""

FINAL_VERIFY_ACTIONS = """Run final integration checks with bash/read, or return:
{"action":"final_verified","evidence_ids":["ev-..."],"summary":"why all mandatory outcomes and regressions pass","risks":["..."]}
You may also use rotate_context. final_verified requires successful current-revision command evidence."""

DELIVER_ACTIONS = """Return final_delivery only:
{"action":"final_delivery","summary":"concise delivered outcome","tests":["..."],"changed_files":["..."],"risks":["..."]}"""

TERMINAL_STATUSES = {"completed", "paused_limit", "failed_infra", "cancelled"}


class ControllerError(RuntimeError):
    pass


class RunController:
    def __init__(
        self,
        store: StateStore,
        model: ModelClient,
        *,
        skills_root: Path,
        protected_paths: list[Path] | None = None,
        context_window_tokens: int = 128_000,
    ) -> None:
        self.store = store
        state = store.load()
        self.tools = WorkspaceTools(
            Path(state.workspace), store, protected_paths=protected_paths
        )
        self.commands = CommandSupervisor(self.tools)
        self.skills = SkillRegistry(skills_root)
        if not self.skills.metadata():
            raise FileNotFoundError(f"no skills found under {skills_root}")
        self.context = ContextManager(
            store,
            self.tools,
            self.skills,
            context_window_tokens=context_window_tokens,
            handoffs_enabled="no-handoffs"
            not in state.runtime_config.get("ablations", []),
        )
        self.agent = CodingAgent(model, self.context, store)

    @classmethod
    def create(
        cls,
        objective: str,
        workspace: Path,
        model: ModelClient,
        *,
        state_root: Path | None = None,
        skills_root: Path,
        wall_time_seconds: float = 0.0,
        protected_paths: list[Path] | None = None,
        context_window_tokens: int = 128_000,
        ablations: list[str] | None = None,
    ) -> "RunController":
        workspace = workspace.resolve()
        if not workspace.is_dir():
            raise FileNotFoundError(f"workspace does not exist: {workspace}")
        state = RunState.create(
            objective,
            workspace,
            wall_time_seconds=wall_time_seconds,
            runtime_config={"ablations": sorted(set(ablations or []))},
        )
        store = StateStore.create(state_root or default_state_root(workspace), state)
        return cls(
            store,
            model,
            skills_root=skills_root,
            protected_paths=protected_paths,
            context_window_tokens=context_window_tokens,
        )

    def run(self, *, max_cycles: int | None = None) -> RunState:
        cycles = 0
        while True:
            state = self.step()
            if state.status in TERMINAL_STATUSES or state.status == "waiting":
                return state
            retry_delay = self._retry_delay(state)
            if retry_delay > 0:
                time.sleep(min(retry_delay, 60.0))
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                self.store.append_event("controller_yielded", {"cycles": cycles})
                return state

    def step(self) -> RunState:
        with self.store.lease():
            return self._step_locked()

    def _step_locked(self) -> RunState:
        state = self.store.load()
        if state.status in TERMINAL_STATUSES:
            return state
        if self._deadline_transition(state):
            return self._commit(state)
        if self._retry_delay(state) > 0:
            return state
        if state.status in {"new", "waiting"}:
            state.status = "running"
            if not state.episodes:
                state.episodes.append(
                    Episode(
                        0,
                        utc_now(),
                        state.active_work_item_id,
                        transcript_start=self.store.transcript_line_count(),
                    )
                )
            self.store.append_event(
                "run_started" if state.revision == 0 else "run_resumed"
            )

        if state.phase == "recon":
            return self._model_step(state, PROFILE_ACTIONS, "profile-task")
        if state.phase == "plan":
            return self._model_step(
                state, PLAN_ACTIONS, "plan-work", self._playbook(state)
            )
        if state.phase in {"standard_work", "long_horizon_work"}:
            return self._work_step(state)
        if state.phase == "final_verify":
            return self._model_step(
                state, FINAL_VERIFY_ACTIONS, "finalize-delivery", self._playbook(state)
            )
        if state.phase == "deliver":
            return self._model_step(state, DELIVER_ACTIONS, "finalize-delivery")
        raise ControllerError(f"cannot step phase: {state.phase}")

    def resume(self, note: str = "") -> RunState:
        with self.store.lease():
            state = self.store.load()
            if state.status != "waiting":
                raise ControllerError(f"run is not waiting: {state.status}")
            state.status = "running"
            if note:
                self.store.append_event("external_input", {"note": note})
                self.store.append_transcript("user", note, kind="external_input")
            return self._commit(state)

    def cancel(self, reason: str = "cancelled by operator") -> RunState:
        with self.store.lease():
            state = self.store.load()
            if state.status in TERMINAL_STATUSES:
                return state
            for command in self.commands.recover():
                if command.get("status") == "running":
                    self.commands.terminate(str(command["id"]))
            state.status = "cancelled"
            state.final = {"reason": reason, "cancelled_at": utc_now()}
            self.store.append_event("run_cancelled", state.final)
            return self._commit(state)

    def _work_step(self, state: RunState) -> RunState:
        active = state.work_item(state.active_work_item_id)
        if active is None:
            active = state.next_ready_item()
            if active is None:
                if state.mandatory_complete():
                    state.phase = "final_verify"
                    state.final["verification_started_at"] = utc_now()
                    self.store.append_event("phase_changed", {"phase": state.phase})
                    return self._commit(state)
                raise ControllerError(
                    "work graph has no ready item but mandatory work remains"
                )
            active.status = "running"
            active.attempt_count += 1
            state.active_work_item_id = active.id
            self.store.append_event("work_item_selected", {"work_item_id": active.id})
            return self._commit(state)

        if active.status == "verifying":
            skill = "verify-work-item"
        elif active.failure_signatures:
            skill = "diagnose-and-replan"
        elif state.phase == "long_horizon_work":
            skill = "long-horizon"
        else:
            skill = "execute-work-item"
        return self._model_step(state, WORK_ACTIONS, skill, active.playbook)

    def _model_step(
        self,
        state: RunState,
        contract: str,
        core_skill: str,
        playbook: str | None = None,
    ) -> RunState:
        if state.episodes and state.episodes[-1].token_estimate >= int(
            self.context.context_window_tokens * self.context.rotate_fraction
        ):
            self.context.rotate(
                state, reason="context_threshold", next_action="continue current phase"
            )
            return self._commit(state)
        try:
            state.counters["model_calls"] = state.counters.get("model_calls", 0) + 1
            decision = self.agent.decide(
                state, contract, core_skill=core_skill, playbook=playbook
            )
            state.counters["consecutive_model_errors"] = 0
            state.retry_at = ""
            if state.episodes:
                state.episodes[-1].token_estimate = decision.prompt_tokens_estimate
            self._apply_action(state, decision.action)
        except ModelError as error:
            failures = state.counters.get("consecutive_model_errors", 0) + 1
            state.counters["consecutive_model_errors"] = failures
            delay = min(300.0, float(2 ** min(failures, 8)))
            state.retry_at = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()
            self.store.append_event(
                "model_retry_scheduled",
                {
                    "error": str(error),
                    "delay_seconds": delay,
                    "retry_at": state.retry_at,
                },
            )
            if "context" in str(error).lower():
                self.context.rotate(
                    state,
                    reason="provider_context_exhaustion",
                    next_action="retry current phase",
                )
        except (ActionError, StateValidationError, ValueError) as error:
            state.counters["invalid_actions"] = (
                state.counters.get("invalid_actions", 0) + 1
            )
            self.store.append_event("agent_action_rejected", {"error": str(error)})
            self.store.append_transcript(
                "user",
                f"Controller rejected the previous action: {error}",
                kind="controller_feedback",
            )
        return self._commit(state)

    def _apply_action(self, state: RunState, action: dict[str, Any]) -> None:
        name = str(action["action"])
        self.store.append_event(
            "agent_action", {"action": name, "rationale": action.get("rationale", "")}
        )
        if name == "profile_task" and state.phase == "recon":
            state.profile = TaskProfile.from_dict(self._mapping(action, "profile"))
            if "standard-only" in state.runtime_config.get("ablations", []):
                state.profile.execution_regime = "standard"
                state.profile.rationale += " [ablation: standard-only]"
            state.phase = "plan"
            return
        if name == "set_plan" and state.phase == "plan":
            items = self._parse_plan(action.get("work_items"))
            state.work_items = items
            state.phase = (
                "long_horizon_work"
                if state.profile and state.profile.execution_regime == "long_horizon"
                else "standard_work"
            )
            return
        if name in {"bash", "read", "write", "poll", "terminate"}:
            if state.phase not in {
                "standard_work",
                "long_horizon_work",
                "final_verify",
            }:
                raise ValueError(f"tool action not allowed in {state.phase}")
            self._execute_tool(state, action)
            return
        if name == "begin_verification" and state.phase in {
            "standard_work",
            "long_horizon_work",
        }:
            item = self._active(state)
            item.status = "verifying"
            return
        if name == "accept_work_item" and state.phase in {
            "standard_work",
            "long_horizon_work",
        }:
            item = self._active(state)
            if item.status != "verifying":
                raise ValueError("begin_verification is required before acceptance")
            ids = self._evidence_ids(action)
            self._validate_evidence(ids, require_successful_command=False)
            self._validate_work_item_commands(item)
            item.status = "accepted"
            item.evidence_ids.extend(x for x in ids if x not in item.evidence_ids)
            state.active_work_item_id = None
            self.store.append_event(
                "work_item_accepted", {"work_item_id": item.id, "evidence_ids": ids}
            )
            if (
                state.phase == "long_horizon_work"
                and "no-checkpoints" not in state.runtime_config.get("ablations", [])
            ):
                self._checkpoint(
                    state,
                    {"restore_notes": str(action.get("summary", "accepted milestone"))},
                )
            self.context.rotate(
                state,
                reason="milestone_finished",
                next_action="select next ready work item",
            )
            return
        if name == "reject_work_item" and state.phase in {
            "standard_work",
            "long_horizon_work",
        }:
            item = self._active(state)
            signature = str(action.get("failure_signature", "")).strip()
            strategy = str(action.get("next_strategy", "")).strip()
            if not signature or not strategy:
                raise ValueError(
                    "rejection requires a failure signature and materially different next strategy"
                )
            ids = self._evidence_ids(action)
            if ids:
                self._validate_evidence(ids, require_successful_command=False)
                item.evidence_ids.extend(x for x in ids if x not in item.evidence_ids)
            item.failure_signatures.append(f"{signature} | next: {strategy}")
            item.status = "rejected"
            state.active_work_item_id = None
            self.store.append_event(
                "work_item_rejected",
                {"work_item_id": item.id, "next_strategy": strategy},
            )
            return
        if name == "revise_plan" and state.phase in {
            "standard_work",
            "long_horizon_work",
        }:
            self._revise_plan(state, self._parse_plan(action.get("work_items")))
            return
        if name == "checkpoint" and state.phase in {
            "standard_work",
            "long_horizon_work",
        }:
            self._checkpoint(state, action)
            return
        if name == "rotate_context" and state.phase != "done":
            self.context.rotate(
                state,
                reason=str(action.get("reason", "agent_requested")),
                next_action=str(action.get("next_action", "")),
            )
            return
        if name == "wait" and state.phase in {"standard_work", "long_horizon_work"}:
            reason = str(action.get("reason", "")).strip()
            if not reason:
                raise ValueError("wait requires a specific external event")
            state.status = "waiting"
            self.store.append_event(
                "run_waiting",
                {"reason": reason, "resume_hint": action.get("resume_hint", "")},
            )
            return
        if name == "final_verified" and state.phase == "final_verify":
            hardening = bool(state.final.get("deadline_hardening"))
            if not state.mandatory_complete() and not hardening:
                raise ValueError("mandatory work is incomplete")
            ids = self._evidence_ids(action)
            self._validate_evidence(
                ids,
                require_successful_command=True,
                created_after=str(state.final.get("verification_started_at", "")),
            )
            state.final["verification"] = {
                "evidence_ids": ids,
                "summary": str(action.get("summary", "")),
                "risks": list(action.get("risks", [])),
                "workspace_revision": self.tools.workspace_revision(),
                "partial": not state.mandatory_complete(),
            }
            state.phase = "deliver"
            return
        if name == "final_delivery" and state.phase == "deliver":
            if "verification" not in state.final:
                raise ValueError("final verification is missing")
            state.final["delivery"] = {
                "summary": str(action.get("summary", "")),
                "tests": list(action.get("tests", [])),
                "changed_files": list(action.get("changed_files", [])),
                "risks": list(action.get("risks", [])),
                "delivered_at": utc_now(),
            }
            state.phase = "done"
            state.status = (
                "paused_limit" if state.final.get("deadline_hardening") else "completed"
            )
            return
        raise ValueError(f"action {name!r} is not allowed in phase {state.phase}")

    def _execute_tool(self, state: RunState, action: dict[str, Any]) -> None:
        name = str(action["action"])
        if name == "bash":
            result = self.commands.run(
                str(action.get("command", "")),
                cwd=str(action.get("cwd", ".")),
                timeout_seconds=float(action.get("timeout_seconds", 1_800)),
                background=bool(action.get("background", False)),
            )
        elif name == "read":
            result = self.tools.read(
                str(action.get("path", "")),
                start_line=int(action.get("start_line", 1)),
                max_lines=int(action.get("max_lines", 400)),
            )
        elif name == "write":
            result = self.tools.write(
                str(action.get("path", "")), str(action.get("content", ""))
            )
        elif name == "poll":
            result = self.commands.poll(str(action.get("command_id", "")))
        else:
            result = self.commands.terminate(str(action.get("command_id", "")))
        evidence = self._tool_evidence(state, result, action)
        self.store.record_evidence(evidence)
        state.evidence_ids.append(evidence.id)
        active = state.work_item(state.active_work_item_id)
        if active:
            active.evidence_ids.append(evidence.id)
        self.store.append_event(
            "tool_result", {"evidence_id": evidence.id, **result.to_dict()}
        )

    def _tool_evidence(
        self, state: RunState, result: ToolResult, action: dict[str, Any]
    ) -> Evidence:
        if result.tool in {"bash", "poll", "terminate"}:
            kind = "command"
        elif result.tool == "read":
            kind = "observation"
        else:
            kind = "mutation"
        return Evidence(
            id=new_id("ev"),
            kind=kind,
            created_at=utc_now(),
            work_item_id=state.active_work_item_id,
            workspace_revision=self.tools.workspace_revision(),
            summary=result.output[:1_000],
            command=str(action.get("command", "")),
            cwd=str(action.get("cwd", ".")),
            exit_code=result.exit_code,
            duration_seconds=result.duration_seconds,
            raw_log=result.raw_log,
            data={"success": result.success, **result.data},
        )

    def _validate_evidence(
        self,
        ids: list[str],
        *,
        require_successful_command: bool,
        created_after: str = "",
    ) -> None:
        if not ids:
            raise ValueError("at least one evidence id is required")
        evidence = self.store.evidence_by_id(ids)
        if len(evidence) != len(set(ids)):
            raise ValueError("one or more evidence ids do not exist")
        revision = self.tools.workspace_revision()
        if any(item.workspace_revision != revision for item in evidence):
            raise ValueError("evidence does not match the current workspace revision")
        if not any(
            item.data.get("success") is True
            and (
                item.kind == "observation"
                or (item.kind == "command" and item.exit_code == 0)
            )
            for item in evidence
        ):
            raise ValueError(
                "at least one successful command or read observation is required"
            )
        if require_successful_command and not any(
            item.kind == "command" and item.exit_code == 0 for item in evidence
        ):
            raise ValueError("successful current-revision command evidence is required")
        if created_after:
            threshold = datetime.fromisoformat(created_after)
            if any(
                datetime.fromisoformat(item.created_at) < threshold for item in evidence
            ):
                raise ValueError(
                    "final verification evidence predates the final verification phase"
                )

    def _validate_work_item_commands(self, item: WorkItem) -> None:
        revision = self.tools.workspace_revision()
        successful = {
            observation.command
            for observation in self.store.evidence_by_id(item.evidence_ids)
            if observation.kind == "command"
            and observation.exit_code == 0
            and observation.workspace_revision == revision
        }
        missing = [
            command
            for command in item.verification_commands
            if command not in successful
        ]
        if missing:
            raise ValueError(
                f"work item verification commands lack passing evidence: {missing}"
            )

    def _checkpoint(self, state: RunState, action: dict[str, Any]) -> None:
        checkpoint_id = new_id("checkpoint")
        changed_files = self.tools.changed_files()
        artifact_paths = [str(path) for path in action.get("artifact_paths", [])]
        snapshot_path = self.tools.create_checkpoint_snapshot(
            checkpoint_id, changed_files + artifact_paths
        )
        checkpoint = Checkpoint(
            id=checkpoint_id,
            created_at=utc_now(),
            workspace_revision=self.tools.workspace_revision(),
            changed_files=changed_files,
            accepted_work_items=[
                item.id for item in state.work_items if item.status == "accepted"
            ],
            evidence_ids=state.evidence_ids[-50:],
            restore_notes=str(action.get("restore_notes", "")),
            base_revision=self.tools.git_head(),
            snapshot_path=snapshot_path,
            metric_name=str(action.get("metric_name", "")),
            metric_value=float(action["metric_value"])
            if action.get("metric_value") is not None
            else None,
            artifact_paths=artifact_paths,
        )
        self.store.write_checkpoint(checkpoint)
        state.best_checkpoint_id = checkpoint.id
        self.store.append_event("checkpoint_promoted", asdict(checkpoint))

    def _parse_plan(self, value: Any) -> list[WorkItem]:
        if not isinstance(value, list) or not value:
            raise ValueError("plan requires at least one work item")
        items = [WorkItem.from_dict(item) for item in value if isinstance(item, dict)]
        if len(items) != len(value):
            raise ValueError("each work item must be an object")
        if any(item.mandatory and not item.acceptance for item in items):
            raise ValueError("every mandatory work item requires acceptance criteria")
        if any(item.mandatory and not item.verification_commands for item in items):
            raise ValueError("every mandatory work item requires verification commands")
        probe = RunState.create("plan validation", Path.cwd())
        probe.work_items = items
        probe.validate()
        return items

    def _revise_plan(self, state: RunState, proposed: list[WorkItem]) -> None:
        existing = {item.id: item for item in state.work_items}
        for item in proposed:
            previous = existing.get(item.id)
            if previous:
                item.status = previous.status
                item.evidence_ids = previous.evidence_ids
                item.failure_signatures = previous.failure_signatures
                item.attempt_count = previous.attempt_count
        accepted_ids = {
            item.id for item in state.work_items if item.status == "accepted"
        }
        if not accepted_ids <= {item.id for item in proposed}:
            raise ValueError("revised plan cannot remove accepted work items")
        state.work_items = proposed
        if state.active_work_item_id not in {item.id for item in proposed}:
            state.active_work_item_id = None
        state.validate()

    def _deadline_transition(self, state: RunState) -> bool:
        limit = state.deadline.wall_time_seconds
        if limit <= 0:
            return False
        started = datetime.fromisoformat(state.deadline.started_at)
        elapsed = max(0.0, time.time() - started.timestamp())
        state.counters["elapsed_seconds"] = int(elapsed)
        if elapsed >= limit:
            state.status = "paused_limit"
            state.final["limit"] = {"elapsed_seconds": elapsed, "reached_at": utc_now()}
            self.store.append_event("hard_deadline_reached", state.final["limit"])
            return True
        harden_at = limit * (1.0 - state.deadline.harden_fraction)
        if elapsed >= harden_at and state.phase in {
            "standard_work",
            "long_horizon_work",
        }:
            state.phase = "final_verify"
            state.active_work_item_id = None
            state.final["verification_started_at"] = utc_now()
            state.final["deadline_hardening"] = {
                "started_at": utc_now(),
                "elapsed_seconds": elapsed,
                "incomplete_work_items": [
                    item.id
                    for item in state.work_items
                    if item.mandatory and item.status != "accepted"
                ],
            }
            self.store.append_event(
                "deadline_hardening_started", {"elapsed_seconds": elapsed}
            )
            return True
        return False

    def _commit(self, state: RunState) -> RunState:
        return self.store.commit(state, expected_revision=state.revision)

    @staticmethod
    def _retry_delay(state: RunState) -> float:
        if not state.retry_at:
            return 0.0
        try:
            return max(
                0.0, datetime.fromisoformat(state.retry_at).timestamp() - time.time()
            )
        except ValueError:
            return 0.0

    def _active(self, state: RunState) -> WorkItem:
        item = state.work_item(state.active_work_item_id)
        if item is None:
            raise ValueError("there is no active work item")
        return item

    @staticmethod
    def _mapping(action: dict[str, Any], key: str) -> dict[str, Any]:
        value = action.get(key)
        if not isinstance(value, dict):
            raise ValueError(f"{key} must be an object")
        return value

    @staticmethod
    def _evidence_ids(action: dict[str, Any]) -> list[str]:
        value = action.get("evidence_ids", [])
        if not isinstance(value, list):
            raise ValueError("evidence_ids must be a list")
        return [str(item) for item in value]

    @staticmethod
    def _playbook(state: RunState) -> str | None:
        return state.profile.primary_playbook if state.profile else None
