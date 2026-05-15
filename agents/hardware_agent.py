from __future__ import annotations

import json

from .base_agent import AgentError, BaseAgent
from tools.llm_client import llm_client


class HardwareAgent(BaseAgent):
    """Selects sensors, actuators, microcontrollers, and edge devices for the IoT solution."""

    def __init__(self) -> None:
        super().__init__("hardware_agent")

    async def process(self, payload: dict) -> dict:
        if "requirements" not in payload:
            raise AgentError(
                agent_name=self.agent_name,
                message="payload must include 'requirements' from requirements_agent",
            )

        user_message = json.dumps(
            {
                "requirements": payload["requirements"],
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
