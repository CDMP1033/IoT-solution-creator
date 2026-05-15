from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from agents.base_agent import AgentError
from agents.cloud_agent import CloudAgent
from agents.connectivity_agent import ConnectivityAgent
from agents.data_agent import DataAgent
from agents.deployment_agent import DeploymentAgent
from agents.hardware_agent import HardwareAgent
from agents.methodology_agent import MethodologyAgent
from agents.requirements_agent import RequirementsAgent
from agents.security_agent import SecurityAgent
from tests.conftest import (
    CLOUD_OUTPUT,
    CONNECTIVITY_OUTPUT,
    DATA_OUTPUT,
    DEPLOYMENT_OUTPUT,
    HARDWARE_OUTPUT,
    METHODOLOGY_OUTPUT,
    REQUIREMENTS_OUTPUT,
    SECURITY_OUTPUT,
    make_llm_return,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PATCH_TARGET = "tools.llm_client.llm_client.complete"


def _patch_llm(output: dict) -> tuple:
    mock = AsyncMock(return_value=json.dumps(output))
    return patch(PATCH_TARGET, mock), mock


# ---------------------------------------------------------------------------
# RequirementsAgent
# ---------------------------------------------------------------------------

class TestRequirementsAgent:
    @pytest.fixture(autouse=True)
    def _agent(self) -> None:
        self.agent = RequirementsAgent()

    async def test_valid_payload_returns_parsed_dict(self) -> None:
        ctx, mock = _patch_llm(REQUIREMENTS_OUTPUT)
        with ctx:
            result = await self.agent.run(
                {"statement": "Monitor soil moisture", "region": "colombia"}
            )
        assert result["business_goal"] == REQUIREMENTS_OUTPUT["business_goal"]
        mock.assert_awaited_once()

    async def test_missing_statement_raises_agent_error(self) -> None:
        with pytest.raises(AgentError, match="statement"):
            await self.agent.run({"region": "colombia"})

    async def test_empty_statement_raises_agent_error(self) -> None:
        with pytest.raises(AgentError, match="statement"):
            await self.agent.run({"statement": "   ", "region": "colombia"})

    async def test_non_json_llm_response_raises_agent_error(self) -> None:
        with patch(PATCH_TARGET, AsyncMock(return_value="This is not JSON")):
            with pytest.raises(AgentError, match="non-JSON"):
                await self.agent.run({"statement": "Test", "region": "colombia"})


# ---------------------------------------------------------------------------
# HardwareAgent
# ---------------------------------------------------------------------------

class TestHardwareAgent:
    @pytest.fixture(autouse=True)
    def _agent(self) -> None:
        self.agent = HardwareAgent()

    async def test_valid_payload_returns_parsed_dict(self) -> None:
        ctx, _ = _patch_llm(HARDWARE_OUTPUT)
        with ctx:
            result = await self.agent.run(
                {"requirements": REQUIREMENTS_OUTPUT, "region": "colombia"}
            )
        assert "microcontroller" in result
        assert result["microcontroller"]["model"] == "ESP32-WROOM-32"

    async def test_missing_requirements_raises_agent_error(self) -> None:
        with pytest.raises(AgentError, match="requirements"):
            await self.agent.run({"region": "colombia"})

    async def test_non_json_response_raises_agent_error(self) -> None:
        with patch(PATCH_TARGET, AsyncMock(return_value="bad output")):
            with pytest.raises(AgentError, match="non-JSON"):
                await self.agent.run({"requirements": REQUIREMENTS_OUTPUT, "region": "colombia"})


# ---------------------------------------------------------------------------
# ConnectivityAgent
# ---------------------------------------------------------------------------

class TestConnectivityAgent:
    @pytest.fixture(autouse=True)
    def _agent(self) -> None:
        self.agent = ConnectivityAgent()

    async def test_valid_payload_returns_parsed_dict(self) -> None:
        ctx, _ = _patch_llm(CONNECTIVITY_OUTPUT)
        with ctx:
            result = await self.agent.run(
                {"requirements": REQUIREMENTS_OUTPUT, "hardware": HARDWARE_OUTPUT,
                 "region": "colombia"}
            )
        assert result["device_protocol"]["name"] == "LoRaWAN"

    @pytest.mark.parametrize("missing_key", ["requirements", "hardware"])
    async def test_missing_required_key_raises_agent_error(self, missing_key: str) -> None:
        payload = {"requirements": REQUIREMENTS_OUTPUT, "hardware": HARDWARE_OUTPUT,
                   "region": "colombia"}
        del payload[missing_key]
        with pytest.raises(AgentError, match=missing_key):
            await self.agent.run(payload)


# ---------------------------------------------------------------------------
# DataAgent
# ---------------------------------------------------------------------------

class TestDataAgent:
    @pytest.fixture(autouse=True)
    def _agent(self) -> None:
        self.agent = DataAgent()

    async def test_valid_payload_returns_parsed_dict(self) -> None:
        ctx, _ = _patch_llm(DATA_OUTPUT)
        with ctx:
            result = await self.agent.run(
                {"requirements": REQUIREMENTS_OUTPUT, "hardware": HARDWARE_OUTPUT,
                 "connectivity": CONNECTIVITY_OUTPUT, "region": "colombia"}
            )
        assert "ingestion" in result
        assert "storage" in result

    @pytest.mark.parametrize("missing_key", ["requirements", "hardware", "connectivity"])
    async def test_missing_required_key_raises_agent_error(self, missing_key: str) -> None:
        payload = {"requirements": REQUIREMENTS_OUTPUT, "hardware": HARDWARE_OUTPUT,
                   "connectivity": CONNECTIVITY_OUTPUT, "region": "colombia"}
        del payload[missing_key]
        with pytest.raises(AgentError, match=missing_key):
            await self.agent.run(payload)


# ---------------------------------------------------------------------------
# CloudAgent
# ---------------------------------------------------------------------------

class TestCloudAgent:
    @pytest.fixture(autouse=True)
    def _agent(self) -> None:
        self.agent = CloudAgent()

    async def test_valid_payload_returns_parsed_dict(self) -> None:
        ctx, _ = _patch_llm(CLOUD_OUTPUT)
        with ctx:
            result = await self.agent.run(
                {"requirements": REQUIREMENTS_OUTPUT, "data": DATA_OUTPUT,
                 "connectivity": CONNECTIVITY_OUTPUT, "region": "colombia"}
            )
        assert result["provider"] == "AWS"
        assert "iac" in result

    @pytest.mark.parametrize("missing_key", ["requirements", "data", "connectivity"])
    async def test_missing_required_key_raises_agent_error(self, missing_key: str) -> None:
        payload = {"requirements": REQUIREMENTS_OUTPUT, "data": DATA_OUTPUT,
                   "connectivity": CONNECTIVITY_OUTPUT, "region": "colombia"}
        del payload[missing_key]
        with pytest.raises(AgentError, match=missing_key):
            await self.agent.run(payload)


# ---------------------------------------------------------------------------
# SecurityAgent
# ---------------------------------------------------------------------------

class TestSecurityAgent:
    @pytest.fixture(autouse=True)
    def _agent(self) -> None:
        self.agent = SecurityAgent()

    async def test_valid_payload_returns_parsed_dict(self) -> None:
        ctx, _ = _patch_llm(SECURITY_OUTPUT)
        with ctx:
            result = await self.agent.run(
                {"requirements": REQUIREMENTS_OUTPUT, "hardware": HARDWARE_OUTPUT,
                 "connectivity": CONNECTIVITY_OUTPUT, "cloud": CLOUD_OUTPUT,
                 "region": "colombia"}
            )
        assert "threat_model" in result
        assert len(result["threat_model"]) >= 5

    @pytest.mark.parametrize("missing_key", ["requirements", "hardware", "connectivity", "cloud"])
    async def test_missing_required_key_raises_agent_error(self, missing_key: str) -> None:
        payload = {"requirements": REQUIREMENTS_OUTPUT, "hardware": HARDWARE_OUTPUT,
                   "connectivity": CONNECTIVITY_OUTPUT, "cloud": CLOUD_OUTPUT,
                   "region": "colombia"}
        del payload[missing_key]
        with pytest.raises(AgentError, match=missing_key):
            await self.agent.run(payload)


# ---------------------------------------------------------------------------
# DeploymentAgent
# ---------------------------------------------------------------------------

class TestDeploymentAgent:
    @pytest.fixture(autouse=True)
    def _agent(self) -> None:
        self.agent = DeploymentAgent()

    async def test_valid_payload_returns_parsed_dict(self) -> None:
        ctx, _ = _patch_llm(DEPLOYMENT_OUTPUT)
        with ctx:
            result = await self.agent.run(
                {"requirements": REQUIREMENTS_OUTPUT, "hardware": HARDWARE_OUTPUT,
                 "cloud": CLOUD_OUTPUT, "security": SECURITY_OUTPUT,
                 "region": "colombia"}
            )
        assert "rollout_phases" in result
        assert result["rollout_phases"][0]["phase"] == "Pilot"

    @pytest.mark.parametrize("missing_key", ["requirements", "hardware", "cloud", "security"])
    async def test_missing_required_key_raises_agent_error(self, missing_key: str) -> None:
        payload = {"requirements": REQUIREMENTS_OUTPUT, "hardware": HARDWARE_OUTPUT,
                   "cloud": CLOUD_OUTPUT, "security": SECURITY_OUTPUT,
                   "region": "colombia"}
        del payload[missing_key]
        with pytest.raises(AgentError, match=missing_key):
            await self.agent.run(payload)


# ---------------------------------------------------------------------------
# MethodologyAgent
# ---------------------------------------------------------------------------

class TestMethodologyAgent:
    @pytest.fixture(autouse=True)
    def _agent(self) -> None:
        self.agent = MethodologyAgent()

    def _full_payload(self) -> dict:
        return {
            "requirements": REQUIREMENTS_OUTPUT,
            "hardware": HARDWARE_OUTPUT,
            "connectivity": CONNECTIVITY_OUTPUT,
            "data": DATA_OUTPUT,
            "cloud": CLOUD_OUTPUT,
            "security": SECURITY_OUTPUT,
            "deployment": DEPLOYMENT_OUTPUT,
            "region": "colombia",
        }

    async def test_valid_payload_returns_parsed_dict(self) -> None:
        ctx, _ = _patch_llm(METHODOLOGY_OUTPUT)
        with ctx:
            result = await self.agent.run(self._full_payload())
        assert "executive_summary" in result
        assert "risk_register" in result
        assert len(result["risk_register"]) >= 6

    @pytest.mark.parametrize("missing_key", [
        "requirements", "hardware", "connectivity", "data", "cloud", "security", "deployment"
    ])
    async def test_missing_required_key_raises_agent_error(self, missing_key: str) -> None:
        payload = self._full_payload()
        del payload[missing_key]
        with pytest.raises(AgentError, match=missing_key):
            await self.agent.run(payload)
