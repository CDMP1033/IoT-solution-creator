from __future__ import annotations

import json

from .base_agent import AgentError, BaseAgent
from tools.llm_client import llm_client


class SecurityAgent(BaseAgent):
    """Produces the security model: auth, encryption, OTA strategy, and threat model."""

    def __init__(self) -> None:
        super().__init__("security_agent")

    async def process(self, payload: dict) -> dict:
        for key in ("requirements", "hardware", "connectivity", "cloud"):
            if key not in payload:
                raise AgentError(
                    agent_name=self.agent_name,
                    message=f"payload must include '{key}'",
                )

        user_message = json.dumps(
            {
                "requirements": payload["requirements"],
                "hardware": payload["hardware"],
                "connectivity": payload["connectivity"],
                "cloud": payload["cloud"],
                "region": payload.get("region", "colombia"),
            },
            ensure_ascii=False,
            indent=2,
        )

        raw = await llm_client.complete(
            system_prompt=self.system_prompt,
            user_message=user_message,
            max_tokens=8000,
        )

        try:
            return self._parse_json(raw)
        except json.JSONDecodeError as exc:
            raise AgentError(
                agent_name=self.agent_name,
                message=f"LLM returned non-JSON output: {raw[:200]}",
                cause=exc,
            ) from exc
