from __future__ import annotations

import json
import urllib.request

from lightcoder.model import ChatMessage, OpenAICompatibleClient


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

    assert timeouts == [None, 492.0]
