# IoT Solution Creator

> A multi-agent system that designs complete, production-ready IoT solutions end-to-end — from a plain-language problem statement to a full technical specification and executive report.

---

## Table of Contents

1. [Overview](#overview)
2. [Why This Project](#why-this-project)
3. [System Architecture](#system-architecture)
4. [The 8 Specialized Agents](#the-8-specialized-agents)
5. [Execution Pipeline](#execution-pipeline)
6. [Output Formats](#output-formats)
7. [Project Structure](#project-structure)
8. [Installation](#installation)
9. [Configuration](#configuration)
10. [Usage](#usage)
11. [Examples](#examples)
12. [Testing](#testing)
13. [Usage Recommendations](#usage-recommendations)
14. [Limitations and Known Constraints](#limitations-and-known-constraints)

---

## Overview

**IoT Solution Creator** takes a business problem statement as input and autonomously produces a complete IoT solution specification. It coordinates 8 specialized AI agents — each an expert in one domain — through a central orchestrator that enforces dependency order, handles failures, and assembles the outputs into coherent reports.

**Input example:**

```
Monitor soil moisture across 500 hectares of farmland and trigger irrigation automatically.
```

**What you get back:**

- A structured technical report covering hardware, connectivity, data pipeline, cloud infrastructure, security model, and deployment plan.
- A PM/executive-friendly report with tables, recommendations, risk register, and an AI-generated executive summary.
- A persistent JSON state file that allows interrupted pipelines to resume.

---

## Why This Project

Designing an IoT solution from scratch requires expertise across domains that rarely coexist in a single person or even a small team: embedded hardware, wireless protocols, cloud architecture, cybersecurity, data engineering, and project management. This project addresses that gap by codifying each domain as an autonomous AI agent with a focused system prompt, strict input/output contracts, and access to shared tools.

The multi-agent approach offers several advantages over a single monolithic LLM call:

| Concern | Single-prompt approach | Multi-agent approach |
|---|---|---|
| **Context quality** | All domains compete for the same context window | Each agent receives only the context it needs |
| **Specialization** | Generalist output | Each agent is guided by a domain-specific system prompt |
| **Traceability** | One opaque blob of output | Every agent's output is independently inspectable |
| **Resilience** | One failure = total failure | Agents are retried; partial failures are isolated and flagged |
| **Parallelism** | Sequential by nature | Independent agents (e.g., hardware + connectivity) run concurrently |
| **Iterability** | Hard to improve one section without re-running everything | Individual agents can be swapped, tuned, or re-run in isolation |

The system is designed with **Colombian IoT deployment context** as the default (`REGION=colombia`), applying local regulatory constraints (MinTIC resolutions, RNDC, CRC), hardware availability filters, and connectivity realities (e.g., LoRaWAN coverage maps, cellular operators). The region setting is configurable.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Orchestrator                           │
│                                                                 │
│   IoTProblem ──► Planner ──► Execution Graph ──► Assembler      │
│                                    │                            │
│                       persists project_state.json               │
└─────────────────────────────────────────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │         Message Bus          │
              │     (async pub/sub)          │
              └──────────────┬──────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                     ▼
  RequirementsAgent    HardwareAgent        ConnectivityAgent
        │                    │                     │
        └────────────────────┼─────────────────────┘
                             ▼
                        DataAgent
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
          CloudAgent               SecurityAgent
                │                         │
                └────────────┬────────────┘
                             ▼
                      DeploymentAgent
                             │
                             ▼
                     MethodologyAgent
```

### Key components

| Component | Location | Responsibility |
|---|---|---|
| **Orchestrator** | `orchestrator/orchestrator.py` | Runs the pipeline, enforces dependency order, retries, persists state |
| **Planner** | `orchestrator/planner.py` | Resolves the execution graph; yields batches of concurrently-runnable agents |
| **Assembler** | `orchestrator/assembler.py` | Merges all agent outputs into the two final Markdown reports |
| **Message Bus** | `bus/message_bus.py` | Async pub/sub channel; agents communicate only through this |
| **LLM Client** | `tools/llm_client.py` | Single shared `AsyncAnthropic` wrapper; all agents go through here |
| **Report Renderer** | `tools/report_renderer.py` | Converts raw agent JSON into human-readable Markdown sections |

---

## The 8 Specialized Agents

Each agent inherits from `BaseAgent` (`agents/base_agent.py`), loads its system prompt from `prompts/<agent_name>.md` at startup, and implements one method: `async def process(payload: dict) -> dict`.

### 1. Requirements Agent (`requirements_agent`)

**Input:** Raw problem statement + region metadata.

**Responsibility:** Extracts and structures all functional and non-functional requirements. Identifies scale, latency targets, data retention policies, regulatory constraints, and open ambiguities that downstream agents must resolve.

**Key output fields:**
```json
{
  "business_goal": "string",
  "functional_requirements": ["..."],
  "non_functional_requirements": {
    "latency_ms": 500,
    "availability_pct": 99.5,
    "data_retention_days": 365,
    "regulatory": ["MinTIC Res. 415", "IEC 62443"]
  },
  "scale": { "nodes": 200, "area_ha": 500, "locations": 1 },
  "region_constraints": { "country": "colombia", "notes": "..." },
  "ambiguities": ["..."]
}
```

---

### 2. Hardware Agent (`hardware_agent`)

**Input:** Structured requirements.

**Responsibility:** Selects the hardware stack — sensors, actuators, microcontrollers, edge gateways, power systems — taking into account regional availability and regulatory homologation.

**Key output fields:**
```json
{
  "sensors": [{ "type": "soil_moisture", "model": "...", "protocol": "SDI-12" }],
  "microcontroller": { "model": "...", "cores": 1, "flash_kb": 512 },
  "gateway": { "model": "...", "connectivity": ["LoRaWAN", "LTE"] },
  "power": { "source": "solar", "battery_wh": 20, "autonomy_days": 7 },
  "bom_estimate_usd": 18500,
  "regional_notes": "..."
}
```

---

### 3. Connectivity Agent (`connectivity_agent`)

**Input:** Structured requirements.

**Responsibility:** Selects communication protocols, defines the network topology, specifies QoS requirements, and maps protocol capabilities against range, power, and bandwidth constraints.

**Key output fields:**
```json
{
  "primary_protocol": "LoRaWAN",
  "secondary_protocol": "LTE-M",
  "network_topology": "star",
  "uplink_frequency_sec": 300,
  "payload_size_bytes": 64,
  "frequency_band": "915 MHz ISM (Colombia)",
  "operator_recommendation": "...",
  "justification": "..."
}
```

---

### 4. Data Agent (`data_agent`)

**Input:** Requirements + hardware + connectivity outputs.

**Responsibility:** Designs the full data pipeline: ingestion endpoints, real-time streaming vs. batch processing, storage tiers (hot/warm/cold), schema design, and data quality strategy.

**Key output fields:**
```json
{
  "ingestion": { "protocol": "MQTT", "broker": "AWS IoT Core", "qos": 1 },
  "streaming": { "engine": "Kinesis Data Streams", "shards": 2 },
  "storage": {
    "hot": { "engine": "DynamoDB", "retention_days": 7 },
    "warm": { "engine": "S3 + Athena", "retention_days": 90 },
    "cold": { "engine": "S3 Glacier", "retention_years": 5 }
  },
  "schema": { "fields": ["device_id", "timestamp", "moisture_pct", "battery_mv"] },
  "processing": { "aggregation_window_min": 15, "anomaly_detection": true }
}
```

---

### 5. Cloud Agent (`cloud_agent`)

**Input:** Requirements + data pipeline outputs.

**Responsibility:** Specifies cloud services, Infrastructure-as-Code approach, auto-scaling strategy, multi-region or single-region deployment, and a cost estimate.

**Key output fields:**
```json
{
  "provider": "AWS",
  "services": ["IoT Core", "Lambda", "DynamoDB", "S3", "CloudWatch"],
  "iac_tool": "Terraform",
  "scaling": { "strategy": "auto", "min_instances": 1, "max_instances": 10 },
  "region": "us-east-1",
  "monthly_cost_usd_estimate": 320,
  "ha_strategy": "multi-az"
}
```

---

### 6. Security Agent (`security_agent`)

**Input:** Requirements + connectivity + cloud outputs.

**Responsibility:** Produces the security model: device identity and authentication, data encryption in transit and at rest, firmware OTA update strategy, and a threat model aligned to IEC 62443 / OWASP IoT.

**Key output fields:**
```json
{
  "device_identity": { "method": "X.509 certificates", "provisioning": "AWS IoT Fleet Provisioning" },
  "transport_security": { "protocol": "TLS 1.3", "cipher": "ECDHE-AES256-GCM" },
  "storage_encryption": { "algorithm": "AES-256", "key_management": "AWS KMS" },
  "ota_strategy": { "tool": "AWS IoT Jobs", "signing": true, "rollback": true },
  "threat_model": [{ "threat": "...", "mitigation": "...", "severity": "high" }],
  "compliance_references": ["IEC 62443-4-2", "OWASP IoT Top 10"]
}
```

---

### 7. Deployment Agent (`deployment_agent`)

**Input:** Requirements + cloud + security outputs.

**Responsibility:** Creates the rollout plan: device provisioning workflow, CI/CD pipeline for firmware and cloud infrastructure, monitoring and alerting setup, and operational runbooks.

**Key output fields:**
```json
{
  "provisioning": { "method": "zero-touch", "tool": "AWS IoT Fleet Provisioning" },
  "firmware_cicd": { "platform": "GitHub Actions", "stages": ["build", "test", "sign", "ota"] },
  "cloud_cicd": { "platform": "GitHub Actions + Terraform Cloud", "stages": ["plan", "apply"] },
  "monitoring": { "platform": "CloudWatch + Grafana", "alerting": "PagerDuty" },
  "rollout_phases": [{ "phase": 1, "devices": 20, "duration_days": 14, "go_criteria": "..." }]
}
```

---

### 8. Methodology Agent (`methodology_agent`)

**Input:** All previous agent outputs.

**Responsibility:** Synthesizes the project management layer: recommended methodology (Agile/Stage-Gate), work breakdown structure, risk register, budget timeline, and an executive summary paragraph suitable for a steering committee.

**Key output fields:**
```json
{
  "methodology": "Stage-Gate + Agile sprints",
  "phases": [{ "name": "Discovery", "duration_weeks": 2, "deliverables": ["..."] }],
  "risks": [{ "risk": "...", "probability": "medium", "impact": "high", "mitigation": "..." }],
  "total_duration_weeks": 24,
  "team_roles": ["IoT Architect", "Cloud Engineer", "Firmware Engineer", "PM"],
  "executive_summary": "..."
}
```

---

## Execution Pipeline

The orchestrator enforces this dependency graph. Agents at the same level run concurrently.

```
requirements_agent
        │
        ▼
hardware_agent ──── connectivity_agent   ← parallel
        │                   │
        └──────────┬─────────┘
                   ▼
             data_agent
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
  cloud_agent          security_agent     ← parallel
        │                     │
        └──────────┬───────────┘
                   ▼
          deployment_agent
                   │
                   ▼
         methodology_agent
```

**Failure handling:**

- Each agent is retried up to **2 times** before the orchestrator marks it as failed.
- A failed agent does not stop the pipeline; downstream agents that depend on it are marked `skipped`, while independent agents continue.
- The final report clearly marks any section that could not be completed.
- The orchestrator emits a `PIPELINE_COMPLETE` or `PIPELINE_FAILED` terminal event.

**State persistence:**

After each agent completes, the orchestrator atomically writes `project_state.json`. If the process is interrupted mid-run, restart the CLI and the orchestrator will prompt you to resume from the last completed agent.

---

## Output Formats

The system produces two Markdown files and one JSON state file.

### 1. Technical Report (`<problem_name>_report.md`)

A structured document containing the raw JSON output of each agent, rendered as human-readable Markdown using section-specific formatters. Intended for IoT architects, engineers, and technical leads.

**Sections included:**

| Section | Source agent |
|---|---|
| Requirements | `requirements_agent` |
| Hardware Selection | `hardware_agent` |
| Connectivity Design | `connectivity_agent` |
| Data Pipeline | `data_agent` |
| Cloud Infrastructure | `cloud_agent` |
| Security Model | `security_agent` |
| Deployment Plan | `deployment_agent` |
| Project Methodology | `methodology_agent` |

**Sample rendering (hardware section):**

```markdown
## Hardware Selection

### Bill of Materials

| Component | Model | Qty | Unit Cost (USD) |
|---|---|---|---|
| Soil Moisture Sensor | Decagon 5TM | 200 | $45 |
| Microcontroller | STM32WL55 | 200 | $12 |
| LoRaWAN Gateway | RAK7249 | 5 | $350 |

**Estimated BOM total:** $18,500 USD

### Power Strategy
Solar + 3.7V LiPo (20 Wh). Estimated autonomy: 7 days without sun.
```

---

### 2. Executive Report (`<problem_name>_report_executive.md`)

A PM/PO-friendly document with the same content reformatted for non-technical stakeholders. Produced by the `Assembler` using the `report_renderer.py` formatters plus a final LLM call that generates a cohesive executive summary.

**Additions over the technical report:**

- **Executive Summary** — 3–5 paragraph narrative generated by Claude, synthesizing the entire solution.
- **Risk Register table** — probability/impact matrix with mitigations.
- **Budget overview** — hardware BOM + cloud monthly cost + implementation estimate.
- **Recommended team structure** — roles and approximate staffing.
- **Project timeline overview** — phases and durations in a structured table.
- **Key recommendations** — top 5 actionable bullets drawn from all agents.

---

### 3. Pipeline State (`project_state.json`)

A runtime JSON file that captures the full pipeline state. **Not intended for end users** — it is the orchestrator's source of truth for resumption and auditing.

```json
{
  "problem": {
    "statement": "Monitor soil moisture...",
    "region": "colombia",
    "metadata": {}
  },
  "agent_outputs": {
    "requirements_agent": { "business_goal": "...", "functional_requirements": [] },
    "hardware_agent": {},
    "connectivity_agent": {},
    "data_agent": {},
    "cloud_agent": {},
    "security_agent": {},
    "deployment_agent": {},
    "methodology_agent": {}
  },
  "pipeline_status": "complete"
}
```

`pipeline_status` values:

| Value | Meaning |
|---|---|
| `pending` | Pipeline created but not yet started |
| `running` | One or more agents are currently executing |
| `complete` | All agents finished successfully |
| `failed` | One or more agents failed after all retries |

---

## Project Structure

```
iot_solution_creator/
├── agents/
│   ├── base_agent.py           # Abstract base; all agents inherit from here
│   ├── requirements_agent.py
│   ├── hardware_agent.py
│   ├── connectivity_agent.py
│   ├── data_agent.py
│   ├── cloud_agent.py
│   ├── security_agent.py
│   ├── deployment_agent.py
│   └── methodology_agent.py
│
├── bus/
│   ├── message.py              # Message & MessageType dataclasses
│   └── message_bus.py          # Async in-process pub/sub
│
├── models/
│   ├── problem.py              # IoTProblem dataclass (input)
│   └── solution.py             # IoTSolution dataclass (assembled output)
│
├── orchestrator/
│   ├── __main__.py             # CLI entry point
│   ├── orchestrator.py         # Main pipeline logic
│   ├── planner.py              # Dependency graph + batch resolver
│   └── assembler.py            # Report generation
│
├── prompts/                    # System prompt for each agent (Markdown)
│   ├── requirements_agent.md
│   ├── hardware_agent.md
│   ├── connectivity_agent.md
│   ├── data_agent.md
│   ├── cloud_agent.md
│   ├── security_agent.md
│   ├── deployment_agent.md
│   └── methodology_agent.md
│
├── tools/
│   ├── llm_client.py           # Shared AsyncAnthropic wrapper
│   └── report_renderer.py      # Markdown formatters per agent section
│
├── tests/
│   ├── conftest.py             # Shared fixtures and mock agent outputs
│   ├── unit/
│   │   ├── test_orchestrator.py
│   │   └── agents/test_agents.py
│   └── integration/
│       └── test_full_pipeline.py
│
├── examples/
│   ├── smart_irrigation.py
│   ├── smart_building.py
│   ├── industrial_monitoring.py
│   └── .env                    # Environment variable template
│
├── pyproject.toml
├── CLAUDE.md                   # Developer architecture guide
└── README.md
```

---

## Installation

**Requirements:** Python 3.11+, an Anthropic API key.

```bash
# Clone the repository
git clone <repo-url>
cd iot_solution_creator

# Install the package and all dependencies (including dev tools)
pip install -e ".[dev]"
```

This installs:

| Package | Purpose |
|---|---|
| `anthropic` | Anthropic Python SDK (LLM calls) |
| `structlog` | Structured JSON logging |
| `pytest` + `pytest-asyncio` | Test runner for async code |
| `pytest-cov` | Coverage reporting |
| `ruff` | Linting and formatting |

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Your Anthropic API key |
| `REGION` | No | `colombia` | Filters hardware recommendations and applies local regulations |

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export REGION="colombia"
```

Or copy `examples/.env` to `.env` and fill in the values.

### Model Configuration

The default model is `claude-sonnet-4-6`. To change it, edit `tools/llm_client.py`:

```python
DEFAULT_MODEL = "claude-sonnet-4-6"
```

Available options: `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`.

### Token Budgets

Default per-agent limits (configurable in each agent's `process()` method):

| Agent | Max output tokens |
|---|---|
| `requirements_agent` | 4,000 |
| `hardware_agent` | 4,000 |
| `connectivity_agent` | 4,000 |
| `data_agent` | 8,000 |
| `cloud_agent` | 8,000 |
| `security_agent` | 8,000 |
| `deployment_agent` | 16,000 |
| `methodology_agent` | 16,000 |

---

## Usage

### CLI

```bash
# Basic run
python -m orchestrator --problem "Monitor soil moisture across 500 hectares and trigger irrigation automatically"

# With explicit region
python -m orchestrator --problem "Track location of 1000 shipping containers across 3 ports" --region colombia

# Resume an interrupted pipeline
python -m orchestrator --resume
```

Output files are written to the current directory:
- `<sanitized_problem>_report.md`
- `<sanitized_problem>_report_executive.md`

### Programmatic API

```python
import asyncio
from models.problem import IoTProblem
from orchestrator.orchestrator import Orchestrator

async def main():
    problem = IoTProblem(
        statement="Monitor air quality across 20 schools in Bogotá",
        region="colombia",
    )
    orchestrator = Orchestrator(problem)
    solution = await orchestrator.run()
    print(f"Status: {solution.pipeline_status}")
    print(f"Reports: {solution.report_paths}")

asyncio.run(main())
```

---

## Examples

Three fully worked examples are provided in `examples/`:

### Smart Irrigation (500 ha)

```bash
python examples/smart_irrigation.py
```

Covers: 200 soil moisture sensor nodes, LoRaWAN 915 MHz, solar power, automated irrigation valves, AWS IoT Core + Lambda, S3 time-series storage.

### Smart Building (Hospital Asset Tracking)

```bash
python examples/smart_building.py
```

Covers: BLE + UWB hybrid positioning, multi-floor topology, real-time asset location dashboard, HIPAA-aware data handling.

### Industrial Motor Monitoring

```bash
python examples/industrial_monitoring.py
```

Covers: 80 motors, vibration + temperature sensors, OPC-UA to cloud bridge, predictive maintenance model integration, SCADA compatibility.

---

## Testing

```bash
# Run all tests with coverage
pytest tests/ -v --cov=agents --cov=orchestrator --cov-report=term-missing

# Unit tests only (fast, no API calls)
pytest tests/unit/ -v

# Integration tests (mocked LLM — no real API calls)
pytest tests/integration/ -v

# Lint and format check
ruff check .
ruff format --check .
```

**Coverage target:** 80%+ across `agents/` and `orchestrator/`.

All LLM calls in tests are mocked via fixtures in `tests/conftest.py`. No real API key is needed to run the test suite.

---

## Usage Recommendations

### When to use this system

- **Pre-sales / scoping:** Generate a first-cut technical specification in minutes to validate feasibility and estimate costs before committing an engineering team.
- **Architecture workshops:** Use the output as a structured starting point for collaborative refinement — it is easier to critique and improve a concrete proposal than to start from a blank whiteboard.
- **RFP responses:** Quickly produce a technically coherent IoT architecture for a customer proposal, then have your engineers review and adapt each section.
- **Education and training:** Walk junior engineers through a complete IoT design by studying each agent's output and the tradeoffs it encodes.
- **Multi-domain onboarding:** When a team is new to IoT, the report surfaces the domains they need to hire or consult for.

### Crafting effective problem statements

The quality of the output depends heavily on the input. Follow these guidelines:

| Do | Avoid |
|---|---|
| State the business outcome, not the technology | "I need MQTT and LoRa" |
| Include scale (number of devices, geographic area) | Vague quantities like "many sensors" |
| Mention the operational environment (indoor/outdoor, harsh conditions) | Assuming context is obvious |
| List any known regulatory constraints | Assuming the system knows your specific certifications |
| Specify data freshness requirements | Leaving latency and retention unspecified |

**Good example:**
> "Monitor temperature and humidity in 15 cold-storage warehouses across Colombia. Alerts must trigger within 30 seconds of a threshold breach. Data must be retained for 3 years for INVIMA compliance. Each warehouse has intermittent internet."

**Poor example:**
> "IoT monitoring for warehouses."

### Reviewing and validating the output

The system produces recommendations, not final engineering decisions. Before acting on any section:

1. **Hardware:** Verify regional availability and pricing with local distributors. MCU and sensor models change frequently.
2. **Connectivity:** Validate LoRaWAN or NB-IoT coverage for your specific geography using operator coverage maps.
3. **Cloud costs:** Treat the cost estimate as an order-of-magnitude figure. Use the cloud provider's actual pricing calculator with your real traffic projections.
4. **Security:** Have a security engineer review the threat model. The agent applies general best practices; your specific deployment may have additional attack surfaces.
5. **Regulatory:** Confirm all regulatory references with a legal/compliance specialist. MinTIC resolutions and homologation requirements change.
6. **Methodology:** Adjust team size and timeline estimates to your organization's actual capacity and velocity.

### Working with the reports

- **Technical report** → share with your engineering team for design review.
- **Executive report** → share with project sponsors, customers, or steering committees.
- Both reports are plain Markdown — paste them into Notion, Confluence, Google Docs, or any Markdown-rendering system.
- The JSON in `project_state.json` is machine-readable and can be consumed by downstream tools or dashboards.

### Iterating on a solution

If a section is unsatisfactory, you do not need to re-run the full pipeline:

1. Edit the relevant `prompts/<agent_name>.md` to add constraints or correct the agent's behavior.
2. Delete the agent's key from `project_state.json` `agent_outputs`.
3. Re-run the orchestrator with `--resume`. It will re-execute only the cleared agent and all downstream dependencies.

### Extending the system

To add a new agent:

1. Create `agents/<new_agent>.py` inheriting from `BaseAgent`.
2. Implement `async def process(self, payload: dict) -> dict`.
3. Add a system prompt to `prompts/<new_agent>.md` with the output JSON schema.
4. Register the agent in `orchestrator/planner.py` with its upstream dependencies.
5. Add a renderer function in `tools/report_renderer.py`.
6. Write unit tests in `tests/unit/agents/test_agents.py`.

---

## Limitations and Known Constraints

| Limitation | Notes |
|---|---|
| **No real-time data access** | Agents work from training knowledge and your problem statement. They cannot browse datasheets, check live pricing, or query coverage maps at runtime. |
| **Hardware models may be outdated** | LLM training data has a cutoff. Always verify recommended hardware models against current distributor catalogs. |
| **Cost estimates are approximate** | Cloud cost figures are directional. Use the AWS/GCP/Azure pricing calculator for production planning. |
| **No CAD or schematic output** | The system produces specifications and recommendations, not hardware schematics or PCB layouts. |
| **Single region per run** | The `REGION` variable applies globally. Multi-region deployments require separate runs or a custom orchestrator extension. |
| **Sequential on small machines** | The `asyncio` concurrency model means parallel agents share one event loop. On CPU-bound workloads or very slow LLM responses, throughput is limited. |
| **No human-in-the-loop** | The current pipeline runs fully automated. There is no built-in step for an engineer to review and correct intermediate outputs before downstream agents consume them. |

---

## License

This project is private. All rights reserved.

---

*Built with [Claude](https://anthropic.com/claude) · Powered by the Anthropic API*
