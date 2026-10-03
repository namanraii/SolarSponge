from solarsponge.config import load_config
from solarsponge.kpi.metrics import compute_day_kpis
import numpy as np


def test_cea_emission_factor_is_official_not_placeholder():
    s = load_config()
    assert s.economics.grid_emission_factor_t_per_mwh == 0.675
    assert "CEA" in s.economics.grid_emission_factor_source
    assert "22.0" in s.economics.grid_emission_factor_source


def test_co2_formula():
    s = load_config()
    T = s.time.slots_per_day
    zeros = np.zeros(T)
    absorbed = np.ones(T) * 100  # 100 kW all day = 2400 kWh = 2.4 MWh
    kpis = compute_day_kpis(
        s, zeros, zeros, zeros, absorbed, absorbed, 2400, 0, 1, False, "clear"
    )
    assert abs(kpis.co2_avoided_t - 2.4 * 0.675) < 1e-9
