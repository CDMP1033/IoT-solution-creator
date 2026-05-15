from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared sample outputs — reused across unit and integration tests
# ---------------------------------------------------------------------------

REQUIREMENTS_OUTPUT = {
    "business_goal": "Monitor soil moisture across 500 ha and trigger irrigation automatically",
    "functional_requirements": ["Read soil moisture every 5 min", "Trigger irrigation valve"],
    "non_functional_requirements": {
        "latency_ms": 5000,
        "availability_percent": 99.5,
        "data_retention_days": 365,
        "max_cost_usd_per_device_month": 2.0,
        "regulatory": ["MinTIC spectrum"],
    },
    "scale": {"num_devices": 200, "data_frequency_seconds": 300, "geographic_spread_km2": 5.0},
    "region_constraints": ["915 MHz ISM band"],
    "ambiguities": [],
}

HARDWARE_OUTPUT = {
    "sensors": [{"name": "Capacitive Soil Sensor v1.2", "measurement": "soil moisture",
                 "interface": "analog", "unit_cost_usd": 3.5, "notes": ""}],
    "actuators": [{"name": "Solenoid Valve 12V", "function": "irrigation control",
                   "interface": "digital", "unit_cost_usd": 8.0, "notes": ""}],
    "microcontroller": {"model": "ESP32-WROOM-32", "cpu": "Xtensa LX6 240 MHz",
                        "ram_kb": 520, "flash_kb": 4096,
                        "built_in_connectivity": ["WiFi", "BLE"],
                        "unit_cost_usd": 4.0, "justification": "Low cost, LoRa via SX1276 add-on"},
    "edge_gateway": {"model": "Raspberry Pi 4 2GB", "role": "LoRa gateway",
                     "unit_cost_usd": 45.0},
    "power": {"strategy": "solar", "battery_type": "LiPo",
              "estimated_battery_life_days": None, "solar_panel_w": 5.0},
    "bom_summary": {"cost_per_device_usd": 25.5, "total_deployment_cost_usd": 5100.0,
                    "num_devices": 200},
    "region_availability_notes": "Available via Electronilab Colombia",
    "alternatives": ["RAK Wireless WisDuo"],
}

CONNECTIVITY_OUTPUT = {
    "device_protocol": {"name": "LoRaWAN", "frequency_band": "915 MHz ISM",
                        "max_range_m": 5000, "data_rate_bps": 5470,
                        "power_consumption": "ultra-low",
                        "justification": "Long range, low power, ideal for rural"},
    "backhaul": {"name": "LTE", "provider_examples": ["Claro", "Movistar"],
                 "estimated_monthly_cost_usd": 15.0},
    "messaging_protocol": {"name": "MQTT", "broker_or_endpoint": "AWS IoT Core",
                           "qos_level": 1, "payload_format": "JSON"},
    "topology": {"type": "star", "description": "Devices → LoRa gateway → cloud",
                 "num_gateways": 2},
    "bandwidth_per_device": {"uplink_bytes_per_message": 50,
                             "messages_per_day": 288, "total_daily_mb_all_devices": 2.74},
    "coverage_notes": "915 MHz good rural coverage in Colombia",
    "alternatives": ["NB-IoT with Claro"],
}

DATA_OUTPUT = {
    "ingestion": {"service": "AWS IoT Core", "protocol": "MQTT",
                  "throughput_msgs_per_second": 0.67, "partitioning_key": "device_id"},
    "stream_processing": {"engine": "AWS Lambda",
                          "rules": ["Alert if moisture < 20% for 3 consecutive readings"],
                          "latency_target_ms": 5000},
    "storage": {
        "hot": {"service": "InfluxDB Cloud", "retention_days": 30, "estimated_gb": 1.5},
        "warm": {"service": "S3", "retention_days": 365, "format": "Parquet", "estimated_gb": 18.0},
        "cold": {"service": "S3 Glacier", "retention_days": None, "estimated_gb": None},
    },
    "serving": {"dashboard": "Grafana", "api": "REST", "alerting": "SNS"},
    "telemetry_schema": {"device_id": "string", "timestamp": "ISO8601",
                         "readings": "moisture_pct: float, battery_mv: int"},
    "cost_estimate_usd_per_month": 35.0,
    "data_quality_notes": "Deduplicate on device_id + timestamp; fill gaps with last-known-good",
}

CLOUD_OUTPUT = {
    "provider": "AWS",
    "primary_region": "sa-east-1",
    "iot_platform": {"name": "AWS IoT Core", "justification": "Managed MQTT, scales to millions"},
    "services": [{"name": "AWS IoT Core", "role": "Device connectivity",
                  "tier": "standard", "estimated_cost_usd_per_month": 10.0}],
    "iac": {"tool": "Terraform", "language": "HCL", "repo_structure": "modules/ per service"},
    "scalability": {"auto_scaling": "Lambda scales automatically",
                    "peak_devices": 500, "peak_msgs_per_second": 1.5},
    "high_availability": {"multi_az": True, "rpo_minutes": 15, "rto_minutes": 30},
    "total_cost_usd_per_month": 55.0,
    "cost_optimization_notes": "Use S3 Intelligent-Tiering for warm storage",
}

SECURITY_OUTPUT = {
    "device_identity": {"mechanism": "X.509 certificates",
                        "provisioning": "factory provisioning",
                        "certificate_authority": "AWS IoT CA"},
    "encryption": {"in_transit": "TLS 1.3", "at_rest": "AES-256",
                   "key_management": "AWS KMS"},
    "ota_updates": {"mechanism": "AWS IoT Jobs", "signing": "code signing with private key",
                    "rollback": "automatic rollback on failure", "delta_updates": True},
    "threat_model": [
        {"threat": "Physical device tampering", "attack_vector": "physical",
         "likelihood": "medium", "impact": "high", "mitigation": "Tamper-evident enclosure"},
        {"threat": "MQTT broker DoS", "attack_vector": "network",
         "likelihood": "low", "impact": "medium", "mitigation": "AWS IoT throttling"},
        {"threat": "Firmware injection", "attack_vector": "supply chain",
         "likelihood": "low", "impact": "high", "mitigation": "Signed firmware only"},
        {"threat": "Credential theft", "attack_vector": "network",
         "likelihood": "medium", "impact": "high", "mitigation": "Certificate rotation"},
        {"threat": "Insider threat", "attack_vector": "insider",
         "likelihood": "low", "impact": "medium", "mitigation": "RBAC + audit logs"},
    ],
    "access_control": {"model": "RBAC", "roles": ["admin", "operator", "viewer"],
                       "mfa_required": True},
    "compliance": {"frameworks": ["OWASP IoT Top 10", "Ley 1581 Colombia"],
                   "notes": "No PII collected — only sensor readings"},
    "hardening_checklist": ["Disable UART in production", "Unique cert per device"],
}

DEPLOYMENT_OUTPUT = {
    "rollout_phases": [
        {"phase": "Pilot", "num_devices": 10, "duration_weeks": 4,
         "success_criteria": "99% uptime", "rollback_trigger": "uptime < 90%"},
        {"phase": "Full", "num_devices": 200, "duration_weeks": 8,
         "success_criteria": "All devices reporting", "rollback_trigger": "20% devices offline"},
    ],
    "firmware_cicd": {"tool": "GitHub Actions",
                      "stages": ["build", "unit test", "static analysis", "sign", "OTA deploy"],
                      "artifact_storage": "S3", "branch_strategy": "trunk-based"},
    "cloud_cicd": {"tool": "GitHub Actions", "stages": ["lint", "plan", "apply", "integration test"],
                   "environment_promotion": "dev → staging → prod", "approval_gates": True},
    "provisioning_workflow": {
        "steps": ["Flash firmware", "Inject X.509 cert", "Register in IoT Core", "Field install"],
        "tooling": "AWS IoT Fleet Provisioning",
        "estimated_time_per_device_minutes": 10,
    },
    "monitoring": {"infrastructure": "CloudWatch",
                   "device_health": "AWS IoT Device Defender",
                   "alerting_channels": ["SNS", "email"],
                   "key_metrics": ["moisture_pct", "device_heartbeat_age_s"]},
    "runbook_outline": ["on-call escalation", "device offline procedure",
                        "OTA failure recovery", "cloud incident response"],
}

METHODOLOGY_OUTPUT = {
    "methodology": {"name": "Scrum", "justification": "Short feedback loops for HW/SW iteration",
                    "sprint_length_weeks": 2,
                    "key_ceremonies": ["Sprint Planning", "Daily Standup", "Retrospective"]},
    "project_plan": [
        {"phase": "Discovery", "duration_weeks": 2,
         "deliverables": ["Requirements doc"], "dependencies": []},
        {"phase": "Pilot", "duration_weeks": 6,
         "deliverables": ["Deployed pilot"], "dependencies": ["Discovery"]},
    ],
    "risk_register": [
        {"risk": "LoRa coverage gaps", "category": "technical",
         "probability": "medium", "impact": "high",
         "mitigation": "Site survey before full rollout", "owner": "RF Engineer"},
        {"risk": "Import delays on hardware", "category": "schedule",
         "probability": "medium", "impact": "medium",
         "mitigation": "Order 12 weeks in advance", "owner": "Procurement"},
        {"risk": "AWS cost overrun", "category": "budget",
         "probability": "low", "impact": "medium",
         "mitigation": "Budget alerts at 80%", "owner": "Cloud Architect"},
        {"risk": "Ley 1581 non-compliance", "category": "regulatory",
         "probability": "low", "impact": "high",
         "mitigation": "Legal review of data flows", "owner": "Legal"},
        {"risk": "Firmware OTA failure in field", "category": "operational",
         "probability": "medium", "impact": "high",
         "mitigation": "Automatic rollback enabled", "owner": "DevOps"},
        {"risk": "Solar panel theft", "category": "operational",
         "probability": "medium", "impact": "medium",
         "mitigation": "Lockable enclosures", "owner": "Field Team"},
    ],
    "executive_summary": (
        "This solution monitors soil moisture across 500 hectares using 200 wireless sensors "
        "and automatically activates irrigation valves, reducing water waste by up to 40%."
    ),
    "architecture_decisions": [
        {"id": "ADR-001", "title": "LoRaWAN over NB-IoT",
         "decision": "Use LoRaWAN at 915 MHz",
         "rationale": "Better rural coverage and lower per-device cost",
         "consequences": "Requires on-site LoRa gateways"},
    ],
    "total_estimated_cost_usd": {
        "hardware": 5100.0, "cloud_per_month": 55.0, "development_weeks": 16,
    },
}


@pytest.fixture
def mock_llm():
    """Patch llm_client.complete for the entire test. Returns the AsyncMock."""
    with patch("tools.llm_client.llm_client.complete", new_callable=AsyncMock) as mock:
        yield mock


def make_llm_return(mock: AsyncMock, output: dict) -> None:
    """Configure mock to return *output* serialized as JSON."""
    mock.return_value = json.dumps(output)
