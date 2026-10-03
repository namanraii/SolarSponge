"""Forecast service: train on history, emit p10/p50/p90 for PV, load, surplus."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from solarsponge.config import Settings
from solarsponge.forecasting.baselines import clearsky_climatology, persistence, point_to_quantiles
from solarsponge.forecasting.features import make_features
from solarsponge.forecasting.lgbm import QuantileModel, apply_conformal, fit_quantile_models
from solarsponge.forecasting.surplus import surplus_quantiles
from solarsponge.twin.simulator import DayTwin, simulate_day


@dataclass
class ForecastBundle:
    issued_at: datetime
    times: list[datetime]
    pv: dict[str, np.ndarray]
    load: dict[str, np.ndarray]
    surplus: dict[str, np.ndarray]
    model_version: str
    backend: str


@dataclass
class ForecastService:
    settings: Settings
    pv_model: QuantileModel | None = None
    load_model: QuantileModel | None = None
    history: list[DayTwin] = field(default_factory=list)

    def fit_from_history(self, days: list[DayTwin]) -> None:
        self.history = days
        rows = []
        for d in days:
            T = len(d.pv_kw)
            idx = pd.date_range(d.day_start, periods=T, freq=f"{self.settings.time.slot_minutes}min")
            df = pd.DataFrame(
                {
                    "ghi_fc": d.ghi_wm2,
                    "ghi_clearsky": d.ghi_clearsky,
                    "temp_fc": d.temp_c,
                    "cloud_fc": d.cloud_frac * 100,
                    "wind_fc": d.weather.get("wind_ms", np.zeros(T)),
                    "pv_kw": d.pv_kw,
                    "load_kw": d.baseline_load_kw,
                    "horizon_h": np.arange(T) * self.settings.time.dt_h,
                },
                index=idx,
            )
            rows.append(df)
        hist = pd.concat(rows)
        X = make_features(hist)
        self.pv_model = fit_quantile_models(X, hist["pv_kw"], self.settings.forecast)
        self.load_model = fit_quantile_models(X, hist["load_kw"], self.settings.forecast)

    def predict_day(self, twin: DayTwin, issued_at: datetime | None = None, oracle: bool = False) -> ForecastBundle:
        T = len(twin.pv_kw)
        times = list(pd.date_range(twin.day_start, periods=T, freq=f"{self.settings.time.slot_minutes}min"))
        issued = issued_at or twin.day_start
        if oracle:
            pv_q = point_to_quantiles(twin.pv_kw, rel_width=0.0)
            load_q = point_to_quantiles(twin.baseline_load_kw, rel_width=0.0)
            surplus = {
                "p10": twin.surplus_kw.copy(),
                "p50": twin.surplus_kw.copy(),
                "p90": twin.surplus_kw.copy(),
            }
            return ForecastBundle(issued, times, pv_q, load_q, surplus, "oracle", "oracle")

        df = pd.DataFrame(
            {
                "ghi_fc": twin.ghi_wm2,
                "ghi_clearsky": twin.ghi_clearsky,
                "temp_fc": twin.temp_c,
                "cloud_fc": twin.cloud_frac * 100,
                "wind_fc": twin.weather.get("wind_ms", np.zeros(T)),
                "pv_kw": twin.pv_kw,
                "load_kw": twin.baseline_load_kw,
                "horizon_h": np.arange(T) * self.settings.time.dt_h,
            },
            index=pd.DatetimeIndex(times),
        )
        X = make_features(df, issued_at=pd.Timestamp(issued))

        if self.pv_model is None:
            pv_point = persistence(twin.pv_kw, T) if self.history else twin.pv_kw * 0.9
            load_point = persistence(twin.baseline_load_kw, T) if self.history else twin.baseline_load_kw
            # B1 physics baseline for PV using clear-sky index climatology from history if present
            if self.history:
                ghi_cs = np.concatenate([d.ghi_clearsky for d in self.history])
                ghi_a = np.concatenate([d.ghi_wm2 for d in self.history])
                # map climatology onto today
                csi = clearsky_climatology(ghi_cs, ghi_a, T)
                # last day's worth of csi applied to today's clearsky
                slot_csi = np.array([csi[i % T] / max(ghi_cs[i % T], 1) for i in range(T)])
                pv_point = twin.ghi_clearsky / 1000.0 * self.settings.zone.pv_nameplate_kw * np.clip(slot_csi, 0, 1.2)
                pv_point *= 1.0 - self.settings.zone.pv_system_losses_pct / 100.0
            pv_q = point_to_quantiles(pv_point)
            load_q = point_to_quantiles(load_point)
            backend = "b1_clearsky"
        else:
            pv_raw = apply_conformal(self.pv_model.predict(X), self.pv_model)
            load_raw = apply_conformal(self.load_model.predict(X), self.load_model)
            pv_q = {f"p{int(float(q)*100)}": v for q, v in pv_raw.items()} if 0.5 not in pv_raw else {
                "p10": pv_raw.get(0.1, pv_raw.get(0.5)),
                "p50": pv_raw[0.5],
                "p90": pv_raw.get(0.9, pv_raw[0.5]),
            }
            # normalize keys
            def _norm(d):
                if 0.5 in d:
                    return {"p10": d.get(0.1, d[0.5]), "p50": d[0.5], "p90": d.get(0.9, d[0.5])}
                return d

            pv_q = _norm(pv_raw)
            load_q = _norm(load_raw)
            backend = self.pv_model.backend

        pv_for_s = {0.1: pv_q["p10"], 0.5: pv_q["p50"], 0.9: pv_q["p90"]}
        load_for_s = {0.1: load_q["p10"], 0.5: load_q["p50"], 0.9: load_q["p90"]}
        surplus = surplus_quantiles(
            pv_for_s,
            load_for_s,
            self.settings.zone,
            n_samples=self.settings.forecast.scenario_samples,
            rho=self.settings.forecast.pv_load_corr_rho,
            seed=self.settings.forecast.seed,
        )
        return ForecastBundle(issued, times, pv_q, load_q, surplus, f"m1-{backend}", backend)


def build_history(settings: Settings, n_days: int, start: datetime | None = None) -> list[DayTwin]:
    if start is None:
        start = datetime(2026, 4, 1)
        from datetime import timezone

        start = start.replace(tzinfo=timezone.utc)
    out = []
    for d in range(n_days):
        out.append(simulate_day(settings, start + timedelta(days=d), day_index=d))
    return out
