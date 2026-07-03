"""Free-tier LLM wrapper — BOOT-06.

Every agent goes through this module. Wraps OpenRouter's OpenAI-compatible
`POST /chat/completions` endpoint with:

- Two-tier routing (`fast` / `thorough`) via `Config.LLM_TEXT_MODEL_*`.
- Structured JSON output enforcement via `response_model`.
- Per-model RPM rate limiting (see `app.utils.rate_limit`).
- Retry-with-backoff on 5xx / 429 / JSON-parse / structured-validation failures.
- Trace-backend routing (see `app.utils.tracing`).
- Row-per-call insertion into `llm_calls` for benchmarking (see OPT-05).

`cache_key` is accepted but the lookup is a no-op today; OPT-05 wires the
exact + semantic cache. Callers should already pass `cache_key` on
low-fidelity classifier calls so OPT-05 lights up automatically.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.db.base import get_session_factory
from app.db.models.llm_call import LlmCall
from app.utils.config import Config
from app.utils.rate_limit import acquire as rate_limit_acquire

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Non-retryable LLM failure (4xx that isn't 429)."""


class LLMRetryableError(LLMError):
    """Retryable LLM failure: transport error, 5xx, 429, or JSON/schema failure."""


@dataclass
class Message:
    role: Literal["system", "user", "assistant"]
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class LLMResponse(BaseModel):
    content: str
    parsed: Any | None = None
    model: str
    tier: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int
    cache_hit: bool = False
    cache_source: str | None = None


class LLMClient:
    """Async wrapper around OpenRouter's chat completions endpoint.

    Typical usage: one instance per process, injected as a FastAPI dependency
    or module-global. Tests can pass a custom `httpx.AsyncClient`.
    """

    def __init__(self, *, http_client: httpx.AsyncClient | None = None):
        self._http = http_client
        self._own_http = http_client is None

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=Config.OPENROUTER_BASE_URL,
                timeout=60.0,
                headers={
                    "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://github.com/CoderUzumaki/Lumen",
                    "X-Title": "Lumen",
                },
            )
        return self._http

    async def aclose(self) -> None:
        if self._http is not None and self._own_http:
            await self._http.aclose()
            self._http = None

    async def complete(
        self,
        messages: list[Message],
        *,
        tier: Literal["fast", "thorough"] = "thorough",
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        user_id: UUID | None = None,
        cache_key: str | None = None,
        agent_name: str = "adhoc",
    ) -> LLMResponse:
        started = time.monotonic()
        model = self._model_for_tier(tier)

        if cache_key is not None:
            cached = await self._cache_lookup(cache_key, messages)
            if cached is not None:
                # Timestamp against wall-clock so caller sees the true latency.
                cached_latency = int((time.monotonic() - started) * 1000)
                cached = cached.model_copy(update={"latency_ms": cached_latency})
                await self._record_call(cached, user_id=user_id, agent_name=agent_name)
                return cached

        await rate_limit_acquire(model)

        request_body = self._build_request(
            model=model,
            messages=messages,
            response_model=response_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        content, usage = await self._call_with_retry(request_body, response_model)

        parsed: Any | None = None
        if response_model is not None:
            parsed = response_model.model_validate_json(content)

        latency_ms = int((time.monotonic() - started) * 1000)
        response = LLMResponse(
            content=content,
            parsed=parsed,
            model=model,
            tier=tier,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_ms=latency_ms,
        )
        await self._record_call(response, user_id=user_id, agent_name=agent_name)
        return response

    # -- internals ------------------------------------------------------------

    def _model_for_tier(self, tier: str) -> str:
        if tier == "fast":
            return Config.LLM_TEXT_MODEL_FAST
        return Config.LLM_TEXT_MODEL_THOROUGH

    def _build_request(
        self,
        *,
        model: str,
        messages: list[Message],
        response_model: type[BaseModel] | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        payload_messages: list[dict[str, str]] = [m.as_dict() for m in messages]
        body: dict[str, Any] = {
            "model": model,
            "messages": payload_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_model is not None:
            body["response_format"] = {"type": "json_object"}
            schema = response_model.model_json_schema()
            schema_prompt = (
                "You MUST reply with a single JSON object matching this schema, "
                "with no prose, no markdown, and no code fences:\n"
                + json.dumps(schema)
            )
            body["messages"] = [{"role": "system", "content": schema_prompt}, *payload_messages]
        return body

    async def _call_with_retry(
        self,
        body: dict[str, Any],
        response_model: type[BaseModel] | None,
    ) -> tuple[str, dict]:
        retrying = AsyncRetrying(
            reraise=True,
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.25, min=0.1, max=4.0),
            retry=retry_if_exception_type(LLMRetryableError),
        )
        async for attempt in retrying:
            with attempt:
                content, usage = await self._one_call(body)
                # Validate structured output inside the retry envelope so a
                # bad JSON reply triggers another attempt.
                if response_model is not None:
                    try:
                        response_model.model_validate_json(content)
                    except ValidationError as e:
                        raise LLMRetryableError(
                            f"structured output validation failed: {e}"
                        ) from e
                return content, usage
        raise LLMRetryableError("exhausted retries")  # pragma: no cover — reraise=True

    async def _one_call(self, body: dict[str, Any]) -> tuple[str, dict]:
        http = await self._get_http()
        try:
            resp = await http.post("/chat/completions", json=body)
        except httpx.HTTPError as e:
            raise LLMRetryableError(f"transport error: {e}") from e

        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise LLMRetryableError(
                f"upstream {resp.status_code}: {resp.text[:200]}"
            )
        if resp.status_code >= 400:
            raise LLMError(f"upstream {resp.status_code}: {resp.text[:200]}")

        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            raise LLMRetryableError(f"invalid JSON body: {e}") from e

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMRetryableError(f"malformed response shape: {e}") from e
        usage = data.get("usage") or {}
        return content, usage

    async def _cache_lookup(
        self,
        cache_key: str,
        messages: list[Message],
    ) -> LLMResponse | None:
        """Return a cached `LLMResponse` or `None`.

        BOOT-06 stub — always `None`. OPT-05 replaces this with the exact +
        semantic lookup against the `llm_cache` table. Tests can monkey-patch
        this method to simulate a hit.
        """
        return None

    async def _record_call(
        self,
        response: LLMResponse,
        *,
        user_id: UUID | None,
        agent_name: str,
    ) -> None:
        try:
            factory = get_session_factory()
        except Exception:  # engine not configured (e.g. tests without DB)
            log.debug("llm_calls: session factory unavailable, skipping record")
            return
        try:
            async with factory() as session:
                session.add(
                    LlmCall(
                        id=uuid.uuid4(),
                        agent_name=agent_name,
                        tier=response.tier,
                        model=response.model,
                        prompt_tokens=response.prompt_tokens,
                        completion_tokens=response.completion_tokens,
                        latency_ms=response.latency_ms,
                        cache_hit=response.cache_hit,
                        cache_source=response.cache_source,
                        user_id=user_id,
                    )
                )
                await session.commit()
        except Exception:
            log.exception("failed to record llm_call")


# ING-07 lands the real `EmbeddingClient` in `app.utils.embeddings`. Re-export
# it here so existing `from app.utils.llm import EmbeddingClient` imports keep
# working. Behavior is now backed by local sentence-transformers.
from app.utils.embeddings import EmbeddingClient  # noqa: E402, F401
