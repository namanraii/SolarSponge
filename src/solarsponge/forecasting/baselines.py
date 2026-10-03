"""Honest forecast baselines: persistence (B0) and clear-sky climatology (B1)."""

from __future__ import annotations

import numpy as np


def persistence(series: np.ndarray, slots_per_day: int = 96) -> np.ndarray:
    """Same slot yesterday. Falls back to zeros for the first day."""
    out = np.zeros_like(series, dtype=float)
    if len(series) > slots_per_day:
        out[slots_per_day:] = series[:-slots_per_day]
    else:
        out[:] = series
    return out


def clearsky_climatology(
    ghi_clearsky: np.ndarray,
    ghi_actual: np.ndarray,
    slots_per_day: int = 96,
) -> np.ndarray:
    """B1: clear-sky GHI × climatological clear-sky index by slot of day."""
    T = len(ghi_clearsky)
    csi = np.divide(ghi_actual, np.clip(ghi_clearsky, 1, None), out=np.zeros(T), where=ghi_clearsky > 1)
    csi = np.clip(csi, 0, 1.5)
    by_slot = np.zeros(slots_per_day)
    counts = np.zeros(slots_per_day)
    for i in range(T):
        s = i % slots_per_day
        by_slot[s] += csi[i]
        counts[s] += 1
    counts[counts == 0] = 1
    mean_csi = by_slot / counts
    return ghi_clearsky * mean_csi[np.arange(T) % slots_per_day]


def point_to_quantiles(point: np.ndarray, rel_width: float = 0.25) -> dict[str, np.ndarray]:
    """Wrap a point forecast in a crude p10/p50/p90 band (used by baselines)."""
    point = np.asarray(point, dtype=float)
    return {
        "p10": np.clip(point * (1 - rel_width), 0, None),
        "p50": np.clip(point, 0, None),
        "p90": np.clip(point * (1 + rel_width), 0, None),
    }
