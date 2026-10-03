"""Re-check hard constraints after a solve. Dispatch uses this as a second gate."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from solarsponge.twin.loads import FlexLoad, simulate_soc, simulate_soil, simulate_thermal


@dataclass
class Validation:
    ok: bool
    energy_ok: bool
    window_ok: bool
    min_run_ok: bool
    max_starts_ok: bool
    absorbed_ok: bool
    thermal_ok: bool
    soil_ok: bool
    soc_ok: bool
    unmet_kwh: dict[str, float]
    notes: list[str]


def count_starts(row: np.ndarray) -> int:
    prev = 0
    n = 0
    for v in row:
        if v == 1 and prev == 0:
            n += 1
        prev = int(v)
    return n


def min_run_holds(row: np.ndarray, min_run: int) -> bool:
    if min_run <= 1:
        return True
    run = 0
    for v in list(row) + [0]:
        if v == 1:
            run += 1
        else:
            if 0 < run < min_run:
                return False
            run = 0
    return True


def validate_plan(
    surplus_kw: np.ndarray,
    loads: list[FlexLoad],
    on: np.ndarray,
    absorbed_kwh: float,
    dt_h: float,
    energy_tol_kwh: float = 0.51,
) -> Validation:
    notes: list[str] = []
    unmet: dict[str, float] = {}
    window_ok = True
    min_run_ok = True
    max_starts_ok = True
    energy_ok = True
    T = len(surplus_kw)

    shifted = np.zeros(T)
    for i, L in enumerate(loads):
        row = on[i].astype(int)
        lo, hi = L.window
        lo_c, hi_c = max(0, lo), min(T - 1, hi)
        if lo_c <= hi_c and (np.any(row[:lo_c]) or np.any(row[hi_c + 1 :])):
            window_ok = False
            notes.append(f"{L.load_id} ON outside window")
        elif hi_c < lo_c and np.any(row):
            window_ok = False
            notes.append(f"{L.load_id} ON outside window")
        if not min_run_holds(row, L.min_run):
            min_run_ok = False
            notes.append(f"{L.load_id} min-run violated")
        if count_starts(row) > L.max_starts:
            max_starts_ok = False
            notes.append(f"{L.load_id} max-starts violated")
        delivered = float(row.sum() * L.power_kw * dt_h)
        short = max(0.0, L.energy_kwh - delivered)
        unmet[L.load_id] = short
        if L.kind in {"pump", "ev_depot"} and short > energy_tol_kwh:
            energy_ok = False
            notes.append(f"{L.load_id} unmet {short:.1f} kWh")
        shifted += L.power_kw * row

    cap = float(np.minimum(surplus_kw, shifted).sum() * dt_h)
    absorbed_ok = absorbed_kwh <= cap + 1e-3
    if not absorbed_ok:
        notes.append("absorbed exceeds min(surplus, shifted load)")

    thermal_ok = True
    soil_ok = True
    soc_ok = True
    for i, L in enumerate(loads):
        row = on[i].astype(int)
        if L.kind in {"cold_store", "hvac"} and L.temp_band is not None:
            temp = simulate_thermal(L, row, dt_h)
            lo_t, hi_t = L.temp_band
            check = temp
            if L.kind == "hvac" and L.occupancy is not None:
                a, b = L.occupancy
                a, b = max(0, a), min(T - 1, b)
                check = temp[a : b + 1] if a <= b else temp[:0]
            if np.any(check < lo_t - 0.6) or np.any(check > hi_t + 0.6):
                thermal_ok = False
                notes.append(f"{L.load_id} temperature band")
        if L.kind == "pump" and L.max_depletion_mm is not None:
            d = simulate_soil(L, row)
            if float(d[-1]) > L.max_depletion_mm + 1.0:
                soil_ok = False
                notes.append(f"{L.load_id} soil deficit {d[-1]:.1f} mm")
        if L.kind == "ev_depot" and L.soc_target is not None:
            soc = simulate_soc(L, row, dt_h)
            idx = L.departure_slot if L.departure_slot is not None else T - 1
            idx = min(max(0, idx), T - 1)
            if soc[idx] + 1e-3 < L.soc_target:
                # overnight wrap: if departure is morning, energy after midnight still counts
                if float(soc[-1]) + 1e-3 < L.soc_target:
                    soc_ok = False
                    notes.append(f"{L.load_id} SoC {soc[idx]:.2f} < {L.soc_target}")

    ok = window_ok and min_run_ok and max_starts_ok and absorbed_ok
    return Validation(
        ok=ok,
        energy_ok=energy_ok,
        window_ok=window_ok,
        min_run_ok=min_run_ok,
        max_starts_ok=max_starts_ok,
        absorbed_ok=absorbed_ok,
        thermal_ok=thermal_ok,
        soil_ok=soil_ok,
        soc_ok=soc_ok,
        unmet_kwh=unmet,
        notes=notes,
    )
