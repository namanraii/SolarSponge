"""Simulated device adapter: delay, non-compliance, telemetry noise."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from solarsponge.config import DevicesCfg


@dataclass
class DeviceSim:
    cfg: DevicesCfg
    rng: np.random.Generator
    pending: dict[str, list[int]] = field(default_factory=dict)
    last_actual: dict[str, int] = field(default_factory=dict)

    def command(self, load_id: str, commanded_on: int) -> int:
        q = self.pending.setdefault(load_id, [])
        q.append(int(commanded_on))
        delay = max(0, self.cfg.response_delay_slots)
        if len(q) <= delay:
            actual = self.last_actual.get(load_id, 0)
        else:
            actual = q.pop(0)
        if self.rng.random() < self.cfg.noncompliance_prob:
            actual = self.last_actual.get(load_id, actual)
        self.last_actual[load_id] = int(actual)
        return int(actual)

    def noisy_power(self, power_kw: float) -> float:
        noise = 1.0 + self.rng.normal(0, self.cfg.telemetry_noise_pct / 100.0)
        return max(0.0, power_kw * noise)
