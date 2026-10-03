"""Read-only tools. None of these write device commands."""

from __future__ import annotations

import json
from typing import Any

from solarsponge.config import Settings
from solarsponge.forecasting.service import ForecastService
from solarsponge.loop import run_closed_loop_day
from solarsponge.optimizer.service import plan_day, risk_surplus
from solarsponge.store import Store
from solarsponge.twin.simulator import simulate_day


TOOL_SCHEMAS = [
    {
        "name": "get_plan",
        "description": "Return the latest optimizer plan for a zone, including schedules and solver status.",
        "input_schema": {
            "type": "object",
            "properties": {"zone_id": {"type": "string"}},
            "required": ["zone_id"],
        },
    },
    {
        "name": "get_forecast",
        "description": "Return the latest quantile forecast (p10/p50/p90) for pv, load, or surplus.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zone_id": {"type": "string"},
                "target": {"type": "string", "enum": ["pv", "load", "surplus"]},
            },
            "required": ["zone_id"],
        },
    },
    {
        "name": "get_kpis",
        "description": "Return KPI snapshot for the latest simulated day.",
        "input_schema": {
            "type": "object",
            "properties": {"zone_id": {"type": "string"}},
            "required": ["zone_id"],
        },
    },
    {
        "name": "diff_plans",
        "description": "Compare the two most recent plans: which loads changed slot.",
        "input_schema": {
            "type": "object",
            "properties": {"zone_id": {"type": "string"}},
            "required": ["zone_id"],
        },
    },
    {
        "name": "get_load_info",
        "description": "Return load config, window, and latest state.",
        "input_schema": {
            "type": "object",
            "properties": {"load_id": {"type": "string"}},
            "required": ["load_id"],
        },
    },
    {
        "name": "run_scenario",
        "description": "Run a sandboxed what-if. Does not dispatch. Returns KPIs and a new plan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zone_id": {"type": "string"},
                "horizon_hours": {"type": "integer", "minimum": 1, "maximum": 48},
                "overrides": {
                    "type": "object",
                    "properties": {
                        "cloud_delta_pct": {"type": "number", "minimum": -50, "maximum": 50},
                        "disabled_load_ids": {"type": "array", "items": {"type": "string"}},
                        "risk_quantile": {"type": "number", "minimum": 0.1, "maximum": 0.9},
                    },
                },
            },
            "required": ["zone_id"],
        },
    },
]


class ToolLayer:
    def __init__(self, settings: Settings, store: Store, fc_svc: ForecastService | None = None):
        self.settings = settings
        self.store = store
        self.fc_svc = fc_svc

    def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        fn = getattr(self, name, None)
        if fn is None:
            return {"error": f"unknown tool {name}"}
        return fn(**args)

    def get_plan(self, zone_id: str) -> dict:
        p = self.store.latest_plan(zone_id)
        if not p:
            return {"error": "no plan"}
        return {k: v for k, v in p.items() if k != "on"}

    def get_forecast(self, zone_id: str, target: str = "surplus") -> dict:
        f = self.store.latest_forecast(zone_id, target)
        return f or {"error": "no forecast"}

    def get_kpis(self, zone_id: str) -> dict:
        return dict(self.store.kpis) if self.store.kpis else {"error": "no kpis"}

    def diff_plans(self, zone_id: str) -> dict:
        plans = [p for p in self.store.plans if p.get("zone_id") == zone_id]
        if len(plans) < 2:
            return {"changed_slots": 0, "note": "fewer than two plans"}
        a, b = plans[-2], plans[-1]
        changed = 0
        details = []
        for sa, sb in zip(a.get("schedules", []), b.get("schedules", [])):
            on_a, on_b = sa.get("on", []), sb.get("on", [])
            n = sum(1 for x, y in zip(on_a, on_b) if x != y)
            changed += n
            if n:
                details.append({"load_id": sa.get("load_id"), "changed_slots": n})
        return {"changed_slots": changed, "details": details, "from_plan": a.get("plan_id"), "to_plan": b.get("plan_id")}

    def get_load_info(self, load_id: str) -> dict:
        replay = self.store.replay or {}
        for s in replay.get("schedules", []):
            if s["load_id"] == load_id:
                return {
                    "load_id": load_id,
                    "name": s.get("name"),
                    "kind": s.get("kind"),
                    "power_kw": s.get("power_kw"),
                    "window": s.get("window"),
                    "energy_kwh": s.get("energy_kwh"),
                    "unmet_kwh": s.get("unmet_kwh"),
                    "state": (replay.get("states") or {}).get(load_id, {}),
                }
        return {"error": f"unknown load {load_id}"}

    def run_scenario(
        self,
        zone_id: str,
        horizon_hours: int = 24,
        overrides: dict | None = None,
    ) -> dict:
        overrides = overrides or {}
        from datetime import timedelta

        cloud = float(overrides.get("cloud_delta_pct") or 0)
        disabled = list(overrides.get("disabled_load_ids") or [])
        rq = overrides.get("risk_quantile")
        day_start = datetime.fromisoformat(self.store.replay["day_start"]) if self.store.replay else None
        if day_start is None:
            from datetime import timezone as tz

            day_start = datetime(2026, 4, 15, tzinfo=tz.utc)
        twin = simulate_day(self.settings, day_start, day_index=14, cloud_delta_pct=cloud)
        fc_svc = self.fc_svc or ForecastService(self.settings)
        # sandbox store so we never dispatch
        sandbox = Store(self.settings)
        replay = run_closed_loop_day(
            self.settings,
            twin,
            fc_svc,
            sandbox,
            risk_quantile=rq,
            disabled_load_ids=disabled,
            cloud_delta_pct=cloud,
        )
        return {
            "dispatched": False,
            "kpis": replay["kpis"],
            "plan_id": replay["plan"]["plan_id"],
            "solver_status": replay["plan"]["solver_status"],
            "absorbed_kwh_expected": replay["plan"]["absorbed_kwh_expected"],
            "cloud_delta_pct": cloud,
            "disabled_load_ids": disabled,
            "risk_quantile": rq or self.settings.optimizer.risk_quantile,
        }
