from __future__ import annotations

import json
import shlex
import tarfile
import time
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .agent import ActionError, CodingAgent
from .context import ContextManager
from .model import ModelClient, ModelError, PermanentModelError
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


PROFILE_ACTIONS = """Return profile_task: call the profile_task tool with an observable task classification. Use long_horizon only when the task has a multi-hour search, compilation, or external wait."""

PLAN_ACTIONS = """Return set_plan: call the set_plan tool with a small dependency DAG. Every mandatory item needs an executable verification command; prefer vertical, scoreable milestones over file-by-file decomposition."""

WORK_ACTIONS = """Use the provided tools to complete the active work item. Use run only for bounded foreground commands (default 300 seconds, maximum 1200); use start, poll, logs, and stop for services and long jobs. Read before uncertain edits and run a focused check after mutations. Once the acceptance criteria are satisfied, call begin_verification, then accept_work_item with current evidence."""

LONG_HORIZON_ACTIONS = """Use the provided tools to make measured progress toward a scoreable artifact. Keep decomposition advisory, preserve the best valid artifact, and use checkpoints after verified improvements. Long work must use start/poll/logs/stop; run is only for bounded foreground checks. Call begin_final_verification only after relevant checks succeed."""

FINAL_VERIFY_ACTIONS = """Use run, read, and the provided tools for final integration checks. Call final_verified only with successful current-revision command evidence."""

DELIVER_ACTIONS = """Call final_delivery with the verified outcome, tests, changed files, and remaining risks."""

TERMINAL_STATUSES = {"completed", "paused_limit", "failed_infra", "cancelled"}


def _tool_schema(
    name: str,
    description: str,
    properties: dict[str, Any] | None = None,
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }


def native_tool_schemas(phase: str) -> list[dict[str, Any]]:
    """Native Chat Completions tools exposed for one controller phase.

    The tool names deliberately match the durable controller actions.  This keeps
    tool results and old checkpoints inspectable while moving the model boundary
    from text-parsed JSON to the OpenAI/DeepSeek function-calling protocol.
    """
    text = {"type": "string"}
    integer = {"type": "integer"}
    number = {"type": "number"}
    boolean = {"type": "boolean"}
    object_value = {"type": "object", "additionalProperties": True}
    array = {"type": "array", "items": object_value}
    common_tools = [
        _tool_schema(
            "run",
            "Run a bounded foreground shell command. Default 300 seconds; maximum 1200 seconds. Never use this for a service, watch mode, or long experiment.",
            {"command": text, "cwd": text, "timeout_seconds": number, "rationale": text},
            ["command"],
        ),
        _tool_schema(
            "start",
            "Start a managed long-running job or service. It is independently stopped at the task's remaining wall-time (or an earlier timeout_seconds); inspect it with poll or logs and terminate it with stop.",
            {"command": text, "cwd": text, "timeout_seconds": number, "rationale": text},
            ["command"],
        ),
        _tool_schema(
            "poll",
            "Return current managed-job status without reading its full output.",
            {"command_id": text},
            ["command_id"],
        ),
        _tool_schema(
            "logs",
            "Read a bounded range of output from a managed job.",
            {"command_id": text, "start_line": integer, "max_lines": integer, "rationale": text},
            ["command_id"],
        ),
        _tool_schema(
            "stop",
            "Terminate a managed job and its process group.",
            {"command_id": text},
            ["command_id"],
        ),
        _tool_schema(
            "read",
            "Read a bounded line range from a workspace file.",
            {"path": text, "start_line": integer, "max_lines": integer, "rationale": text},
            ["path"],
        ),
        _tool_schema(
            "write",
            "Atomically create or replace a workspace file.",
            {"path": text, "content": text, "rationale": text},
            ["path", "content"],
        ),
        _tool_schema(
            "edit",
            "Replace exact text in a workspace file. Use read first when the target text is uncertain.",
            {"path": text, "old": text, "new": text, "replace_all": boolean, "rationale": text},
            ["path", "old", "new"],
        ),
        _tool_schema(
            "rotate_context",
            "Create a compact durable handoff before a new strategy or when history is large.",
            {"reason": text, "next_action": text},
            ["reason"],
        ),
    ]
    if phase == "recon":
        return [
            _tool_schema(
                "profile_task",
                "Classify task horizon and playbook so the controller can route it.",
                {"profile": object_value},
                ["profile"],
            )
        ]
    if phase == "plan":
        return [
            _tool_schema(
                "set_plan",
                "Set a dependency-aware plan for a standard task.",
                {"work_items": array},
                ["work_items"],
            )
        ]
    if phase == "deliver":
        return [
            _tool_schema(
                "final_delivery",
                "Record the verified delivery and finish the task.",
                {"summary": text, "tests": {"type": "array", "items": text}, "changed_files": {"type": "array", "items": text}, "risks": {"type": "array", "items": text}},
                ["summary", "tests", "changed_files", "risks"],
            )
        ]
    if phase == "final_verify":
        return common_tools + [
            _tool_schema(
                "final_verified",
                "Mark final verification complete using current successful evidence.",
                {"evidence_ids": {"type": "array", "items": text}, "summary": text, "risks": {"type": "array", "items": text}},
                ["evidence_ids", "summary"],
            )
        ]
    if phase == "standard_work":
        return common_tools + [
            _tool_schema("begin_verification", "Ask the controller to run the active item's acceptance commands.", {"rationale": text}),
            _tool_schema("accept_work_item", "Accept the verified active work item with evidence.", {"evidence_ids": {"type": "array", "items": text}, "summary": text}, ["evidence_ids", "summary"]),
            _tool_schema("reject_work_item", "Record a failed approach and a materially different next strategy.", {"evidence_ids": {"type": "array", "items": text}, "failure_signature": text, "next_strategy": text}, ["failure_signature", "next_strategy"]),
            _tool_schema("revise_plan", "Replace remaining plan work items after new evidence.", {"work_items": array, "rationale": text}, ["work_items"]),
            _tool_schema("checkpoint", "Save validated progress and optional scalar metric.", {"restore_notes": text, "metric_name": text, "metric_value": number, "metric_direction": text, "evidence_ids": {"type": "array", "items": text}, "artifact_paths": {"type": "array", "items": text}}, ["restore_notes", "evidence_ids"]),
        ]
    if phase == "long_horizon_work":
        return common_tools + [
            _tool_schema("checkpoint", "Save validated progress and optional scalar metric.", {"restore_notes": text, "metric_name": text, "metric_value": number, "metric_direction": text, "evidence_ids": {"type": "array", "items": text}, "artifact_paths": {"type": "array", "items": text}}, ["restore_notes", "evidence_ids"]),
            _tool_schema("begin_final_verification", "Move to final verification after all deliverables are ready.", {"rationale": text}),
        ]
    return common_tools


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
        persisted_elapsed = float(state.counters.get("elapsed_seconds", 0))
        try:
            # Monotonic clocks do not survive a process restart. Count only a
            # non-negative wall-clock gap since the last persisted update, then
            # use monotonic time for the lifetime of this controller process.
            # A backward WSL clock correction therefore cannot erase elapsed
            # runtime or delay the internal deadline.
            persisted_elapsed += max(
                0.0,
                time.time() - datetime.fromisoformat(state.updated_at).timestamp(),
            )
        except ValueError:
            pass
        self._deadline_elapsed_base = persisted_elapsed
        self._deadline_monotonic_started = time.monotonic()

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
        managed_evaluation: bool = False,
    ) -> "RunController":
        workspace = workspace.resolve()
        if not workspace.is_dir():
            raise FileNotFoundError(f"workspace does not exist: {workspace}")
        root = (state_root or default_state_root(workspace)).expanduser().resolve()
        state = RunState.create(
            objective,
            workspace,
            wall_time_seconds=wall_time_seconds,
            runtime_config={"ablations": sorted(set(ablations or []))},
        )
        if managed_evaluation:
            state.runtime_config["managed_evaluation"] = {
                "enabled": True,
                "store": str(root / "runs" / state.run_id / "evaluations"),
                "local_check_hint_shown": False,
            }
        store = StateStore.create(root, state)
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
        if state.phase == "standard_work":
            return self._work_step(state)
        if state.phase == "long_horizon_work":
            return self._model_step(
                state,
                LONG_HORIZON_ACTIONS,
                "long-horizon",
                self._playbook(state),
            )
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
            unobserved = self._unobserved_verification_commands(active)
            if unobserved:
                for command in unobserved:
                    self._execute_tool(
                        state,
                        {
                            "action": "bash",
                            "command": command,
                            "cwd": ".",
                            "background": False,
                            "rationale": "controller-managed acceptance verification",
                        },
                    )
                self.store.append_event(
                    "verification_commands_executed",
                    {"work_item_id": active.id, "commands": unobserved},
                )
                return self._commit(state)
            skill = "verify-work-item"
        elif active.failure_signatures:
            skill = "diagnose-and-replan"
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
        if (
            state.episodes
            and state.episodes[-1].token_estimate
            >= self.context.rotation_threshold_tokens
        ):
            self.context.rotate(
                state, reason="context_threshold", next_action="continue current phase"
            )
            return self._commit(state)
        current_action: dict[str, Any] | None = None
        remaining_actions: list[dict[str, Any]] = []
        try:
            state.counters["model_calls"] = state.counters.get("model_calls", 0) + 1
            decision = self.agent.decide(
                state,
                contract,
                core_skill=core_skill,
                playbook=playbook,
                timeout_seconds=self._model_request_timeout(state),
                tools=native_tool_schemas(state.phase),
            )
            state.counters["consecutive_model_errors"] = 0
            state.retry_at = ""
            if state.episodes:
                state.episodes[-1].token_estimate = decision.prompt_tokens_estimate
            # Providers may return a small sequence of independent tool calls in
            # one response.  Execute them in order, exactly as their tool result
            # messages will be replayed on the next model call.  Restrict control
            # actions to one per turn so a stale parallel plan cannot skip a
            # controller phase transition.
            for index, action in enumerate(decision.actions):
                current_action = action
                remaining_actions = decision.actions[index + 1 :]
                if str(action.get("action")) in {
                    "profile_task",
                    "set_plan",
                    "begin_verification",
                    "accept_work_item",
                    "reject_work_item",
                    "revise_plan",
                    "begin_final_verification",
                    "final_verified",
                    "final_delivery",
                    "wait",
                    "rotate_context",
                } and (index or remaining_actions):
                    raise ActionError(
                        "controller-transition tools must be the only call in a response"
                    )
                self._apply_action(state, action)
                if (
                    str(action.get("_tool_call_id", ""))
                    and str(action.get("action", ""))
                    not in {
                        "bash",
                        "run",
                        "start",
                        "read",
                        "read_command_output",
                        "logs",
                        "write",
                        "edit",
                        "poll",
                        "terminate",
                        "stop",
                    }
                ):
                    self._record_control_tool_result(state, action)
                self._rotate_after_control_tool_result(state, action)
        except PermanentModelError as error:
            state.status = "failed_infra"
            state.final["model_error"] = {
                "error": str(error),
                "kind": "permanent_request_error",
            }
            self.store.append_event(
                "model_failure_terminal",
                {"error": str(error), "kind": "permanent_request_error"},
            )
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
            if current_action is not None:
                self._record_rejected_tool_call(state, current_action, str(error))
                # A native assistant turn must receive one tool result for every
                # call it issued, including calls skipped after an earlier error.
                # Otherwise the provider correctly rejects the next request.
                for pending in remaining_actions:
                    self._record_rejected_tool_call(
                        state,
                        pending,
                        "not executed because an earlier tool call in this response was rejected",
                    )
            else:
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
            state.profile = TaskProfile.from_dict(
                self._normalize_profile(self._mapping(action, "profile"))
            )
            # Optimization runs must preserve and compare the best known artifact.
            # Treat this as a controller invariant instead of trusting a model field:
            # a false value here can let a later losing candidate replace the best
            # deliverable, which is especially damaging in long-running benchmarks.
            if state.profile.primary_playbook == "optimization":
                state.profile.requires_best_artifact = True
            if state.deadline.wall_time_seconds >= 3_600:
                state.profile.execution_regime = "long_horizon"
                state.profile.estimated_horizon = "multi_hour"
                state.profile.rationale += " [controller: multi-hour task budget]"
            if "standard-only" in state.runtime_config.get("ablations", []):
                state.profile.execution_regime = "standard"
                state.profile.rationale += " [ablation: standard-only]"
            if state.profile.execution_regime == "long_horizon":
                state.phase = "long_horizon_work"
                state.work_items = []
                state.active_work_item_id = None
                self.store.append_event(
                    "flat_long_horizon_started",
                    {"primary_playbook": state.profile.primary_playbook},
                )
            else:
                state.phase = "plan"
            return
        if name == "set_plan" and state.phase == "plan":
            items = self._parse_plan(action.get("work_items"))
            state.work_items = items
            state.phase = "standard_work"
            return
        if name in {
            "bash",
            "run",
            "start",
            "read",
            "read_command_output",
            "logs",
            "write",
            "edit",
            "poll",
            "terminate",
            "stop",
        }:
            if state.phase not in {
                "standard_work",
                "long_horizon_work",
                "final_verify",
            }:
                raise ValueError(f"tool action not allowed in {state.phase}")
            self._execute_tool(state, action)
            return
        if name == "batch" and state.phase in {
            "standard_work",
            "long_horizon_work",
            "final_verify",
        }:
            actions = action.get("actions", action.get("batched_actions"))
            if not isinstance(actions, list) or not actions or len(actions) > 8:
                raise ValueError("batch requires between 1 and 8 actions")
            allowed = {"bash", "run", "read", "write", "edit"}
            for child in actions:
                if not isinstance(child, dict) or child.get("action") not in allowed:
                    raise ValueError(
                        "batch only supports run, read, write, and edit actions"
                    )
                if child.get("action") == "bash" and child.get("background"):
                    raise ValueError("start is not allowed inside batch")
            rejected_children: list[str] = []
            executed_children = 0
            for child in actions:
                try:
                    self._execute_tool(state, child)
                    executed_children += 1
                except ValueError as error:
                    rejected_children.append(str(error))
                    self.store.append_event(
                        "batch_child_rejected",
                        {"action": child.get("action"), "error": str(error)},
                    )
            if rejected_children:
                feedback = "Controller skipped rejected batch children: " + "; ".join(
                    rejected_children
                )
                self.store.append_transcript(
                    "user", feedback, kind="controller_feedback"
                )
            if executed_children == 0:
                raise ValueError(
                    "all batch actions were rejected: " + "; ".join(rejected_children)
                )
            return
        if name == "begin_verification" and state.phase == "standard_work":
            item = self._active(state)
            item.status = "verifying"
            return
        if name == "accept_work_item" and state.phase == "standard_work":
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
            return
        if name == "reject_work_item" and state.phase == "standard_work":
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
        if name == "revise_plan" and state.phase == "standard_work":
            proposed = self._parse_plan(action.get("work_items"))
            self._revise_plan(state, proposed)
            return
        if name == "checkpoint" and state.phase in {
            "standard_work",
            "long_horizon_work",
        }:
            self._checkpoint(state, action)
            return
        if name == "rotate_context" and state.phase != "done":
            return
        if name == "begin_final_verification" and state.phase == "long_horizon_work":
            state.phase = "final_verify"
            state.active_work_item_id = None
            state.final["verification_started_at"] = utc_now()
            self.store.append_event(
                "phase_changed", {"phase": state.phase, "reason": "agent_ready"}
            )
            return
        if name == "wait" and state.phase in {"standard_work", "long_horizon_work"}:
            reason = str(action.get("reason", "")).strip()
            if not reason:
                raise ValueError("wait requires a specific external event")
            if not any(
                command.get("status") == "running"
                for command in self.commands.recover()
            ):
                raise ValueError(
                    "wait requires a running managed job; run tool results are synchronous"
                )
            state.status = "waiting"
            self.store.append_event(
                "run_waiting",
                {"reason": reason, "resume_hint": action.get("resume_hint", "")},
            )
            return
        if name == "final_verified" and state.phase == "final_verify":
            flat_long_horizon = bool(
                state.profile
                and state.profile.execution_regime == "long_horizon"
            )
            if not state.mandatory_complete() and not flat_long_horizon:
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
                "partial": not flat_long_horizon and not state.mandatory_complete(),
            }
            state.phase = "deliver"
            return
        if name == "final_delivery" and state.phase == "deliver":
            if "verification" not in state.final:
                raise ValueError("final verification is missing")
            self._terminate_managed_jobs(state, reason="final_delivery")
            state.final["delivery"] = {
                "summary": str(action.get("summary", "")),
                "tests": list(action.get("tests", [])),
                "changed_files": list(action.get("changed_files", [])),
                "risks": list(action.get("risks", [])),
                "delivered_at": utc_now(),
            }
            state.phase = "done"
            state.status = "completed"
            return
        raise ValueError(f"action {name!r} is not allowed in phase {state.phase}")

    def _execute_tool(self, state: RunState, action: dict[str, Any]) -> None:
        name = str(action["action"])
        self._validate_tool_action(action)
        remaining = self._deadline_remaining(state)
        if remaining is not None and remaining <= 0:
            raise ValueError("deadline reached before tool execution")
        if name in {"write", "edit"}:
            self._require_mutation_feedback(state, str(action.get("path", "")))
        if name in {"bash", "run"}:
            # `bash` plus background is accepted only for old trajectories.
            # New prompts expose the unambiguous `start` action instead.
            if name == "bash" and bool(action.get("background", False)):
                result = self.commands.start(
                    str(action.get("command", "")),
                    cwd=str(action.get("cwd", ".")),
                    timeout_seconds=self._managed_job_timeout(state, action),
                    env=self._managed_evaluation_env(state),
                )
                self._record_tool_result(state, action, result)
                return
            if name == "run" and "background" in action:
                raise ValueError("run has no background mode; use start for managed jobs")
            command = str(action.get("command", ""))
            if self._requires_managed_start(command):
                raise ValueError(
                    "run appears to start a persistent process; use start, then poll/logs/stop"
                )
            requested_timeout = action.get("timeout_seconds")
            timeout_seconds = float(requested_timeout) if requested_timeout is not None else 300.0
            timeout_seconds = min(
                CommandSupervisor.MAX_RUN_TIMEOUT_SECONDS,
                max(1.0, timeout_seconds),
            )
            if remaining is not None:
                timeout_seconds = min(timeout_seconds, max(1.0, remaining))
            result = self.commands.run(
                command,
                cwd=str(action.get("cwd", ".")),
                timeout_seconds=timeout_seconds,
                env=self._managed_evaluation_env(state),
            )
        elif name == "start":
            result = self.commands.start(
                str(action.get("command", "")),
                cwd=str(action.get("cwd", ".")),
                timeout_seconds=self._managed_job_timeout(state, action),
                env=self._managed_evaluation_env(state),
            )
        elif name == "read":
            self._require_new_read_range(state, action)
            result = self.tools.read(
                str(action.get("path", "")),
                start_line=int(action.get("start_line", 1)),
                max_lines=int(action.get("max_lines", 400)),
            )
        elif name in {"read_command_output", "logs"}:
            result = self.commands.read_output(
                str(action.get("command_id", "")),
                start_line=int(action.get("start_line", 1)),
                max_lines=int(action.get("max_lines", 400)),
            )
        elif name == "write":
            result = self.tools.write(
                str(action.get("path", "")), str(action.get("content", ""))
            )
        elif name == "edit":
            result = self.tools.edit(
                str(action.get("path", "")),
                str(action.get("old", "")),
                str(action.get("new", "")),
                replace_all=bool(action.get("replace_all", False)),
            )
        elif name == "poll":
            result = self.commands.poll(str(action.get("command_id", "")))
        else:
            result = self.commands.terminate(str(action.get("command_id", "")))
        self._record_tool_result(state, action, result)

    def _record_tool_result(
        self, state: RunState, action: dict[str, Any], result: ToolResult
    ) -> None:
        evidence = self._tool_evidence(state, result, action)
        self.store.record_evidence(evidence)
        state.evidence_ids.append(evidence.id)
        active = state.work_item(state.active_work_item_id)
        if active:
            active.evidence_ids.append(evidence.id)
        self.store.append_event(
            "tool_result", {"evidence_id": evidence.id, **result.to_dict()}
        )
        tool_call_id = str(action.get("_tool_call_id", ""))
        if tool_call_id:
            self.store.append_transcript(
                "tool",
                json.dumps(
                    {
                        "success": result.success,
                        "output": result.output,
                        "exit_code": result.exit_code,
                        "duration_seconds": result.duration_seconds,
                        "command_id": result.background_id or result.data.get("command_id", ""),
                        "evidence_id": evidence.id,
                    },
                    ensure_ascii=False,
                ),
                kind="tool_result",
                tool_call_id=tool_call_id,
                name=str(action.get("action", result.tool)),
            )
        if str(action["action"]) in {"write", "edit"} and result.success:
            automatic_command = self._automatic_mutation_check(
                str(action.get("path", ""))
            )
            if automatic_command:
                check_action = {
                    "action": "bash",
                    "command": automatic_command,
                    "cwd": ".",
                    "timeout_seconds": 60,
                    "background": False,
                    "rationale": "controller automatic post-mutation syntax check",
                }
                check_result = self.commands.run(
                    automatic_command,
                    cwd=".",
                    timeout_seconds=60,
                    background=False,
                    env=self._managed_evaluation_env(state),
                )

                check_evidence = self._tool_evidence(state, check_result, check_action)
                self.store.record_evidence(check_evidence)
                state.evidence_ids.append(check_evidence.id)
                if active:
                    active.evidence_ids.append(check_evidence.id)
                self.store.append_event(
                    "automatic_mutation_check",
                    {"evidence_id": check_evidence.id, **check_result.to_dict()},
                )
        self._maybe_remind_managed_evaluation(state, action, result)

    def _managed_evaluation_env(self, state: RunState) -> dict[str, str] | None:
        config = state.runtime_config.get("managed_evaluation", {})
        if not isinstance(config, dict) or not config.get("enabled"):
            return None
        return {
            "LIGHTCODER_EVAL_STORE": str(config["store"]),
            "LIGHTCODER_EVAL_WORKSPACE": state.workspace,
            "LIGHTCODER_STATE_ROOT": str(self.store.root),
            "LIGHTCODER_RUN_ID": state.run_id,
            "LIGHTCODER_MODEL": self.agent.model.model,
        }

    def _maybe_remind_managed_evaluation(
        self, state: RunState, action: dict[str, Any], result: ToolResult
    ) -> None:
        config = state.runtime_config.get("managed_evaluation", {})
        if (
            not isinstance(config, dict)
            or not config.get("enabled")
            or config.get("local_check_hint_shown")
            or str(action.get("action", "")) not in {"bash", "run"}
        ):
            return
        command = str(action.get("command", "")).lower()
        if "lightcoder eval" in command:
            return
        test_markers = (
            "pytest",
            "cargo test",
            "go test",
            "npm test",
            "npm run test",
            "pnpm test",
            "yarn test",
            "ctest",
            "test.sh",
            "benchmark",
        )
        if not any(marker in command for marker in test_markers):
            return
        config["local_check_hint_shown"] = True
        self.store.append_transcript(
            "user",
            "This was recorded as a local check. If managed comparison is useful, "
            "you may create `.lightcoder-eval/evaluate.py` and `metrics.toml`, then "
            "run `lightcoder eval`. It is optional.",
            kind="controller_feedback",
        )
        self.store.append_event(
            "managed_evaluation_hint_shown",
            {"command": str(action.get("command", "")), "success": result.success},
        )

    def _managed_job_timeout(
        self, state: RunState, action: dict[str, Any]
    ) -> float | None:
        """Bound a background job by the official task budget, not a short cap."""
        requested = action.get("timeout_seconds")
        requested_value = (
            max(1.0, float(requested)) if requested is not None else None
        )
        remaining = self._deadline_remaining(state)
        if remaining is None:
            return requested_value
        # Leave a small fixed window for final polling, verifier handoff, and
        # controller-side process cleanup.  This is not a per-command limit.
        task_bound = max(1.0, remaining - 30.0)
        return min(requested_value, task_bound) if requested_value else task_bound

    def _record_control_tool_result(
        self, state: RunState, action: dict[str, Any]
    ) -> None:
        """Close the native tool-call protocol for controller-only actions."""
        self.store.append_transcript(
            "tool",
            json.dumps(
                {
                    "success": True,
                    "phase": state.phase,
                    "status": state.status,
                    "message": "controller action accepted",
                },
                ensure_ascii=False,
            ),
            kind="tool_result",
            tool_call_id=str(action["_tool_call_id"]),
            name=str(action.get("action", "")),
        )

    def _rotate_after_control_tool_result(
        self, state: RunState, action: dict[str, Any]
    ) -> None:
        """Rotate only after the assistant/tool protocol pair is durable."""
        name = str(action.get("action", ""))
        if name == "accept_work_item":
            self.context.rotate(
                state,
                reason="milestone_finished",
                next_action="select next ready work item",
            )
        elif name == "rotate_context":
            self.context.rotate(
                state,
                reason=str(action.get("reason", "agent_requested")),
                next_action=str(action.get("next_action", "")),
            )

    def _record_rejected_tool_call(
        self, state: RunState, action: dict[str, Any], error: str
    ) -> None:
        """Return an error tool result so native tool-call history stays valid."""
        tool_call_id = str(action.get("_tool_call_id", ""))
        if not tool_call_id:
            self.store.append_transcript(
                "user",
                f"Controller rejected the previous action: {error}",
                kind="controller_feedback",
            )
            return
        self.store.append_transcript(
            "tool",
            json.dumps({"success": False, "error": error}, ensure_ascii=False),
            kind="tool_result",
            tool_call_id=tool_call_id,
            name=str(action.get("action", "unknown")),
        )

    def _tool_evidence(
        self, state: RunState, result: ToolResult, action: dict[str, Any]
    ) -> Evidence:
        if result.tool in {"bash", "run", "start", "poll", "stop", "terminate"}:
            kind = "command"
        elif result.tool in {"read", "read_command_output", "logs"}:
            kind = "observation"
        else:
            kind = "mutation"
        summary_limit = (
            16_000
            if result.tool in {"read", "read_command_output", "logs"}
            else 20_000
        )
        action_path = str(action.get("path", ""))
        return Evidence(
            id=new_id("ev"),
            kind=kind,
            created_at=utc_now(),
            work_item_id=state.active_work_item_id,
            workspace_revision=self.tools.workspace_revision(),
            summary=result.output[:summary_limit],
            command=str(action.get("command", "")),
            cwd=str(action.get("cwd", ".")),
            exit_code=result.exit_code,
            duration_seconds=result.duration_seconds,
            raw_log=result.raw_log,
            data={
                "success": result.success,
                "affected_paths": result.affected_paths,
                "path": self._relative_action_path(action_path) if action_path else "",
                "start_line": int(action.get("start_line", 1)),
                "max_lines": int(action.get("max_lines", 400)),
                "tool_call_id": result.call_id,
                "model_call": state.counters.get("model_calls", 0),
                **result.data,
            },
        )

    def _require_mutation_feedback(self, state: RunState, path: str) -> None:
        """Require an executable feedback step between mutations to one file."""
        active = state.work_item(state.active_work_item_id)
        if active is None or not path:
            return
        path = self._relative_action_path(path)
        evidence = self.store.evidence_by_id(active.evidence_ids)
        latest_mutation_index: int | None = None
        for index in range(len(evidence) - 1, -1, -1):
            item = evidence[index]
            if item.kind != "mutation" or item.data.get("success") is not True:
                continue
            if path in item.data.get("affected_paths", []):
                latest_mutation_index = index
                break
        if latest_mutation_index is None:
            return
        if any(item.kind == "command" for item in evidence[latest_mutation_index + 1 :]):
            return
        raise ValueError(
            f"run a focused bash check after the previous mutation to {path!r} "
            "before changing that file again"
        )

    def _require_new_read_range(
        self, state: RunState, action: dict[str, Any]
    ) -> None:
        """Reject duplicate reads while allowing a targeted unseen continuation."""
        active = state.work_item(state.active_work_item_id)
        raw_path = str(action.get("path", ""))
        if active is None or not raw_path:
            return
        path = self._relative_action_path(raw_path)
        revision = self.tools.workspace_revision()
        start_line = int(action.get("start_line", 1))
        evidence = self.store.evidence_by_id(active.evidence_ids)
        for item in reversed(evidence):
            if (
                item.kind != "observation"
                or item.data.get("success") is not True
                or item.workspace_revision != revision
                or item.data.get("path") != path
            ):
                continue
            previous_start = int(item.data.get("start_line", 1))
            previous_max = int(item.data.get("max_lines", 400))
            if "... truncated;" not in item.summary:
                raise ValueError(
                    f"{path!r} was already read completely at this workspace revision; "
                    "use the existing observation"
                )
            first_unseen = previous_start + previous_max
            if start_line < first_unseen:
                raise ValueError(
                    f"read of {path!r} overlaps an existing observation; continue at "
                    f"start_line {first_unseen} or later"
                )
            return

    def _relative_action_path(self, path: str) -> str:
        try:
            return str(self.tools.resolve_path(path).relative_to(self.tools.workspace))
        except (OSError, ValueError):
            return path

    def _automatic_mutation_check(self, path: str) -> str:
        relative = self._relative_action_path(path)
        if Path(relative).suffix == ".py":
            return f"python3 -m py_compile {shlex.quote(relative)}"
        if Path(relative).suffix in {".sh", ".bash"}:
            return f"bash -n {shlex.quote(relative)}"
        return ""

    @staticmethod
    def _requires_managed_start(command: str) -> bool:
        """Catch only unambiguous service/watch modes before they can block run."""
        normalized = f" {command.lower()} "
        markers = (
            " --stdio",
            " uvicorn ",
            " gunicorn ",
            " runserver",
            " start.sh",
            " npm run dev",
            " --watch",
            " tail -f",
            " sleep infinity",
        )
        return any(marker in normalized for marker in markers)

    @staticmethod
    def _validate_tool_action(action: dict[str, Any]) -> None:
        name = str(action.get("action", ""))
        if name in {"bash", "run", "start"} and not isinstance(
            action.get("command"), str
        ):
            raise ValueError(f"{name} requires a string command")
        if name == "read" and not isinstance(action.get("path"), str):
            raise ValueError("read requires a string path")
        if name in {"read_command_output", "logs", "poll", "terminate", "stop"} and not isinstance(
            action.get("command_id"), str
        ):
            raise ValueError(f"{name} requires a string command_id")
        if name == "write" and not isinstance(action.get("content"), str):
            raise ValueError("write requires an explicit string content field")
        if name == "write" and not isinstance(action.get("path"), str):
            raise ValueError("write requires a string path")
        if name == "edit" and not all(
            isinstance(action.get(key), str) for key in ("path", "old", "new")
        ):
            raise ValueError("edit requires string path, old, and new fields")

    def _validate_evidence(
        self,
        ids: list[str],
        *,
        require_successful_command: bool,
        created_after: str = "",
    ) -> None:
        if not ids:
            raise ValueError("at least one evidence id is required")
        requested_evidence = self.store.evidence_by_id(ids)
        if len(requested_evidence) != len(set(ids)):
            raise ValueError("one or more evidence ids do not exist")
        revision = self.tools.workspace_revision()
        evidence = [
            item for item in requested_evidence if item.workspace_revision == revision
        ]
        if not evidence:
            raise ValueError("no evidence matches the current workspace revision")
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

    def _unobserved_verification_commands(self, item: WorkItem) -> list[str]:
        revision = self.tools.workspace_revision()
        observed = {
            evidence.command
            for evidence in self.store.evidence_by_id(item.evidence_ids)
            if evidence.kind == "command"
            and evidence.workspace_revision == revision
        }
        return [
            command
            for command in item.verification_commands
            if command not in observed
        ]

    def _checkpoint(self, state: RunState, action: dict[str, Any]) -> None:
        evidence_ids = self._evidence_ids(action)
        self._validate_evidence(evidence_ids, require_successful_command=True)
        metric_name = str(action.get("metric_name", "")).strip()
        metric_value = (
            float(action["metric_value"])
            if action.get("metric_value") is not None
            else None
        )
        metric_direction = str(action.get("metric_direction", "")).strip()
        requires_metric = bool(
            state.profile
            and state.profile.requires_best_artifact
        )
        if metric_value is not None and (
            not metric_name or metric_direction not in {"maximize", "minimize"}
        ):
            raise ValueError(
                "numeric checkpoint metrics require metric_name and "
                "metric_direction=maximize|minimize"
            )
        if requires_metric and metric_value is None:
            raise ValueError(
                "best-artifact checkpoints require a numeric metric_value"
            )

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
            metric_name=metric_name,
            metric_value=metric_value,
            metric_direction=metric_direction,
            validation_evidence_ids=evidence_ids,
            artifact_paths=artifact_paths,
        )
        self.store.write_checkpoint(checkpoint)
        promoted, reason = self._checkpoint_improves_best(state, checkpoint)
        if promoted:
            state.best_checkpoint_id = checkpoint.id
            self.store.append_event("checkpoint_promoted", asdict(checkpoint))
        else:
            self.store.append_event(
                "checkpoint_retained_not_promoted",
                {**asdict(checkpoint), "reason": reason},
            )
            self.store.append_transcript(
                "user",
                f"Checkpoint retained as history but did not replace the best: {reason}",
                kind="controller_feedback",
            )

    def _checkpoint_improves_best(
        self, state: RunState, checkpoint: Checkpoint
    ) -> tuple[bool, str]:
        if not state.best_checkpoint_id:
            return True, "first validated checkpoint"
        path = self.store.checkpoints_dir / f"{state.best_checkpoint_id}.json"
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return True, "previous best metadata is unavailable"
        previous_value = previous.get("metric_value")
        previous_name = str(previous.get("metric_name", ""))
        previous_direction = str(previous.get("metric_direction", ""))
        if checkpoint.metric_value is None:
            if previous_value is not None:
                return False, "new checkpoint omitted the existing scalar metric"
            return True, "newer validated checkpoint without a scalar metric"
        if previous_value is None:
            return True, "previous checkpoint has no comparable metric"
        if previous_name != checkpoint.metric_name:
            return False, (
                f"metric changed from {previous_name!r} to "
                f"{checkpoint.metric_name!r}"
            )
        if previous_direction and previous_direction != checkpoint.metric_direction:
            return False, "metric direction changed"
        old = float(previous_value)
        new = float(checkpoint.metric_value)
        improved = (
            new > old
            if checkpoint.metric_direction == "maximize"
            else new < old
        )
        if improved:
            return True, f"metric improved from {old} to {new}"
        return False, f"metric did not improve beyond {old}"

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
        elapsed = self._deadline_elapsed()
        state.counters["elapsed_seconds"] = int(elapsed)
        if elapsed >= limit:
            terminated = self._terminate_managed_jobs(
                state, reason="deadline"
            )
            self._restore_best_checkpoint_at_deadline(state)
            state.status = "paused_limit"
            state.final["limit"] = {
                "elapsed_seconds": elapsed,
                "reached_at": utc_now(),
                "clock": "monotonic_with_persisted_resume",
                "terminated_command_ids": terminated,
            }
            self.store.append_event("hard_deadline_reached", state.final["limit"])
            return True
        return False

    def _terminate_managed_jobs(self, state: RunState, *, reason: str) -> list[str]:
        """End every managed process before a deadline or final verifier handoff."""
        terminated: list[str] = []
        for command in self.commands.recover():
            if command.get("status") != "running":
                continue
            command_id = str(command.get("id", ""))
            result = self.commands.terminate(command_id)
            if result.success:
                terminated.append(command_id)
        if terminated:
            self.store.append_event(
                f"{reason}_background_commands_terminated",
                {"command_ids": terminated},
            )
        return terminated

    def _deadline_elapsed(self) -> float:
        return self._deadline_elapsed_base + (
            time.monotonic() - self._deadline_monotonic_started
        )

    def _deadline_remaining(self, state: RunState) -> float | None:
        if state.deadline.wall_time_seconds <= 0:
            return None
        return state.deadline.wall_time_seconds - self._deadline_elapsed()

    def _model_request_timeout(self, state: RunState) -> float | None:
        """Let one inference use the remaining task budget instead of a fixed cap."""
        remaining = self._deadline_remaining(state)
        return None if remaining is None else max(1.0, remaining)

    def _restore_best_checkpoint_at_deadline(self, state: RunState) -> None:
        """Prevent unfinished optimization work from replacing accepted artifacts."""
        if not state.best_checkpoint_id:
            return
        checkpoint_path = (
            self.store.checkpoints_dir / f"{state.best_checkpoint_id}.json"
        )
        if not checkpoint_path.is_file():
            return
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            restored = self.tools.restore_checkpoint_snapshot(
                str(checkpoint.get("snapshot_path", ""))
            )
        except (OSError, ValueError, tarfile.TarError) as error:
            self.store.append_event(
                "best_checkpoint_restore_failed",
                {"checkpoint_id": state.best_checkpoint_id, "error": str(error)},
            )
            return
        self.store.append_event(
            "best_checkpoint_restored",
            {
                "checkpoint_id": state.best_checkpoint_id,
                "restored_files": restored,
                "workspace_revision": self.tools.workspace_revision(),
            },
        )

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
    def _normalize_profile(value: dict[str, Any]) -> dict[str, Any]:
        """Accept concise model profile aliases without silently routing long tasks.

        Tool schemas can be followed loosely by providers.  Treat their common
        `horizon` / `playbook` aliases as the canonical profile fields rather
        than defaulting a clearly multi-hour task to the standard work graph.
        """
        nested = value.get("profile")
        source = {**value, **nested} if isinstance(nested, dict) else dict(value)
        horizon = str(
            source.get("execution_regime")
            or source.get("horizon")
            or source.get("estimated_horizon")
            or "standard"
        )
        regime = "long_horizon" if horizon in {"long_horizon", "multi_hour"} else "standard"
        playbook = str(
            source.get("primary_playbook")
            or source.get("playbook")
            or source.get("task_type")
            or source.get("profile")
            or "generalist"
        )
        valid_playbooks = {
            "repair",
            "feature",
            "project",
            "transformation",
            "optimization",
            "generalist",
        }
        if playbook not in valid_playbooks:
            playbook = "generalist"
        return {
            "execution_regime": regime,
            "primary_playbook": playbook,
            "estimated_horizon": "multi_hour" if regime == "long_horizon" else "short",
            "validation_cost": "high" if regime == "long_horizon" else "low",
            "supports_partial_progress": bool(
                source.get("supports_partial_progress", True)
            ),
            "requires_best_artifact": bool(
                source.get("requires_best_artifact", playbook == "optimization")
            ),
            "rationale": str(source.get("rationale", "")),
        }

    @staticmethod
    def _evidence_ids(action: dict[str, Any]) -> list[str]:
        value = action.get("evidence_ids", [])
        if not isinstance(value, list):
            raise ValueError("evidence_ids must be a list")
        return [str(item) for item in value]

    @staticmethod
    def _playbook(state: RunState) -> str | None:
        return state.profile.primary_playbook if state.profile else None
