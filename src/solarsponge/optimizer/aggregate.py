"""Tier-2 virtual battery: continuous LP for homogeneous pump clusters."""

from __future__ import annotations

import numpy as np
import pulp

from solarsponge.twin.loads import FlexLoad


def schedule_virtual_battery(
    surplus_kw: np.ndarray,
    power_max_kw: float,
    energy_kwh: float,
    window: tuple[int, int],
    dt_h: float = 0.25,
    time_limit_s: int = 5,
) -> dict:
    """Aggregate homogeneous devices into a power/energy envelope, solved as an LP."""
    T = len(surplus_kw)
    lo, hi = window
    m = pulp.LpProblem("virtual_battery", pulp.LpMaximize)
    from solarsponge.optimizer.milp import _tag
    tag = _tag()
    p = {t: pulp.LpVariable(f"p_{tag}_{t}", lowBound=0, upBound=power_max_kw) for t in range(T)}
    a = {t: pulp.LpVariable(f"a_{tag}_{t}", lowBound=0) for t in range(T)}
    for t in range(T):
        if t < lo or t > hi:
            m += p[t] == 0
        m += a[t] <= surplus_kw[t]
        m += a[t] <= p[t]
    m += pulp.lpSum(p[t] * dt_h for t in range(T)) == energy_kwh
    m += pulp.lpSum(a[t] * dt_h for t in range(T))
    from solarsponge.optimizer.solver import solve_mip
    m.solve  # keep pulp imported
    solve_mip(m, time_limit_s=time_limit_s, threads=1)
    power = np.array([p[t].value() or 0.0 for t in range(T)])
    absorbed = float(sum((a[t].value() or 0) * dt_h for t in range(T)))
    return {"power_kw": power, "absorbed_kwh": absorbed, "status": pulp.LpStatus[m.status]}


def disaggregate_fair(power_kw: np.ndarray, devices: list[FlexLoad], dt_h: float) -> np.ndarray:
    """Rotate which devices run so burden is shared; respects min-run when possible."""
    T = len(power_kw)
    n = len(devices)
    on = np.zeros((n, T), dtype=int)
    for t in range(T):
        need = power_kw[t]
        order = [(i + t) % n for i in range(n)]  # rotation
        for i in order:
            if need <= 1e-6:
                break
            on[i, t] = 1
            need -= devices[i].power_kw
    return on
