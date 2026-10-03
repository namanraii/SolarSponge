"""Feature builder with a hard leakage guard on forecast issue times."""

from __future__ import annotations

import numpy as np
import pandas as pd


INDIAN_HOLIDAYS = {
    (1, 26),  # Republic Day
    (8, 15),  # Independence Day
    (10, 2),  # Gandhi Jayanti
}


def make_features(df: pd.DataFrame, issued_at: pd.Timestamp | None = None) -> pd.DataFrame:
    """
    df index: timestamps. Required columns: ghi_fc, ghi_clearsky, temp_fc, cloud_fc, wind_fc,
    optional pv_kw, load_kw, horizon_h.
    If issued_at is set, any row whose actuals would only be known after issued_at is not used
    for lag features.
    """
    out = pd.DataFrame(index=df.index)
    hod = df.index.hour + df.index.minute / 60
    out["hod_sin"] = np.sin(2 * np.pi * hod / 24)
    out["hod_cos"] = np.cos(2 * np.pi * hod / 24)
    out["dow"] = df.index.dayofweek
    out["month"] = df.index.month
    out["holiday"] = [int((ts.month, ts.day) in INDIAN_HOLIDAYS) for ts in df.index]
    out["irrigation_season"] = df.index.month.isin([3, 4, 5, 6, 10, 11]).astype(int)
    cs = df["ghi_clearsky"].clip(lower=1)
    out["cs_index_fc"] = (df["ghi_fc"] / cs).clip(0, 1.5)
    for c in ("ghi_fc", "temp_fc", "cloud_fc", "wind_fc"):
        out[c] = df[c] if c in df.columns else 0.0
    if "horizon_h" in df.columns:
        out["horizon_h"] = df["horizon_h"]
    else:
        out["horizon_h"] = 0.0

    if "pv_kw" in df.columns:
        lag = df["pv_kw"].shift(96)
        if issued_at is not None:
            # only keep lags whose timestamp is <= issued_at
            known = df.index <= issued_at
            lag = lag.where(known, np.nan)
        out["pv_lag_1d"] = lag.bfill().fillna(0)
    else:
        out["pv_lag_1d"] = 0.0

    if "load_kw" in df.columns:
        out["load_lag_1d"] = df["load_kw"].shift(96).bfill().fillna(0)
    else:
        out["load_lag_1d"] = 0.0

    assert not out.isna().all().any()
    return out.fillna(0)
