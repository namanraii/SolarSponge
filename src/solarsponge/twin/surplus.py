"""Node headroom: curtailed power that flexible load inside the zone can absorb."""

from __future__ import annotations

import numpy as np

from solarsponge.config import ZoneCfg


def curtailed_kw(
    pv_kw: np.ndarray | float,
    baseline_load_kw: np.ndarray | float,
    zone: ZoneCfg,
    flex_load_kw: np.ndarray | float = 0.0,
) -> np.ndarray:
    """curtailed = max(0, pv − (baseline + flex) − evac_limit)."""
    pv = np.asarray(pv_kw, dtype=float)
    base = np.asarray(baseline_load_kw, dtype=float)
    flex = np.asarray(flex_load_kw, dtype=float)
    headroom = pv - base - flex - zone.evac_limit_kw
    return np.maximum(headroom, 0.0)


def surplus_without_flex(pv_kw: np.ndarray, baseline_load_kw: np.ndarray, zone: ZoneCfg) -> np.ndarray:
    return curtailed_kw(pv_kw, baseline_load_kw, zone, 0.0)
