"""Klient lokalnej Ollamy za protokołem `LlmClient` (projekt LLM §5.4).

Testy podstawiają własną implementację protokołu, więc reszta pipeline'u nie zależy
od HTTP. Wszystkie błędy transportu i serwera mapujemy na dwa wyjątki domenowe:
`LlmTimeoutError` i `LlmUnavailableError`.
"""

import time
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypedDict

import httpx
from fastapi import Request

from app.core.config import Settings

KEEP_ALIVE = "30m"
TAGS_TIMEOUT_S = 3.0


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class LlmReply:
    content: str
    prompt_tokens: int
    output_tokens: int
    duration_ms: int


class LlmError(Exception):
    """Błąd wywołania modelu."""


class LlmTimeoutError(LlmError):
    """Model nie odpowiedział w zadanym czasie."""


class LlmUnavailableError(LlmError):
    """Serwer modelu nieosiągalny, zwrócił błąd albo nie ma pobranego modelu."""


class LlmClient(Protocol):
    async def chat(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        timeout_s: float,
    ) -> LlmReply: ...

    async def list_models(self) -> set[str]: ...

    async def warm_up(self, model: str) -> None: ...

    async def aclose(self) -> None: ...


class OllamaClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._settings = settings
        self._http = httpx.AsyncClient(base_url=settings.llm_base_url, transport=transport)

    async def chat(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        timeout_s: float,
    ) -> LlmReply:
        body = {
            "model": model,
            "messages": messages,
            "format": schema,
            "stream": False,
            "think": False,
            "keep_alive": KEEP_ALIVE,
            "options": {
                "temperature": self._settings.llm_temperature,
                "seed": self._settings.llm_seed,
                "num_ctx": self._settings.llm_num_ctx,
            },
        }
        started = time.perf_counter()
        data = await self._request("POST", "/api/chat", timeout_s, json=body)
        duration_ms = int((time.perf_counter() - started) * 1000)
        try:
            content = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LlmUnavailableError("odpowiedź Ollamy bez message.content") from exc
        if not isinstance(content, str):
            raise LlmUnavailableError("message.content nie jest tekstem")
        return LlmReply(
            content=content,
            prompt_tokens=int(data.get("prompt_eval_count", 0)),
            output_tokens=int(data.get("eval_count", 0)),
            duration_ms=duration_ms,
        )

    async def list_models(self) -> set[str]:
        data = await self._request("GET", "/api/tags", TAGS_TIMEOUT_S)
        models = data.get("models", [])
        return {m["name"] for m in models if isinstance(m, dict) and "name" in m}

    async def warm_up(self, model: str) -> None:
        body = {"model": model, "messages": [], "keep_alive": KEEP_ALIVE}
        await self._request("POST", "/api/chat", self._settings.llm_timeout_s, json=body)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(
        self, method: str, path: str, timeout_s: float, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = await self._http.request(method, path, json=json, timeout=timeout_s)
        except httpx.TimeoutException as exc:
            raise LlmTimeoutError(f"przekroczono {timeout_s:.0f} s ({path})") from exc
        except httpx.TransportError as exc:
            raise LlmUnavailableError(f"brak połączenia z serwerem modelu: {exc}") from exc
        if response.status_code >= 400:
            raise LlmUnavailableError(
                f"HTTP {response.status_code} z {path}: {response.text[:200]}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise LlmUnavailableError(f"niepoprawny JSON z {path}") from exc
        if not isinstance(data, dict):
            raise LlmUnavailableError(f"nieoczekiwana odpowiedź z {path}")
        return data


def get_llm_client(request: Request) -> LlmClient:
    """Zależność FastAPI: klient modelu utworzony przy starcie aplikacji."""
    client: LlmClient = request.app.state.llm_client
    return client
