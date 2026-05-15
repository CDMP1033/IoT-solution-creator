from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from models.problem import IoTProblem
from models.solution import PipelineStatus
from orchestrator.orchestrator import Orchestrator
from tests.conftest import (
    CLOUD_OUTPUT,
    CONNECTIVITY_OUTPUT,
    DATA_OUTPUT,
    DEPLOYMENT_OUTPUT,
    HARDWARE_OUTPUT,
    METHODOLOGY_OUTPUT,
    REQUIREMENTS_OUTPUT,
    SECURITY_OUTPUT,
)

PATCH_TARGET = "tools.llm_client.llm_client.complete"

# Ordered responses matching the pipeline execution sequence.
# The LLM mock returns these in order, one per agent call.
_ORDERED_RESPONSES = [
    REQUIREMENTS_OUTPUT,
    HARDWARE_OUTPUT,
    CONNECTIVITY_OUTPUT,
    DATA_OUTPUT,
    CLOUD_OUTPUT,
    SECURITY_OUTPUT,
    DEPLOYMENT_OUTPUT,
    METHODOLOGY_OUTPUT,
]

# Placeholder executive summary returned by the mock on the 9th LLM call.
_EXEC_SUMMARY_RESPONSE = (
    "## Executive Summary\n\nTest executive summary.\n\n"
    "## Key Design Decisions\n\n- Decision 1\n\n"
    "## Cost Overview\n\nTotal cost: USD 41 110 hardware + USD 169/month cloud.\n\n"
    "## Timeline at a Glance\n\n| Phase | Duration | Milestone |\n"
    "|---|---|---|\n| Pilot | 6 weeks | 10 nodes |\n\n"
    "## Top Risks\n\n- Risk 1\n"
)


def _make_side_effect() -> list[str]:
    """8 agent responses + 1 executive summary response."""
    return [json.dumps(r) for r in _ORDERED_RESPONSES] + [_EXEC_SUMMARY_RESPONSE]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestFullPipelineHappyPath:
    async def test_pipeline_completes_with_all_sections(self, tmp_path: Path) -> None:
        problem = IoTProblem(
            statement="Monitor soil moisture across 500 hectares and trigger irrigation",
            region="colombia",
        )
        mock = AsyncMock(side_effect=_make_side_effect())
        with patch(PATCH_TARGET, mock):
            orchestrator = Orchestrator(output_path=tmp_path / "report.md")
            # Prevent state file from being written to the real project root.
            with patch("orchestrator.orchestrator._STATE_FILE", tmp_path / "state.json"):
                solution = await orchestrator.run(problem)

        assert solution.pipeline_status == PipelineStatus.COMPLETE
        assert solution.is_complete()
        # 8 agent calls + 1 executive summary LLM call
        assert mock.await_count == 9

    async def test_report_file_is_generated(self, tmp_path: Path) -> None:
        problem = IoTProblem(statement="Smart building energy management", region="colombia")
        mock = AsyncMock(side_effect=_make_side_effect())
        with patch(PATCH_TARGET, mock):
            orchestrator = Orchestrator(output_path=tmp_path / "report.md")
            with patch("orchestrator.orchestrator._STATE_FILE", tmp_path / "state.json"):
                await orchestrator.run(problem)

        report = tmp_path / "report.md"
        assert report.exists()
        content = report.read_text(encoding="utf-8")
        assert "IoT Solution Report" in content
        assert "Smart building energy management" in content
        # All 8 section titles must appear
        for title in ["Requirements", "Hardware", "Connectivity", "Data Pipeline",
                      "Cloud", "Security", "Deployment", "Methodology"]:
            assert title in content

    async def test_all_agent_sections_complete(self, tmp_path: Path) -> None:
        problem = IoTProblem(statement="Industrial machine monitoring", region="colombia")
        mock = AsyncMock(side_effect=_make_side_effect())
        with patch(PATCH_TARGET, mock):
            orchestrator = Orchestrator(output_path=tmp_path / "report.md")
            with patch("orchestrator.orchestrator._STATE_FILE", tmp_path / "state.json"):
                solution = await orchestrator.run(problem)

        for agent_name, section in solution.sections.items():
            assert section.status == "complete", f"{agent_name} did not complete"

    async def test_state_file_written_atomically(self, tmp_path: Path) -> None:
        problem = IoTProblem(statement="Smart parking sensor network", region="colombia")
        state_file = tmp_path / "state.json"
        mock = AsyncMock(side_effect=_make_side_effect())
        with patch(PATCH_TARGET, mock):
            orchestrator = Orchestrator(output_path=tmp_path / "report.md")
            with patch("orchestrator.orchestrator._STATE_FILE", state_file):
                await orchestrator.run(problem)

        assert state_file.exists()
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["pipeline_status"] == "complete"
        assert "requirements_agent" in state["agent_outputs"]


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------

class TestFullPipelineFailures:
    async def test_single_agent_failure_marks_downstream_as_failed(
        self, tmp_path: Path
    ) -> None:
        problem = IoTProblem(statement="Water quality monitoring", region="colombia")

        # requirements_agent succeeds, then hardware_agent raises an exception.
        responses = iter([json.dumps(REQUIREMENTS_OUTPUT)])

        async def side_effect(*args, **kwargs) -> str:
            try:
                return next(responses)
            except StopIteration:
                raise RuntimeError("Simulated LLM timeout")

        with patch(PATCH_TARGET, side_effect=side_effect):
            orchestrator = Orchestrator(output_path=tmp_path / "report.md")
            with patch("orchestrator.orchestrator._STATE_FILE", tmp_path / "state.json"):
                solution = await orchestrator.run(problem)

        assert solution.pipeline_status == PipelineStatus.FAILED
        # requirements succeeded
        assert solution.sections["requirements_agent"].status == "complete"
        # methodology depends on everything — must be failed too
        assert solution.sections["methodology_agent"].status == "failed"

    async def test_partial_failure_report_marks_errored_sections(
        self, tmp_path: Path
    ) -> None:
        problem = IoTProblem(statement="Cold chain logistics tracking", region="colombia")

        responses = iter([json.dumps(REQUIREMENTS_OUTPUT)])

        async def side_effect(*args, **kwargs) -> str:
            try:
                return next(responses)
            except StopIteration:
                raise RuntimeError("API error")

        with patch(PATCH_TARGET, side_effect=side_effect):
            orchestrator = Orchestrator(output_path=tmp_path / "report.md")
            with patch("orchestrator.orchestrator._STATE_FILE", tmp_path / "state.json"):
                await orchestrator.run(problem)

        report = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "ERROR" in report
