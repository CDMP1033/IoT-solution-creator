from __future__ import annotations

import os
import time
from dataclasses import dataclass

import structlog
from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic, AuthenticationError
from anthropic import Timeout

DEFAULT_MODEL = "claude-sonnet-4-6"
_CHARS_PER_TOKEN_ESTIMATE = 4  # rough approximation for logging purposes
# Per-request timeout: 10 min connect + 10 min read. Large agents (deployment,
# methodology) can generate 16k tokens which takes ~3-5 min at normal throughput.
# 600s gives ample headroom while preventing indefinite hangs.
_API_TIMEOUT = Timeout(600.0, connect=30.0)

logger = structlog.get_logger(__name__)


@dataclass
class LLMError(Exception):
    message: str
    cause: BaseException | None = None

    def __str__(self) -> str:
        if self.cause is not None:
            return f"{self.message} — caused by: {self.cause!r}"
        return self.message


class LLMClient:
    """Shared async client for all Anthropic API calls.

    Instantiate once at module level and import the singleton `llm_client`.
    Agents must never instantiate AsyncAnthropic directly.
    """

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMError(message="ANTHROPIC_API_KEY environment variable is not set")
        self._client = AsyncAnthropic(api_key=api_key, timeout=_API_TIMEOUT)
        self._log = logger.bind(model=DEFAULT_MODEL)

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4000,
    ) -> str:
        """Send a single-turn completion request to the Anthropic API.

        Args:
            system_prompt: The agent's system prompt (loaded from prompts/*.md).
            user_message:  The user-facing content for this invocation.
            max_tokens:    Upper bound on response tokens (CLAUDE.md default: 4 000).

        Returns:
            The assistant's text response.

        Raises:
            LLMError: On authentication failure, network error, or API error.
        """
        estimated_input_tokens = (len(system_prompt) + len(user_message)) // _CHARS_PER_TOKEN_ESTIMATE
        self._log.info(
            "llm.request",
            estimated_input_tokens=estimated_input_tokens,
            max_tokens=max_tokens,
        )

        start_ms = time.monotonic_ns() // 1_000_000
        try:
            response = await self._client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
        except AuthenticationError as exc:
            raise LLMError(
                message="Anthropic API authentication failed — check ANTHROPIC_API_KEY",
                cause=exc,
            ) from exc
        except APIConnectionError as exc:
            raise LLMError(
                message="Could not reach the Anthropic API — check network connectivity",
                cause=exc,
            ) from exc
        except APIStatusError as exc:
            raise LLMError(
                message=f"Anthropic API returned an error: HTTP {exc.status_code}",
                cause=exc,
            ) from exc

        elapsed_ms = time.monotonic_ns() // 1_000_000 - start_ms
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        self._log.info(
            "llm.response",
            elapsed_ms=elapsed_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return response.content[0].text


# ---------------------------------------------------------------------------
# Lazy singleton — resolved on first attribute access so that tests can import
# agents without ANTHROPIC_API_KEY being set at collection time.
# ---------------------------------------------------------------------------

class _LazyLLMClient:
    _instance: LLMClient | None = None

    def _get(self) -> LLMClient:
        if self._instance is None:
            self._instance = LLMClient()
        return self._instance

    async def complete(self, *args, **kwargs) -> str:  # type: ignore[override]
        return await self._get().complete(*args, **kwargs)


llm_client: _LazyLLMClient = _LazyLLMClient()
