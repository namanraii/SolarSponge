"""PV plant model. Uses pvlib when installed; otherwise a clear-sky + temperature model."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np

from solarsponge.config import ZoneCfg


def _solar_elevation_deg(lat: float, lon: float, ts: datetime) -> float:
    ts = ts.astimezone(timezone.utc)
    doy = ts.timetuple().tm_yday
    gamma = 2 * math.pi / 365 * (doy - 1)
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
    )
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    minutes = ts.hour * 60 + ts.minute + ts.second / 60
    time_offset = eqtime + 4 * lon
    tst = minutes + time_offset
    ha = math.radians(tst / 4 - 180)
    lat_r = math.radians(lat)
    sin_el = math.sin(lat_r) * math.sin(decl) + math.cos(lat_r) * math.cos(decl) * math.cos(ha)
    sin_el = max(-1.0, min(1.0, sin_el))
    return math.degrees(math.asin(sin_el))


def clearsky_ghi_wm2(lat: float, lon: float, ts: datetime) -> float:
    try:
        import pandas as pd
        import pvlib

        loc = pvlib.location.Location(lat, lon, tz="UTC")
        times = pd.DatetimeIndex([pd.Timestamp(ts).tz_convert("UTC")])
        cs = loc.get_clearsky(times)
        return float(cs["ghi"].iloc[0])
    except Exception:
        el = _solar_elevation_deg(lat, lon, ts)
        if el <= 0:
            return 0.0
        am = 1.0 / max(math.sin(math.radians(el)), 0.04)
        return max(0.0, 1361.0 * 0.7 ** (am**0.678) * math.sin(math.radians(el)))


def pv_power_kw(ghi_wm2: float, temp_c: float, zone: ZoneCfg, clearsky_ghi: float | None = None) -> float:
    poa = max(0.0, ghi_wm2)
    stc = 1000.0
    losses = 1.0 - zone.pv_system_losses_pct / 100.0
    temp_derate = 1.0 + (zone.temp_coeff_pct_per_c / 100.0) * (temp_c - 25.0)
    p = zone.pv_nameplate_kw * (poa / stc) * losses * temp_derate
    return float(np.clip(p, 0.0, zone.pv_nameplate_kw))


def pv_series(ghi: np.ndarray, temp_c: np.ndarray, zone: ZoneCfg) -> np.ndarray:
    return np.array([pv_power_kw(g, t, zone) for g, t in zip(ghi, temp_c)], dtype=float)
