from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .problem import IoTProblem


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class AgentSection:
    """Holds the output of a single agent, including failure info."""

    agent_name: str
    status: str  # "complete" | "failed" | "pending"
    output: dict = field(default_factory=dict)
    error: str | None = None
    completed_at: datetime | None = None

    @classmethod
    def pending(cls, agent_name: str) -> AgentSection:
        return cls(agent_name=agent_name, status="pending")

    @classmethod
    def from_output(cls, agent_name: str, output: dict) -> AgentSection:
        return cls(
            agent_name=agent_name,
            status="complete",
            output=output,
            completed_at=datetime.now(timezone.utc),
        )

    @classmethod
    def from_error(cls, agent_name: str, error: str) -> AgentSection:
        return cls(
            agent_name=agent_name,
            status="failed",
            error=error,
            completed_at=datetime.now(timezone.utc),
        )


@dataclass
class IoTSolution:
    """Assembled output document produced by the orchestrator."""

    problem: IoTProblem
    pipeline_status: PipelineStatus = PipelineStatus.PENDING
    sections: dict[str, AgentSection] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    # Canonical agent order matches the execution graph in CLAUDE.md
    AGENT_ORDER: list[str] = field(
        default_factory=lambda: [
            "requirements_agent",
            "hardware_agent",
            "connectivity_agent",
            "data_agent",
            "cloud_agent",
            "security_agent",
            "deployment_agent",
            "methodology_agent",
        ],
        repr=False,
    )

    def __post_init__(self) -> None:
        for agent_name in self.AGENT_ORDER:
            if agent_name not in self.sections:
                self.sections[agent_name] = AgentSection.pending(agent_name)

    def record(self, section: AgentSection) -> None:
        """Update a section in place."""
        self.sections[section.agent_name] = section

    def mark_complete(self) -> None:
        self.pipeline_status = PipelineStatus.COMPLETE
        self.completed_at = datetime.now(timezone.utc)

    def mark_failed(self) -> None:
        self.pipeline_status = PipelineStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)

    def failed_sections(self) -> list[AgentSection]:
        return [s for s in self.sections.values() if s.status == "failed"]

    def is_complete(self) -> bool:
        return all(s.status == "complete" for s in self.sections.values())
