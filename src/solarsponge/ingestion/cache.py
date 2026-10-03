"""On-disk weather cache (JSON, optional parquet)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def cache_path(root: str | Path, zone_id: str, day: str) -> Path:
    p = Path(root) / "weather"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{zone_id}_{day}.json"


def save_day(root: str | Path, zone_id: str, day: str, payload: dict[str, Any]) -> Path:
    path = cache_path(root, zone_id, day)
    path.write_text(json.dumps(payload, default=str))
    return path


def load_day(root: str | Path, zone_id: str, day: str) -> dict[str, Any] | None:
    path = cache_path(root, zone_id, day)
    if not path.exists():
        return None
    return json.loads(path.read_text())
