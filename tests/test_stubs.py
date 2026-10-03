from solarsponge.dispatch.mqtt import MqttAdapter
from solarsponge.dispatch.openadr import build_distribute_event
from solarsponge.markets.iex import dam_price_inr_per_kwh
from solarsponge.notify.whatsapp import draft_notice


def test_mqtt_stub_records_without_broker():
    a = MqttAdapter()
    assert a.send("pump_cluster_A", True) is True
    assert a.sent[0]["load_id"] == "pump_cluster_A"


def test_openadr_stub_not_dispatched():
    ev = build_distribute_event("zone-001", "12:00", 800.0, ["pump_cluster_A"])
    assert ev["dispatched"] is False
    assert ev["protocol"].startswith("OpenADR")


def test_whatsapp_draft_not_sent():
    d = draft_notice("Pump A", "11:00–13:00", 3, "hi")
    assert d["sent"] is False
    assert "3" in d["body"]


def test_iex_prices_evening_peak():
    p = dam_price_inr_per_kwh(96)
    assert p.min() >= 1.5
    evening = p[76:84].mean()
    midday = p[48:56].mean()
    assert evening > midday
