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
        timeout_seconds: float | None = None,
    ) -> AgentDecision:
        messages = self.context.build_messages(
            state, action_contract, core_skill=core_skill, playbook=playbook
        )
        estimate = self.context.estimate_tokens(messages)
        try:
            response = self.model.complete(messages, timeout_seconds=timeout_seconds)
        except ModelError:
            raise
        self.store.append_transcript(
            "user",
            messages[-1].content,
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
        try:
            action = self.parse_action(response.content)
        except ActionError as error:
            if response.finish_reason == "length":
                raise ActionError(
                    "provider exhausted its own output capacity before returning "
                    "a complete executable action"
                ) from error
            raise
        return AgentDecision(action, response, estimate)

    @staticmethod
    def parse_action(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```json"):
            text = re.sub(r"^```json\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        parse_error: json.JSONDecodeError | None = None
        try:
            value = json.loads(text)
        except json.JSONDecodeError as error:
            parse_error = error
            start = text.find("{")
            if start >= 0:
                try:
                    # Some providers occasionally prepend tool-call markup or emit
                    # multiple JSON objects despite the one-action contract. Execute
                    # the first complete object deterministically instead of losing
                    # an otherwise valid tool turn to trailing text.
                    value, _ = json.JSONDecoder().raw_decode(text[start:])
                except json.JSONDecodeError:
                    value = None
            else:
                value = None
        if isinstance(value, dict) and isinstance(value.get("action"), str):
            return value

        # DeepSeek sometimes emits an otherwise valid shell action as Markdown
        # despite the JSON-only contract. Shell execution is already an allowed
        # agent capability, so recover only explicitly tagged shell fences and
        # preserve their contents verbatim in one deterministic bash action.
        shell_blocks = [
            block.strip()
            for block in re.findall(
                r"```(?:bash|sh|shell)\s*\n(.*?)```", content, flags=re.I | re.S
            )
            if block.strip()
        ]
        if shell_blocks:
            return {
                "action": "bash",
                "command": "\n".join(shell_blocks),
                "cwd": ".",
                "background": False,
                "rationale": "Recovered explicitly fenced shell action",
            }
        xml_action = CodingAgent._parse_xml_tool_actions(content)
        if xml_action is not None:
            return xml_action
        relaxed_bash = CodingAgent._parse_relaxed_json_bash(content)
        if relaxed_bash is not None:
            return relaxed_bash
        relaxed_write = CodingAgent._parse_relaxed_json_write(content)
        if relaxed_write is not None:
            return relaxed_write
        if not isinstance(value, dict) or not isinstance(value.get("action"), str):
            if parse_error is not None:
                raise ActionError(
                    f"model did not return a JSON action: {parse_error}"
                ) from parse_error
            raise ActionError(
                "action must be a JSON object with a string 'action' field"
            )
        return value

    @staticmethod
    def _parse_xml_tool_actions(content: str) -> dict[str, Any] | None:
        """Recover DeepSeek's occasional XML-like shell action format."""
        tags = re.findall(r"<action\s+(.*?)/>", content, flags=re.I | re.S)
        children: list[dict[str, Any]] = []
        for attributes in tags:
            kind_match = re.search(r'\b(?:action|type)="([^"]+)"', attributes)
            if not kind_match or kind_match.group(1) != "bash":
                return None
            # DeepSeek may leave quotes inside command unescaped. The following
            # field boundary is more reliable than treating this as strict XML.
            command_match = re.search(
                r'\bcommand="(.*?)"\s+(?:cwd|timeout_seconds|background|rationale)="',
                attributes,
                flags=re.S,
            )
            if not command_match:
                return None
            child: dict[str, Any] = {
                "action": "bash",
                "command": command_match.group(1),
            }
            cwd_match = re.search(r'\bcwd="([^"]*)"', attributes)
            timeout_match = re.search(r'\btimeout_seconds="([0-9.]+)"', attributes)
            background_match = re.search(r'\bbackground="(true|false)"', attributes)
            rationale_match = re.search(r'\brationale="([^"]*)"', attributes)
            if cwd_match:
                child["cwd"] = cwd_match.group(1)
            if timeout_match:
                child["timeout_seconds"] = float(timeout_match.group(1))
            if background_match:
                child["background"] = background_match.group(1) == "true"
            if rationale_match:
                child["rationale"] = rationale_match.group(1)
            children.append(child)
        if not children:
            return None
        if len(children) == 1 and "<batch" not in content.lower():
            return children[0]
        return {
            "action": "batch",
            "actions": children,
            "rationale": "Recovered XML-like shell actions",
        }

    @staticmethod
    def _parse_relaxed_json_bash(content: str) -> dict[str, Any] | None:
        """Recover a bash JSON action containing unescaped multiline quotes."""
        if not re.search(r'"action"\s*:\s*"bash"', content):
            return None
        command_match = re.search(
            r'"command"\s*:\s*"(.*?)"\s*,\s*"(?:cwd|timeout_seconds|background|rationale)"\s*:',
            content,
            flags=re.S,
        )
        if not command_match:
            return None
        command = (
            command_match.group(1)
            .replace(r"\n", "\n")
            .replace(r'\"', '"')
            .replace(r"\\", "\\")
        )
        action: dict[str, Any] = {
            "action": "bash",
            "command": command,
            "rationale": "Recovered relaxed multiline bash JSON",
        }
        cwd_match = re.search(r'"cwd"\s*:\s*"([^"]*)"', content)
        timeout_match = re.search(r'"timeout_seconds"\s*:\s*([0-9.]+)', content)
        background_match = re.search(r'"background"\s*:\s*(true|false)', content)
        if cwd_match:
            action["cwd"] = cwd_match.group(1)
        if timeout_match:
            action["timeout_seconds"] = float(timeout_match.group(1))
        if background_match:
            action["background"] = background_match.group(1) == "true"
        return action

    @staticmethod
    def _parse_relaxed_json_write(content: str) -> dict[str, Any] | None:
        """Recover one fenced write action with literal multiline source text.

        Long source files occasionally make the provider emit a JSON-looking
        write action whose ``content`` field has raw newlines or inner quotes.
        Treat only a fenced, explicitly labelled write action this way.  The
        normal JSON parser remains authoritative for every other action.
        """
        fenced = re.findall(r"```json\s*\n(.*?)```", content, flags=re.I | re.S)
        for candidate in fenced:
            if not re.search(r'"action"\s*:\s*"write"', candidate):
                continue
            path_match = re.search(r'"path"\s*:\s*"((?:\\.|[^"\\])*)"', candidate)
            content_match = re.search(
                r'"content"\s*:\s*"(.*?)"\s*,?\s*"rationale"\s*:',
                candidate,
                flags=re.S,
            )
            rationale_match = re.search(
                r'"rationale"\s*:\s*"((?:\\.|[^"\\])*)"\s*}\s*$',
                candidate,
                flags=re.S,
            )
            if not path_match or not content_match or not rationale_match:
                continue
            try:
                path = json.loads(f'"{path_match.group(1)}"')
                rationale = json.loads(f'"{rationale_match.group(1)}"')
            except json.JSONDecodeError:
                continue
            raw_content = content_match.group(1)
            return {
                "action": "write",
                "path": path,
                "content": (
                    raw_content.replace(r"\n", "\n")
                    .replace(r'\"', '"')
                    .replace(r"\\", "\\")
                ),
                "rationale": rationale,
            }
        return None
