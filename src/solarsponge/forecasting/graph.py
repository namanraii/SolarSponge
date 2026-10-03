"""Neighbor blend of quantile forecasts (GNN-style smoothing without a trained graph net)."""

from __future__ import annotations

import numpy as np


def blend_quantiles(
    center: dict[str, np.ndarray],
    neighbors: list[dict[str, np.ndarray]],
    weight: float = 0.3,
) -> dict[str, np.ndarray]:
    """p' = (1-w) * center + w * mean(neighbors). Weight 0 keeps the local model."""
    if not neighbors or weight <= 0:
        return {k: np.asarray(v) for k, v in center.items()}
    w = min(max(weight, 0.0), 1.0)
    out = {}
    for key, arr in center.items():
        acc = np.zeros_like(np.asarray(arr), dtype=float)
        n = 0
        for nb in neighbors:
            if key in nb:
                acc = acc + np.asarray(nb[key], dtype=float)
                n += 1
        mean = acc / max(n, 1)
        out[key] = (1.0 - w) * np.asarray(arr, dtype=float) + w * mean
    return out
