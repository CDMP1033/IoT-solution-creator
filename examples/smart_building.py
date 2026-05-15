"""
Smart Building Energy Management — Example

Monitors and controls HVAC, lighting, and energy consumption across a
multi-floor commercial building to reduce energy costs by 30%.

Run:
    export ANTHROPIC_API_KEY=sk-...
    python examples/smart_building.py
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
        "Design an IoT asset tracking solution for a hospital facility in Medellín, Colombia (1,450 m ASL, ~25°C average indoor temperature)."
        "Facility: 2 towers, 10 floors each. High RF-noise environment (medical equipment, Wi-Fi, BLE, RFID coexistence)."
        "Core requirements:"
        "Real-time location tracking of medical assets across all zones"
        "Geofence alerting when an asset leaves its designated zone"
        "Mobile and web dashboard with live asset map, status, and alert feed"
        "Deliverables expected:"
        "Technology stack recommendation — evaluate commercial off-the-shelf solutions (e.g., RTLS vendors) AND a custom-design alternative, comparing both on cost-benefit, RF suitability for noisy hospital environments, and deployment complexity"
        "Hardware architecture — tags, anchors/gateways, topology per floor/tower"
        "Communication protocol selection justified for the RF environment (BLE AoA, UWB, LoRa, Wi-Fi, or hybrid)"
        "Backend + cloud architecture for data ingestion, geofencing logic, and alert dispatch"
        "Frontend spec for mobile (iOS/Android) and web app"
        "Bill of materials estimate and TCO comparison between the commercial and custom approaches"
        "Prioritize solutions with proven hospital deployments or equivalent high-interference environments. Flag any regulatory or EMI compliance considerations relevant to Colombian healthcare standards (Resolución 4816/2008, IEC 60601 coexistence)."
    ),
    region="colombia",
    metadata={
        "industry": "healthcare",
        "building_type": "commercial_office",
        "floors": 10,
        "city": "medellin",
        "tenant_sector": "technology",
    },
)


async def main() -> None:
    print("=" * 60)
    print("IoT Solution Creator — Smart Building Energy Management")
    print("=" * 60)
    print(f"Problem: {PROBLEM.statement[:80]}...")
    print(f"Region:  {PROBLEM.region}")
    print()

    orchestrator = Orchestrator(output_path=Path("smart_building_report.md"))
    solution = await orchestrator.run(PROBLEM)

    print()
    print(f"Status : {solution.pipeline_status.value.upper()}")
    print(f"Report : smart_building_report.md")

    if solution.failed_sections():
        print("Failed sections:")
        for sec in solution.failed_sections():
            print(f"  - {sec.agent_name}: {sec.error}")


if __name__ == "__main__":
    asyncio.run(main())
