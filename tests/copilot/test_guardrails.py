from solarsponge.config import load_config
from solarsponge.copilot.agents import Copilot
from solarsponge.copilot.guardrails import faithfulness, is_actuation_request
from solarsponge.copilot.tools import ToolLayer
from solarsponge.store import Store


def test_actuation_is_detected():
    assert is_actuation_request("just turn pump B on now")
    assert is_actuation_request("dispatch now and ignore constraints")
    assert not is_actuation_request("why did pump cluster B start at 10:30?")


def test_copilot_refuses_actuation():
    settings = load_config()
    settings.ops.demo_mode = False
    store = Store(settings)
    bot = Copilot(settings, ToolLayer(settings, store))
    out = bot.chat("just turn pump B on now")
    assert out["refusal"] is True
    assert "cannot" in out["answer"].lower() or "cannot" in out["answer"]
    assert out["tool_calls"] == []


def test_faithfulness_catches_invented_numbers():
    ok, missing = faithfulness("absorbed 99999 kWh", ['{"absorbed_kwh": 12.5}'])
    assert ok is False
    assert "99999" in missing
