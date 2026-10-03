"""The blueprint's executed reference scheduler must still solve on the toy day."""

import numpy as np

from solarsponge.optimizer.reference import FlexLoad, schedule


def test_reference_scheduler_optimal():
    T = 96
    t = np.arange(T)
    surplus = np.clip(900 * np.exp(-((t - 50) ** 2) / (2 * 6 ** 2)), 0, None)
    surplus[surplus < 30] = 0
    loads = [
        FlexLoad("pump_cluster_A", 150, 900, (24, 80), min_run=8, max_starts=2),
        FlexLoad("pump_cluster_B", 120, 720, (24, 80), min_run=8, max_starts=2),
        FlexLoad("cold_store_1", 200, 800, (0, 95), min_run=4, max_starts=6),
        FlexLoad("ev_depot", 300, 1200, (30, 90), min_run=2, max_starts=4),
    ]
    r = schedule(surplus, loads)
    assert r["status"] == "Optimal"
    assert r["absorbed_kwh"] > 0
    for row in r["on"]:
        assert row.sum() > 0
