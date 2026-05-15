from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IoTProblem:
    """Represents the user's IoT problem statement fed into the pipeline."""

    statement: str
    region: str = "colombia"
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.statement.strip():
            raise ValueError("IoTProblem.statement must not be empty")
        self.region = self.region.lower().strip()
