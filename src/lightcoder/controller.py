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
Every mandatory item requires at least one verification command.
For a multi-hour task, prefer 3-6 substantial vertical milestones rather than one item per file or endpoint. The first milestone must produce a scoreable end-to-end artifact, not only scaffolding.
Mandatory work items must describe a path to satisfying the objective, including iteration or strategy changes when needed; never make "report/flag failure" the terminal plan for a required outcome.
Verification commands must be executable in the observed environment. Use python3 rather than python unless a python executable has already been observed. Prefer Python standard-library checks for numeric thresholds instead of assuming utilities such as bc are installed."""

WORK_ACTIONS = """Return exactly one action:
{"action":"bash","command":"...","cwd":".","background":false,"rationale":"..."}
{"action":"read","path":"...","start_line":1,"max_lines":400,"rationale":"..."}
{"action":"read_command_output","command_id":"cmd-...","start_line":1,"max_lines":400,"rationale":"inspect a truncated command log"}
{"action":"write","path":"...","content":"...","rationale":"..."}
{"action":"edit","path":"...","old":"exact text","new":"replacement","replace_all":false,"rationale":"..."}
{"action":"batch","actions":[{"action":"read","path":"..."},{"action":"bash","command":"..."}],"rationale":"group short sequential operations; maximum 8"}
{"action":"poll","command_id":"cmd-..."}
{"action":"terminate","command_id":"cmd-..."}
{"action":"begin_verification","rationale":"implementation is ready for its acceptance oracle"}
{"action":"accept_work_item","evidence_ids":["ev-..."],"summary":"why the acceptance criteria pass"}
{"action":"reject_work_item","evidence_ids":["ev-..."],"failure_signature":"specific observed failure","next_strategy":"materially different next approach"}
{"action":"revise_plan","work_items":[...],"rationale":"new evidence requiring decomposition change"}
{"action":"checkpoint","restore_notes":"how to recover this known-good state","metric_name":"score","metric_value":0.0,"metric_direction":"maximize|minimize","evidence_ids":["ev-..."],"artifact_paths":[]}
{"action":"rotate_context","reason":"...","next_action":"..."}
{"action":"wait","reason":"specific external event","resume_hint":"how to determine it is ready"}
Prefer edit over rewriting an existing file. Prefer batch for independent reads, inspections, and small edits. Prefer one focused bash script over many tiny shell turns.
Batch children execute sequentially. Never use batch to launch multiple long jobs under the assumption that they run in parallel; start each long job as a separate background bash action and poll it.
When a known check is needed after a mutation, default to one batch containing the edit/write followed by the focused bash check so both happen in one model turn.
Keep bash actions short and auditable. For Python logic longer than a few lines, write a named helper script and execute it instead of embedding a large python heredoc or python -c program; this gives syntax-check evidence, preserves reusable instrumentation, and avoids shell/JSON quoting failures.
Do not reread the same file or repeat the same inspection at an unchanged workspace revision unless the previous observation was truncated and you request a specific unseen range.
After writing or editing a file, run a focused executable check before changing that same file again. Use the check output to make the next change; do not perform consecutive speculative rewrites.
For optimization tasks, write experiments to candidate paths. Independently score each candidate and promote it to a required deliverable path only if it improves the recorded best; never let a losing experiment overwrite the best artifact. Microbenchmark a small iteration count before launching a long search.
Work only on the active work item. Do not implement a downstream work item early. As soon as the active item's implementation appears to satisfy its acceptance criteria, the next action must be begin_verification.
After begin_verification, the controller runs the exact verification commands automatically. Do not run them repeatedly.
Do not accept an item without current-revision observational evidence. Use begin_verification before acceptance."""

LONG_HORIZON_ACTIONS = """Return exactly one action:
{"action":"bash","command":"...","cwd":".","background":false,"rationale":"..."}
{"action":"read","path":"...","start_line":1,"max_lines":400,"rationale":"..."}
{"action":"read_command_output","command_id":"cmd-...","start_line":1,"max_lines":400,"rationale":"inspect a truncated command log"}
{"action":"write","path":"...","content":"...","rationale":"..."}
{"action":"edit","path":"...","old":"exact text","new":"replacement","replace_all":false,"rationale":"..."}
{"action":"batch","actions":[{"action":"read","path":"..."},{"action":"bash","command":"..."}],"rationale":"group short sequential operations; maximum 8"}
{"action":"poll","command_id":"cmd-..."}
{"action":"terminate","command_id":"cmd-..."}
{"action":"checkpoint","restore_notes":"how to recover this known-good state","metric_name":"score","metric_value":0.0,"metric_direction":"maximize|minimize","evidence_ids":["ev-..."],"artifact_paths":[]}
{"action":"rotate_context","reason":"...","next_action":"..."}
{"action":"wait","reason":"specific external event","resume_hint":"how to determine it is ready"}
{"action":"begin_final_verification","rationale":"all required deliverables are ready for a clean final check"}
There is no controller-managed work-item plan in long-horizon mode. Keep decomposition advisory and freely change strategy from observations; never wait for an artificial milestone before working on another part of the objective.
Create a valid scoreable baseline for every required deliverable early. Then allocate effort by measured correctness or metric gain per wall-clock time.
Treat required deliverable paths as promoted best-so-far artifacts. Run experiments on candidate paths, independently score them, and atomically promote only verified improvements. Checkpoint all currently valid required deliverables together after a material improvement.
Every checkpoint requires successful current-revision command evidence. For optimization checkpoints, provide a numeric metric and its minimize/maximize direction; the controller retains a non-improving snapshot as history but does not replace the best checkpoint.
Batch children execute sequentially. Start independent long jobs as separate background bash actions and poll them. Microbenchmark before a long search and leave time for final verification.
Prefer edit over rewriting an existing file. Keep bash actions short and auditable. Put nontrivial Python logic in a named helper file rather than a heredoc or large python -c command.
Do not reread unchanged files or repeat failed experiments without a materially different hypothesis. Use rotate_context for a compact handoff when history grows.
Use begin_final_verification only after running relevant checks and confirming required artifacts exist. Continue useful implementation and testing until then; the controller does not reserve a fixed hardening fraction."""

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
        try:
            state.counters["model_calls"] = state.counters.get("model_calls", 0) + 1
            decision = self.agent.decide(
                state,
                contract,
                core_skill=core_skill,
                playbook=playbook,
                timeout_seconds=self._model_request_timeout(state),
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
            # Optimization runs must preserve and compare the best known artifact.
            # Treat this as a controller invariant instead of trusting a model field:
            # a false value here can let a later losing candidate replace the best
            # deliverable, which is especially damaging in long-running benchmarks.
            if state.profile.primary_playbook == "optimization":
                state.profile.requires_best_artifact = True
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
            "read",
            "read_command_output",
            "write",
            "edit",
            "poll",
            "terminate",
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
            allowed = {"bash", "read", "write", "edit"}
            for child in actions:
                if not isinstance(child, dict) or child.get("action") not in allowed:
                    raise ValueError(
                        "batch only supports bash, read, write, and edit actions"
                    )
                if child.get("action") == "bash" and child.get("background"):
                    raise ValueError("background bash is not allowed inside batch")
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
            self.context.rotate(
                state,
                reason="milestone_finished",
                next_action="select next ready work item",
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
            self.context.rotate(
                state,
                reason=str(action.get("reason", "agent_requested")),
                next_action=str(action.get("next_action", "")),
            )
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
                    "wait requires a running background command; tool results are already synchronous"
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
        if name == "bash":
            requested_timeout = action.get("timeout_seconds")
            timeout_seconds = (
                float(requested_timeout)
                if requested_timeout is not None
                else (max(1.0, remaining) if remaining is not None else None)
            )
            if remaining is not None:
                timeout_seconds = min(timeout_seconds, max(1.0, remaining))
            result = self.commands.run(
                str(action.get("command", "")),
                cwd=str(action.get("cwd", ".")),
                timeout_seconds=timeout_seconds,
                background=bool(action.get("background", False)),
            )
        elif name == "read":
            self._require_new_read_range(state, action)
            result = self.tools.read(
                str(action.get("path", "")),
                start_line=int(action.get("start_line", 1)),
                max_lines=int(action.get("max_lines", 400)),
            )
        elif name == "read_command_output":
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
        evidence = self._tool_evidence(state, result, action)
        self.store.record_evidence(evidence)
        state.evidence_ids.append(evidence.id)
        active = state.work_item(state.active_work_item_id)
        if active:
            active.evidence_ids.append(evidence.id)
        self.store.append_event(
            "tool_result", {"evidence_id": evidence.id, **result.to_dict()}
        )
        if name in {"write", "edit"} and result.success:
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

    def _tool_evidence(
        self, state: RunState, result: ToolResult, action: dict[str, Any]
    ) -> Evidence:
        if result.tool in {"bash", "poll", "terminate"}:
            kind = "command"
        elif result.tool in {"read", "read_command_output"}:
            kind = "observation"
        else:
            kind = "mutation"
        summary_limit = (
            16_000
            if result.tool in {"read", "read_command_output"}
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
    def _validate_tool_action(action: dict[str, Any]) -> None:
        name = str(action.get("action", ""))
        if name == "bash" and not isinstance(action.get("command"), str):
            raise ValueError("bash requires a string command")
        if name == "read" and not isinstance(action.get("path"), str):
            raise ValueError("read requires a string path")
        if name == "read_command_output" and not isinstance(
            action.get("command_id"), str
        ):
            raise ValueError("read_command_output requires a string command_id")
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
                    "deadline_background_commands_terminated",
                    {"command_ids": terminated},
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
    def _evidence_ids(action: dict[str, Any]) -> list[str]:
        value = action.get("evidence_ids", [])
        if not isinstance(value, list):
            raise ValueError("evidence_ids must be a list")
        return [str(item) for item in value]

    @staticmethod
    def _playbook(state: RunState) -> str | None:
        return state.profile.primary_playbook if state.profile else None
