import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.pipeline.llm_client import (
    LlmReply,
    LlmTimeoutError,
    LlmUnavailableError,
    OllamaClient,
)

SCHEMA: dict[str, Any] = {"type": "object", "properties": {"title": {"type": "string"}}}
MESSAGES: list[Any] = [{"role": "user", "content": "x"}]


def _settings() -> Settings:
    return Settings(app_env="development", auth_enabled=False, _env_file=None)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> OllamaClient:
    return OllamaClient(_settings(), transport=httpx.MockTransport(handler))


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "message": {"content": '{"title": "x"}'},
            "prompt_eval_count": 1592,
            "eval_count": 546,
        },
    )


async def _chat(client: OllamaClient) -> LlmReply:
    return await client.chat(model="qwen3:8b", messages=MESSAGES, schema=SCHEMA, timeout_s=10)


async def test_chat_sends_contract_body() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok(request)

    await _chat(_client(handler))
    assert seen[0].url.path == "/api/chat"
    body = json.loads(seen[0].content)
    assert body["think"] is False and body["stream"] is False
    assert body["format"] == SCHEMA and body["model"] == "qwen3:8b"
    assert body["messages"] == MESSAGES and body["keep_alive"] == "30m"
    assert body["options"] == {"temperature": 0, "seed": 42, "num_ctx": 16384}


async def test_chat_parses_reply() -> None:
    reply = await _chat(_client(_ok))
    assert reply.content == '{"title": "x"}'
    assert (reply.prompt_tokens, reply.output_tokens) == (1592, 546)
    assert reply.duration_ms >= 0


async def test_missing_token_counts_default_to_zero() -> None:
    reply = await _chat(_client(lambda r: httpx.Response(200, json={"message": {"content": "{}"}})))
    assert (reply.prompt_tokens, reply.output_tokens) == (0, 0)


async def test_timeout_raises_llm_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LlmTimeoutError):
        await _chat(_client(handler))


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404, json={"error": "model 'qwen3:4b' not found"}),
        httpx.Response(500, json={"error": "boom"}),
        httpx.Response(200, text="not json"),
    ],
)
async def test_bad_responses_raise_unavailable(response: httpx.Response) -> None:
    with pytest.raises(LlmUnavailableError):
        await _chat(_client(lambda r: response))


async def test_missing_model_raises_unavailable() -> None:
    client = _client(lambda r: httpx.Response(404, json={"error": "model 'qwen3:4b' not found"}))
    with pytest.raises(LlmUnavailableError, match="qwen3:4b"):
        await _chat(client)


async def test_connection_error_raises_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LlmUnavailableError):
        await _chat(_client(handler))


async def test_list_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen3:8b"}, {"name": "qwen3:4b"}]})

    assert await _client(handler).list_models() == {"qwen3:8b", "qwen3:4b"}


async def test_warm_up_posts_empty_chat() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"done": True})

    await _client(handler).warm_up("qwen3:4b")
    assert seen == [{"model": "qwen3:4b", "messages": [], "keep_alive": "30m"}]
