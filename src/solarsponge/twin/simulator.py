"""One-zone digital twin: weather → PV → baseline load → surplus."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from solarsponge.config import Settings
from solarsponge.twin.loads import FlexLoad, build_flex_loads, power_from_on
from solarsponge.twin.pv import pv_series
from solarsponge.twin.surplus import curtailed_kw
from solarsponge.twin.weather_gen import generate_day, weather_class_for_day


def baseline_load_kw(settings: Settings, T: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    peak = settings.zone.baseline_load_kw_peak
    hod = np.arange(T) * settings.time.dt_h
    # Morning and evening peaks; lower midday (the duck).
    shape = (
        0.45
        + 0.35 * np.exp(-((hod - 8) ** 2) / 8)
        + 0.55 * np.exp(-((hod - 19.5) ** 2) / 10)
        + 0.12 * np.exp(-((hod - 13) ** 2) / 20)
    )
    noise = 1.0 + rng.normal(0, settings.zone.baseline_load_noise_pct / 100.0, T)
    return np.clip(peak * shape * noise, 50.0, None)


@dataclass
class DayTwin:
    day_start: datetime
    weather_class: str
    ghi_wm2: np.ndarray
    temp_c: np.ndarray
    ghi_clearsky: np.ndarray
    cloud_frac: np.ndarray
    et0_mm: np.ndarray
    rain_mm: np.ndarray
    pv_kw: np.ndarray
    baseline_load_kw: np.ndarray
    surplus_kw: np.ndarray
    loads: list[FlexLoad]
    weather: dict


def simulate_day(
    settings: Settings,
    day_start: datetime,
    day_index: int = 0,
    weather_class: str | None = None,
    cloud_delta_pct: float = 0.0,
) -> DayTwin:
    if weather_class is None:
        weather_class = weather_class_for_day(day_index, settings.evaluation.weather_classes)
    wx = generate_day(
        day_start,
        settings,
        weather_class,
        seed=settings.forecast.seed + day_index * 17,
    )
    if cloud_delta_pct:
        scale = 1.0 - cloud_delta_pct / 100.0 * 0.8
        wx["ghi_wm2"] = np.clip(wx["ghi_wm2"] * max(scale, 0.05), 0, None)
        wx["cloud_frac"] = np.clip(wx["cloud_frac"] + cloud_delta_pct / 100.0, 0, 1)
    pv = pv_series(wx["ghi_wm2"], wx["temp_c"], settings.zone)
    T = settings.time.slots_per_day
    base = baseline_load_kw(settings, T, seed=settings.forecast.seed + 1000 + day_index)
    surplus = curtailed_kw(pv, base, settings.zone, 0.0)
    surplus[surplus < settings.optimizer.surplus_floor_kw] = 0.0
    loads = build_flex_loads(settings, T, wx)
    return DayTwin(
        day_start=day_start,
        weather_class=weather_class,
        ghi_wm2=wx["ghi_wm2"],
        temp_c=wx["temp_c"],
        ghi_clearsky=wx["ghi_clearsky"],
        cloud_frac=wx["cloud_frac"],
        et0_mm=wx["et0_mm"],
        rain_mm=wx["rain_mm"],
        pv_kw=pv,
        baseline_load_kw=base,
        surplus_kw=surplus,
        loads=loads,
        weather=wx,
    )


def apply_schedule(twin: DayTwin, on: np.ndarray, settings: Settings) -> dict[str, np.ndarray]:
    flex = power_from_on(twin.loads, on)
    curtailed = curtailed_kw(twin.pv_kw, twin.baseline_load_kw, settings.zone, flex)
    absorbed = np.minimum(flex, twin.surplus_kw)
    return {
        "flex_load_kw": flex,
        "curtailed_kw": curtailed,
        "absorbed_kw": absorbed,
    }
