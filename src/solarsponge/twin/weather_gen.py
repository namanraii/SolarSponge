"""Seeded synthetic weather for the digital twin when APIs are offline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from solarsponge.config import Settings
from solarsponge.twin.pv import clearsky_ghi_wm2


WEATHER_CLASS_CLOUD = {
    "clear": 0.08,
    "partly_cloudy": 0.35,
    "overcast": 0.78,
    "monsoon": 0.88,
}


def weather_class_for_day(day_index: int, classes: list[str]) -> str:
    return classes[day_index % len(classes)]


def generate_day(
    day_start: datetime,
    settings: Settings,
    weather_class: str = "partly_cloudy",
    seed: int = 7,
) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    cfg = settings.time
    zone = settings.zone
    T = cfg.slots_per_day
    dt = timedelta(minutes=cfg.slot_minutes)
    times = [day_start.astimezone(timezone.utc) + i * dt for i in range(T)]

    cloud_mean = WEATHER_CLASS_CLOUD.get(weather_class, 0.35)
    cloud = np.clip(rng.normal(cloud_mean, 0.08, T), 0.0, 1.0)
    # diurnal smoother
    kernel = np.array([0.25, 0.5, 0.25])
    cloud = np.convolve(cloud, kernel, mode="same")

    ghi = np.zeros(T)
    dni = np.zeros(T)
    dhi = np.zeros(T)
    cs = np.zeros(T)
    for i, ts in enumerate(times):
        cs[i] = clearsky_ghi_wm2(zone.lat, zone.lon, ts)
        # simple cloud attenuation
        ghi[i] = cs[i] * (1.0 - 0.75 * cloud[i])
        dhi[i] = ghi[i] * (0.2 + 0.5 * cloud[i])
        dni[i] = max(0.0, (ghi[i] - dhi[i]) / max(0.2, 1.0 - cloud[i] * 0.5))

    hod = np.arange(T) * cfg.dt_h
    temp = 18 + 12 * np.sin((hod - 8) / 24 * 2 * np.pi) ** 2 + rng.normal(0, 0.4, T)
    if weather_class == "monsoon":
        temp -= 4
        rain = np.clip(rng.gamma(1.2, 0.15, T), 0, None)
        rain[rng.random(T) > 0.25] = 0
    else:
        rain = np.zeros(T)
        rain[rng.random(T) < 0.02] = rng.uniform(0.1, 1.0)

    # FAO-style placeholder: ~5 mm/day on a clear day, scaled by GHI share (blueprint irrigation example).
    ghi_sum = float(ghi.sum()) or 1.0
    daily_et = 5.0 * (1.0 - 0.45 * float(cloud.mean()))
    et0 = daily_et * ghi / ghi_sum
    wind = np.clip(rng.normal(3.5, 1.0, T), 0.2, None)
    humidity = np.clip(45 + 40 * cloud + rng.normal(0, 3, T), 15, 95)

    return {
        "ghi_wm2": ghi,
        "dni_wm2": dni,
        "dhi_wm2": dhi,
        "ghi_clearsky": cs,
        "temp_c": temp,
        "cloud_frac": cloud,
        "wind_ms": wind,
        "humidity_pct": humidity,
        "et0_mm": et0,
        "rain_mm": rain,
        "weather_class": np.array([weather_class] * T),
    }


def generate_history(settings: Settings, n_days: int, start: datetime | None = None) -> list[dict]:
    if start is None:
        start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    days = []
    classes = settings.evaluation.weather_classes
    for d in range(n_days):
        wclass = weather_class_for_day(d, classes)
        day_start = start + timedelta(days=d)
        wx = generate_day(day_start, settings, wclass, seed=settings.forecast.seed + d * 17)
        days.append({"day_start": day_start, "weather_class": wclass, **wx})
    return days
