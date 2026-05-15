from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentTask:
    """A single node in the execution graph."""

    agent_name: str
    depends_on: list[str] = field(default_factory=list)

    def is_ready(self, completed: set[str]) -> bool:
        return all(dep in completed for dep in self.depends_on)


# Execution graph as declared in CLAUDE.md.
# Agents at the same level with no shared dependencies may run concurrently.
_EXECUTION_GRAPH: list[AgentTask] = [
    AgentTask("requirements_agent", depends_on=[]),
    AgentTask("hardware_agent",     depends_on=["requirements_agent"]),
    AgentTask("connectivity_agent", depends_on=["requirements_agent"]),
    AgentTask("data_agent",         depends_on=["hardware_agent", "connectivity_agent"]),
    AgentTask("cloud_agent",        depends_on=["data_agent", "connectivity_agent"]),
    AgentTask("security_agent",     depends_on=["hardware_agent", "connectivity_agent", "cloud_agent"]),
    AgentTask("deployment_agent",   depends_on=["cloud_agent", "security_agent"]),
    AgentTask("methodology_agent",  depends_on=[
        "requirements_agent", "hardware_agent", "connectivity_agent",
        "data_agent", "cloud_agent", "security_agent", "deployment_agent",
    ]),
]


class Planner:
    """Resolves the execution graph and yields batches of agents ready to run concurrently."""

    def __init__(self) -> None:
        self._tasks: dict[str, AgentTask] = {t.agent_name: t for t in _EXECUTION_GRAPH}

    @property
    def all_agent_names(self) -> list[str]:
        return list(self._tasks.keys())

    def next_batch(self, completed: set[str], failed: set[str]) -> list[str]:
        """Return agents that are ready to run but have not started yet.

        An agent is ready when all its dependencies are in *completed*.
        Agents that depend on a *failed* agent are skipped permanently — the
        orchestrator is responsible for marking them as failed too.

        Args:
            completed: Names of agents that finished successfully.
            failed:    Names of agents that failed (after retries).

        Returns:
            List of agent names that can start in parallel right now.
        """
        pending = set(self._tasks) - completed - failed
        return [
            name
            for name in pending
            if self._tasks[name].is_ready(completed)
            and not self._has_failed_dependency(name, failed)
        ]

    def downstream_of(self, agent_name: str) -> list[str]:
        """Return all agents that (transitively) depend on *agent_name*."""
        result: list[str] = []
        queue = [agent_name]
        visited: set[str] = set()
        while queue:
            current = queue.pop()
            for task in self._tasks.values():
                if current in task.depends_on and task.agent_name not in visited:
                    visited.add(task.agent_name)
                    result.append(task.agent_name)
                    queue.append(task.agent_name)
        return result

    def _has_failed_dependency(self, agent_name: str, failed: set[str]) -> bool:
        return any(dep in failed for dep in self._tasks[agent_name].depends_on)
