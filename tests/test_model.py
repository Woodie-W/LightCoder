from __future__ import annotations

import json
from io import BytesIO
import time
import urllib.error
import urllib.request

import pytest

from lightcoder.model import ChatMessage, ModelError, OpenAICompatibleClient


def test_openai_compatible_request_omits_client_output_limit(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {"content": '{"action":"read"}'},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {},
                }
            ).encode()

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = OpenAICompatibleClient(
        base_url="https://example.invalid/v1",
        model="test-model",
        api_key="test-key",
    )

    client.complete([ChatMessage("user", "return one action")])

    assert "max_tokens" not in captured["body"]


def test_model_request_timeout_is_optional_and_can_follow_remaining_wall_time(
    monkeypatch,
) -> None:
    timeouts: list[float | None] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {"content": '{"action":"read"}'},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {},
                }
            ).encode()

    def fake_urlopen(request, *args, **kwargs):
        timeouts.append(kwargs.get("timeout"))
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = OpenAICompatibleClient(
        base_url="https://example.invalid/v1",
        model="test-model",
        api_key="test-key",
    )

    client.complete([ChatMessage("user", "unbounded")])
    client.complete([ChatMessage("user", "bounded")], timeout_seconds=492.0)

    assert timeouts[0] is None
    assert timeouts[1] == pytest.approx(492.0, abs=0.01)


def test_openai_compatible_client_round_trips_native_tool_calls(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "read",
                                            "arguments": '{"path":"README.md"}',
                                        },
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                    "usage": {},
                }
            ).encode()

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode())
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = OpenAICompatibleClient(
        base_url="https://example.invalid/v1", model="test-model", api_key="test-key"
    )
    response = client.complete(
        [
            ChatMessage("assistant", None, tool_calls=[{"id": "old", "type": "function", "function": {"name": "read", "arguments": "{}"}}]),
            ChatMessage("tool", "{}", tool_call_id="old", name="read"),
            ChatMessage("user", "continue"),
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "read",
                    "description": "read a file",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    )

    body = captured["body"]
    assert body["tool_choice"] == "auto"
    assert body["tools"][0]["function"]["name"] == "read"
    assert body["messages"][0]["tool_calls"][0]["id"] == "old"
    assert body["messages"][1]["tool_call_id"] == "old"
    assert response.finish_reason == "tool_calls"
    assert response.tool_calls[0]["function"]["name"] == "read"


def test_model_client_retries_429_using_retry_after(monkeypatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {"choices": [{"message": {"content": "ok"}}], "usage": {}}
            ).encode()

    def fake_urlopen(request, timeout=None):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {"Retry-After": "7"},
                BytesIO(b"temporary rate limit"),
            )
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(time, "sleep", sleeps.append)
    client = OpenAICompatibleClient(base_url="https://example.invalid/v1")

    assert client.complete([ChatMessage("user", "continue")]).content == "ok"
    assert attempts == 2
    assert sleeps == [7.0]


def test_model_client_does_not_retry_permanent_http_errors(monkeypatch) -> None:
    attempts = 0

    def fake_urlopen(request, timeout=None):
        nonlocal attempts
        attempts += 1
        raise urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", {}, BytesIO(b"bad key")
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = OpenAICompatibleClient(base_url="https://example.invalid/v1")

    with pytest.raises(ModelError, match="HTTP 401"):
        client.complete([ChatMessage("user", "continue")])
    assert attempts == 1


def test_model_client_does_not_wait_past_request_deadline(monkeypatch) -> None:
    sleeps: list[float] = []

    def fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            {"Retry-After": "10"},
            BytesIO(b"temporary rate limit"),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(time, "sleep", sleeps.append)
    client = OpenAICompatibleClient(base_url="https://example.invalid/v1")

    with pytest.raises(ModelError, match="insufficient remaining time"):
        client.complete([ChatMessage("user", "continue")], timeout_seconds=1.0)
    assert sleeps == []
