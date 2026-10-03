"""OpenADR 2.0b-style event stub. Builds a report; does not talk to a VTN."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_distribute_event(zone_id: str, slot_label: str, surplus_kw: float, loads_on: list[str]) -> dict[str, Any]:
    return {
        "protocol": "OpenADR-2.0b-stub",
        "eiEvent": {
            "eventDescriptor": {
                "eventID": f"{zone_id}-{slot_label}",
                "createdDateTime": datetime.now(timezone.utc).isoformat(),
                "eventStatus": "far",
                "vtnComment": "SolarSponge surplus window (simulation)",
            },
            "eiActivePeriod": {"slot": slot_label},
            "eiEventSignals": [
                {"signalName": "LOAD_DISPATCH", "signalType": "level", "payload": loads_on},
                {"signalName": "SURPLUS_KW", "signalType": "delta", "payload": surplus_kw},
            ],
        },
        "dispatched": False,
    }
