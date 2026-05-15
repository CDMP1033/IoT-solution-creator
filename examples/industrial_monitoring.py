"""
Industrial Machine Monitoring — Example

Monitors vibration, temperature, and current on industrial motors to detect
anomalies and predict failures before they cause downtime.

Run:
    export ANTHROPIC_API_KEY=sk-...
    python examples/industrial_monitoring.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.problem import IoTProblem
from orchestrator.orchestrator import Orchestrator


PROBLEM = IoTProblem(
    statement=(
        "Monitor vibration (3-axis), temperature, and electrical current on 80 industrial "
        "motors in a bottling plant in Medellín. Detect anomalies in real time and trigger "
        "maintenance alerts before equipment failure. The system must integrate with the "
        "plant's existing SCADA via OPC-UA and provide a predictive maintenance dashboard. "
        "Downtime costs USD 15,000/hour so availability must be 99.9%."
    ),
    region="colombia",
    metadata={
        "industry": "manufacturing",
        "facility": "bottling_plant",
        "city": "medellin",
        "existing_scada": True,
    },
)


async def main() -> None:
    print("=" * 60)
    print("IoT Solution Creator — Industrial Machine Monitoring")
    print("=" * 60)
    print(f"Problem: {PROBLEM.statement[:80]}...")
    print(f"Region:  {PROBLEM.region}")
    print()

    orchestrator = Orchestrator(output_path=Path("industrial_monitoring_report.md"))
    solution = await orchestrator.run(PROBLEM)

    print()
    print(f"Status : {solution.pipeline_status.value.upper()}")
    print(f"Report : industrial_monitoring_report.md")

    if solution.failed_sections():
        print("Failed sections:")
        for sec in solution.failed_sections():
            print(f"  - {sec.agent_name}: {sec.error}")


if __name__ == "__main__":
    asyncio.run(main())
