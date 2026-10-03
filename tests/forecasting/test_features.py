import pandas as pd
import numpy as np

from solarsponge.forecasting.features import make_features
from solarsponge.forecasting.baselines import persistence


def test_lag_does_not_use_future():
    idx = pd.date_range("2026-04-01", periods=200, freq="15min", tz="UTC")
    df = pd.DataFrame(
        {
            "ghi_fc": np.arange(200),
            "ghi_clearsky": np.ones(200) * 800,
            "temp_fc": np.ones(200) * 30,
            "cloud_fc": np.zeros(200),
            "wind_fc": np.ones(200),
            "pv_kw": np.arange(200),
        },
        index=idx,
    )
    issued = idx[100]
    X = make_features(df, issued_at=issued)
    # lags after issued_at should not contain "future" pv (shift 96 still uses past)
    assert "pv_lag_1d" in X.columns
    assert not X.isna().any().any()


def test_persistence_is_yesterday():
    x = np.arange(192, dtype=float)
    y = persistence(x, 96)
    assert np.allclose(y[96:], x[:96])
    assert np.allclose(y[:96], 0)
