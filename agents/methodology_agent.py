from __future__ import annotations

import json

from .base_agent import AgentError, BaseAgent
from tools.llm_client import llm_client


class MethodologyAgent(BaseAgent):
    """Synthesizes the full solution into project methodology, plan, risks, and executive summary."""

    def __init__(self) -> None:
        super().__init__("methodology_agent")

    async def process(self, payload: dict) -> dict:
        required_keys = (
            "requirements", "hardware", "connectivity",
            "data", "cloud", "security", "deployment",
        )
        for key in required_keys:
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
                "data": payload["data"],
                "cloud": payload["cloud"],
                "security": payload["security"],
                "deployment": payload["deployment"],
                "region": payload.get("region", "colombia"),
            },
            ensure_ascii=False,
            indent=2,
        )

        raw = await llm_client.complete(
            system_prompt=self.system_prompt,
            user_message=user_message,
            max_tokens=16000,
        )

        try:
            return self._parse_json(raw)
        except json.JSONDecodeError as exc:
            raise AgentError(
                agent_name=self.agent_name,
                message=f"LLM returned non-JSON output: {raw[:200]}",
                cause=exc,
            ) from exc
