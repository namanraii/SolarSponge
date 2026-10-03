"""Optimizer service: MILP, then fallbacks. Never calls an LLM."""

from __future__ import annotations

from typing import Any

import numpy as np

from solarsponge.config import Settings
from solarsponge.optimizer.aggregate import disaggregate_fair, schedule_virtual_battery
from solarsponge.optimizer.heuristic import default_schedule, greedy_schedule, naive_noon_schedule
from solarsponge.optimizer.milp import schedule as milp_schedule
from solarsponge.optimizer.validate import validate_plan
from solarsponge.twin.loads import FlexLoad


def risk_surplus(quantiles: dict[str, np.ndarray], q: float) -> np.ndarray:
    """Interpolate a surplus trajectory from p10/p50/p90 for the chosen risk quantile."""
    p10, p50, p90 = quantiles["p10"], quantiles["p50"], quantiles["p90"]
    if q <= 0.1:
        return p10
    if q >= 0.9:
        return p90
    if q <= 0.5:
        a = (q - 0.1) / 0.4
        return (1 - a) * p10 + a * p50
    a = (q - 0.5) / 0.4
    return (1 - a) * p50 + a * p90


def plan_day(
    surplus_kw: np.ndarray,
    loads: list[FlexLoad],
    settings: Settings,
    warm_start_on: np.ndarray | None = None,
    force_fallback: str | None = None,
    naive_noon: bool = False,
    optimizer_disabled: bool = False,
) -> dict[str, Any]:
    dt_h = settings.time.dt_h
    T = len(surplus_kw)
    opt = settings.optimizer

    if settings.ops.kill_switch or optimizer_disabled:
        on = default_schedule(loads, T)
        return _pack("Fallback", on, surplus_kw, loads, dt_h, 0, "kill_switch" if settings.ops.kill_switch else "disabled")

    if naive_noon:
        on = naive_noon_schedule(loads, T, dt_h)
        return _pack("Fallback", on, surplus_kw, loads, dt_h, 0, "naive_noon")

    if force_fallback == "greedy":
        on = greedy_schedule(surplus_kw, loads, dt_h)
        return _pack("Fallback", on, surplus_kw, loads, dt_h, 0, "greedy")

    if force_fallback == "default_schedule":
        on = default_schedule(loads, T)
        return _pack("Fallback", on, surplus_kw, loads, dt_h, 0, "default_schedule")

    n_pumps = sum(1 for L in loads if L.kind == "pump")
    use_vb = opt.use_virtual_battery or n_pumps >= opt.virtual_battery_min_devices
    if use_vb:
        try:
            vb_packed = _plan_virtual_battery(surplus_kw, loads, settings, warm_start_on)
            if vb_packed is not None:
                return vb_packed
        except Exception:
            pass

    try:
        result = milp_schedule(
            surplus_kw,
            loads,
            dt_h=dt_h,
            w_switch=opt.weights.w_switch,
            w_late=opt.weights.w_late,
            w_shortfall=opt.weights.w_shortfall,
            time_limit_s=opt.time_limit_s,
            mip_gap=opt.mip_gap,
            threads=opt.threads,
            warm_start_on=warm_start_on if opt.warm_start else None,
        )
    except Exception as exc:  # solver crash
        result = {"status": "Error", "on": None, "absorbed_kwh": 0.0, "unmet_kwh": {}, "solve_ms": 0, "error": str(exc)}

    status = result.get("status")
    on = result.get("on")
    reason = None

    if status in {"Optimal", "Feasible"} and on is not None:
        val = validate_plan(surplus_kw, loads, on, result["absorbed_kwh"], dt_h)
        if val.window_ok and val.min_run_ok and val.max_starts_ok and val.absorbed_ok:
            packed = _pack(status, on, surplus_kw, loads, dt_h, result["solve_ms"], None, result)
            packed["validation"] = val
            packed["unmet_kwh"] = {**val.unmet_kwh, **result.get("unmet_kwh", {})}
            return packed
        reason = "invalid_incumbent"

    # Fallback chain
    for step in opt.fallback:
        if step == "incumbent" and on is not None and status in {"Optimal", "Feasible", "Undefined"}:
            if np.any(on):
                packed = _pack("Feasible", on, surplus_kw, loads, dt_h, result.get("solve_ms", 0), "incumbent")
                packed["validation"] = validate_plan(surplus_kw, loads, on, packed["absorbed_kwh"], dt_h)
                return packed
        if step == "greedy":
            on_g = greedy_schedule(surplus_kw, loads, dt_h)
            packed = _pack("Fallback", on_g, surplus_kw, loads, dt_h, result.get("solve_ms", 0), "greedy")
            packed["validation"] = validate_plan(surplus_kw, loads, on_g, packed["absorbed_kwh"], dt_h)
            return packed
        if step == "default_schedule":
            on_d = default_schedule(loads, T)
            packed = _pack("Fallback", on_d, surplus_kw, loads, dt_h, result.get("solve_ms", 0), "default_schedule")
            packed["validation"] = validate_plan(surplus_kw, loads, on_d, packed["absorbed_kwh"], dt_h)
            return packed

    on_d = default_schedule(loads, T)
    packed = _pack("Infeasible", on_d, surplus_kw, loads, dt_h, result.get("solve_ms", 0), reason or "infeasible")
    packed["validation"] = validate_plan(surplus_kw, loads, on_d, packed["absorbed_kwh"], dt_h)
    return packed


def _plan_virtual_battery(surplus_kw, loads, settings: Settings, warm_start_on):
    """Homogeneous pumps as a power/energy envelope; remaining loads stay MILP."""
    pumps = [L for L in loads if L.kind == "pump"]
    rest = [L for L in loads if L.kind != "pump"]
    if not pumps:
        return None
    dt_h = settings.time.dt_h
    power_max = float(sum(L.power_kw for L in pumps))
    energy = float(sum(L.energy_kwh for L in pumps))
    lo = min(L.window[0] for L in pumps)
    hi = max(L.window[1] for L in pumps)
    vb = schedule_virtual_battery(surplus_kw, power_max, energy, (lo, hi), dt_h=dt_h, time_limit_s=min(5, settings.optimizer.time_limit_s))
    on_p = disaggregate_fair(vb["power_kw"], pumps, dt_h)
    residual = np.maximum(0.0, np.asarray(surplus_kw) - vb["power_kw"])
    T = len(surplus_kw)
    if rest:
        warm_rest = None
        if warm_start_on is not None:
            idx = [i for i, L in enumerate(loads) if L.kind != "pump"]
            warm_rest = warm_start_on[idx]
        rest_res = milp_schedule(
            residual,
            rest,
            dt_h=dt_h,
            w_switch=settings.optimizer.weights.w_switch,
            w_late=settings.optimizer.weights.w_late,
            w_shortfall=settings.optimizer.weights.w_shortfall,
            time_limit_s=settings.optimizer.time_limit_s,
            mip_gap=settings.optimizer.mip_gap,
            threads=settings.optimizer.threads,
            warm_start_on=warm_rest if settings.optimizer.warm_start else None,
        )
        on_r = rest_res.get("on")
        if on_r is None:
            on_r = default_schedule(rest, T)
        on = np.zeros((len(loads), T), dtype=int)
        pi = ri = 0
        for i, L in enumerate(loads):
            if L.kind == "pump":
                on[i] = on_p[pi]
                pi += 1
            else:
                on[i] = on_r[ri]
                ri += 1
        packed = _pack(rest_res.get("status") or vb.get("status") or "Feasible", on, surplus_kw, loads, dt_h, rest_res.get("solve_ms", 0), None, rest_res)
    else:
        on = on_p
        packed = _pack(str(vb.get("status") or "Feasible"), on, surplus_kw, loads, dt_h, 0, None)
    packed["virtual_battery"] = True
    packed["vb_absorbed_kwh"] = vb.get("absorbed_kwh")
    return packed


def _pack(status, on, surplus_kw, loads, dt_h, solve_ms, fallback_reason, milp=None):
    shifted = sum(L.power_kw * on[i] for i, L in enumerate(loads))
    absorbed = float(np.minimum(surplus_kw, shifted).sum() * dt_h)
    schedules = []
    unmet = {}
    for i, L in enumerate(loads):
        delivered = float(on[i].sum() * L.power_kw * dt_h)
        short = max(0.0, L.energy_kwh - delivered) if L.kind in {"pump", "ev_depot"} else 0.0
        unmet[L.load_id] = short
        schedules.append(
            {
                "load_id": L.load_id,
                "name": L.name,
                "kind": L.kind,
                "power_kw": L.power_kw,
                "on": on[i].astype(int).tolist(),
                "energy_kwh": delivered,
                "unmet_kwh": short,
                "window": list(L.window),
            }
        )
    return {
        "status": status,
        "on": on,
        "schedules": schedules,
        "absorbed_kwh": absorbed,
        "unmet_kwh": unmet,
        "solve_ms": solve_ms,
        "fallback_reason": fallback_reason,
        "objective": None if milp is None else milp.get("objective"),
        "loads": loads,
    }
