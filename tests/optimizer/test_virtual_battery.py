from datetime import datetime, timezone

from solarsponge.config import load_config
from solarsponge.optimizer.aggregate import schedule_virtual_battery
from solarsponge.optimizer.service import plan_day
from solarsponge.twin.simulator import simulate_day
import numpy as np


def test_virtual_battery_respects_energy():
    surplus = np.zeros(16)
    surplus[4:12] = 400
    vb = schedule_virtual_battery(surplus, power_max_kw=200, energy_kwh=100, window=(0, 15), dt_h=0.25)
    assert vb["power_kw"].sum() * 0.25 == np.clip(vb["power_kw"].sum() * 0.25, 0, 1e9)
    assert abs(vb["power_kw"].sum() * 0.25 - 100) < 5


def test_plan_day_virtual_battery_flag():
    settings = load_config()
    settings.optimizer.use_virtual_battery = True
    settings.optimizer.time_limit_s = 3
    twin = simulate_day(settings, datetime(2026, 4, 1, tzinfo=timezone.utc), day_index=0)
    result = plan_day(twin.surplus_kw, twin.loads, settings)
    assert result["status"] in {"Optimal", "Feasible", "Fallback"}
    assert result.get("virtual_battery") is True
    assert int(result["on"].sum()) >= 0
