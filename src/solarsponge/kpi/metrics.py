"""KPI formulas from the blueprint. Emission factor is the CEA official figure in config."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from solarsponge.config import Settings


@dataclass
class DayKPIs:
    curtailed_s0_kwh: float
    curtailed_sx_kwh: float
    curtailment_avoided_kwh: float
    curtailment_avoided_pct: float
    absorbed_kwh: float
    shiftable_kwh: float
    absorption_efficiency: float
    wasted_load_kwh: float
    co2_avoided_t: float
    farmer_saving_inr: float
    constraint_violations: int
    solve_ms: float
    fallback: bool
    weather_class: str


def kwh(power_kw: np.ndarray, dt_h: float) -> float:
    return float(np.asarray(power_kw).sum() * dt_h)


def compute_day_kpis(
    settings: Settings,
    surplus_kw: np.ndarray,
    curtailed_s0_kw: np.ndarray,
    curtailed_sx_kw: np.ndarray,
    flex_kw: np.ndarray,
    absorbed_kw: np.ndarray,
    shiftable_kwh: float,
    violations: int,
    solve_ms: float,
    fallback: bool,
    weather_class: str,
) -> DayKPIs:
    dt = settings.time.dt_h
    c0 = kwh(curtailed_s0_kw, dt)
    cx = kwh(curtailed_sx_kw, dt)
    avoided = max(0.0, c0 - cx)
    absorbed = kwh(absorbed_kw, dt)
    wasted = kwh(np.maximum(flex_kw - surplus_kw, 0.0), dt)
    ef = settings.economics.grid_emission_factor_t_per_mwh
    co2 = (absorbed / 1000.0) * ef
    saving = absorbed * settings.economics.farmer_tariff_discount_per_kwh_inr
    return DayKPIs(
        curtailed_s0_kwh=c0,
        curtailed_sx_kwh=cx,
        curtailment_avoided_kwh=avoided,
        curtailment_avoided_pct=(avoided / c0 * 100.0) if c0 else 0.0,
        absorbed_kwh=absorbed,
        shiftable_kwh=shiftable_kwh,
        absorption_efficiency=(absorbed / shiftable_kwh) if shiftable_kwh else 0.0,
        wasted_load_kwh=wasted,
        co2_avoided_t=co2,
        farmer_saving_inr=saving,
        constraint_violations=violations,
        solve_ms=solve_ms,
        fallback=fallback,
        weather_class=weather_class,
    )


def bootstrap_ci(values: list[float], n: int = 2000, seed: int = 7) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    if len(arr) == 0:
        return 0.0, 0.0, 0.0
    means = []
    for _ in range(n):
        sample = rng.choice(arr, size=len(arr), replace=True)
        means.append(sample.mean())
    lo, hi = np.quantile(means, [0.025, 0.975])
    return float(arr.mean()), float(lo), float(hi)
