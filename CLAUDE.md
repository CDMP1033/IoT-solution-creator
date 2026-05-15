# IoT Solution Creator — CLAUDE.md

## Project Overview

Multi-agent system that designs complete IoT solutions end-to-end. Given a business problem or use case, the system produces a full technical specification: hardware selection, connectivity stack, data pipeline, cloud architecture, security model, and deployment plan.

The system is composed of 8 specialized agents coordinated by a central orchestrator. All agents are implemented in Python and communicate through a shared message bus (structured JSON payloads).

---

## System Architecture

### Orchestrator

**`orchestrator/`** — Receives the user's IoT problem statement, decomposes it into subtasks, dispatches work to the appropriate agents in the correct order, resolves dependencies between agents, and assembles the final solution document.

The orchestrator owns the global execution graph. Agents never call each other directly.

### The 8 Specialized Agents

| # | Agent | Responsibility |
|---|-------|---------------|
| 1 | `requirements_agent` | Extracts functional and non-functional requirements from the raw problem statement |
| 2 | `hardware_agent` | Selects sensors, actuators, microcontrollers, and edge devices |
| 3 | `connectivity_agent` | Chooses communication protocols (MQTT, CoAP, LoRaWAN, BLE, etc.) and network topology |
| 4 | `data_agent` | Designs the data pipeline: ingestion, processing, storage, and streaming strategy |
| 5 | `cloud_agent` | Defines the cloud infrastructure: services, IaC, scalability, and cost estimate |
| 6 | `security_agent` | Produces the security model: auth, encryption, firmware update strategy, threat model |
| 7 | `deployment_agent` | Creates the rollout plan: provisioning, CI/CD for firmware and cloud, monitoring setup |
| 8 | `methodology_agent` | Proposes the project methodology (Agile/Stage-Gate), generates structured technical documentation (use cases, diagrams, meeting minutes), and tracks project risks |

---

## Project Structure

```
iot_solution_creator/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── requirements.txt
│
├── orchestrator/
│   ├── __init__.py
│   ├── orchestrator.py        # Main orchestration logic and execution graph
│   ├── planner.py             # Decomposes problem into ordered agent tasks
│   └── assembler.py           # Merges agent outputs into the final document
│
├── agents/
│   ├── __init__.py
│   ├── base_agent.py          # Abstract base class all agents inherit from
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
│   ├── __init__.py
│   ├── message.py             # Message and Payload dataclasses
│   └── message_bus.py         # In-process pub/sub bus (async)
│
├── models/
│   ├── __init__.py
│   ├── problem.py             # Input: IoTProblem dataclass
│   └── solution.py            # Output: IoTSolution dataclass (assembled report)
│
├── prompts/
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
│   ├── __init__.py
│   └── ...                    # Shared utility tools (web search, doc retrieval, etc.)
│
├── tests/
│   ├── unit/
│   │   ├── test_orchestrator.py
│   │   └── agents/
│   │       └── test_*.py      # One test file per agent
│   └── integration/
│       └── test_full_pipeline.py
│
└── examples/
    ├── smart_irrigation.py
    ├── industrial_monitoring.py
    └── smart_building.py
```

---

## Python Conventions

### General

- Python 3.11+. Use `match` statements where appropriate.
- Type hints are mandatory on all function signatures. Use `from __future__ import annotations` at the top of every file.
- Prefer `dataclasses` or `pydantic` models over plain dicts for structured data.
- Use `async/await` throughout. The system is fully asynchronous — no blocking I/O.
- Line length: 100 characters. Formatter: `ruff format`. Linter: `ruff check`.
- No unused imports. No star imports (`from x import *`).
- Do not suppress type errors with `# type: ignore` without an inline comment explaining why.

### Naming

- Modules, variables, functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Agent class names follow the pattern `<Domain>Agent` (e.g., `HardwareAgent`, `SecurityAgent`)

### Error Handling

- Agents must never crash silently. All exceptions must be caught, logged, and re-raised as `AgentError` (defined in `agents/base_agent.py`).
- Use structured logging via `structlog`. Log every message received and sent by an agent.
- Do not use bare `except:` clauses. Catch the most specific exception type possible.

### Testing

- Every agent must have unit tests that mock the LLM call and the message bus.
- Integration tests must run a full pipeline with at least one real example problem.
- Target: 80%+ line coverage across `agents/` and `orchestrator/`.
- Use `pytest` with `pytest-asyncio` for async tests.

---

## Agent Interaction Rules

### Communication Protocol

All inter-agent communication goes through the message bus. Direct method calls between agents are forbidden.

Each message has the following structure:

```python
@dataclass
class Message:
    id: str                          # UUID
    sender: str                      # agent name or "orchestrator"
    recipient: str                   # agent name or "orchestrator"
    type: MessageType                # REQUEST | RESPONSE | ERROR
    payload: dict                    # agent-specific content
    correlation_id: str | None       # links a RESPONSE back to its REQUEST
    timestamp: datetime
```

### Execution Order

The orchestrator enforces this default dependency order:

```
requirements_agent
       │
       ▼
hardware_agent ──── connectivity_agent
       │                    │
       └────────┬───────────┘
                ▼
          data_agent
                │
       ┌────────┴────────┐
       ▼                 ▼
 cloud_agent      security_agent
       │                 │
       └────────┬────────┘
                ▼
        deployment_agent
                │
                ▼
       methodology_agent
```

Agents at the same level (e.g., `hardware_agent` and `connectivity_agent`) may run concurrently. The orchestrator must not start an agent until all its upstream dependencies have completed successfully.

### Context Passing

Each agent receives the outputs of its upstream dependencies as part of its input payload. The orchestrator injects the relevant context automatically — agents must not query the bus for other agents' outputs directly.

### Retries and Failures

- If an agent fails, the orchestrator retries it up to 2 times before marking the pipeline as failed.
- A partial failure (one agent failing) must not silently corrupt the final output — the assembled document must clearly mark which sections could not be completed.
- The orchestrator emits a final `PIPELINE_COMPLETE` or `PIPELINE_FAILED` event when done.

### Agent Contract

Every agent class must:

1. Inherit from `BaseAgent` in `agents/base_agent.py`.
2. Implement `async def process(self, payload: dict) -> dict`.
3. Not hold state between invocations — agents are stateless.
4. Not make direct HTTP calls outside of the tools provided in `tools/`.
5. Return a dict that conforms to the output schema defined in its corresponding `prompts/*.md` file.

---

## LLM Integration

- Use the Anthropic Python SDK (`anthropic`). Default model: `claude-sonnet-4-6`.
- All LLM calls must go through the shared client in `tools/llm_client.py` — no direct SDK instantiation inside agents.
- System prompts for each agent live in `prompts/<agent_name>.md`. Load them at agent startup, not on every call.
- Token budgets per agent call: input ≤ 8 000 tokens, output ≤ 4 000 tokens. The orchestrator may override these for complex tasks.

---

## State Management

The global pipeline state is persisted to `project_state.json` in the project root. This file is written by the orchestrator after every agent completes and is the single source of truth for resuming interrupted pipelines.

```json
{
  "problem": {
    "statement": "...",
    "region": "colombia",
    "metadata": {}
  },
  "agent_outputs": {
    "requirements_agent": {},
    "hardware_agent": {},
    "connectivity_agent": {},
    "data_agent": {},
    "cloud_agent": {},
    "security_agent": {},
    "deployment_agent": {},
    "methodology_agent": {}
  },
  "pipeline_status": "pending|running|complete|failed"
}
```

Rules:
- `project_state.json` is written atomically (write to a `.tmp` file, then rename) to avoid corruption.
- Agents must never read or write `project_state.json` directly — only the orchestrator does.
- The file is excluded from version control (add to `.gitignore`). It is runtime state, not source code.
- On startup, if `project_state.json` exists and `pipeline_status` is `running`, the orchestrator must prompt the user to resume or restart.

---

## Running the System

```bash
# Install dependencies
pip install -e ".[dev]"

# Set required environment variables
export REGION=colombia   # Filters hardware recommendations by local availability
                         # and applies MinTIC regulations (Resolución CRC, RNDC, etc.)

# Run on an example problem
python -m orchestrator --problem "Monitor soil moisture across 500 hectares of farmland and trigger irrigation automatically"

# Run tests
pytest tests/ -v

# Lint and format
ruff check . && ruff format .
```
