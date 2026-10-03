"""15-minute grid helpers. Internal timestamps are timezone-aware UTC."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from solarsponge.config import TimeCfg


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def slot_index(ts: datetime, cfg: TimeCfg) -> int:
    local = ts.astimezone(ZoneInfo(cfg.timezone_display))
    minutes = local.hour * 60 + local.minute
    return minutes // cfg.slot_minutes


def hhmm_to_slot(hhmm: str, cfg: TimeCfg) -> int:
    h, m = hhmm.split(":")
    minutes = int(h) * 60 + int(m)
    if minutes >= 24 * 60:
        return cfg.slots_per_day - 1
    return minutes // cfg.slot_minutes


def slot_to_hhmm(slot: int, cfg: TimeCfg) -> str:
    minutes = slot * cfg.slot_minutes
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def day_start_utc(ts: datetime, cfg: TimeCfg) -> datetime:
    local = ts.astimezone(ZoneInfo(cfg.timezone_display))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)


def slot_times(day_start: datetime, cfg: TimeCfg) -> list[datetime]:
    dt = timedelta(minutes=cfg.slot_minutes)
    return [day_start + i * dt for i in range(cfg.slots_per_day)]


def floor_slot(ts: datetime, cfg: TimeCfg) -> datetime:
    ts = ts.astimezone(timezone.utc)
    discard = ts.minute % cfg.slot_minutes
    return ts.replace(second=0, microsecond=0) - timedelta(minutes=discard)
