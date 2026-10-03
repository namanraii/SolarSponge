from __future__ import annotations

import numpy as np

from solarsponge.config import DevicesCfg
from solarsponge.twin.devices import DeviceSim
from solarsponge.twin.loads import FlexLoad


class SimAdapter:
    def __init__(self, cfg: DevicesCfg, loads: list[FlexLoad], seed: int = 7):
        self.sim = DeviceSim(cfg, np.random.default_rng(seed))
        self.limits = {L.load_id: L for L in loads}

    def safety_ok(self, load_id: str, commanded_on: bool) -> bool:
        return load_id in self.limits

    def send(self, load_id: str, commanded_on: bool) -> bool:
        if not self.safety_ok(load_id, commanded_on):
            return False
        return bool(self.sim.command(load_id, int(commanded_on)))
