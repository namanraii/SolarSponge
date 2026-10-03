from datetime import datetime, timezone

from solarsponge.config import load_config
from solarsponge.forecasting.features import make_features
from solarsponge.forecasting.graph import blend_quantiles
from solarsponge.forecasting.service import ForecastService, build_history
import numpy as np
import pandas as pd


def test_save_and_load_quantile_model(tmp_path):
    settings = load_config()
    days = build_history(settings, 16)
    svc = ForecastService(settings)
    svc.fit_from_history(days[:14])
    path = svc.save(tmp_path / "models")
    assert path.exists()
    pq = svc.export_parquet(tmp_path / "features.parquet")
    assert pq is not None and pq.exists()
    loaded = ForecastService(settings)
    assert loaded.load(tmp_path / "models")
    twin = days[-1]
    a = svc.predict_day(twin)
    b = loaded.predict_day(twin)
    assert np.allclose(a.pv["p50"], b.pv["p50"], rtol=0.05, atol=50)


def test_features_reject_contemporaneous_actuals():
    idx = pd.date_range("2026-04-01", periods=10, freq="15min", tz="UTC")
    df = pd.DataFrame(
        {
            "ghi_fc": np.ones(10),
            "ghi_clearsky": np.ones(10) * 800,
            "temp_fc": np.ones(10) * 30,
            "cloud_fc": np.zeros(10),
            "wind_fc": np.ones(10),
            "pv_kw": np.arange(10),
            "load_kw": np.arange(10),
        },
        index=idx,
    )
    X = make_features(df, issued_at=idx[0])
    assert "pv_kw" not in X.columns
    assert "load_kw" not in X.columns


def test_neighbor_blend_moves_toward_peer():
    c = {"p50": np.array([0.0, 10.0])}
    n = [{"p50": np.array([10.0, 0.0])}]
    out = blend_quantiles(c, n, weight=0.5)
    assert abs(out["p50"][0] - 5.0) < 1e-9
