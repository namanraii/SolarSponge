import numpy as np

from solarsponge.config import load_config
from solarsponge.twin.surplus import curtailed_kw


def test_flex_load_inside_zone_reduces_curtailment():
    cfg = load_config()
    pv = np.array([4000.0, 4000.0])
    base = np.array([500.0, 500.0])
    none = curtailed_kw(pv, base, cfg.zone, 0.0)
    with_flex = curtailed_kw(pv, base, cfg.zone, 800.0)
    assert np.all(with_flex <= none)
    assert with_flex[0] == np.maximum(0, pv[0] - base[0] - 800 - cfg.zone.evac_limit_kw)


def test_no_negative_curtailment():
    cfg = load_config()
    out = curtailed_kw(100.0, 5000.0, cfg.zone, 0.0)
    assert float(out) == 0.0
