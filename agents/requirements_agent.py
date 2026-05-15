from __future__ import annotations

import json

from .base_agent import AgentError, BaseAgent
from tools.llm_client import llm_client


class RequirementsAgent(BaseAgent):
    """Extracts functional and non-functional requirements from the raw IoT problem statement."""

    def __init__(self) -> None:
        super().__init__("requirements_agent")

    async def process(self, payload: dict) -> dict:
        statement = payload.get("statement", "").strip()
        if not statement:
            raise AgentError(
                agent_name=self.agent_name,
                message="payload must include a non-empty 'statement' field",
            )

        region = payload.get("region", "colombia")
        metadata = payload.get("metadata", {})

        user_message = json.dumps(
            {"statement": statement, "region": region, "metadata": metadata},
            ensure_ascii=False,
            indent=2,
        )

        raw = await llm_client.complete(
            system_prompt=self.system_prompt,
            user_message=user_message,
        )

        return self._parse_json(raw)
