"""Second-zone twin for neighbor-blend demos."""

from __future__ import annotations

from datetime import datetime

from solarsponge.config import Settings
from solarsponge.twin.simulator import DayTwin, simulate_day


def peer_settings(settings: Settings, zone_id: str = "zone-002") -> Settings:
    s = settings.model_copy(deep=True)
    s.zone.id = zone_id
    s.zone.name = f"{settings.zone.name} peer"
    s.zone.lat = settings.zone.lat + 0.4
    s.zone.lon = settings.zone.lon + 0.3
    s.zone.pv_nameplate_kw = settings.zone.pv_nameplate_kw * 0.8
    return s


def simulate_peer_day(settings: Settings, day_start: datetime, day_index: int = 0) -> DayTwin:
    return simulate_day(peer_settings(settings), day_start, day_index=day_index + 3)
