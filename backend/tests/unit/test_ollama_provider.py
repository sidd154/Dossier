import json

import httpx
import pytest

from app.core.exceptions import UpstreamError
from app.llm.ollama import OllamaProvider
from app.llm.provider import ChatMessage

_REAL_CLIENT = httpx.AsyncClient


def _patch(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    transport = httpx.MockTransport(handler)

    def factory(*_args: object, **_kwargs: object) -> httpx.AsyncClient:
        return _REAL_CLIENT(transport=transport)

    monkeypatch.setattr("app.llm.ollama.httpx.AsyncClient", factory)


async def test_complete_sends_the_expected_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json={"message": {"content": "  Hello team  "}})

    _patch(monkeypatch, handler)
    provider = OllamaProvider(base_url="http://ollama:11434", model="test-model")

    result = await provider.complete(
        [ChatMessage(role="system", content="sys"), ChatMessage(role="user", content="u")],
        temperature=0.1,
        max_tokens=250,
    )

    assert result == "Hello team"
    assert captured[0]["model"] == "test-model"
    assert captured[0]["stream"] is False
    assert captured[0]["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u"},
    ]
    assert captured[0]["options"]["temperature"] == 0.1
    assert captured[0]["options"]["num_predict"] == 250


async def test_http_failure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, lambda _request: httpx.Response(500, text="boom"))
    provider = OllamaProvider(base_url="http://ollama:11434", model="m")

    with pytest.raises(UpstreamError):
        await provider.complete([ChatMessage(role="user", content="hi")])


async def test_empty_response_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        lambda _request: httpx.Response(200, json={"message": {"content": "   "}}),
    )
    provider = OllamaProvider(base_url="http://ollama:11434", model="m")

    with pytest.raises(UpstreamError):
        await provider.complete([ChatMessage(role="user", content="hi")])


async def test_connection_error_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    _patch(monkeypatch, handler)
    provider = OllamaProvider(base_url="http://ollama:11434", model="m")

    with pytest.raises(UpstreamError):
        await provider.complete([ChatMessage(role="user", content="hi")])
