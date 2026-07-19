from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path

import pytest

from lightcoder.model import ChatMessage, ModelResponse


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


class ScriptedModel:
    model = "scripted-test"

    def __init__(self, actions: list[dict[str, object]]) -> None:
        self.actions = deque(actions)
        self.messages: list[list[ChatMessage]] = []

    def complete(
        self, messages: list[ChatMessage], *, timeout_seconds: float | None = None
    ) -> ModelResponse:
        self.messages.append(messages)
        if not self.actions:
            raise AssertionError("scripted model ran out of actions")
        return ModelResponse(json.dumps(self.actions.popleft()))


class CompletingModel:
    model = "completing-test"

    def __init__(self, workspace: Path, *, regime: str = "standard") -> None:
        self.workspace = workspace
        self.regime = regime
        self.calls = 0

    def complete(
        self, messages: list[ChatMessage], *, timeout_seconds: float | None = None
    ) -> ModelResponse:
        self.calls += 1
        prompt = "\n".join(message.content for message in messages)
        command_evidence = re.findall(
            r'"id": "(ev-[^"]+)"(?:(?!"id":).){0,1400}?"kind": "command"'
            r'(?:(?!"id":).){0,1400}?"exit_code": 0',
            prompt,
            re.S,
        )
        if "Return profile_task:" in prompt:
            action = {
                "action": "profile_task",
                "profile": {
                    "execution_regime": self.regime,
                    "primary_playbook": "generalist",
                    "estimated_horizon": "multi_hour"
                    if self.regime == "long_horizon"
                    else "short",
                    "validation_cost": "low",
                    "supports_partial_progress": True,
                    "requires_best_artifact": self.regime == "long_horizon",
                    "rationale": "one observable capability",
                },
            }
        elif "Return set_plan" in prompt:
            action = {
                "action": "set_plan",
                "work_items": [
                    {
                        "id": "W1",
                        "title": "Create marker",
                        "description": "Create a marker file",
                        "kind": "capability",
                        "playbook": "generalist",
                        "dependencies": [],
                        "mandatory": True,
                        "acceptance": ["test -f marker.txt"],
                        "verification_commands": ["test -f marker.txt"],
                    }
                ],
            }
        elif "Return final_delivery only" in prompt:
            action = {
                "action": "final_delivery",
                "summary": "marker delivered",
                "tests": ["test -f marker.txt"],
                "changed_files": ["marker.txt"],
                "risks": [],
            }
        elif "Run final integration checks" in prompt:
            final_commands = re.findall(
                r'"id": "(ev-[^"]+)"(?:(?!"id":).){0,1400}?"kind": "command"'
                r'(?:(?!"id":).){0,1400}?"work_item_id": null',
                prompt,
                re.S,
            )
            action = (
                {
                    "action": "final_verified",
                    "evidence_ids": [final_commands[-1]],
                    "summary": "pass",
                    "risks": [],
                }
                if final_commands
                else {"action": "bash", "command": "test -f marker.txt"}
            )
        elif '"status": "verifying"' in prompt:
            action = (
                {
                    "action": "accept_work_item",
                    "evidence_ids": [command_evidence[-1]],
                    "summary": "pass",
                }
                if command_evidence
                else {"action": "bash", "command": "test -f marker.txt"}
            )
        elif (
            '"action":"begin_final_verification"' in prompt
            and (self.workspace / "marker.txt").exists()
        ):
            action = {
                "action": "begin_final_verification",
                "rationale": "flat task is ready",
            }
        elif not (self.workspace / "marker.txt").exists():
            action = {"action": "write", "path": "marker.txt", "content": "ok\n"}
        else:
            action = {"action": "begin_verification", "rationale": "ready"}
        return ModelResponse(json.dumps(action))


@pytest.fixture
def skills_root() -> Path:
    return SKILLS
