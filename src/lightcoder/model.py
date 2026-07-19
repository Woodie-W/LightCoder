from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


class ModelError(RuntimeError):
    pass


@dataclass(slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(slots=True)
class ModelResponse:
    content: str
    reasoning: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = ""
    provider_payload: dict[str, Any] = field(default_factory=dict)


class ModelClient(Protocol):
    model: str

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        timeout_seconds: float | None = None,
    ) -> ModelResponse: ...


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("LIGHTCODER_BASE_URL") or "https://api.deepseek.com"
        ).rstrip("/")
        self.model = model or os.getenv("LIGHTCODER_MODEL") or "deepseek-chat"
        self.api_key = (
            api_key if api_key is not None else os.getenv("LIGHTCODER_API_KEY", "")
        )
        self.timeout_seconds = timeout_seconds
        self.extra_body = extra_body or {}

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        timeout_seconds: float | None = None,
    ) -> ModelResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "stream": False,
        }
        body.update(self.extra_body)
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "LightCoder/0.2",
            },
            method="POST",
        )
        started = time.monotonic()
        effective_timeout = (
            timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        )
        try:
            if effective_timeout is None:
                opened = urllib.request.urlopen(request)
            else:
                opened = urllib.request.urlopen(
                    request, timeout=max(1.0, effective_timeout)
                )
            with opened as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise ModelError(f"model HTTP {error.code}: {detail[:2_000]}") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ModelError(
                f"model request failed after {time.monotonic() - started:.1f}s: {error}"
            ) from error
        try:
            choice = payload["choices"][0]
            message = choice["message"]
            content = message.get("content") or ""
            reasoning = message.get("reasoning_content") or ""
            usage = {
                str(key): int(value)
                for key, value in payload.get("usage", {}).items()
                if isinstance(value, int)
            }
            return ModelResponse(
                content=str(content),
                reasoning=str(reasoning),
                usage=usage,
                finish_reason=str(choice.get("finish_reason", "")),
                provider_payload=payload,
            )
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError(
                f"invalid model response: {str(payload)[:2_000]}"
            ) from error
