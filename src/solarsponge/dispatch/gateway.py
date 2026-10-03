"""Dispatch gateway: translates a plan into device commands and re-checks limits."""

from __future__ import annotations

from solarsponge.config import Settings
from solarsponge.dispatch.sim import SimAdapter
from solarsponge.twin.loads import FlexLoad


class DispatchGateway:
    def __init__(self, settings: Settings, loads: list[FlexLoad], adapter: SimAdapter | None = None):
        self.settings = settings
        self.loads = {L.load_id: L for L in loads}
        self.adapter = adapter or SimAdapter(settings.devices, loads, seed=settings.forecast.seed)

    def dispatch_slot(self, schedules: list[dict], slot: int) -> dict[str, dict]:
        """Send ON/OFF for one slot. Kill switch returns every load to default."""
        out = {}
        for sch in schedules:
            lid = sch["load_id"]
            L = self.loads.get(lid)
            if L is None:
                continue
            if self.settings.ops.kill_switch:
                cmd = bool(L.default_on[slot]) if L.default_on is not None else False
            else:
                cmd = bool(sch["on"][slot]) if slot < len(sch["on"]) else False
            lo, hi = L.window
            if cmd and (slot < lo or slot > hi):
                cmd = False  # second gate
            actual = self.adapter.send(lid, cmd)
            power = L.power_kw if actual else 0.0
            out[lid] = {"commanded_on": cmd, "actual_on": actual, "power_kw": power}
        return out
