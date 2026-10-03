"""Data quality rules from the blueprint."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


GHI_MAX = 1400.0


@dataclass
class QualityReport:
    ok: bool
    imputed_slots: int
    notes: list[str]


def validate_ghi(ghi: np.ndarray) -> np.ndarray:
    ghi = np.asarray(ghi, dtype=float)
    return np.clip(ghi, 0.0, GHI_MAX)


def fill_short_gaps(x: np.ndarray, max_gap: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """Linear-interpolate gaps of length ≤ max_gap. Longer gaps stay NaN."""
    y = np.array(x, dtype=float)
    imputed = np.zeros(len(y), dtype=bool)
    nans = np.isnan(y)
    if not nans.any():
        return y, imputed
    idx = np.arange(len(y))
    valid = ~nans
    if valid.sum() < 2:
        return y, imputed
    # find gaps
    i = 0
    while i < len(y):
        if not nans[i]:
            i += 1
            continue
        j = i
        while j < len(y) and nans[j]:
            j += 1
        gap = j - i
        if gap <= max_gap and i > 0 and j < len(y):
            y[i:j] = np.linspace(y[i - 1], y[j], gap + 2)[1:-1]
            imputed[i:j] = True
        i = j
    return y, imputed


def resample_rule(kind: str) -> str:
    """Power → mean, energy → sum."""
    return "mean" if kind == "power" else "sum"
