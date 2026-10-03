"""Operator copilot. Explains plans; never controls a load."""

from __future__ import annotations

import json
import os
from typing import Any

from solarsponge.config import Settings
from solarsponge.copilot.guardrails import faithfulness, is_actuation_request, sanitize_tool_text
from solarsponge.copilot.tools import TOOL_SCHEMAS, ToolLayer
from solarsponge.timeutil import slot_to_hhmm


SYSTEM = """You are SolarSponge's operator copilot.
You explain schedules, forecasts, and what-if results.
You NEVER control loads. You have no write tools.
Every numeric claim must come from a tool result. If a tool is missing, say you do not know.
If the user asks you to turn equipment on or off, refuse and explain that only the optimizer may dispatch.
Cite plan_id and config_hash when you quote a plan.
"""


def _slot_on(schedule: dict, settings: Settings) -> str:
    on = schedule.get("on") or []
    runs = []
    start = None
    for i, v in enumerate(list(on) + [0]):
        if v and start is None:
            start = i
        if not v and start is not None:
            runs.append(f"{slot_to_hhmm(start, settings.time)}–{slot_to_hhmm(i, settings.time)}")
            start = None
    return ", ".join(runs) or "off all day"


class Copilot:
    def __init__(self, settings: Settings, tools: ToolLayer):
        self.settings = settings
        self.tools = tools
        self.cache: dict[str, str] = {}

    def chat(self, message: str, zone_id: str | None = None) -> dict[str, Any]:
        zone_id = zone_id or self.settings.zone.id
        if is_actuation_request(message):
            return {
                "role": "coordinator",
                "refusal": True,
                "answer": (
                    "I cannot turn loads on or off. Dispatch only goes Optimizer → Dispatch gateway. "
                    "I can explain the current plan or run a sandboxed what-if that does not dispatch."
                ),
                "tool_calls": [],
            }

        route = self._route(message)
        calls = self._tool_plan(route, message, zone_id)
        blobs = []
        results = []
        for name, args in calls:
            raw = self.tools.call(name, args)
            text = sanitize_tool_text(json.dumps(raw, default=str))
            blobs.append(text)
            results.append({"name": name, "args": args, "result": raw})

        answer = self._llm_or_template(route, message, results, zone_id)
        ok, missing = faithfulness(answer, blobs + [json.dumps(results, default=str)])
        if not ok and missing:
            # strip ungrounded numbers by falling back to the template
            answer = self._template(route, results, zone_id)
        return {
            "role": route,
            "refusal": False,
            "answer": answer,
            "tool_calls": [{"name": c["name"], "args": c["args"]} for c in results],
            "faithful": ok,
        }

    def _route(self, message: str) -> str:
        m = message.lower()
        if any(w in m for w in ("what if", "what-if", "cloud", "unavailable", "disable", "risk quantile")):
            return "whatif"
        if any(w in m for w in ("message", "whatsapp", "farmer", "hindi", "tamil", "notify")):
            return "messenger"
        return "explainer"

    def _tool_plan(self, route: str, message: str, zone_id: str) -> list[tuple[str, dict]]:
        calls: list[tuple[str, dict]] = [("get_plan", {"zone_id": zone_id}), ("get_kpis", {"zone_id": zone_id})]
        if route == "explainer":
            calls.append(("get_forecast", {"zone_id": zone_id, "target": "surplus"}))
            lid = _extract_load_id(message)
            if lid:
                calls.append(("get_load_info", {"load_id": lid}))
        if route == "whatif":
            overrides: dict[str, Any] = {}
            if "cloud" in message.lower():
                overrides["cloud_delta_pct"] = _extract_delta(message)
            lid = _extract_load_id(message)
            if lid and any(w in message.lower() for w in ("unavailable", "disable", "offline")):
                overrides["disabled_load_ids"] = [lid]
            if "risk" in message.lower():
                overrides["risk_quantile"] = 0.3
            calls.append(("run_scenario", {"zone_id": zone_id, "overrides": overrides}))
        if route == "messenger":
            lid = _extract_load_id(message) or "pump_cluster_A"
            calls.append(("get_load_info", {"load_id": lid}))
        return calls[: self.settings.copilot.max_tool_calls]

    def _llm_or_template(self, route, message, results, zone_id) -> str:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if key and self.settings.copilot.enabled:
            try:
                return self._anthropic(route, message, results)
            except Exception:
                pass
        return self._template(route, results, zone_id)

    def _anthropic(self, route, message, results) -> str:
        import anthropic

        model = (
            self.settings.copilot.model_whatif if route == "whatif" else self.settings.copilot.model_explainer
        )
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        content = json.dumps(results, default=str)[:12000]
        msg = client.messages.create(
            model=model,
            max_tokens=self.settings.copilot.max_output_tokens,
            system=SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"User question: {message}\n\nTool results (JSON):\n{content}\n\nAnswer using only these numbers.",
                }
            ],
        )
        return msg.content[0].text

    def _template(self, route: str, results: list[dict], zone_id: str) -> str:
        by = {r["name"]: r["result"] for r in results}
        plan = by.get("get_plan") or {}
        kpis = by.get("get_kpis") or {}
        if plan.get("error"):
            return "No plan is stored yet. Run a simulated day first."
        pid = plan.get("plan_id")
        status = plan.get("solver_status")
        absorbed = kpis.get("absorbed_kwh") or plan.get("absorbed_kwh_expected")
        avoided = kpis.get("curtailment_avoided_kwh")
        co2 = kpis.get("co2_avoided_t")
        viol = kpis.get("constraint_violations")
        if route == "whatif":
            sc = by.get("run_scenario") or {}
            sk = sc.get("kpis") or {}
            return (
                f"Sandboxed what-if (not dispatched). Solver {sc.get('solver_status')} on plan_id {sc.get('plan_id')}. "
                f"Absorbed {sk.get('absorbed_kwh')} kWh, curtailment avoided {sk.get('curtailment_avoided_kwh')} kWh, "
                f"CO2 avoided {sk.get('co2_avoided_t')} t. Constraint violations {sk.get('constraint_violations')}. "
                f"cloud_delta_pct={sc.get('cloud_delta_pct')}, disabled={sc.get('disabled_load_ids')}."
            )
        if route == "messenger":
            info = by.get("get_load_info") or {}
            sch = next((s for s in plan.get("schedules", []) if s.get("load_id") == info.get("load_id")), None)
            when = _slot_on(sch or {}, self.settings) if sch else "see dashboard"
            return (
                f"Farmer notice (draft, not sent). {info.get('name') or info.get('load_id')}: run {when}. "
                f"This window is inside today's surplus forecast. Crop energy need is a hard constraint "
                f"(unmet {info.get('unmet_kwh')} kWh). Plan {pid}."
            )
        lines = [
            f"Plan {pid} for {zone_id} solved as {status} in {plan.get('solve_ms')} ms "
            f"(config_hash {plan.get('config_hash')}, risk_quantile {plan.get('risk_quantile')})."
        ]
        if absorbed is not None:
            lines.append(f"Expected absorbed surplus {absorbed} kWh.")
        if avoided is not None:
            lines.append(f"Curtailment avoided {avoided} kWh; CO2 avoided {co2} t using the CEA factor in config.")
        if viol is not None:
            lines.append(f"Hard constraint violations: {viol}.")
        for s in plan.get("schedules", []):
            lines.append(
                f"{s.get('name') or s.get('load_id')} ON { _slot_on(s, self.settings) } "
                f"(delivered {s.get('energy_kwh')} kWh, unmet {s.get('unmet_kwh')} kWh)."
            )
        if plan.get("fallback_reason"):
            lines.append(f"Fallback reason: {plan.get('fallback_reason')}.")
        return " ".join(lines)


def _extract_load_id(message: str) -> str | None:
    m = message.lower()
    mapping = {
        "pump cluster a": "pump_cluster_A",
        "pump a": "pump_cluster_A",
        "cluster a": "pump_cluster_A",
        "pump cluster b": "pump_cluster_B",
        "pump b": "pump_cluster_B",
        "cluster b": "pump_cluster_B",
        "cold": "cold_store_1",
        "ev": "ev_depot",
        "hvac": "hvac_precool",
    }
    for k, v in mapping.items():
        if k in m:
            return v
    return None


def _extract_delta(message: str) -> float:
    import re

    m = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", message)
    if m:
        return float(m.group(1))
    if "+" in message or "increase" in message.lower():
        return 20.0
    return 20.0
