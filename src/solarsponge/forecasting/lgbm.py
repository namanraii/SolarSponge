"""Quantile models: LightGBM when installed, else a slot-of-day empirical quantile fallback."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from solarsponge.config import ForecastCfg
from solarsponge.forecasting.features import make_features


QUANTILES = (0.1, 0.5, 0.9)


def _try_lgbm():
    try:
        import lightgbm as lgb

        return lgb
    except Exception:
        return None


@dataclass
class QuantileModel:
    models: dict = field(default_factory=dict)
    empirical: dict = field(default_factory=dict)
    feature_names: list[str] = field(default_factory=list)
    backend: str = "empirical"
    conformal: dict[float, float] = field(default_factory=dict)

    def predict(self, X: pd.DataFrame) -> dict[str, np.ndarray]:
        if self.backend == "lightgbm" and self.models:
            X = X[self.feature_names]
            return {q: np.clip(self.models[q].predict(X), 0, None) for q in self.models}
        # empirical: slot-of-day quantiles
        T = len(X)
        hod = (X.index.hour * 4 + X.index.minute // 15) if hasattr(X.index, "hour") else np.arange(T) % 96
        out = {}
        for q, table in self.empirical.items():
            out[q] = np.array([table[int(h) % len(table)] for h in hod], dtype=float)
        return out


def fit_quantile_models(
    X: pd.DataFrame,
    y: pd.Series,
    cfg: ForecastCfg,
) -> QuantileModel:
    lgb = _try_lgbm()
    qm = QuantileModel(feature_names=list(X.columns))
    if lgb is not None and cfg.model.startswith("lightgbm"):
        models = {}
        for q in cfg.quantiles:
            m = lgb.LGBMRegressor(
                objective="quantile",
                alpha=q,
                n_estimators=cfg.lgbm.n_estimators,
                learning_rate=cfg.lgbm.learning_rate,
                num_leaves=cfg.lgbm.num_leaves,
                min_child_samples=cfg.lgbm.min_child_samples,
                subsample=cfg.lgbm.subsample,
                colsample_bytree=cfg.lgbm.colsample_bytree,
                random_state=cfg.seed,
                verbosity=-1,
            )
            m.fit(X, y)
            models[q] = m
        qm.models = models
        qm.backend = "lightgbm"
    else:
        # slot-of-day empirical quantiles
        slots = 96
        idx = np.arange(len(y)) % slots
        for q in cfg.quantiles:
            table = np.zeros(slots)
            for s in range(slots):
                vals = y.to_numpy()[idx == s]
                table[s] = float(np.quantile(vals, q)) if len(vals) else 0.0
            qm.empirical[q] = table
        qm.backend = "empirical"

    if cfg.conformal_calibration and len(y) > 20:
        pred = qm.predict(X)
        for q in cfg.quantiles:
            key = q
            yhat = pred.get(q, pred.get(str(q), np.zeros(len(y))))
            resid = y.to_numpy() - yhat
            qm.conformal[q] = float(np.quantile(resid, q))
    return qm


def apply_conformal(pred: dict, model: QuantileModel) -> dict[str, np.ndarray]:
    out = {}
    for q, arr in pred.items():
        qf = float(q)
        adj = model.conformal.get(qf, 0.0)
        out[qf] = np.clip(np.asarray(arr) + adj, 0, None)
    return out
