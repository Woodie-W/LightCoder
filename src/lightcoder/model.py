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
    content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""

    def to_payload(self) -> dict[str, Any]:
        """Convert the durable internal representation to Chat Completions form."""
        payload: dict[str, Any] = {"role": self.role}
        if self.role == "assistant":
            payload["content"] = self.content
            if self.tool_calls:
                payload["tool_calls"] = self.tool_calls
        elif self.role == "tool":
            payload["content"] = self.content or ""
            payload["tool_call_id"] = self.tool_call_id
            if self.name:
                payload["name"] = self.name
        else:
            payload["content"] = self.content or ""
        return payload


@dataclass(slots=True)
class ModelResponse:
    content: str
    reasoning: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = ""
    provider_payload: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class ModelClient(Protocol):
    model: str

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        timeout_seconds: float | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> ModelResponse: ...


class OpenAICompatibleClient:
    """Small OpenAI-compatible client with bounded transient-failure retries.

    Retries belong at this transport boundary: they preserve the exact prompt
    and tool payload and never change controller policy.  A supplied timeout is
    an end-to-end budget, so retry sleeps and subsequent requests cannot extend
    the task's wall-clock allowance.
    """

    _MAX_TRANSIENT_RETRIES = 4
    _MAX_RETRY_DELAY_SECONDS = 60.0

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
        tools: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [message.to_payload() for message in messages],
            "stream": False,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
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
        deadline = (
            started + effective_timeout if effective_timeout is not None else None
        )
        last_error: Exception | None = None
        for attempt in range(self._MAX_TRANSIENT_RETRIES + 1):
            request_timeout = self._remaining_timeout(deadline)
            try:
                if request_timeout is None:
                    opened = urllib.request.urlopen(request)
                else:
                    opened = urllib.request.urlopen(request, timeout=request_timeout)
                with opened as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as error:
                last_error = error
                detail = error.read().decode("utf-8", errors="replace")
                if not self._is_transient_http_status(error.code):
                    raise ModelError(
                        f"model HTTP {error.code}: {detail[:2_000]}"
                    ) from error
                retry_after = self._retry_after_seconds(error)
                failure = f"model HTTP {error.code}: {detail[:2_000]}"
            except (urllib.error.URLError, TimeoutError) as error:
                last_error = error
                retry_after = None
                failure = (
                    "model request failed after "
                    f"{time.monotonic() - started:.1f}s: {error}"
                )

            if attempt >= self._MAX_TRANSIENT_RETRIES:
                raise ModelError(
                    f"{failure} (transient retries exhausted)"
                ) from last_error
            delay = retry_after if retry_after is not None else min(
                float(2**attempt), self._MAX_RETRY_DELAY_SECONDS
            )
            if not self._sleep_within_deadline(delay, deadline):
                raise ModelError(
                    f"{failure} (insufficient remaining time for retry)"
                ) from last_error
        else:  # pragma: no cover - the loop always breaks or raises.
            raise AssertionError("model request retry loop exited unexpectedly")
        try:
            choice = payload["choices"][0]
            message = choice["message"]
            content = message.get("content") or ""
            reasoning = message.get("reasoning_content") or ""
            tool_calls = message.get("tool_calls") or []
            if not isinstance(tool_calls, list):
                raise TypeError("message.tool_calls must be a list")
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
                tool_calls=[item for item in tool_calls if isinstance(item, dict)],
            )
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError(
                f"invalid model response: {str(payload)[:2_000]}"
            ) from error

    @staticmethod
    def _is_transient_http_status(status: int) -> bool:
        return status == 429 or status in {408, 409, 500, 502, 503, 504}

    @staticmethod
    def _retry_after_seconds(error: urllib.error.HTTPError) -> float | None:
        value = error.headers.get("Retry-After") if error.headers else None
        if value is None:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            return None

    @staticmethod
    def _remaining_timeout(deadline: float | None) -> float | None:
        if deadline is None:
            return None
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ModelError("model request deadline exhausted")
        return max(1.0, remaining)

    @staticmethod
    def _sleep_within_deadline(delay: float, deadline: float | None) -> bool:
        if deadline is not None and time.monotonic() + delay >= deadline:
            return False
        time.sleep(delay)
        return True
