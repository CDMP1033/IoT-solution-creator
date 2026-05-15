from __future__ import annotations

import json

from .base_agent import AgentError, BaseAgent
from tools.llm_client import llm_client


class ConnectivityAgent(BaseAgent):
    """Designs the connectivity stack: device protocol, backhaul, and messaging layer."""

    def __init__(self) -> None:
        super().__init__("connectivity_agent")

    async def process(self, payload: dict) -> dict:
        for key in ("requirements", "hardware"):
            if key not in payload:
                raise AgentError(
                    agent_name=self.agent_name,
                    message=f"payload must include '{key}'",
                )

        user_message = json.dumps(
            {
                "requirements": payload["requirements"],
                "hardware": payload["hardware"],
                "region": payload.get("region", "colombia"),
            },
            ensure_ascii=False,
            indent=2,
        )

        raw = await llm_client.complete(
            system_prompt=self.system_prompt,
            user_message=user_message,
        )

        try:
            return self._parse_json(raw)
        except json.JSONDecodeError as exc:
            raise AgentError(
                agent_name=self.agent_name,
                message=f"LLM returned non-JSON output: {raw[:200]}",
                cause=exc,
            ) from exc
