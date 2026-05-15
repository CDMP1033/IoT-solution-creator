from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import structlog

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

logger = structlog.get_logger(__name__)


@dataclass
class AgentError(Exception):
    agent_name: str
    message: str
    cause: BaseException | None = None

    def __str__(self) -> str:
        if self.cause is not None:
            return f"[{self.agent_name}] {self.message} — caused by: {self.cause!r}"
        return f"[{self.agent_name}] {self.message}"


class BaseAgent(ABC):
    """Abstract base class for all IoT Solution Creator agents.

    Subclasses must implement `process()`. Runtime behaviour (logging,
    error handling, timing) is provided by the concrete `run()` method.
    """

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self.system_prompt = self._load_system_prompt()
        self._log = logger.bind(agent=agent_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_system_prompt(self) -> str:
        prompt_path = PROMPTS_DIR / f"{self.agent_name}.md"
        try:
            return prompt_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise AgentError(
                agent_name=self.agent_name,
                message=f"System prompt not found at '{prompt_path}'",
                cause=exc,
            ) from exc
        except OSError as exc:
            raise AgentError(
                agent_name=self.agent_name,
                message=f"Failed to read system prompt at '{prompt_path}'",
                cause=exc,
            ) from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_json(self, raw: str) -> dict:
        """Strip optional markdown code fences and parse JSON.

        Handles three cases:
        - Plain JSON
        - ```json ... ``` fenced JSON (closed fence)
        - ```json ... (truncated — opening fence but no closing fence)
        """
        import json
        import re

        stripped = raw.strip()

        # Closed fence: ```json ... ```
        fenced = re.match(r"^```(?:json)?\s*([\s\S]*?)```\s*$", stripped)
        if fenced:
            stripped = fenced.group(1).strip()
        else:
            # Opening fence without closing (truncated output)
            open_fence = re.match(r"^```(?:json)?\s*([\s\S]*)$", stripped)
            if open_fence:
                stripped = open_fence.group(1).strip()

        try:
            return json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise AgentError(
                agent_name=self.agent_name,
                message=f"LLM returned non-JSON output: {raw[:200]}",
                cause=exc,
            ) from exc

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def process(self, payload: dict) -> dict:
        """Execute the agent's core logic.

        Args:
            payload: Input data provided by the orchestrator. The exact
                     schema is defined in prompts/<agent_name>.md.

        Returns:
            A dict conforming to the output schema in prompts/<agent_name>.md.
        """

    async def run(self, payload: dict) -> dict:
        """Wrap `process()` with logging, timing, and error handling.

        This is the method the orchestrator should call — never `process()` directly.
        """
        self._log.info("agent.received", payload_keys=list(payload.keys()))
        start_ms = time.monotonic_ns() // 1_000_000

        try:
            result = await self.process(payload)
        except AgentError:
            raise
        except Exception as exc:
            elapsed_ms = time.monotonic_ns() // 1_000_000 - start_ms
            self._log.error(
                "agent.failed",
                elapsed_ms=elapsed_ms,
                error=repr(exc),
            )
            raise AgentError(
                agent_name=self.agent_name,
                message="Unhandled exception inside process()",
                cause=exc,
            ) from exc

        elapsed_ms = time.monotonic_ns() // 1_000_000 - start_ms
        self._log.info(
            "agent.completed",
            elapsed_ms=elapsed_ms,
            result_keys=list(result.keys()),
        )
        return result
