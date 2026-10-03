"""MILP scheduler: absorb surplus subject to hard load constraints.

Pin: pulp==2.9.0 (pulp 4.x changed LpVariable and this formulation fails).
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pulp

from solarsponge.twin.loads import FlexLoad

_NAME_SEQ = 0


def _tag() -> int:
    global _NAME_SEQ
    _NAME_SEQ += 1
    return _NAME_SEQ


def schedule(
    surplus_kw,
    loads: list[FlexLoad],
    dt_h: float = 0.25,
    w_switch: float = 0.5,
    w_late: float = 0.0,
    w_shortfall: float = 1000.0,
    time_limit_s: int = 10,
    mip_gap: float = 0.01,
    threads: int = 2,
    warm_start_on: np.ndarray | None = None,
) -> dict[str, Any]:
    """
    Maximise absorbed surplus. Energy needs are hard; a penalized slack reports shortfall
    instead of silently under-serving.
    """
    surplus_kw = np.asarray(surplus_kw, dtype=float)
    T = len(surplus_kw)
    n = len(loads)
    t0 = time.perf_counter()

    m = pulp.LpProblem("solarsponge", pulp.LpMaximize)
    tag = _tag()
    x = {(i, t): pulp.LpVariable(f"x_{tag}_{i}_{t}", cat="Binary") for i in range(n) for t in range(T)}
    u = {(i, t): pulp.LpVariable(f"u_{tag}_{i}_{t}", cat="Binary") for i in range(n) for t in range(T)}
    a = {t: pulp.LpVariable(f"a_{tag}_{t}", lowBound=0) for t in range(T)}
    s = {i: pulp.LpVariable(f"s_{tag}_{i}", lowBound=0) for i in range(n)}  # unmet kWh
    extra_pen = []

    if warm_start_on is not None:
        for i in range(min(n, warm_start_on.shape[0])):
            for t in range(T):
                x[i, t].setInitialValue(int(warm_start_on[i, t]))

    for t in range(T):
        m += a[t] <= float(surplus_kw[t])
        m += a[t] <= pulp.lpSum(loads[i].power_kw * x[i, t] for i in range(n))

    for i, L in enumerate(loads):
        lo, hi = L.window
        for t in range(T):
            if t < lo or t > hi:
                m += x[i, t] == 0
            prev = x[i, t - 1] if t > 0 else 0
            m += u[i, t] >= x[i, t] - prev
            for k in range(1, L.min_run):
                if t + k < T:
                    m += x[i, t + k] >= u[i, t]
        m += pulp.lpSum(u[i, t] for t in range(T)) <= L.max_starts

        delivered = pulp.lpSum(L.power_kw * dt_h * x[i, t] for t in range(T))
        if L.kind in {"pump", "ev_depot"}:
            m += delivered + s[i] >= L.energy_kwh
            m += delivered <= L.energy_kwh * 1.15 + 1e-3
        else:
            # thermal loads: energy is a soft preference to run during surplus, not a delivery quota
            m += s[i] == 0

        if L.kind in {"cold_store", "hvac"} and L.temp_band is not None and L.thermal_mass:
            extra_pen.append(_add_thermal(m, x, i, L, T, dt_h))
        if L.kind == "pump" and L.max_depletion_mm is not None and L.irrig_mm_per_on_slot:
            extra_pen.append(_add_soil(m, x, i, L, T))
        if L.kind == "ev_depot" and L.battery_kwh and L.soc_target is not None:
            extra_pen.append(_add_soc(m, x, i, L, T, dt_h))

    m += (
        pulp.lpSum(a[t] * dt_h for t in range(T))
        - w_switch * pulp.lpSum(u[i, t] for i in range(n) for t in range(T))
        - w_late * pulp.lpSum(t * x[i, t] for i in range(n) for t in range(T))
        - w_shortfall * pulp.lpSum(s[i] for i in range(n))
        - w_shortfall * pulp.lpSum(extra_pen)
    )

    from solarsponge.optimizer.solver import solve_mip

    status_code = solve_mip(m, time_limit_s=time_limit_s, mip_gap=mip_gap, threads=threads)
    status = pulp.LpStatus[status_code]
    solve_ms = int((time.perf_counter() - t0) * 1000)

    on = np.array(
        [[int(round((x[i, t].value() or 0))) for t in range(T)] for i in range(n)],
        dtype=int,
    )
    absorbed = float(sum((a[t].value() or 0) * dt_h for t in range(T)))
    unmet = {loads[i].load_id: float(s[i].value() or 0) for i in range(n)}
    objective = float(pulp.value(m.objective) or 0.0)
    return {
        "status": status,
        "on": on,
        "absorbed_kwh": absorbed,
        "unmet_kwh": unmet,
        "solve_ms": solve_ms,
        "objective": objective,
        "solver": "cbc",
    }


def _add_thermal(m, x, i, L: FlexLoad, T: int, dt_h: float):
    lo_t, hi_t = L.temp_band
    c = L.thermal_mass
    ua = L.ua or 5.0
    cop = L.cop or 2.5
    amb = L.t_amb if L.t_amb is not None else np.full(T, 30.0)
    tag = _tag()
    viol = pulp.LpVariable(f"tviol_{tag}_{i}", lowBound=0)
    temp = [pulp.LpVariable(f"temp_{tag}_{i}_{t}") for t in range(T)]
    t0 = L.t_init if L.t_init is not None else 0.5 * (lo_t + hi_t)
    cool = L.power_kw * cop
    alpha = 1.0 - dt_h * ua / c
    for t in range(T):
        prev = t0 if t == 0 else temp[t - 1]
        m += temp[t] == prev * alpha + dt_h * ((-cool * x[i, t] + ua * float(amb[t])) / c)
        enforce = True
        if L.kind == "hvac" and L.occupancy is not None:
            a, b = L.occupancy
            enforce = a <= t <= b
        if enforce:
            m += temp[t] >= lo_t - viol
            m += temp[t] <= hi_t + viol
    return viol


def _add_soil(m, x, i, L: FlexLoad, T: int):
    tag = _tag()
    d = [pulp.LpVariable(f"def_{tag}_{i}_{t}", lowBound=0) for t in range(T)]
    d0 = L.deficit_init_mm or 0.0
    et = L.et_mm if L.et_mm is not None else np.zeros(T)
    rain = L.rain_mm if L.rain_mm is not None else np.zeros(T)
    irr = L.irrig_mm_per_on_slot or 0.0
    cap = L.max_depletion_mm
    viol = pulp.LpVariable(f"sviol_{tag}_{i}", lowBound=0)
    for t in range(T):
        prev = d0 if t == 0 else d[t - 1]
        m += d[t] >= prev + float(et[t]) - float(rain[t]) - irr * x[i, t]
        m += d[t] <= cap + viol
    return viol


def _add_soc(m, x, i, L: FlexLoad, T: int, dt_h: float):
    tag = _tag()
    soc = [pulp.LpVariable(f"soc_{tag}_{i}_{t}", lowBound=0, upBound=1.05) for t in range(T)]
    s0 = L.soc_init or 0.3
    cap = L.battery_kwh or 1.0
    eff = L.charging_eff or 0.92
    gain = L.power_kw * dt_h * eff / cap
    viol = pulp.LpVariable(f"socviol_{tag}_{i}", lowBound=0)
    for t in range(T):
        prev = s0 if t == 0 else soc[t - 1]
        m += soc[t] == prev + gain * x[i, t]
    m += soc[T - 1] >= (L.soc_target or 0.9) - viol
    return viol
