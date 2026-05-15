from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from models.problem import IoTProblem
from models.solution import AgentSection, IoTSolution, PipelineStatus
from orchestrator.assembler import Assembler
from orchestrator.planner import Planner


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class TestPlanner:
    def setup_method(self) -> None:
        self.planner = Planner()

    def test_first_batch_is_requirements_only(self) -> None:
        batch = self.planner.next_batch(completed=set(), failed=set())
        assert batch == ["requirements_agent"]

    def test_hardware_and_connectivity_run_concurrently(self) -> None:
        batch = self.planner.next_batch(
            completed={"requirements_agent"}, failed=set()
        )
        assert set(batch) == {"hardware_agent", "connectivity_agent"}

    def test_data_agent_waits_for_both_dependencies(self) -> None:
        # Only hardware done — connectivity still running
        batch = self.planner.next_batch(
            completed={"requirements_agent", "hardware_agent"}, failed=set()
        )
        assert "data_agent" not in batch

        # Both done
        batch = self.planner.next_batch(
            completed={"requirements_agent", "hardware_agent", "connectivity_agent"},
            failed=set(),
        )
        assert "data_agent" in batch

    def test_failed_agent_blocks_downstream(self) -> None:
        batch = self.planner.next_batch(
            completed={"requirements_agent"},
            failed={"hardware_agent"},
        )
        # connectivity_agent is still unblocked (different dependency chain)
        assert "connectivity_agent" in batch
        # data_agent depends on hardware_agent, so it should be excluded
        assert "data_agent" not in batch

    def test_empty_batch_when_all_done(self) -> None:
        all_agents = set(self.planner.all_agent_names)
        batch = self.planner.next_batch(completed=all_agents, failed=set())
        assert batch == []

    def test_downstream_of_requirements(self) -> None:
        downstream = self.planner.downstream_of("requirements_agent")
        # Every other agent transitively depends on requirements
        assert "hardware_agent" in downstream
        assert "methodology_agent" in downstream

    def test_downstream_of_leaf_is_empty(self) -> None:
        downstream = self.planner.downstream_of("methodology_agent")
        assert downstream == []


# ---------------------------------------------------------------------------
# Assembler
# ---------------------------------------------------------------------------

class TestAssembler:
    def _make_solution(self, *, all_complete: bool = True) -> IoTSolution:
        problem = IoTProblem(statement="Test problem", region="colombia")
        solution = IoTSolution(problem=problem)
        for agent_name in solution.AGENT_ORDER:
            if all_complete:
                solution.record(AgentSection.from_output(agent_name, {"key": "value"}))
            else:
                # Fail the last agent to simulate partial failure
                if agent_name == "methodology_agent":
                    solution.record(AgentSection.from_error(agent_name, "LLM timeout"))
                else:
                    solution.record(AgentSection.from_output(agent_name, {"key": "value"}))
        return solution

    def test_assembler_marks_complete_when_all_succeed(self, tmp_path: Path) -> None:
        solution = self._make_solution(all_complete=True)
        assembler = Assembler(output_path=tmp_path / "report.md")
        result = assembler.assemble(solution)
        assert result.pipeline_status == PipelineStatus.COMPLETE

    def test_assembler_marks_failed_on_partial_failure(self, tmp_path: Path) -> None:
        solution = self._make_solution(all_complete=False)
        assembler = Assembler(output_path=tmp_path / "report.md")
        result = assembler.assemble(solution)
        assert result.pipeline_status == PipelineStatus.FAILED

    def test_report_file_is_written(self, tmp_path: Path) -> None:
        solution = self._make_solution(all_complete=True)
        report_path = tmp_path / "report.md"
        assembler = Assembler(output_path=report_path)
        assembler.assemble(solution)
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "# IoT Solution Report" in content
        assert "Test problem" in content

    def test_report_flags_failed_sections(self, tmp_path: Path) -> None:
        solution = self._make_solution(all_complete=False)
        report_path = tmp_path / "report.md"
        assembler = Assembler(output_path=report_path)
        assembler.assemble(solution)
        content = report_path.read_text(encoding="utf-8")
        assert "ERROR" in content
        assert "LLM timeout" in content
