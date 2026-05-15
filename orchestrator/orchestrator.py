from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from agents import (
    AgentError,
    CloudAgent,
    ConnectivityAgent,
    DataAgent,
    DeploymentAgent,
    HardwareAgent,
    MethodologyAgent,
    RequirementsAgent,
    SecurityAgent,
)
from models.problem import IoTProblem
from models.solution import AgentSection, IoTSolution, PipelineStatus
from .assembler import Assembler
from .planner import Planner

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent

logger = structlog.get_logger(__name__)

_STATE_FILE = Path("project_state.json")
_MAX_RETRIES = 2

_AGENT_REGISTRY: dict[str, type] = {
    "requirements_agent":  RequirementsAgent,
    "hardware_agent":      HardwareAgent,
    "connectivity_agent":  ConnectivityAgent,
    "data_agent":          DataAgent,
    "cloud_agent":         CloudAgent,
    "security_agent":      SecurityAgent,
    "deployment_agent":    DeploymentAgent,
    "methodology_agent":   MethodologyAgent,
}

# Maps each agent to the keys it needs from prior agent outputs.
_CONTEXT_KEYS: dict[str, list[str]] = {
    "requirements_agent":  [],
    "hardware_agent":      ["requirements"],
    "connectivity_agent":  ["requirements", "hardware"],
    "data_agent":          ["requirements", "hardware", "connectivity"],
    "cloud_agent":         ["requirements", "data", "connectivity"],
    "security_agent":      ["requirements", "hardware", "connectivity", "cloud"],
    "deployment_agent":    ["requirements", "hardware", "cloud", "security"],
    "methodology_agent":   [
        "requirements", "hardware", "connectivity",
        "data", "cloud", "security", "deployment",
    ],
}

# Friendly key used in payloads (strips "_agent" suffix).
def _key(agent_name: str) -> str:
    return agent_name.replace("_agent", "")


class Orchestrator:
    """Drives the full IoT solution pipeline.

    Responsibilities:
    - Load or create the pipeline state.
    - Dispatch agents in dependency order (concurrent where possible).
    - Retry failed agents up to _MAX_RETRIES times.
    - Persist state after every agent completes.
    - Assemble the final report.
    """

    def __init__(self, output_path: Path | None = None) -> None:
        self._planner = Planner()
        self._assembler = Assembler(output_path)
        self._log = logger.bind(component="orchestrator")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self, problem: IoTProblem) -> IoTSolution:
        """Execute the full pipeline for *problem* and return the assembled solution."""
        solution = await self._load_or_create(problem)

        if solution.pipeline_status == PipelineStatus.RUNNING:
            self._log.info("orchestrator.resuming", problem=problem.statement[:60])
        else:
            solution.pipeline_status = PipelineStatus.RUNNING
            self._save_state(solution)

        # agent_outputs accumulates completed outputs for context passing.
        agent_outputs: dict[str, dict] = {
            _key(name): section.output
            for name, section in solution.sections.items()
            if section.status == "complete"
        }

        completed: set[str] = {
            name for name, sec in solution.sections.items() if sec.status == "complete"
        }
        failed: set[str] = {
            name for name, sec in solution.sections.items() if sec.status == "failed"
        }

        while True:
            batch = self._planner.next_batch(completed, failed)
            if not batch:
                break

            self._log.info("orchestrator.batch", agents=batch)
            results = await asyncio.gather(
                *[self._run_agent(name, agent_outputs, problem) for name in batch],
                return_exceptions=True,
            )

            for agent_name, result in zip(batch, results):
                if isinstance(result, BaseException):
                    self._log.error("orchestrator.agent_failed", agent=agent_name, error=repr(result))
                    solution.record(AgentSection.from_error(agent_name, str(result)))
                    failed.add(agent_name)
                    # Mark all downstream agents as failed too.
                    for downstream in self._planner.downstream_of(agent_name):
                        if downstream not in completed and downstream not in failed:
                            solution.record(
                                AgentSection.from_error(
                                    downstream,
                                    f"Skipped: upstream agent '{agent_name}' failed",
                                )
                            )
                            failed.add(downstream)
                else:
                    agent_outputs[_key(agent_name)] = result
                    solution.record(AgentSection.from_output(agent_name, result))
                    completed.add(agent_name)

            self._save_state(solution)

        solution = await self._assembler.assemble_async(solution)
        self._save_state(solution)
        self._log.info(
            "orchestrator.done",
            status=solution.pipeline_status.value,
            report=str(self._assembler._output_path),
            executive_report=str(self._assembler._exec_path),
        )
        return solution

    # ------------------------------------------------------------------
    # Agent execution with retries
    # ------------------------------------------------------------------

    async def _run_agent(
        self,
        agent_name: str,
        agent_outputs: dict[str, dict],
        problem: IoTProblem,
    ) -> dict:
        agent: BaseAgent = _AGENT_REGISTRY[agent_name]()
        payload = self._build_payload(agent_name, agent_outputs, problem)

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 2):
            try:
                self._log.info("orchestrator.agent_start", agent=agent_name, attempt=attempt)
                result = await agent.run(payload)
                self._log.info("orchestrator.agent_done", agent=agent_name, attempt=attempt)
                return result
            except AgentError as exc:
                last_exc = exc
                self._log.warning(
                    "orchestrator.agent_retry",
                    agent=agent_name,
                    attempt=attempt,
                    max_retries=_MAX_RETRIES + 1,
                    error=str(exc),
                )

        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Payload construction
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        agent_name: str,
        agent_outputs: dict[str, dict],
        problem: IoTProblem,
    ) -> dict:
        payload: dict = {"region": problem.region}
        if agent_name == "requirements_agent":
            payload["statement"] = problem.statement
            payload["metadata"] = problem.metadata
        for key in _CONTEXT_KEYS.get(agent_name, []):
            payload[key] = agent_outputs.get(key, {})
        return payload

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _save_state(self, solution: IoTSolution) -> None:
        state = {
            "problem": {
                "statement": solution.problem.statement,
                "region": solution.problem.region,
                "metadata": solution.problem.metadata,
            },
            "agent_outputs": {
                name: sec.output for name, sec in solution.sections.items()
            },
            "agent_errors": {
                name: sec.error
                for name, sec in solution.sections.items()
                if sec.error is not None
            },
            "pipeline_status": solution.pipeline_status.value,
        }
        tmp = _STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_STATE_FILE)

    async def _load_or_create(self, problem: IoTProblem) -> IoTSolution:
        if _STATE_FILE.exists():
            try:
                state = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
                status = PipelineStatus(state.get("pipeline_status", "pending"))
                if status == PipelineStatus.RUNNING:
                    answer = await self._ask_resume()
                    if not answer:
                        _STATE_FILE.unlink(missing_ok=True)
                        return IoTSolution(problem=problem)
                    # Restore from state file.
                    saved_problem = IoTProblem(
                        statement=state["problem"]["statement"],
                        region=state["problem"]["region"],
                        metadata=state["problem"].get("metadata", {}),
                    )
                    solution = IoTSolution(problem=saved_problem, pipeline_status=status)
                    for agent_name, output in state.get("agent_outputs", {}).items():
                        if output:
                            solution.record(AgentSection.from_output(agent_name, output))
                    for agent_name, error in state.get("agent_errors", {}).items():
                        solution.record(AgentSection.from_error(agent_name, error))
                    return solution
            except (json.JSONDecodeError, KeyError, ValueError):
                self._log.warning("orchestrator.corrupt_state", file=str(_STATE_FILE))

        return IoTSolution(problem=problem)

    async def _ask_resume(self) -> bool:
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(
            None,
            lambda: input(
                "A previous pipeline run was interrupted. Resume it? [y/N]: "
            ).strip().lower(),
        )
        return answer in ("y", "yes")
