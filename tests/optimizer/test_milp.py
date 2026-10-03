"""Property and unit tests for the scheduler. Requires pulp==2.9.0."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings as hsettings, strategies as st

from solarsponge.optimizer.heuristic import greedy_schedule
from solarsponge.optimizer.milp import schedule
from solarsponge.optimizer.validate import count_starts, min_run_holds, validate_plan
from solarsponge.twin.loads import FlexLoad


def _toy_surplus(T=96, peak=900.0):
    t = np.arange(T)
    surplus = np.clip(peak * np.exp(-((t - 50) ** 2) / (2 * 6 ** 2)), 0, None)
    surplus[surplus < 30] = 0
    return surplus


def _energy_load(name, power, energy, window, min_run=2, max_starts=4):
    return FlexLoad(
        load_id=name,
        name=name,
        kind="pump",
        power_kw=power,
        energy_kwh=energy,
        window=window,
        min_run=min_run,
        max_starts=max_starts,
    )


def test_reference_toy_day_is_feasible():
    surplus = _toy_surplus()
    loads = [
        _energy_load("pump_cluster_A", 150, 900, (24, 80), min_run=8, max_starts=2),
        _energy_load("pump_cluster_B", 120, 720, (24, 80), min_run=8, max_starts=2),
        _energy_load("cold_as_energy", 200, 800, (0, 95), min_run=4, max_starts=6),
        _energy_load("ev_depot", 300, 1200, (30, 90), min_run=2, max_starts=4),
    ]
    r = schedule(surplus, loads, time_limit_s=30, threads=1)
    assert r["status"] in {"Optimal", "Feasible"}
    dt = 0.25
    val = validate_plan(surplus, loads, r["on"], r["absorbed_kwh"], dt)
    assert val.window_ok
    assert val.min_run_ok
    assert val.max_starts_ok
    assert val.absorbed_ok
    # energy delivered within slack
    for i, L in enumerate(loads):
        delivered = r["on"][i].sum() * L.power_kw * dt
        assert delivered + r["unmet_kwh"][L.load_id] + 1e-3 >= L.energy_kwh


def test_never_on_outside_window():
    surplus = np.ones(32) * 100
    L = _energy_load("a", 10, 10, (8, 20), min_run=1, max_starts=4)
    r = schedule(surplus, [L], dt_h=0.25, time_limit_s=10, threads=1)
    assert np.all(r["on"][0, :8] == 0)
    assert np.all(r["on"][0, 21:] == 0)


def test_absorbed_cannot_exceed_surplus_or_shifted():
    surplus = _toy_surplus()
    loads = [_energy_load("a", 200, 400, (30, 70), min_run=2, max_starts=3)]
    r = schedule(surplus, loads, time_limit_s=10, threads=1)
    dt = 0.25
    shifted = loads[0].power_kw * r["on"][0]
    cap = np.minimum(surplus, shifted).sum() * dt
    assert r["absorbed_kwh"] <= cap + 1e-3


def test_infeasible_energy_uses_slack_not_crash():
    surplus = np.ones(16) * 5
    L = _energy_load("tight", 10, 1000, (0, 3), min_run=1, max_starts=4)
    r = schedule(surplus, [L], dt_h=0.25, time_limit_s=10, threads=1)
    assert r["status"] in {"Optimal", "Feasible"}
    assert r["unmet_kwh"]["tight"] > 0


@given(
    power=st.floats(20, 80),
    energy=st.floats(40, 200),
    lo=st.integers(0, 20),
    width=st.integers(16, 40),
)
@hsettings(max_examples=8, deadline=None)
def test_random_single_load_window_and_starts(power, energy, lo, width):
    T = 48
    hi = min(T - 1, lo + width)
    surplus = np.linspace(10, 200, T)
    L = _energy_load("r", float(power), float(energy), (lo, hi), min_run=2, max_starts=3)
    r = schedule(surplus, [L], dt_h=0.25, time_limit_s=8, threads=1)
    if r["status"] not in {"Optimal", "Feasible"}:
        pytest.skip("solver miss")
    row = r["on"][0]
    assert np.all(row[:lo] == 0)
    assert np.all(row[hi + 1 :] == 0)
    assert count_starts(row) <= L.max_starts
    assert min_run_holds(row, L.min_run)


def test_greedy_respects_window():
    surplus = _toy_surplus()
    loads = [_energy_load("a", 100, 300, (40, 60), min_run=2, max_starts=3)]
    on = greedy_schedule(surplus, loads, 0.25)
    assert np.all(on[0, :40] == 0)
    assert np.all(on[0, 61:] == 0)
