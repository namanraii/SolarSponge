"""Greedy fallback: place loads in the highest-surplus slots that still fit constraints."""

from __future__ import annotations

import numpy as np

from solarsponge.twin.loads import FlexLoad


def greedy_schedule(
    surplus_kw: np.ndarray,
    loads: list[FlexLoad],
    dt_h: float = 0.25,
) -> np.ndarray:
    T = len(surplus_kw)
    on = np.zeros((len(loads), T), dtype=int)
    remaining_surplus = surplus_kw.astype(float).copy()

    order = sorted(
        range(len(loads)),
        key=lambda i: _slack(loads[i], T, dt_h),
    )
    for i in order:
        L = loads[i]
        lo, hi = _clip_window(L.window, T)
        if hi < lo:
            continue
        slots_needed = int(np.ceil(L.energy_kwh / max(L.power_kw * dt_h, 1e-9)))
        slots_needed = min(slots_needed, hi - lo + 1)
        placed = 0
        starts = 0
        t = lo
        while t <= hi and placed < slots_needed and starts < L.max_starts:
            run = min(max(L.min_run, 1), slots_needed - placed, hi - t + 1)
            if run <= 0:
                break
            window = remaining_surplus[t : t + run]
            # skip empty surplus unless we have no choice near the deadline
            urgency = slots_needed - placed >= (hi - t + 1)
            if window.mean() <= 0 and not urgency:
                t += 1
                continue
            on[i, t : t + run] = 1
            remaining_surplus[t : t + run] = np.maximum(0.0, remaining_surplus[t : t + run] - L.power_kw)
            placed += run
            starts += 1
            t += run
        # fill leftover slots in the best remaining surplus
        if placed < slots_needed:
            candidates = np.argsort(-remaining_surplus)
            for s in candidates:
                if placed >= slots_needed:
                    break
                if s < lo or s > hi or on[i, s] == 1:
                    continue
                on[i, s] = 1
                remaining_surplus[s] = max(0.0, remaining_surplus[s] - L.power_kw)
                placed += 1
    return on


def naive_noon_schedule(loads: list[FlexLoad], T: int, dt_h: float, noon_slot: int | None = None) -> np.ndarray:
    """Run everything around solar noon, ignoring surplus shape and most constraints except windows."""
    if noon_slot is None:
        noon_slot = T // 2
    on = np.zeros((len(loads), T), dtype=int)
    for i, L in enumerate(loads):
        lo, hi = _clip_window(L.window, T)
        if hi < lo:
            continue
        slots_needed = int(np.ceil(L.energy_kwh / max(L.power_kw * dt_h, 1e-9)))
        start = min(max(noon_slot - slots_needed // 2, lo), hi)
        end = min(start + slots_needed, hi + 1)
        on[i, start:end] = 1
    return on


def default_schedule(loads: list[FlexLoad], T: int) -> np.ndarray:
    on = np.zeros((len(loads), T), dtype=int)
    for i, L in enumerate(loads):
        if L.default_on is not None:
            src = np.asarray(L.default_on, dtype=int)
            n = min(T, len(src))
            on[i, :n] = src[:n]
        else:
            lo, hi = _clip_window(L.window, T)
            if hi >= lo:
                on[i, lo : min(lo + max(L.min_run, 1), hi + 1)] = 1
    return on


def _clip_window(window: tuple[int, int], T: int) -> tuple[int, int]:
    lo, hi = window
    return max(0, lo), min(T - 1, hi)


def _slack(L: FlexLoad, T: int, dt_h: float) -> int:
    lo, hi = L.window
    need = int(np.ceil(L.energy_kwh / max(L.power_kw * dt_h, 1e-9)))
    return (hi - lo + 1) - need
