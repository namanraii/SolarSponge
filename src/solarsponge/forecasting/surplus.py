"""Joint scenario sampling: p10(pv) − p90(load) is not p10(surplus)."""

from __future__ import annotations

import numpy as np

from solarsponge.config import ZoneCfg
from solarsponge.twin.surplus import curtailed_kw


def surplus_quantiles(
    pv_q: dict[float, np.ndarray],
    load_q: dict[float, np.ndarray],
    zone: ZoneCfg,
    n_samples: int = 200,
    rho: float = 0.0,
    seed: int = 7,
    quantiles: tuple[float, ...] = (0.1, 0.5, 0.9),
) -> dict[str, np.ndarray]:
    """Sample correlated PV/load residuals around p50 and take surplus quantiles per slot."""
    p50_pv = pv_q[0.5]
    p50_load = load_q[0.5]
    T = len(p50_pv)
    rng = np.random.default_rng(seed)

    pv_scale = np.clip((pv_q.get(0.9, p50_pv) - pv_q.get(0.1, p50_pv)) / 2.56, 1.0, None)
    load_scale = np.clip((load_q.get(0.9, p50_load) - load_q.get(0.1, p50_load)) / 2.56, 1.0, None)

    mean = np.zeros(2)
    cov = np.array([[1.0, rho], [rho, 1.0]])
    z = rng.multivariate_normal(mean, cov, size=(n_samples, T))
    samples = np.zeros((n_samples, T))
    for k in range(n_samples):
        pv_s = np.clip(p50_pv + z[k, :, 0] * pv_scale, 0, None)
        load_s = np.clip(p50_load + z[k, :, 1] * load_scale, 0, None)
        samples[k] = curtailed_kw(pv_s, load_s, zone, 0.0)
    out = {}
    for q in quantiles:
        out[f"p{int(q * 100)}"] = np.quantile(samples, q, axis=0)
    out["scenarios"] = samples
    return out
