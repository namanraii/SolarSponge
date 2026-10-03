import numpy as np
from datetime import datetime, timezone

from solarsponge.config import load_config
from solarsponge.forecasting.service import ForecastService, build_history
from solarsponge.loop import run_closed_loop_day, shift_warm, slice_loads
from solarsponge.store import Store
from solarsponge.twin.simulator import simulate_day


def test_shift_warm_moves_horizon():
    on = np.array([[1, 1, 0, 0], [0, 1, 1, 0]])
    shifted = shift_warm(on, 1)
    assert shifted[0, 0] == 1
    assert shifted[0, 1] == 0
    assert shifted[0, 3] == 0


def test_slice_loads_subtracts_delivered_energy():
    settings = load_config()
    twin = simulate_day(settings, datetime(2026, 4, 1, tzinfo=timezone.utc), day_index=0)
    T = settings.time.slots_per_day
    already = np.zeros((len(twin.loads), T), dtype=int)
    already[0, :8] = 1
    sliced = slice_loads(twin.loads, 8, already, settings.time.dt_h)
    delivered = 8 * twin.loads[0].power_kw * settings.time.dt_h
    assert sliced[0].energy_kwh == max(0.0, twin.loads[0].energy_kwh - delivered)
    assert sliced[0].window[0] == twin.loads[0].window[0] - 8


def test_rolling_replans_more_than_once():
    settings = load_config()
    settings.ops.demo_mode = False
    settings.ops.database_url = "sqlite:///:memory:"
    settings.time.replan_every_minutes = 360
    settings.optimizer.time_limit_s = 3
    twin = simulate_day(settings, datetime(2026, 4, 1, tzinfo=timezone.utc), day_index=0)
    hist = build_history(settings, 4)
    fc = ForecastService(settings)
    fc.fit_from_history(hist)
    store = Store(settings)
    replay = run_closed_loop_day(settings, twin, fc, store, rolling=True)
    assert replay["kpis"]["n_replans"] >= 2
    assert 0.0 <= replay["kpis"]["schedule_stability"] <= 1.0
    assert replay["plan"]["n_replans"] >= 2
