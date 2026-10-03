"""Exact reference scheduler from the blueprint [T]. Kept for regression against pulp==2.9.0."""
from dataclasses import dataclass
import numpy as np
import pulp

_NAME_SEQ = 0

def _tag() -> int:
    global _NAME_SEQ
    _NAME_SEQ += 1
    return _NAME_SEQ

@dataclass
class FlexLoad:
    name: str
    power_kw: float
    energy_kwh: float
    window: tuple
    min_run: int = 1
    max_starts: int = 4

def schedule(surplus_kw, loads, dt_h=0.25, w_switch=0.5, w_late=0.0):
    T = len(surplus_kw)
    m = pulp.LpProblem("solarsponge", pulp.LpMaximize)
    tag = _tag()
    x = {(i, t): pulp.LpVariable(f"x_{tag}_{i}_{t}", cat="Binary") for i in range(len(loads)) for t in range(T)}
    u = {(i, t): pulp.LpVariable(f"u_{tag}_{i}_{t}", cat="Binary") for i in range(len(loads)) for t in range(T)}
    a = {t: pulp.LpVariable(f"a_{tag}_{t}", lowBound=0) for t in range(T)}

    for t in range(T):
        m += a[t] <= surplus_kw[t]
        m += a[t] <= pulp.lpSum(loads[i].power_kw * x[i, t] for i in range(len(loads)))

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
        slots_needed = int(np.ceil(L.energy_kwh / (L.power_kw * dt_h)))
        m += pulp.lpSum(x[i, t] for t in range(T)) == slots_needed
        m += pulp.lpSum(u[i, t] for t in range(T)) <= L.max_starts

    m += (pulp.lpSum(a[t] * dt_h for t in range(T))
          - w_switch * pulp.lpSum(u.values())
          - w_late * pulp.lpSum(t * x[i, t] for i in range(len(loads)) for t in range(T)))

    from solarsponge.optimizer.solver import solve_mip
    status = solve_mip(m, time_limit_s=30, threads=1)
    on = np.array([[int(round(x[i, t].value() or 0)) for t in range(T)] for i in range(len(loads))])
    absorbed = sum((a[t].value() or 0) * dt_h for t in range(T))
    return {"status": pulp.LpStatus[status], "on": on, "absorbed_kwh": absorbed}
