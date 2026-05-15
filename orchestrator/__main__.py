from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import structlog

from models.problem import IoTProblem
from orchestrator.orchestrator import Orchestrator

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)

logger = structlog.get_logger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m orchestrator",
        description="IoT Solution Creator — generate a complete IoT solution from a problem statement.",
    )
    parser.add_argument(
        "--problem",
        required=True,
        help="The IoT problem statement to solve.",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("REGION", "colombia"),
        help="Deployment region (default: colombia or $REGION env var).",
    )
    parser.add_argument(
        "--output",
        default="iot_solution_report.md",
        help="Path for the output Markdown report (default: iot_solution_report.md).",
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("startup.missing_api_key")
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        return 1

    problem = IoTProblem(statement=args.problem, region=args.region)
    orchestrator = Orchestrator(output_path=Path(args.output))

    logger.info("pipeline.start", problem=args.problem[:80], region=args.region)
    solution = await orchestrator.run(problem)

    if solution.is_complete():
        print(f"\nSolution complete. Report saved to: {args.output}")
        return 0
    else:
        failed = [s.agent_name for s in solution.failed_sections()]
        print(f"\nPipeline finished with failures in: {failed}", file=sys.stderr)
        print(f"Partial report saved to: {args.output}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
