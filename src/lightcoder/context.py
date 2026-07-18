from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from .model import ChatMessage
from .models import Episode, RunState, utc_now
from .skills import SkillRegistry
from .store import StateStore
from .tools import WorkspaceTools


SYSTEM_CONTRACT = """You are the only reasoning agent in LightCoder. Work directly on the target repository.
The deterministic controller owns routing, persistence, deadlines, and completion guards.
Return exactly one JSON object matching an allowed action. Never wrap it in Markdown.
Use evidence, not confidence, to claim completion. Do not stop because a strategy failed.
Do not modify runtime metadata or harness-protected paths. Treat disk and tool results as authoritative.
Keep private reasoning private; put only a concise rationale in the JSON action."""


class ContextManager:
    def __init__(
        self,
        store: StateStore,
        tools: WorkspaceTools,
        skills: SkillRegistry,
        *,
        context_window_tokens: int = 128_000,
        rotate_fraction: float = 0.72,
        transcript_tail: int = 512,
        handoffs_enabled: bool = True,
    ) -> None:
        self.store = store
        self.tools = tools
        self.skills = skills
        self.context_window_tokens = max(8_000, context_window_tokens)
        self.rotate_fraction = min(0.95, max(0.4, rotate_fraction))
        self.transcript_tail = max(2, transcript_tail)
        self.handoffs_enabled = handoffs_enabled

    def build_messages(
        self,
        state: RunState,
        action_contract: str,
        *,
        core_skill: str | None = None,
        playbook: str | None = None,
    ) -> list[ChatMessage]:
        # Keep task-static material in the system prefix and append the episode
        # transcript chronologically. DeepSeek's cache is prefix based: rebuilding
        # the latest state before history turns every cycle into a cache miss.
        system_sections = [
            SYSTEM_CONTRACT,
            f"TASK OBJECTIVE\n{state.objective}",
            f"ALLOWED ACTIONS\n{action_contract}",
        ]
        if core_skill:
            system_sections.append(
                f"CORE SKILL: {core_skill}\n{self.skills.load(core_skill)}"
            )
        if playbook and playbook in {item.name for item in self.skills.metadata()}:
            system_sections.append(
                f"PLAYBOOK: {playbook}\n{self.skills.load(playbook)}"
            )
        handoff = self.latest_handoff(state)
        if handoff:
            system_sections.append(
                f"LATEST VALIDATED HANDOFF\n{json.dumps(handoff, ensure_ascii=False, indent=2)}"
            )
        current_sections = [self._durable_state(state)]
        messages = [ChatMessage("system", "\n\n".join(system_sections))]
        messages.extend(self._recent_transcript(state))
        messages.append(ChatMessage("user", "\n\n".join(current_sections)))
        return messages

    def estimate_tokens(self, messages: list[ChatMessage]) -> int:
        return sum(max(1, len(message.content) // 4) + 6 for message in messages)

    def should_rotate(
        self, messages: list[ChatMessage], *, milestone_finished: bool = False
    ) -> bool:
        return milestone_finished or self.estimate_tokens(messages) >= int(
            self.context_window_tokens * self.rotate_fraction
        )

    def rotate(
        self, state: RunState, *, reason: str, next_action: str = ""
    ) -> dict[str, Any]:
        revision = self.tools.workspace_revision()
        handoff = {
            "schema_version": 1,
            "run_id": state.run_id,
            "generation": len(state.episodes),
            "created_at": utc_now(),
            "phase": state.phase,
            "control_mode": "flat"
            if state.profile and state.profile.execution_regime == "long_horizon"
            else "work_graph",
            "profile": asdict(state.profile) if state.profile else None,
            "workspace_revision": revision,
            "changed_files": self.tools.changed_files(),
            "active_work_item": self._compact_work_item(
                state.work_item(state.active_work_item_id), evidence_limit=8
            )
            if state.work_item(state.active_work_item_id)
            else None,
            "accepted_work_items": [
                self._compact_work_item(item, evidence_limit=5)
                for item in state.work_items
                if item.status == "accepted"
            ],
            "best_checkpoint_id": state.best_checkpoint_id,
            "recent_evidence_ids": state.evidence_ids[-20:],
            "failed_strategies": {
                item.id: item.failure_signatures[-5:]
                for item in state.work_items
                if item.failure_signatures
            },
            "open_risks": [
                item.title
                for item in state.work_items
                if item.mandatory and item.status not in {"accepted"}
            ],
            "next_action": next_action,
            "reason": reason,
        }
        path = (
            self.store.write_handoff(len(state.episodes), handoff)
            if self.handoffs_enabled
            else None
        )
        if state.episodes and not state.episodes[-1].ended_at:
            state.episodes[-1].ended_at = utc_now()
            state.episodes[-1].end_reason = reason
            state.episodes[-1].handoff_path = (
                str(path.relative_to(self.store.run_dir)) if path is not None else ""
            )
            state.episodes[-1].transcript_end = self.store.transcript_line_count()
        state.episodes.append(
            Episode(
                generation=len(state.episodes),
                started_at=utc_now(),
                active_work_item_id=state.active_work_item_id,
                transcript_start=self.store.transcript_line_count(),
            )
        )
        return handoff

    def latest_handoff(self, state: RunState) -> dict[str, Any] | None:
        if not state.episodes:
            return None
        previous = state.episodes[-2] if len(state.episodes) > 1 else None
        if previous is None or not previous.handoff_path:
            return None
        path = (self.store.run_dir / previous.handoff_path).resolve()
        try:
            path.relative_to(self.store.handoffs_dir.resolve())
            value = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError, json.JSONDecodeError):
            return None
        if value.get("run_id") != state.run_id:
            return None
        value["workspace_revision_matches"] = (
            value.get("workspace_revision") == self.tools.workspace_revision()
        )
        return value

    def _durable_state(self, state: RunState) -> str:
        active = state.work_item(state.active_work_item_id)
        # This message is appended to the provider conversation every cycle. Keep
        # it small: the objective and action contract already live in the stable
        # system prefix, and future work-item details become available when that
        # item is selected. Repeating the whole state here causes quadratic prompt
        # growth even when prefix caching makes those tokens cheaper.
        all_evidence = self.store.evidence()
        latest_model_call = max(
            (
                int(item.data["model_call"])
                for item in all_evidence
                if item.data.get("model_call") is not None
            ),
            default=None,
        )
        # Keep the ordinary five-item tail, plus every child result from the
        # newest model action. A batch may contain up to eight children, and the
        # state's model-call counter can already be one step ahead while the
        # action is being resumed, so comparing against the counter is brittle.
        recent_ids = {item.id for item in all_evidence[-5:]}
        if latest_model_call is not None:
            recent_ids.update(
                item.id
                for item in all_evidence
                if item.data.get("model_call") == latest_model_call
            )
        recent_evidence = [item for item in all_evidence if item.id in recent_ids]
        compact = {
            "run_id": state.run_id,
            "phase": state.phase,
            "status": state.status,
            "control_mode": "flat"
            if state.profile and state.profile.execution_regime == "long_horizon"
            else "work_graph",
            "counters": {
                "elapsed_seconds": state.counters.get("elapsed_seconds", 0),
                "model_calls": state.counters.get("model_calls", 0),
                "invalid_actions": state.counters.get("invalid_actions", 0),
            },
            "profile": {
                "execution_regime": state.profile.execution_regime,
                "primary_playbook": state.profile.primary_playbook,
                "validation_cost": state.profile.validation_cost,
                "requires_best_artifact": state.profile.requires_best_artifact,
            }
            if state.profile
            else None,
            "active_work_item": self._compact_work_item(active, evidence_limit=8)
            if active
            else None,
            "work_item_statuses": [
                {
                    "id": item.id,
                    "title": item.title,
                    "status": item.status,
                    "dependencies": item.dependencies,
                    "mandatory": item.mandatory,
                }
                for item in state.work_items
            ],
            "best_checkpoint_id": state.best_checkpoint_id,
            "workspace_revision": self.tools.workspace_revision(),
            "recent_evidence": [
                {
                    "id": item.id,
                    "kind": item.kind,
                    "work_item_id": item.work_item_id,
                    "workspace_revision": item.workspace_revision,
                    # Preserve the newest tool result once so the next model turn
                    # can actually use a file read or diagnostic output. Older
                    # evidence remains compact and cacheable.
                    "summary": item.summary[: (
                        16_000
                        if (
                            index == len(recent_evidence) - 1
                            or item.data.get("model_call") == latest_model_call
                        )
                        else 700
                    )],
                    "command": item.command[:700],
                    "exit_code": item.exit_code,
                    "duration_seconds": item.duration_seconds,
                    "raw_log": item.raw_log,
                    "success": item.data.get("success"),
                }
                for index, item in enumerate(recent_evidence)
            ],
        }
        return "CANONICAL RUN STATE\n" + json.dumps(
            compact, ensure_ascii=False, indent=2
        )

    @staticmethod
    def _compact_work_item(item: Any, *, evidence_limit: int = 5) -> dict[str, Any]:
        return {
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "kind": item.kind,
            "playbook": item.playbook,
            "status": item.status,
            "dependencies": item.dependencies,
            "mandatory": item.mandatory,
            "acceptance": item.acceptance,
            "verification_commands": item.verification_commands,
            "evidence_ids": item.evidence_ids[-evidence_limit:],
            "failure_signatures": item.failure_signatures[-3:],
            "attempt_count": item.attempt_count,
        }

    @staticmethod
    def _compact_transcript_content(role: str, content: str) -> str:
        if role == "assistant":
            try:
                action = json.loads(content)
            except json.JSONDecodeError:
                action = None
            if isinstance(action, dict) and isinstance(action.get("action"), str):
                compact: dict[str, Any] = {
                    "type": action["action"],
                    "rationale": str(action.get("rationale", ""))[:500],
                }
                for key in (
                    "path",
                    "cwd",
                    "command_id",
                    "evidence_ids",
                    "summary",
                    "failure_signature",
                    "next_strategy",
                ):
                    if key in action:
                        value = action[key]
                        compact[key] = value[:1_000] if isinstance(value, str) else value
                if "command" in action:
                    command = str(action["command"])
                    compact["command"] = command[:1_500]
                    if len(command) > 1_500:
                        compact["command_omitted_chars"] = len(command) - 1_500
                if "content" in action:
                    compact["content_omitted_chars"] = len(str(action["content"]))
                for key in ("old", "new"):
                    if key in action:
                        compact[f"{key}_omitted_chars"] = len(str(action[key]))
                if action["action"] == "set_plan":
                    compact["work_item_ids"] = [
                        str(item.get("id", ""))
                        for item in action.get("work_items", [])
                        if isinstance(item, dict)
                    ]
                if action["action"] == "batch":
                    compact["children"] = [
                        {"type": str(item.get("action", ""))}
                        for item in action.get("actions", [])
                        if isinstance(item, dict)
                    ]
                return (
                    "COMPLETED ACTION HISTORY — not a current executable action\n"
                    + json.dumps(compact, ensure_ascii=False)
                )
            shell_blocks = [
                block.strip()
                for block in re.findall(
                    r"```(?:bash|sh|shell)\s*\n(.*?)```",
                    content,
                    flags=re.I | re.S,
                )
                if block.strip()
            ]
            if shell_blocks:
                command = "\n".join(shell_blocks)
                compact = {"type": "bash", "command": command[:1_500]}
                if len(command) > 1_500:
                    compact["command_omitted_chars"] = len(command) - 1_500
                return (
                    "COMPLETED SHELL ACTION HISTORY — not a current executable action\n"
                    + json.dumps(compact, ensure_ascii=False)
                )
        if len(content) <= 3_000:
            return content
        return f"{content[:2_400]}\n... {len(content) - 2_800} characters omitted ...\n{content[-400:]}"

    def _recent_transcript(self, state: RunState) -> list[ChatMessage]:
        path = self.store.transcript_path
        if not path.is_file():
            return []
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if state.episodes:
            lines = lines[state.episodes[-1].transcript_start :]
        messages: list[ChatMessage] = []
        for line in reversed(lines):
            try:
                value = json.loads(line)
                role = value.get("role")
                metadata = value.get("metadata", {})
                if role in {"user", "assistant"}:
                    raw_content = str(value.get("content", ""))
                    content = (
                        raw_content
                        if metadata.get("kind") == "controller_context"
                        else self._compact_transcript_content(role, raw_content)
                    )
                    messages.append(ChatMessage(role, content))
                    if len(messages) >= self.transcript_tail:
                        break
            except json.JSONDecodeError:
                continue
        return list(reversed(messages))
