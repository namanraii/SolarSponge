"""Rolling-origin backtest. Time-based splits only."""

from __future__ import annotations

import numpy as np

from solarsponge.config import Settings
from solarsponge.forecasting.baselines import clearsky_climatology, persistence
from solarsponge.forecasting.service import ForecastService, build_history
from solarsponge.twin.pv import pv_series


def mae(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    return float(np.mean(np.abs(a - b)))


def skill(model_mae: float, base_mae: float) -> float:
    if base_mae <= 1e-9:
        return 0.0
    return 1.0 - model_mae / base_mae


def coverage(actual, p10, p90) -> float:
    a = np.asarray(actual)
    return float(np.mean((a >= p10) & (a <= p90)))


def pinball(actual, pred, q: float) -> float:
    e = np.asarray(actual) - np.asarray(pred)
    return float(np.mean(np.maximum(q * e, (q - 1) * e)))


def run_backtest(settings: Settings, n_days: int | None = None) -> dict:
    n_days = n_days or max(settings.forecast.backtest.train_min_days + 7, 21)
    history = build_history(settings, n_days)
    train_n = settings.forecast.backtest.train_min_days
    svc = ForecastService(settings)
    svc.fit_from_history(history[:train_n])

    pv_mae_m, pv_mae_b0, pv_mae_b1 = [], [], []
    cov = []
    for d in history[train_n:]:
        bundle = svc.predict_day(d)
        pv_mae_m.append(mae(d.pv_kw, bundle.pv["p50"]))
        b0 = persistence(d.pv_kw, settings.time.slots_per_day)
        # B0 using previous day from history
        prev = history[history.index(d) - 1] if d in history else d
        b0 = prev.pv_kw
        pv_mae_b0.append(mae(d.pv_kw, b0))
        b1_ghi = clearsky_climatology(
            np.concatenate([x.ghi_clearsky for x in history[:train_n]]),
            np.concatenate([x.ghi_wm2 for x in history[:train_n]]),
            settings.time.slots_per_day,
        )
        # use last-day climatology mapped to today
        slot_ghi = np.array([b1_ghi[i % settings.time.slots_per_day] for i in range(len(d.ghi_clearsky))])
        # scale by today's clearsky ratio
        b1_pv = pv_series(d.ghi_clearsky * np.clip(slot_ghi / np.clip(d.ghi_clearsky, 1, None), 0, 1.5), d.temp_c, settings.zone)
        pv_mae_b1.append(mae(d.pv_kw, b1_pv))
        cov.append(coverage(d.pv_kw, bundle.pv["p10"], bundle.pv["p90"]))

    cov_mean = float(np.mean(cov) if cov else 0)
    result = {
        "n_test_days": len(pv_mae_m),
        "mae_p50": float(np.mean(pv_mae_m) if pv_mae_m else 0),
        "mae_b0": float(np.mean(pv_mae_b0) if pv_mae_b0 else 0),
        "mae_b1": float(np.mean(pv_mae_b1) if pv_mae_b1 else 0),
        "skill_vs_b1": skill(float(np.mean(pv_mae_m) if pv_mae_m else 0), float(np.mean(pv_mae_b1) or 1)),
        "coverage_p10_p90": cov_mean,
        "conformal_ok": abs(cov_mean - 0.80) <= 0.15 if cov else False,
        "backend": svc.pv_model.backend if svc.pv_model else "none",
        "beats_clearsky": bool(pv_mae_m and np.mean(pv_mae_m) <= np.mean(pv_mae_b1) + 1e-6),
    }
    from pathlib import Path
    import json

    out = Path("artifacts")
    out.mkdir(exist_ok=True)
    (out / "backtest.json").write_text(json.dumps(result, indent=2))
    return result
