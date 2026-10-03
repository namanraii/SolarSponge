"""Device adapter interface. Same code path for simulator and future hardware."""

from __future__ import annotations

from typing import Protocol


class DeviceAdapter(Protocol):
    def send(self, load_id: str, commanded_on: bool) -> bool:
        """Return actual ON/OFF after delay/noise. Must not violate device limits."""
        ...

    def safety_ok(self, load_id: str, commanded_on: bool) -> bool:
        ...
