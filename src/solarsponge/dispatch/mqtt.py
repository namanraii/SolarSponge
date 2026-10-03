"""MQTT dispatch stub. Logs payloads; publishes only if paho-mqtt is installed and a broker is up."""

from __future__ import annotations

import json
from typing import Any


class MqttAdapter:
    def __init__(self, host: str = "localhost", port: int = 1883, topic: str = "solarsponge/dispatch"):
        self.host = host
        self.port = port
        self.topic = topic
        self.sent: list[dict[str, Any]] = []
        self._client = None
        try:
            import paho.mqtt.client as mqtt

            self._client = mqtt.Client()
            self._client.connect(host, port, keepalive=2)
        except Exception:
            self._client = None

    def send(self, load_id: str, commanded_on: bool) -> bool:
        payload = {"load_id": load_id, "on": bool(commanded_on)}
        self.sent.append(payload)
        if self._client is not None:
            try:
                self._client.publish(self.topic, json.dumps(payload))
            except Exception:
                pass
        return commanded_on

    def safety_ok(self, load_id: str, commanded_on: bool) -> bool:
        return True
