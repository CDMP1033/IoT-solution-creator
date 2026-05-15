"""
Smart Irrigation — Example

Monitors soil moisture across large agricultural land and automatically
triggers irrigation valves when moisture drops below threshold.

Run:
    export ANTHROPIC_API_KEY=sk-...
    python examples/smart_irrigation.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make the project root importable when running as a script.
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.problem import IoTProblem
from orchestrator.orchestrator import Orchestrator


PROBLEM = IoTProblem(
    statement=(
        "Monitor soil moisture across 500 hectares of farmland in the Sabana de Bogotá "
        "and automatically trigger drip irrigation valves when moisture drops below 30%. "
        "The system must support up to 200 sensor nodes, operate on solar power, and "
        "send agronomist alerts via mobile app when critical thresholds are breached."
        "the system should also provide a dashboard with real-time soil moisture data, irrigation "
        "the sensor shuold be able to reprogrwmming over the air and the system should be able to predict irrigation needs based on weather forecasts and historical data." \
        "Additionally, the solution should be cost-effective, easy to maintain, and scalable for future expansion to neighboring farms."
    ),
    region="colombia",
    metadata={
        "industry": "agriculture",
        "crop": "potato",
        "altitude_m": 2600,
    },
)


async def main() -> None:
    print("=" * 60)
    print("IoT Solution Creator — Smart Irrigation")
    print("=" * 60)
    print(f"Problem: {PROBLEM.statement[:80]}...")
    print(f"Region:  {PROBLEM.region}")
    print()

    orchestrator = Orchestrator(output_path=Path("smart_irrigation_report.md"))
    solution = await orchestrator.run(PROBLEM)

    print()
    print(f"Status : {solution.pipeline_status.value.upper()}")
    print(f"Report : smart_irrigation_report.md")

    if solution.failed_sections():
        print("Failed sections:")
        for sec in solution.failed_sections():
            print(f"  - {sec.agent_name}: {sec.error}")


if __name__ == "__main__":
    asyncio.run(main())
