from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .context import ContextManager
from .model import ModelClient, ModelError, ModelResponse
from .models import RunState
from .store import StateStore


class ActionError(ValueError):
    pass


@dataclass(slots=True)
class AgentDecision:
    action: dict[str, Any]
    response: ModelResponse
    prompt_tokens_estimate: int


class CodingAgent:
    def __init__(
        self, model: ModelClient, context: ContextManager, store: StateStore
    ) -> None:
        self.model = model
        self.context = context
        self.store = store

    def decide(
        self,
        state: RunState,
        action_contract: str,
        *,
        core_skill: str | None = None,
        playbook: str | None = None,
    ) -> AgentDecision:
        messages = self.context.build_messages(
            state, action_contract, core_skill=core_skill, playbook=playbook
        )
        estimate = self.context.estimate_tokens(messages)
        try:
            response = self.model.complete(messages)
        except ModelError:
            raise
        self.store.append_transcript(
            "user",
            messages[1].content,
            kind="controller_context",
            prompt_tokens_estimate=estimate,
        )
        self.store.append_transcript(
            "assistant",
            response.content,
            model=self.model.model,
            usage=response.usage,
            finish_reason=response.finish_reason,
        )
        return AgentDecision(self.parse_action(response.content), response, estimate)

    @staticmethod
    def parse_action(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as error:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise ActionError(
                    f"model did not return a JSON action: {error}"
                ) from error
            try:
                value = json.loads(text[start : end + 1])
            except json.JSONDecodeError as nested:
                raise ActionError(f"invalid JSON action: {nested}") from nested
        if not isinstance(value, dict) or not isinstance(value.get("action"), str):
            raise ActionError(
                "action must be a JSON object with a string 'action' field"
            )
        return value
