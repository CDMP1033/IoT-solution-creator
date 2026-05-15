from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from models.solution import AgentSection, IoTSolution, PipelineStatus
from tools.report_renderer import RENDERERS

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

_SECTION_TITLES: dict[str, str] = {
    "requirements_agent":  "1. Requirements",
    "hardware_agent":      "2. Hardware Selection",
    "connectivity_agent":  "3. Connectivity Stack",
    "data_agent":          "4. Data Pipeline",
    "cloud_agent":         "5. Cloud Infrastructure",
    "security_agent":      "6. Security Model",
    "deployment_agent":    "7. Deployment Plan",
    "methodology_agent":   "8. Methodology & Project Plan",
}

_EXECUTIVE_SYSTEM_PROMPT = """You are a senior IoT solutions architect writing a concise executive briefing for a Product Manager or Product Owner. Your audience understands business value but not deep technical detail.

Given structured IoT solution data, write a Markdown executive summary with these sections:

## Executive Summary
3–4 sentences covering: what the system does, the technology approach chosen, and why it fits the business context.

## Key Design Decisions
A bullet list (5–7 items) of the most important architectural choices made and the business rationale behind each. Focus on trade-offs visible to a PM: cost, reliability, scalability, time-to-market.

## Cost Overview
A brief paragraph summarising: hardware deployment cost, monthly cloud cost, cost per device per month, and how these compare to the stated budget ceiling.

## Timeline at a Glance
A single Markdown table showing each project phase, its duration in weeks, and 1 key milestone.

## Top Risks
A bullet list of the 3–5 most business-critical risks with one-line mitigation for each.

Rules:
- Write in clear, jargon-free English.
- Do not repeat information covered in the detailed sections below the summary.
- Total length: 400–600 words.
- Output only valid Markdown — no preamble, no JSON, no code blocks."""


def _build_executive_context(solution: IoTSolution) -> str:
    """Build a condensed text payload for the executive summary LLM call."""
    parts: list[str] = [f"IoT Problem: {solution.problem.statement[:400]}",
                        f"Region: {solution.problem.region}"]

    def _pick(agent: str, *keys: str) -> str:
        sec = solution.sections.get(agent)
        if not sec or sec.status != "complete":
            return ""
        out = sec.output
        snippets = []
        for key in keys:
            val = out.get(key)
            if val is not None:
                snippets.append(f"{key}: {json.dumps(val, ensure_ascii=False)[:300]}")
        return "\n".join(snippets)

    parts.append(_pick("requirements_agent", "business_goal", "scale", "non_functional_requirements"))
    parts.append(_pick("hardware_agent", "bom_summary", "microcontroller", "edge_gateway"))
    parts.append(_pick("connectivity_agent", "device_protocol", "topology"))
    parts.append(_pick("data_agent", "cost_estimate_usd_per_month", "storage"))
    parts.append(_pick("cloud_agent", "total_cost_usd_per_month", "provider", "primary_region",
                       "high_availability"))
    parts.append(_pick("security_agent", "device_identity", "encryption"))
    parts.append(_pick("deployment_agent", "rollout_phases"))
    parts.append(_pick("methodology_agent", "project_plan"))

    return "\n\n".join(p for p in parts if p)


class Assembler:
    """Merges all agent outputs into the final IoTSolution documents.

    Produces:
    - A PM/PO-friendly executive report (*_executive.md) with human-readable
      tables, bullet lists, and an LLM-generated executive summary.
    - A developer-facing technical report (original output_path) with raw JSON
      blocks for full fidelity.
    """

    def __init__(self, output_path: Path | None = None) -> None:
        self._output_path = output_path or Path("iot_solution_report.md")
        stem = self._output_path.stem
        suffix = self._output_path.suffix
        self._exec_path = self._output_path.with_name(f"{stem}_executive{suffix}")
        self._log = logger.bind(component="assembler")

    def assemble(self, solution: IoTSolution) -> IoTSolution:
        """Finalize the solution status and write both Markdown reports."""
        failed = solution.failed_sections()
        if failed:
            solution.pipeline_status = PipelineStatus.FAILED
        else:
            solution.mark_complete()

        self._write_technical_report(solution)
        return solution

    async def assemble_async(self, solution: IoTSolution) -> IoTSolution:
        """Async variant that also generates the LLM executive summary."""
        failed = solution.failed_sections()
        if failed:
            solution.pipeline_status = PipelineStatus.FAILED
        else:
            solution.mark_complete()

        self._write_technical_report(solution)
        await self._write_executive_report(solution)
        return solution

    # ------------------------------------------------------------------
    # Technical report (raw JSON — unchanged from original)
    # ------------------------------------------------------------------

    def _write_technical_report(self, solution: IoTSolution) -> None:
        lines: list[str] = []
        lines.append("# IoT Solution Report — Technical Reference\n")
        lines.append(f"**Problem:** {solution.problem.statement}\n")
        lines.append(f"**Region:** {solution.problem.region}\n")
        lines.append(f"**Status:** {solution.pipeline_status.value}\n")
        if solution.completed_at:
            lines.append(f"**Completed at:** {solution.completed_at.isoformat()}\n")
        lines.append("\n---\n")

        for agent_name in solution.AGENT_ORDER:
            section: AgentSection = solution.sections[agent_name]
            title = _SECTION_TITLES.get(agent_name, agent_name)
            lines.append(f"## {title}\n")

            if section.status == "complete":
                lines.append("```json")
                lines.append(json.dumps(section.output, indent=2, ensure_ascii=False))
                lines.append("```\n")
            elif section.status == "failed":
                lines.append(f"> **ERROR:** {section.error}\n")
                lines.append("> This section could not be completed.\n")
            else:
                lines.append("> *(skipped — upstream dependency failed)*\n")

        self._output_path.write_text("\n".join(lines), encoding="utf-8")
        self._log.info("assembler.technical_report_written", path=str(self._output_path))

    # ------------------------------------------------------------------
    # Executive report (human-readable + LLM summary)
    # ------------------------------------------------------------------

    async def _write_executive_report(self, solution: IoTSolution) -> None:
        exec_summary = await self._generate_executive_summary(solution)

        lines: list[str] = []
        lines.append("# IoT Solution — Executive Report\n")
        lines.append(f"**Problem:** {solution.problem.statement}\n")
        lines.append(f"**Region:** {solution.problem.region}\n")
        lines.append(f"**Status:** {solution.pipeline_status.value}\n")
        if solution.completed_at:
            lines.append(f"**Completed at:** {solution.completed_at.isoformat()}\n")
        lines.append("\n---\n")

        lines.append(exec_summary)
        lines.append("\n---\n")

        for agent_name in solution.AGENT_ORDER:
            section: AgentSection = solution.sections[agent_name]
            title = _SECTION_TITLES.get(agent_name, agent_name)
            lines.append(f"## {title}\n")

            if section.status == "complete":
                renderer = RENDERERS.get(agent_name)
                if renderer:
                    lines.append(renderer(section.output))  # type: ignore[operator]
                else:
                    lines.append("```json")
                    lines.append(json.dumps(section.output, indent=2, ensure_ascii=False))
                    lines.append("```\n")
            elif section.status == "failed":
                lines.append(f"> **ERROR:** {section.error}\n")
                lines.append("> This section could not be completed.\n")
            else:
                lines.append("> *(skipped — upstream dependency failed)*\n")

        self._exec_path.write_text("\n".join(lines), encoding="utf-8")
        self._log.info("assembler.executive_report_written", path=str(self._exec_path))

    async def _generate_executive_summary(self, solution: IoTSolution) -> str:
        try:
            from tools.llm_client import llm_client

            context = _build_executive_context(solution)
            self._log.info("assembler.generating_executive_summary")
            return await llm_client.complete(
                system_prompt=_EXECUTIVE_SYSTEM_PROMPT,
                user_message=context,
                max_tokens=1200,
            )
        except Exception as exc:
            self._log.warning("assembler.executive_summary_failed", error=repr(exc))
            return (
                "> **Note:** Executive summary could not be generated automatically. "
                f"Error: {exc}\n"
            )
