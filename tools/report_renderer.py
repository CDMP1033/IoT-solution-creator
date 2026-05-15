from __future__ import annotations

"""Static Markdown renderer for PM/PO-friendly IoT Solution reports.

Each render_* function accepts the raw dict output of its corresponding agent
and returns a human-readable Markdown string — no LLM call required.
"""

_TRUNC = 400  # max chars for long prose before truncation


def _trunc(text: str, limit: int = _TRUNC) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _fmt(value: object, fmt: str = ",") -> str:
    """Format a numeric value; return '—' gracefully if value is missing or non-numeric."""
    if value is None or value == "—":
        return "—"
    try:
        return format(float(value), fmt)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(value)


def _table(headers: list[str], rows: list[list[str]]) -> str:
    sep = " | ".join("---" for _ in headers)
    head = " | ".join(headers)
    body = "\n".join(" | ".join(str(c) for c in row) for row in rows)
    return f"| {head} |\n| {sep} |\n" + "\n".join(f"| {' | '.join(str(c) for c in r)} |" for r in rows)


def _bullets(items: list, prefix: str = "-") -> str:
    return "\n".join(f"{prefix} {item}" for item in items)


# ---------------------------------------------------------------------------
# 1. Requirements
# ---------------------------------------------------------------------------

def render_requirements(data: dict) -> str:
    lines: list[str] = []

    goal = data.get("business_goal", "")
    if goal:
        lines.append(f"> **Business Goal:** {goal}\n")

    frs = data.get("functional_requirements", [])
    if frs:
        lines.append("### Functional Requirements\n")
        for i, fr in enumerate(frs, 1):
            lines.append(f"{i}. {fr}")
        lines.append("")

    nfr = data.get("non_functional_requirements", {})
    if nfr:
        lines.append("### Non-Functional Requirements\n")
        nfr_rows = []
        if nfr.get("latency_ms") is not None:
            nfr_rows.append(["End-to-end latency", f"{nfr['latency_ms']} ms"])
        if nfr.get("availability_percent") is not None:
            nfr_rows.append(["Availability", f"{nfr['availability_percent']}%"])
        if nfr.get("data_retention_days") is not None:
            nfr_rows.append(["Data retention", f"{nfr['data_retention_days']} days"])
        if nfr.get("max_cost_usd_per_device_month") is not None:
            nfr_rows.append(["Max cost", f"USD {_fmt(nfr['max_cost_usd_per_device_month'], '.2f')}/device/month"])
        if nfr_rows:
            lines.append(_table(["Attribute", "Target"], nfr_rows))
            lines.append("")
        regs = nfr.get("regulatory", [])
        if regs:
            lines.append("**Regulatory requirements:**\n")
            lines.append(_bullets(regs))
            lines.append("")

    scale = data.get("scale", {})
    if scale:
        lines.append("### Scale\n")
        scale_rows = [
            ["Devices", str(scale.get("num_devices", "—"))],
            ["Reporting interval", f"{scale.get('data_frequency_seconds', '—')} s"],
            ["Geographic spread", f"{scale.get('geographic_spread_km2', '—')} km²"],
        ]
        lines.append(_table(["Parameter", "Value"], scale_rows))
        lines.append("")

    constraints = data.get("region_constraints", [])
    if constraints:
        lines.append("### Regional Constraints\n")
        lines.append(_bullets(constraints))
        lines.append("")

    ambiguities = data.get("ambiguities", [])
    if ambiguities:
        lines.append("### Open Questions / Ambiguities\n")
        lines.append(_bullets(ambiguities, prefix="⚠"))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. Hardware
# ---------------------------------------------------------------------------

def render_hardware(data: dict) -> str:
    lines: list[str] = []

    sensors = data.get("sensors", [])
    if sensors:
        lines.append("### Sensors\n")
        rows = [
            [s.get("name", ""), s.get("measurement", ""), f"USD {s.get('unit_cost_usd', '—')}"]
            for s in sensors
        ]
        lines.append(_table(["Sensor", "Measures", "Unit Cost"], rows))
        lines.append("")

    actuators = data.get("actuators", [])
    if actuators:
        lines.append("### Actuators\n")
        rows = [
            [a.get("name", ""), a.get("function", ""), f"USD {a.get('unit_cost_usd', '—')}"]
            for a in actuators
        ]
        lines.append(_table(["Actuator", "Function", "Unit Cost"], rows))
        lines.append("")

    mcu = data.get("microcontroller", {})
    if mcu:
        lines.append("### Microcontroller / Node SoC\n")
        lines.append(f"**Model:** {mcu.get('model', '—')}  \n")
        lines.append(f"**CPU:** {mcu.get('cpu', '—')} | **RAM:** {mcu.get('ram_kb', '—')} KB | "
                     f"**Flash:** {mcu.get('flash_kb', '—')} KB | **Unit cost:** USD {mcu.get('unit_cost_usd', '—')}\n")
        conn = mcu.get("built_in_connectivity", [])
        if conn:
            lines.append(f"**Connectivity:** {', '.join(conn)}\n")

    gw = data.get("edge_gateway", {})
    if gw:
        lines.append("### Edge Gateway\n")
        lines.append(f"**Model:** {gw.get('model', '—')} — Unit cost: USD {gw.get('unit_cost_usd', '—')}\n")
        lines.append(f"{_trunc(gw.get('role', ''))}\n")

    power = data.get("power", {})
    if power:
        lines.append("### Power Strategy\n")
        power_rows = [
            ["Strategy", power.get("strategy", "—")],
            ["Battery type", power.get("battery_type", "—")],
            ["Autonomy (no solar)", f"{power.get('estimated_battery_life_days', '—')} days"],
            ["Solar panel", f"{power.get('solar_panel_w', '—')} W"],
        ]
        lines.append(_table(["Parameter", "Value"], power_rows))
        lines.append("")

    bom = data.get("bom_summary", {})
    if bom:
        lines.append("### Bill of Materials — Cost Summary\n")
        bd = bom.get("breakdown_notes", {})
        n = bom.get("num_devices", 0) or 0
        cpp = bom.get("cost_per_device_usd", 0) or 0
        bom_rows = [
            ["Sensor nodes", f"{bom.get('num_devices', '—')} × USD {bom.get('cost_per_device_usd', '—')}",
             f"USD {_fmt(n * cpp, ',.0f')}"],
            ["Edge gateways", f"{bd.get('gateways_qty', '—')} × USD {bd.get('gateway_unit_cost', '—')}",
             f"USD {_fmt(bd.get('gateway_subtotal_usd'), ',.0f')}"],
            ["Solenoid valves", f"{bd.get('valves_qty', '—')} × USD {bd.get('valve_unit_cost', '—')}",
             f"USD {_fmt(bd.get('solenoid_valves_subtotal_usd'), ',.0f')}"],
        ]
        bom_rows.append(["**TOTAL HARDWARE**", "", f"**USD {_fmt(bom.get('total_deployment_cost_usd'), ',.0f')}**"])
        lines.append(_table(["Item", "Qty × Unit cost", "Subtotal"], bom_rows))
        lines.append("")

    alts = data.get("alternatives", [])
    if alts:
        lines.append("### Alternative Options Considered\n")
        for alt in alts:
            lines.append(f"- {_trunc(alt, 200)}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. Connectivity
# ---------------------------------------------------------------------------

def render_connectivity(data: dict) -> str:
    lines: list[str] = []

    proto = data.get("device_protocol", {})
    if proto:
        lines.append("### Device Protocol\n")
        rows = [
            ["Protocol", proto.get("name", "—")],
            ["Frequency band", proto.get("frequency_band", "—")],
            ["Max range", f"{proto.get('max_range_m', '—')} m"],
            ["Data rate", f"{proto.get('data_rate_bps', '—')} bps"],
            ["Power consumption", proto.get("power_consumption", "—")],
        ]
        lines.append(_table(["Parameter", "Value"], rows))
        lines.append(f"\n_{_trunc(proto.get('justification', ''))}_\n")

    topo = data.get("topology", {})
    if topo:
        lines.append("### Network Topology\n")
        topo_rows = [
            ["Type", topo.get("type", "—")],
            ["Gateways", str(topo.get("num_gateways", "—"))],
        ]
        lines.append(_table(["Parameter", "Value"], topo_rows))
        lines.append(f"\n{_trunc(topo.get('description', ''))}\n")

    backhaul = data.get("backhaul", {})
    msg = data.get("messaging_protocol", {})
    if backhaul or msg:
        lines.append("### Backhaul & Messaging\n")
        rows = []
        if backhaul:
            rows.append(["Backhaul", backhaul.get("name", "—"),
                         f"~USD {backhaul.get('estimated_monthly_cost_usd', '—')}/month"])
        if msg:
            rows.append(["Messaging", msg.get("name", "—"),
                         f"Broker: {_trunc(msg.get('broker_or_endpoint', ''), 60)}"])
        lines.append(_table(["Layer", "Technology", "Notes"], rows))
        lines.append("")

    bw = data.get("bandwidth_per_device", {})
    if bw:
        lines.append("### Bandwidth per Device\n")
        bw_rows = [
            ["Uplink payload", f"{bw.get('uplink_bytes_per_message', '—')} bytes/msg"],
            ["Messages/day", str(bw.get("messages_per_day", "—"))],
            ["Total fleet daily data", f"{bw.get('total_daily_mb_all_devices', '—')} MB"],
        ]
        lines.append(_table(["Metric", "Value"], bw_rows))
        lines.append("")

    alts = data.get("alternatives", [])
    if alts:
        lines.append("### Alternatives Considered\n")
        for alt in alts:
            lines.append(f"- {_trunc(alt, 200)}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. Data Pipeline
# ---------------------------------------------------------------------------

def render_data(data: dict) -> str:
    lines: list[str] = []

    ingestion = data.get("ingestion", {})
    if ingestion:
        lines.append("### Ingestion\n")
        ing_rows = [
            ["Service", ingestion.get("service", "—")[:80]],
            ["Protocol", ingestion.get("protocol", "—")],
            ["Throughput", f"{ingestion.get('throughput_msgs_per_second', '—')} msg/s"],
        ]
        lines.append(_table(["Parameter", "Value"], ing_rows))
        lines.append("")

    stream = data.get("stream_processing", {})
    if stream:
        lines.append("### Stream Processing Rules\n")
        lines.append(f"**Engine:** {stream.get('engine', '—')} | "
                     f"**Latency target:** {stream.get('latency_target_ms', '—')} ms\n")
        rules = stream.get("rules", [])
        for i, rule in enumerate(rules, 1):
            lines.append(f"{i}. {_trunc(rule, 180)}")
        lines.append("")

    storage = data.get("storage", {})
    if storage:
        lines.append("### Storage Tiers\n")
        stor_rows = []
        for tier_key, label in [("hot", "Hot"), ("warm", "Warm"), ("cold", "Cold")]:
            tier = storage.get(tier_key, {})
            if tier:
                stor_rows.append([
                    label,
                    tier.get("service", "—")[:60],
                    f"{tier.get('retention_days', '—')} days",
                    f"{tier.get('estimated_gb', '—')} GB",
                    tier.get("format", "native") if "format" in tier else "native",
                ])
        lines.append(_table(["Tier", "Service", "Retention", "Est. Size", "Format"], stor_rows))
        lines.append("")

    serving = data.get("serving", {})
    if serving:
        lines.append("### Serving Layer\n")
        serving_rows = [
            ["Dashboard", _trunc(str(serving.get("dashboard", "—")), 120)],
            ["API style", serving.get("api", "—")],
            ["Alerting", serving.get("alerting", "—")],
        ]
        lines.append(_table(["Component", "Details"], serving_rows))
        lines.append("")

    cost = data.get("cost_estimate_usd_per_month")
    if cost is not None:
        lines.append(f"> 💰 **Estimated data pipeline cost: USD {_fmt(cost, ',.0f')}/month**\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5. Cloud Infrastructure
# ---------------------------------------------------------------------------

def render_cloud(data: dict) -> str:
    lines: list[str] = []

    provider = data.get("provider", "")
    region = data.get("primary_region", "")
    if provider or region:
        lines.append(f"**Provider:** {provider} | **Primary Region:** {region}\n")

    iot = data.get("iot_platform", {})
    if iot:
        lines.append(f"**IoT Platform:** {iot.get('name', '—')}\n")
        lines.append(f"_{_trunc(iot.get('justification', ''))}_\n")

    services = data.get("services", [])
    if services:
        lines.append("### AWS Services\n")
        rows = [
            [
                s.get("name", "—"),
                _trunc(s.get("role", "—"), 120),
                f"USD {_fmt(s.get('estimated_cost_usd_per_month'), '.1f')}",
            ]
            for s in services
        ]
        lines.append(_table(["Service", "Role", "Est. $/month"], rows))
        lines.append("")

    total = data.get("total_cost_usd_per_month")
    if total is not None:
        try:
            per_device = f"{float(total)/200:.2f}"
        except (TypeError, ValueError, ZeroDivisionError):
            per_device = "—"
        lines.append(f"> 💰 **Total cloud cost: USD {_fmt(total, ',.1f')}/month "
                     f"(≈ USD {per_device}/device/month)**\n")

    ha = data.get("high_availability", {})
    if ha:
        lines.append("### High Availability\n")
        ha_rows = [
            ["Multi-AZ", "Yes" if ha.get("multi_az") else "No"],
            ["RPO", f"{ha.get('rpo_minutes', '—')} min"],
            ["RTO", f"{ha.get('rto_minutes', '—')} min"],
        ]
        lines.append(_table(["Attribute", "Value"], ha_rows))
        lines.append("")

    iac = data.get("iac", {})
    if iac:
        lines.append(f"**IaC:** {iac.get('tool', '—')} ({iac.get('language', '—')})\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6. Security Model
# ---------------------------------------------------------------------------

def render_security(data: dict) -> str:
    lines: list[str] = []

    identity = data.get("device_identity", {})
    enc = data.get("encryption", {})
    ota = data.get("ota_updates", {})

    if identity or enc or ota:
        lines.append("### Security Controls\n")
        rows = []
        if identity:
            rows.append(["Device identity", identity.get("mechanism", "—"),
                         identity.get("provisioning", "—")])
        if enc:
            rows.append(["Encryption in-transit", enc.get("in_transit", "—"), ""])
            rows.append(["Encryption at-rest", enc.get("at_rest", "—"),
                         f"Key mgmt: {enc.get('key_management', '—')}"])
        if ota:
            rows.append(["OTA signing", ota.get("signing", "—"),
                         f"Rollback: {ota.get('rollback', '—')}"])
        lines.append(_table(["Control", "Mechanism", "Notes"], rows))
        lines.append("")

    threats = data.get("threat_model", [])
    if threats:
        lines.append("### Threat Model\n")
        threat_rows = [
            [
                t.get("threat", "—"),
                t.get("attack_vector", "—"),
                t.get("likelihood", "—"),
                t.get("impact", "—"),
                _trunc(t.get("mitigation", ""), 120),
            ]
            for t in threats
        ]
        lines.append(_table(
            ["Threat", "Vector", "Likelihood", "Impact", "Mitigation (summary)"],
            threat_rows,
        ))
        lines.append("")

    checklist = data.get("hardening_checklist", [])
    if checklist:
        lines.append("### Hardening Checklist\n")
        for item in checklist:
            lines.append(f"- [ ] {_trunc(item, 160)}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7. Deployment Plan
# ---------------------------------------------------------------------------

def render_deployment(data: dict) -> str:
    lines: list[str] = []

    phases = data.get("rollout_phases", [])
    if phases:
        lines.append("### Rollout Phases\n")
        phase_rows = [
            [
                p.get("phase", "—"),
                str(p.get("num_devices", "—")),
                f"{p.get('duration_weeks', '—')} weeks",
                _trunc(p.get("success_criteria", ""), 160),
            ]
            for p in phases
        ]
        lines.append(_table(["Phase", "Devices", "Duration", "Success Criteria (summary)"], phase_rows))
        lines.append("")

    fw_cicd = data.get("firmware_cicd", {})
    cloud_cicd = data.get("cloud_cicd", {})
    if fw_cicd or cloud_cicd:
        lines.append("### CI/CD Pipelines\n")
        cicd_rows = []
        if fw_cicd:
            stages = fw_cicd.get("stages", [])
            cicd_rows.append(["Firmware", fw_cicd.get("tool", "—"),
                               f"{len(stages)} stages"])
        if cloud_cicd:
            stages = cloud_cicd.get("stages", [])
            cicd_rows.append(["Cloud infra", cloud_cicd.get("tool", "—"),
                               f"{len(stages)} stages"])
        lines.append(_table(["Pipeline", "Tool", "Stages"], cicd_rows))
        lines.append("")

    monitoring = data.get("monitoring_setup", data.get("monitoring", {}))
    if monitoring and isinstance(monitoring, dict):
        lines.append("### Monitoring\n")
        for key, value in monitoring.items():
            if isinstance(value, str):
                lines.append(f"- **{key.replace('_', ' ').title()}:** {_trunc(value, 120)}")
            elif isinstance(value, list):
                lines.append(f"- **{key.replace('_', ' ').title()}:** {', '.join(str(v) for v in value[:5])}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 8. Methodology & Project Plan
# ---------------------------------------------------------------------------

def render_methodology(data: dict) -> str:
    lines: list[str] = []

    methodology = data.get("methodology", "")
    if methodology:
        lines.append(f"**Approach:** {_trunc(str(methodology), 300)}\n")

    ceremonies = data.get("ceremonies", [])
    if ceremonies:
        lines.append("### Key Ceremonies / Meetings\n")
        for ceremony in ceremonies:
            lines.append(f"- {_trunc(str(ceremony), 160)}")
        lines.append("")

    plan = data.get("project_plan", [])
    if plan:
        lines.append("### Project Plan\n")
        plan_rows = [
            [
                p.get("phase", "—"),
                f"{p.get('duration_weeks', '—')} weeks",
                str(len(p.get("deliverables", []))),
            ]
            for p in plan
        ]
        lines.append(_table(["Phase", "Duration", "# Deliverables"], plan_rows))
        total_weeks = sum(p.get("duration_weeks", 0) for p in plan)
        lines.append(f"\n**Total estimated project duration: {total_weeks} weeks "
                     f"(~{total_weeks // 4} months)**\n")

    risks = data.get("risks", [])
    if risks:
        lines.append("### Risk Register\n")
        risk_rows = [
            [
                r.get("risk", r.get("description", "—")),
                r.get("likelihood", r.get("probability", "—")),
                r.get("impact", "—"),
                _trunc(r.get("mitigation", r.get("response", "")), 120),
            ]
            for r in risks
        ]
        lines.append(_table(["Risk", "Likelihood", "Impact", "Mitigation"], risk_rows))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

RENDERERS: dict[str, object] = {
    "requirements_agent": render_requirements,
    "hardware_agent": render_hardware,
    "connectivity_agent": render_connectivity,
    "data_agent": render_data,
    "cloud_agent": render_cloud,
    "security_agent": render_security,
    "deployment_agent": render_deployment,
    "methodology_agent": render_methodology,
}
