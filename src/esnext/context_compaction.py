from __future__ import annotations

import json, os, uuid

from langgraph.checkpoint.memory import MemorySaver

from .backends import log_step
from .data_models import AgentSession
from .events import EventBus
from .model_config import invoke_plain_text

SUMMARY_PROMPT = """You are the previous agent handing off a long-running task to a new agent.
Read the full history and write a concise but concrete handoff.
Preserve the major actions completed, important information learned, difficult problems already investigated, useful files and paths, commands or experiments that mattered, current status, and the next useful steps.
If the history already contains an older handoff summary, merge it without duplication."""

QUESTION_PROMPT = """You are the new agent taking over the same task.
You can see the original task, the current handoff summary, and the recent context, but not the full history.
Ask up to 5 concrete questions about missing details that would matter for continuing effectively and safely.
Focus on exact paths, commands, errors, results, environment state, unresolved blockers, and what has already been tried.
Return 'None.' if the summary is already sufficient."""

ANSWER_PROMPT = """You are recovering missing details for a handoff.
Answer the takeover questions using only the full transcript as evidence.
Be concise. If the transcript does not support an answer, say 'Unknown.'
Return short bullet answers aligned with the questions."""

HANDOFF_PROMPT = """Build the final handoff for the next agent.
Use the original task, the handoff summary, the review questions, the recovered answers, and the recent context.
Return short Markdown with exactly these sections:
## Goal
## Done
## Facts
## Open Issues
## Next Steps"""

_CONTEXT_ERROR_MARKERS = (
    "context length",
    "maximum context length",
    "context_length_exceeded",
    "context window",
    "too many tokens",
    "prompt is too long",
    "maximum input tokens",
)


def maybe_compact_session(
    session: AgentSession, *, event_bus: EventBus | None = None, event_layer: str = "L3", event_data: dict[str, object] | None = None, force: bool = False,
) -> bool:
    if session.handoff_pending or compact_chars() <= 0 or not session.last_result or not session.last_result.messages:
        return False
    transcript = transcript_text(session)
    if not force and len(transcript) < compact_chars():
        return False
    apply_compaction(session, compact_history_text(session, transcript), event_bus=event_bus, event_layer=event_layer, event_data=event_data)
    return True


def compact_chars() -> int:
    raw = os.getenv("LIGHTSCIENTIST_COMPACT_CHARS", "24000").strip()
    return int(raw) if raw.isdigit() else 24000


def transcript_text(session: AgentSession) -> str:
    return json.dumps(session.last_result.messages, ensure_ascii=False)


def compact_history_text(session: AgentSession, transcript: str) -> str:
    task, recent = _task_and_recent(session)
    summary = _ask(session, SUMMARY_PROMPT, f"Original task:\n{task}\n\nFull transcript:\n{transcript}")
    questions = _ask(session, QUESTION_PROMPT, f"Original task:\n{task}\n\nHandoff summary:\n{summary}\n\nRecent context:\n{recent}")
    if questions.strip().lower() in {"none.", "none"}:
        return _ask(session, HANDOFF_PROMPT, f"Original task:\n{task}\n\nSummary:\n{summary}\n\nRecent context:\n{recent}")
    answers = _ask(session, ANSWER_PROMPT, f"Questions:\n{questions}\n\nFull transcript:\n{transcript}")
    return _ask(session, HANDOFF_PROMPT, f"Original task:\n{task}\n\nSummary:\n{summary}\n\nQuestions:\n{questions}\n\nAnswers:\n{answers}\n\nRecent context:\n{recent}")


def apply_compaction(
    session: AgentSession, summary: str, *, event_bus: EventBus | None = None, event_layer: str = "L3", event_data: dict[str, object] | None = None,
) -> None:
    session.memory_summary = summary
    session.checkpointer = MemorySaver()
    session.thread_id = uuid.uuid4().hex[:8]
    session.resume_mode = "message"
    session.compaction_count += 1
    session.handoff_pending = True
    log_step(session.log_path, "context-compacted", f"count: {session.compaction_count}\nthread_id: {session.thread_id}\nsummary:\n{session.memory_summary}")
    emit_compaction_event(session, event_bus=event_bus, event_layer=event_layer, event_data=event_data)


def handoff_input(session: AgentSession, user_input: str) -> str:
    return f"""Previous work summary:

{session.memory_summary}

New input:
{user_input}

Continue the same task. Prefer current workspace state over stale details if they conflict."""


def is_context_limit_error(error: Exception) -> bool:
    text = str(error).lower()
    return any(marker in text for marker in _CONTEXT_ERROR_MARKERS)


def _ask(session: AgentSession, system_prompt: str, user_prompt: str) -> str:
    return invoke_plain_text(system_prompt, user_prompt, model=session.model).strip()


def _task_and_recent(session: AgentSession) -> tuple[str, str]:
    msgs = session.last_result.messages
    task = next((str(msg.get("content", "")).strip() for msg in msgs if msg.get("role") == "user" and str(msg.get("content", "")).strip()), "")
    recent = json.dumps(msgs[-8:], ensure_ascii=False)
    return task or "Unknown.", recent


def emit_compaction_event(
    session: AgentSession, *, event_bus: EventBus | None = None, event_layer: str = "L3", event_data: dict[str, object] | None = None,
) -> None:
    if not event_bus:
        return
    payload = dict(event_data or {})
    event_bus.emit(
        event_layer,
        "agent_context_compacted",
        f"Context compacted #{session.compaction_count}.",
        task_id=str(payload.pop("task_id", "")),
        agent_id=str(payload.pop("agent_id", "")),
        stage=str(payload.pop("stage", "")),
        session_id=session.session_id,
        thread_id=session.thread_id,
        **payload,
    )
