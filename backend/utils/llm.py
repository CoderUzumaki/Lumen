"""OpenRouter chat-completion client for the Ask Lumen pipeline.

Every step of a chat answer (classify -> generate SQL -> write the answer) used
to call OpenRouter with its own copy of the request code and swallow failures
differently, so a dead API key surfaced as the provider's raw error text inside
the assistant's reply. This module is the one place that talks to the chat
endpoint and turns provider failures into a typed `LLMError`.
"""
from __future__ import annotations

import logging
import time

import requests

from config import Config

logger = logging.getLogger(__name__)

# Every configured free text model reasons by default (some at effort "high" or
# "xhigh"), and OpenRouter counts reasoning tokens against max_tokens. With the
# small max_tokens our callers use, reasoning alone exhausts the budget and the
# reply comes back empty. Same prompt, reasoning off: 0.9s instead of tens of
# seconds. Off is the default for every call; pass reasoning=None to opt out.
REASONING_OFF = {"enabled": False}


class LLMError(RuntimeError):
    """The LLM provider could not produce an answer. Branch on `kind`, not the message."""

    AUTH = "auth"  # key missing, invalid or revoked (OpenRouter says "User not found.")
    CREDITS = "insufficient_credits"  # paid model and no credits left
    RATE_LIMITED = "rate_limited"  # per-minute or daily free-tier cap
    CONFIG = "config"  # bad request, e.g. a model id that no longer exists
    UNAVAILABLE = "unavailable"  # timeout, network error, provider 5xx
    BAD_RESPONSE = "bad_response"  # 2xx but nothing usable in it

    # These fail every later call in the same request too, so callers must not
    # paper over them with a fallback.
    FATAL = frozenset({AUTH, CREDITS, RATE_LIMITED, CONFIG, UNAVAILABLE})

    def __init__(self, kind: str, detail: str, status: int | None = None):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail
        self.status = status

    @property
    def is_fatal(self) -> bool:
        return self.kind in self.FATAL


_STATUS_KIND = {
    400: LLMError.CONFIG,
    401: LLMError.AUTH,
    402: LLMError.CREDITS,
    403: LLMError.CONFIG,  # model not available to this key (e.g. restricted access)
    404: LLMError.CONFIG,
    408: LLMError.UNAVAILABLE,
    429: LLMError.RATE_LIMITED,
}


def _kind_for_status(status: int) -> str:
    if status in _STATUS_KIND:
        return _STATUS_KIND[status]
    return LLMError.UNAVAILABLE if status >= 500 else LLMError.BAD_RESPONSE


def _error_message(body: dict) -> str:
    err = body.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err)
    return str(err)


def _auth_hint() -> str:
    if "OPENROUTER_API_KEY" in Config.SHADOWED_ENV_KEYS:
        return (
            " OPENROUTER_API_KEY is set in your shell/system environment, which "
            "overrides backend/.env. Remove that variable or update it."
        )
    return " Check OPENROUTER_API_KEY in backend/.env."


def chat_completion(
    prompt: str | list,
    *,
    temperature: float = 0.0,
    max_tokens: int = 500,
    model: str | None = None,
    fallback_models: list[str] | None = None,
    reasoning: dict | None = REASONING_OFF,
    timeout: float = 60,
) -> str:
    """Send one user message to OpenRouter and return the reply text.

    `prompt` is plain text, or a list of content parts (text + image_url) for
    vision models.

    `reasoning` is sent as OpenRouter's `reasoning` request field (e.g.
    `{"effort": "low"}`); defaults to REASONING_OFF. Pass None to omit the
    field entirely and use the model's own default.

    Raises LLMError for any failure; never returns provider error text as if it
    were an answer. An empty or malformed reply is retried once: with the
    `openrouter/free` router the retry usually lands on a different model.
    """
    models = _model_chain(model, fallback_models)
    try:
        return _chat_completion_once(prompt, temperature, max_tokens, models, reasoning, timeout)
    except LLMError as e:
        if e.kind != LLMError.BAD_RESPONSE:
            raise
        logger.info("Retrying LLM call after unusable reply: %s", e.detail)
        return _chat_completion_once(prompt, temperature, max_tokens, models, reasoning, timeout)


def _model_chain(model: str | None, fallback_models: list[str] | None = None) -> list[str]:
    """Explicit model -> that one plus any explicit fallbacks. Otherwise the
    configured text model plus its fallbacks; OpenRouter moves down the list
    when a model errors, is rate-limited or has been retired. OpenRouter
    accepts at most 3."""
    if model:
        chain = [model, *(fallback_models or [])]
    else:
        chain = [Config.get_llm_text_model(), *Config.get_llm_text_fallback_models()]
    return list(dict.fromkeys(m for m in chain if m))[:3]


def _chat_completion_once(
    prompt: str | list,
    temperature: float,
    max_tokens: int,
    models: list[str],
    reasoning: dict | None,
    timeout: float,
) -> str:
    model = models[0]
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if len(models) > 1:
        payload["models"] = models
    else:
        payload["model"] = model
    if reasoning is not None:
        payload["reasoning"] = reasoning
    start = time.monotonic()
    try:
        resp = requests.post(
            Config.OPENROUTER_CHAT_URL,
            headers={
                "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
    except requests.Timeout as e:
        raise LLMError(LLMError.UNAVAILABLE, f"OpenRouter timed out after {timeout}s") from e
    except requests.RequestException as e:
        raise LLMError(LLMError.UNAVAILABLE, f"OpenRouter request failed: {e}") from e
    latency = time.monotonic() - start

    try:
        body = resp.json()
    except ValueError:
        body = {}

    if resp.status_code != 200 or "error" in body:
        # OpenRouter occasionally reports errors with HTTP 200 and an error body.
        status = resp.status_code
        if status == 200 and isinstance(body.get("error"), dict):
            status = int(body["error"].get("code") or 502)
        kind = _kind_for_status(status)
        detail = f"OpenRouter HTTP {status} (model={model}): {_error_message(body) or resp.text[:200]}"
        if kind == LLMError.AUTH:
            detail += _auth_hint()
        logger.error("LLM call failed [%s]: %s after %.1fs", kind, detail, latency)
        raise LLMError(kind, detail, status=status)

    served = body.get("model") or model
    try:
        choice = body["choices"][0]
    except (KeyError, IndexError, TypeError):
        choice = {}
    usage = body.get("usage") or {}
    usage_details = usage.get("completion_tokens_details") or {}
    finish_reason = choice.get("finish_reason")
    reasoning_tokens = usage_details.get("reasoning_tokens")
    logger.info(
        "LLM %s served=%s latency=%.1fs finish=%s tokens(prompt=%s, completion=%s, reasoning=%s)",
        model,
        served,
        latency,
        finish_reason,
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
        reasoning_tokens,
    )

    try:
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(LLMError.BAD_RESPONSE, f"Unexpected OpenRouter response shape: {e}") from e
    if not content or not content.strip():
        if finish_reason == "length":
            raise LLMError(
                LLMError.BAD_RESPONSE,
                f"{served} hit max_tokens={max_tokens} before writing any output "
                f"(reasoning_tokens={reasoning_tokens})",
            )
        raise LLMError(LLMError.BAD_RESPONSE, f"Empty completion from {served}")
    return content.strip()


def check_api_key(timeout: float = 8) -> tuple[bool, str]:
    """Ask OpenRouter whether the configured key works. Costs no credits.

    Returns (ok, human-readable summary). Used once at startup so a dead key
    shows up in the boot log instead of as a confusing chat error.
    """
    if not Config.OPENROUTER_API_KEY:
        return False, "OPENROUTER_API_KEY is not set."
    try:
        resp = requests.get(
            f"{Config.OPENROUTER_BASE_URL.rstrip('/')}/key",
            headers={"Authorization": f"Bearer {Config.OPENROUTER_API_KEY}"},
            timeout=timeout,
        )
    except requests.RequestException as e:
        return False, f"could not reach OpenRouter to verify the key ({type(e).__name__})."
    if resp.status_code != 200:
        try:
            msg = _error_message(resp.json())
        except ValueError:
            msg = resp.text[:120]
        return False, f"OpenRouter rejected the key (HTTP {resp.status_code}: {msg}).{_auth_hint()}"
    data = resp.json().get("data") or {}
    tier = "free tier" if data.get("is_free_tier") else "paid"
    remaining = data.get("limit_remaining")
    suffix = (
        f", about {round(remaining)} requests left in the current limit window"
        if isinstance(remaining, (int, float))
        else ""
    )
    return True, f"OpenRouter key OK ({tier}{suffix})."
