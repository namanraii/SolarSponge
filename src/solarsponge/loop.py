"""15-minute control cycle and demo-day replay builder."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np

from solarsponge.config import Settings
from solarsponge.dispatch.gateway import DispatchGateway
from solarsponge.forecasting.service import ForecastService
from solarsponge.kpi.metrics import compute_day_kpis
from solarsponge.optimizer.heuristic import default_schedule
from solarsponge.optimizer.service import plan_day, risk_surplus
from solarsponge.optimizer.validate import validate_plan
from solarsponge.store import Store
from solarsponge.twin.loads import power_from_on, simulate_soc, simulate_soil, simulate_thermal
from solarsponge.twin.simulator import DayTwin, apply_schedule, simulate_day



def run_closed_loop_day(
    settings: Settings,
    twin: DayTwin,
    fc_svc: ForecastService,
    store: Store,
    oracle: bool = False,
    risk_quantile: float | None = None,
    disabled_load_ids: list[str] | None = None,
    cloud_delta_pct: float = 0.0,
) -> dict[str, Any]:
    q = risk_quantile if risk_quantile is not None else settings.optimizer.risk_quantile
    loads = [L for L in twin.loads if L.load_id not in set(disabled_load_ids or [])]
    fc = fc_svc.predict_day(twin, oracle=oracle)
    surplus = twin.surplus_kw if oracle else risk_surplus(fc.surplus, q)
    surplus = surplus.copy()
    surplus[surplus < settings.optimizer.surplus_floor_kw] = 0.0

    result = plan_day(surplus, loads, settings)
    on = result["on"]
    T = settings.time.slots_per_day
    gateway = DispatchGateway(settings, loads)
    actual_on = np.zeros_like(on)
    for t in range(T):
        slot_cmds = gateway.dispatch_slot(result["schedules"], t)
        for i, L in enumerate(loads):
            actual_on[i, t] = int(slot_cmds[L.load_id]["actual_on"])

    applied = apply_schedule(twin, actual_on, settings)
    s0 = apply_schedule(twin, default_schedule(twin.loads, T), settings)
    dt = settings.time.dt_h
    val = validate_plan(twin.surplus_kw, loads, on, result["absorbed_kwh"], dt)
    shiftable = sum(L.energy_kwh for L in loads)
    kpis = compute_day_kpis(
        settings,
        twin.surplus_kw,
        s0["curtailed_kw"],
        applied["curtailed_kw"],
        applied["flex_load_kw"],
        applied["absorbed_kw"],
        shiftable,
        0 if val.window_ok and val.min_run_ok and val.max_starts_ok else 1,
        result["solve_ms"],
        result["status"] == "Fallback",
        twin.weather_class,
    )

    states = {}
    for i, L in enumerate(loads):
        st: dict[str, list] = {}
        if L.kind in {"cold_store", "hvac"}:
            st["temp_c"] = simulate_thermal(L, actual_on[i], dt).tolist()
        if L.kind == "pump":
            st["deficit_mm"] = simulate_soil(L, actual_on[i]).tolist()
        if L.kind == "ev_depot":
            st["soc"] = simulate_soc(L, actual_on[i], dt).tolist()
        states[L.load_id] = st

    plan = store.add_plan(
        {
            "plan_id": len(store.plans) + 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "zone_id": settings.zone.id,
            "solver_status": result["status"],
            "risk_quantile": q,
            "objective": result.get("objective"),
            "solve_ms": result["solve_ms"],
            "config_hash": settings.config_hash(),
            "schedules": result["schedules"],
            "unmet_kwh": result["unmet_kwh"],
            "absorbed_kwh_expected": result["absorbed_kwh"],
            "fallback_reason": result.get("fallback_reason"),
            "slot_start": twin.day_start.isoformat(),
            "validation_notes": val.notes,
        }
    )
    store.add_forecast(
        {
            "zone_id": settings.zone.id,
            "target": "surplus",
            "issued_at": fc.issued_at.isoformat() if hasattr(fc.issued_at, "isoformat") else str(fc.issued_at),
            "p10": fc.surplus["p10"].tolist(),
            "p50": fc.surplus["p50"].tolist(),
            "p90": fc.surplus["p90"].tolist(),
            "model_version": fc.model_version,
            "times": [t.isoformat() for t in fc.times],
        }
    )
    store.add_forecast(
        {
            "zone_id": settings.zone.id,
            "target": "pv",
            "issued_at": str(fc.issued_at),
            "p10": np.asarray(fc.pv["p10"]).tolist(),
            "p50": np.asarray(fc.pv["p50"]).tolist(),
            "p90": np.asarray(fc.pv["p90"]).tolist(),
            "model_version": fc.model_version,
            "times": [t.isoformat() for t in fc.times],
        }
    )

    replay = {
        "zone": {
            "id": settings.zone.id,
            "name": settings.zone.name,
            "lat": settings.zone.lat,
            "lon": settings.zone.lon,
            "pv_nameplate_kw": settings.zone.pv_nameplate_kw,
            "evac_limit_kw": settings.zone.evac_limit_kw,
        },
        "day_start": twin.day_start.isoformat(),
        "weather_class": twin.weather_class,
        "slot_minutes": settings.time.slot_minutes,
        "pv_kw": twin.pv_kw.tolist(),
        "baseline_load_kw": twin.baseline_load_kw.tolist(),
        "surplus_kw": twin.surplus_kw.tolist(),
        "evac_limit_kw": [settings.zone.evac_limit_kw] * T,
        "flex_s0_kw": s0["flex_load_kw"].tolist(),
        "flex_sx_kw": applied["flex_load_kw"].tolist(),
        "curtailed_s0_kw": s0["curtailed_kw"].tolist(),
        "curtailed_sx_kw": applied["curtailed_kw"].tolist(),
        "absorbed_kw": applied["absorbed_kw"].tolist(),
        "forecast_surplus": {
            "p10": fc.surplus["p10"].tolist(),
            "p50": fc.surplus["p50"].tolist(),
            "p90": fc.surplus["p90"].tolist(),
        },
        "forecast_pv": {
            "p10": np.asarray(fc.pv["p10"]).tolist(),
            "p50": np.asarray(fc.pv["p50"]).tolist(),
            "p90": np.asarray(fc.pv["p90"]).tolist(),
        },
        "schedules": result["schedules"],
        "default_schedules": [
            {"load_id": L.load_id, "on": (L.default_on if L.default_on is not None else np.zeros(T)).astype(int).tolist()}
            for L in loads
        ],
        "states": states,
        "kpis": kpis.__dict__,
        "plan": {k: v for k, v in plan.items() if k != "on"},
        "emission_factor_t_per_mwh": settings.economics.grid_emission_factor_t_per_mwh,
        "emission_factor_source": settings.economics.grid_emission_factor_source,
        "config_hash": settings.config_hash(),
        "labels": _slot_labels(T, settings.time.slot_minutes),
    }
    store.replay = replay
    store.kpis = kpis.__dict__
    store.log("loop", "closed_loop_day", {"plan_id": plan["plan_id"], "status": result["status"]})
    return replay


def _slot_labels(T: int, slot_minutes: int) -> list[str]:
    labels = []
    for i in range(T):
        m = i * slot_minutes
        labels.append(f"{m // 60:02d}:{m % 60:02d}")
    return labels


def build_demo(settings: Settings, store: Store) -> dict[str, Any]:
    n_train = max(settings.forecast.backtest.train_min_days, 14)
    from solarsponge.forecasting.service import build_history

    history = build_history(settings, n_train + 4)
    train, rest = history[:n_train], history[n_train:]
    fc_svc = ForecastService(settings)
    fc_svc.fit_from_history(train)
    twin = next((d for d in rest if d.weather_class == "clear"), rest[-1])
    return run_closed_loop_day(settings, twin, fc_svc, store)
