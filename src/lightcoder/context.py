from __future__ import annotations

import json
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
        transcript_tail: int = 12,
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
        sections = [self._durable_state(state), f"ALLOWED ACTIONS\n{action_contract}"]
        if core_skill:
            sections.append(f"CORE SKILL: {core_skill}\n{self.skills.load(core_skill)}")
        if playbook and playbook in {item.name for item in self.skills.metadata()}:
            sections.append(f"PLAYBOOK: {playbook}\n{self.skills.load(playbook)}")
        handoff = self.latest_handoff(state)
        if handoff:
            sections.append(
                f"LATEST VALIDATED HANDOFF\n{json.dumps(handoff, ensure_ascii=False, indent=2)}"
            )
        messages = [
            ChatMessage("system", SYSTEM_CONTRACT),
            ChatMessage("user", "\n\n".join(sections)),
        ]
        messages.extend(self._recent_transcript(state))
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
            "objective": state.objective,
            "phase": state.phase,
            "profile": asdict(state.profile) if state.profile else None,
            "workspace_revision": revision,
            "changed_files": self.tools.changed_files(),
            "active_work_item": asdict(state.work_item(state.active_work_item_id))
            if state.work_item(state.active_work_item_id)
            else None,
            "accepted_work_items": [
                asdict(item) for item in state.work_items if item.status == "accepted"
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
        recent_evidence = self.store.evidence()[-12:]
        compact = {
            "run_id": state.run_id,
            "objective": state.objective,
            "phase": state.phase,
            "status": state.status,
            "profile": asdict(state.profile) if state.profile else None,
            "active_work_item": asdict(active) if active else None,
            "work_items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "status": item.status,
                    "dependencies": item.dependencies,
                    "mandatory": item.mandatory,
                    "acceptance": item.acceptance,
                    "evidence_ids": item.evidence_ids[-5:],
                    "verification_commands": item.verification_commands,
                    "failure_signatures": item.failure_signatures[-3:],
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
                    "summary": item.summary,
                    "command": item.command,
                    "exit_code": item.exit_code,
                    "duration_seconds": item.duration_seconds,
                    "raw_log": item.raw_log,
                    "data": item.data,
                }
                for item in recent_evidence
            ],
        }
        return "CANONICAL RUN STATE\n" + json.dumps(
            compact, ensure_ascii=False, indent=2
        )

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
                if (
                    role in {"user", "assistant"}
                    and metadata.get("kind") != "controller_context"
                ):
                    messages.append(ChatMessage(role, str(value.get("content", ""))))
                    if len(messages) >= self.transcript_tail:
                        break
            except json.JSONDecodeError:
                continue
        return list(reversed(messages))
