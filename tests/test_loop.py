from datetime import datetime, timezone

from solarsponge.config import load_config
from solarsponge.optimizer.service import plan_day
from solarsponge.twin.simulator import apply_schedule, simulate_day


def test_clear_day_absorbs_some_surplus():
    settings = load_config()
    twin = simulate_day(settings, datetime(2026, 4, 1, tzinfo=timezone.utc), day_index=0)
    assert twin.weather_class == "clear"
    assert twin.surplus_kw.max() > 0
    result = plan_day(twin.surplus_kw, twin.loads, settings)
    assert result["status"] in {"Optimal", "Feasible", "Fallback"}
    applied = apply_schedule(twin, result["on"], settings)
    assert applied["absorbed_kw"].sum() > 0
    assert int(result["on"].sum()) > 0
    assert result["solve_ms"] < 30_000
