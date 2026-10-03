"""Synthetic IEX DAM prices. Not a live market feed."""

from __future__ import annotations

import numpy as np


def dam_price_inr_per_kwh(n_slots: int = 96, seed: int = 7) -> np.ndarray:
    """Illustrative Indian DAM shape: cheap overnight, midday dip, evening peak."""
    rng = np.random.default_rng(seed)
    t = np.arange(n_slots) * 24.0 / n_slots
    base = 3.2 + 1.4 * np.sin((t - 6) / 24 * 2 * np.pi)
    evening = 2.5 * np.exp(-((t - 19.5) ** 2) / 8.0)
    midday_dip = -0.8 * np.exp(-((t - 13.0) ** 2) / 6.0)
    noise = rng.normal(0, 0.08, n_slots)
    return np.clip(base + evening + midday_dip + noise, 1.5, 12.0)


def value_absorbed_inr(absorbed_kw: np.ndarray, dt_h: float = 0.25, seed: int = 7) -> float:
    prices = dam_price_inr_per_kwh(len(absorbed_kw), seed)
    return float(np.sum(np.asarray(absorbed_kw) * dt_h * prices))
