"""Open-Meteo client with on-disk cache and synthetic fallback."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from solarsponge.config import Settings
from solarsponge.ingestion.quality import validate_ghi
from solarsponge.twin.weather_gen import generate_day


CACHE_DIR = Path("data/cache")


def _cache_path(lat: float, lon: float, day: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"wx_{lat:.2f}_{lon:.2f}_{day}.json"


def fetch_open_meteo(settings: Settings, day_start: datetime) -> dict | None:
    try:
        import httpx
    except Exception:
        return None
    lat, lon = settings.zone.lat, settings.zone.lon
    end = day_start + timedelta(days=1)
    params = {
        "latitude": lat,
        "longitude": lon,
        "minutely_15": [
            "shortwave_radiation",
            "direct_normal_irradiance",
            "diffuse_radiation",
            "temperature_2m",
            "cloud_cover",
            "wind_speed_10m",
            "et0_fao_evapotranspiration",
        ],
        "timezone": "UTC",
        "start_date": day_start.date().isoformat(),
        "end_date": end.date().isoformat(),
    }
    url = "https://api.open-meteo.com/v1/forecast"
    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


def load_weather(settings: Settings, day_start: datetime, weather_class: str = "partly_cloudy", seed: int = 7) -> dict:
    day = day_start.astimezone(timezone.utc).date().isoformat()
    cache = _cache_path(settings.zone.lat, settings.zone.lon, day)
    if cache.exists():
        raw = json.loads(cache.read_text())
        return {k: np.array(v) if isinstance(v, list) else v for k, v in raw.items()}

    api = fetch_open_meteo(settings, day_start) if settings.weather.provider == "open-meteo" else None
    if api and "minutely_15" in api:
        m = api["minutely_15"]
        T = settings.time.slots_per_day
        ghi = validate_ghi(np.array(m.get("shortwave_radiation", [0] * T)[:T], dtype=float))
        wx = generate_day(day_start, settings, weather_class, seed=seed)
        wx["ghi_wm2"] = ghi
        wx["temp_c"] = np.array(m.get("temperature_2m", wx["temp_c"])[:T], dtype=float)
        serial = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in wx.items()}
        cache.write_text(json.dumps(serial, default=str))
        return wx

    if settings.weather.use_synthetic_if_offline:
        return generate_day(day_start, settings, weather_class, seed=seed)
    raise RuntimeError("Weather API unavailable and synthetic fallback disabled")
