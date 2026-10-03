"""15-minute control cycle: rolling-horizon re-plan, dispatch, verify."""

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
from solarsponge.twin.loads import FlexLoad, simulate_soc, simulate_soil, simulate_thermal
from solarsponge.twin.simulator import DayTwin, apply_schedule, simulate_day


def shift_warm(on: np.ndarray | None, steps: int) -> np.ndarray | None:
    if on is None or steps <= 0:
        return on
    out = np.zeros_like(on)
    T = on.shape[1]
    if steps < T:
        out[:, : T - steps] = on[:, steps:]
    return out


def slice_loads(loads: list[FlexLoad], start: int, already_on: np.ndarray, dt_h: float) -> list[FlexLoad]:
    """Remaining horizon: shrink windows and subtract energy already delivered."""
    sliced: list[FlexLoad] = []
    for i, L in enumerate(loads):
        delivered = float(already_on[i, :start].sum() * L.power_kw * dt_h) if start else 0.0
        lo, hi = L.window
        nlo = lo - start
        nhi = hi - start
        energy = max(0.0, L.energy_kwh - delivered)
        occ = None
        if L.occupancy is not None:
            occ = (L.occupancy[0] - start, L.occupancy[1] - start)
        dep = None if L.departure_slot is None else L.departure_slot - start
        sliced.append(
            FlexLoad(
                load_id=L.load_id,
                name=L.name,
                kind=L.kind,
                power_kw=L.power_kw,
                energy_kwh=energy,
                window=(nlo, nhi),
                min_run=L.min_run,
                max_starts=L.max_starts,
                default_on=None if L.default_on is None else L.default_on[start:],
                t_init=L.t_init,
                temp_band=L.temp_band,
                thermal_mass=L.thermal_mass,
                ua=L.ua,
                cop=L.cop,
                occupancy=occ,
                deficit_init_mm=L.deficit_init_mm,
                max_depletion_mm=L.max_depletion_mm,
                et_mm=None if L.et_mm is None else L.et_mm[start:],
                rain_mm=None if L.rain_mm is None else L.rain_mm[start:],
                irrig_mm_per_on_slot=L.irrig_mm_per_on_slot,
                soc_init=L.soc_init,
                soc_target=L.soc_target,
                battery_kwh=L.battery_kwh,
                charging_eff=L.charging_eff,
                departure_slot=dep,
                t_amb=None if L.t_amb is None else L.t_amb[start:],
                params=L.params,
            )
        )
    return sliced


def run_closed_loop_day(
    settings: Settings,
    twin: DayTwin,
    fc_svc: ForecastService,
    store: Store,
    oracle: bool = False,
    risk_quantile: float | None = None,
    disabled_load_ids: list[str] | None = None,
    cloud_delta_pct: float = 0.0,
    rolling: bool = False,
) -> dict[str, Any]:
    q = risk_quantile if risk_quantile is not None else settings.optimizer.risk_quantile
    loads = [L for L in twin.loads if L.load_id not in set(disabled_load_ids or [])]
    issued = twin.day_start
    fc = fc_svc.predict_day(twin, issued_at=issued, oracle=oracle)
    surplus = twin.surplus_kw if oracle else risk_surplus(fc.surplus, q)
    surplus = surplus.copy()
    surplus[surplus < settings.optimizer.surplus_floor_kw] = 0.0

    T = settings.time.slots_per_day
    dt = settings.time.dt_h
    step = max(1, int(settings.time.replan_every_minutes / settings.time.slot_minutes))
    use_rolling = bool(rolling)

    gateway = DispatchGateway(settings, loads)
    committed = np.zeros((len(loads), T), dtype=int)
    warm = None
    last_plan_on = None
    changed = 0
    compared = 0
    last_result = None
    solve_ms_total = 0
    n_plans = 0

    if use_rolling:
        for t in range(0, T, step):
            remaining = surplus[t:]
            sliced = slice_loads(loads, t, committed, dt)
            warm_slice = None if warm is None else shift_warm(warm, step if t else 0)
            if warm_slice is not None and warm_slice.shape[1] != len(remaining):
                warm_slice = warm_slice[:, : len(remaining)] if warm_slice.shape[1] > len(remaining) else None
            result = plan_day(remaining, sliced, settings, warm_start_on=warm_slice)
            n_plans += 1
            solve_ms_total += result["solve_ms"]
            on_rem = result["on"]
            if last_plan_on is not None:
                overlap = min(last_plan_on.shape[1] - step, on_rem.shape[1])
                if overlap > 0:
                    prev = last_plan_on[:, step : step + overlap]
                    now = on_rem[:, :overlap]
                    changed += int(np.sum(prev != now))
                    compared += prev.size
            last_plan_on = on_rem
            warm = on_rem
            end = min(T, t + on_rem.shape[1])
            committed[:, t:end] = on_rem[:, : end - t]
            last_result = result
            for k in range(t, min(t + step, T)):
                gateway.dispatch_slot(
                    [
                        {
                            "load_id": L.load_id,
                            "on": committed[i].tolist(),
                        }
                        for i, L in enumerate(loads)
                    ],
                    k,
                )
    else:
        last_result = plan_day(surplus, loads, settings, warm_start_on=warm)
        committed = last_result["on"]
        n_plans = 1
        solve_ms_total = last_result["solve_ms"]
        for t in range(T):
            gateway.dispatch_slot(last_result["schedules"], t)

    actual_on = _align_on(twin.loads, loads, committed, T)
    applied = apply_schedule(twin, actual_on, settings)
    s0 = apply_schedule(twin, default_schedule(twin.loads, T), settings)
    val = validate_plan(twin.surplus_kw, loads, committed, float(np.minimum(surplus, applied["flex_load_kw"]).sum() * dt), dt)
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
        int(solve_ms_total / max(n_plans, 1)),
        (last_result or {}).get("status") == "Fallback",
        twin.weather_class,
    )
    stability = 1.0 - (changed / compared) if compared else 1.0

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

    schedules = []
    if last_result:
        for i, L in enumerate(loads):
            delivered = float(committed[i].sum() * L.power_kw * dt)
            short = max(0.0, L.energy_kwh - delivered) if L.kind in {"pump", "ev_depot"} else 0.0
            schedules.append(
                {
                    "load_id": L.load_id,
                    "name": L.name,
                    "kind": L.kind,
                    "power_kw": L.power_kw,
                    "on": committed[i].astype(int).tolist(),
                    "energy_kwh": delivered,
                    "unmet_kwh": short,
                    "window": list(L.window),
                }
            )

    plan = store.add_plan(
        {
            "plan_id": len(store.plans) + 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "zone_id": settings.zone.id,
            "solver_status": (last_result or {}).get("status", "Fallback"),
            "risk_quantile": q,
            "objective": (last_result or {}).get("objective"),
            "solve_ms": int(solve_ms_total / max(n_plans, 1)),
            "config_hash": settings.config_hash(),
            "schedules": schedules,
            "unmet_kwh": (last_result or {}).get("unmet_kwh", {}),
            "absorbed_kwh_expected": kpis.absorbed_kwh,
            "fallback_reason": (last_result or {}).get("fallback_reason"),
            "slot_start": twin.day_start.isoformat(),
            "validation_notes": val.notes,
            "n_replans": n_plans,
            "schedule_stability": stability,
        }
    )
    store.add_forecast(
        {
            "zone_id": settings.zone.id,
            "target": "surplus",
            "issued_at": issued.isoformat() if hasattr(issued, "isoformat") else str(issued),
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
            "issued_at": str(issued),
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
        "schedules": schedules,
        "default_schedules": [
            {
                "load_id": L.load_id,
                "on": (L.default_on if L.default_on is not None else np.zeros(T)).astype(int).tolist(),
            }
            for L in loads
        ],
        "states": states,
        "kpis": {**kpis.__dict__, "schedule_stability": stability, "n_replans": n_plans},
        "plan": {k: v for k, v in plan.items() if k != "on"},
        "emission_factor_t_per_mwh": settings.economics.grid_emission_factor_t_per_mwh,
        "emission_factor_source": settings.economics.grid_emission_factor_source,
        "config_hash": settings.config_hash(),
        "labels": _slot_labels(T, settings.time.slot_minutes),
        "kill_switch": settings.ops.kill_switch,
        "iex_dam_value_inr": _iex_value(applied["absorbed_kw"], dt),
    }
    store.replay = replay
    store.kpis = replay["kpis"]
    store.log("loop", "closed_loop_day", {"plan_id": plan["plan_id"], "n_replans": n_plans, "stability": stability})
    return replay


def _align_on(all_loads: list, used: list, on: np.ndarray, T: int) -> np.ndarray:
    if on is None:
        return np.zeros((len(all_loads), T), dtype=int)
    if len(used) == len(all_loads) and on.shape[0] == len(all_loads) and on.shape[1] == T:
        return on
    out = np.zeros((len(all_loads), T), dtype=int)
    idx = {L.load_id: i for i, L in enumerate(all_loads)}
    width = min(T, on.shape[1])
    for j, L in enumerate(used):
        if L.load_id in idx and j < on.shape[0]:
            out[idx[L.load_id], :width] = on[j, :width]
    return out


def _iex_value(absorbed_kw, dt_h: float) -> float:
    from solarsponge.markets.iex import value_absorbed_inr

    return value_absorbed_inr(absorbed_kw, dt_h)


def _slot_labels(T: int, slot_minutes: int) -> list[str]:
    labels = []
    for i in range(T):
        m = i * slot_minutes
        labels.append(f"{m // 60:02d}:{m % 60:02d}")
    return labels


def build_demo(settings: Settings, store: Store, rolling: bool = True) -> dict[str, Any]:
    n_train = max(settings.forecast.backtest.train_min_days, 14)
    from solarsponge.forecasting.service import build_history

    history = build_history(settings, n_train + 4)
    train, rest = history[:n_train], history[n_train:]
    fc_svc = ForecastService(settings)
    fc_svc.fit_from_history(train)
    fc_svc.save(settings.ops.model_dir)
    fc_svc.export_parquet(settings.ops.feature_store)
    twin = next((d for d in rest if d.weather_class == "clear"), rest[-1])
    run_settings = settings
    if rolling and settings.ops.demo_mode:
        # Cap demo replans so API startup stays interactive; live tick uses config interval.
        run_settings = settings.model_copy(deep=True)
        min_interval = max(run_settings.time.slot_minutes, int(run_settings.time.horizon_hours * 60 / 8))
        run_settings.time.replan_every_minutes = max(run_settings.time.replan_every_minutes, min_interval)
    return run_closed_loop_day(run_settings, twin, fc_svc, store, rolling=rolling)
