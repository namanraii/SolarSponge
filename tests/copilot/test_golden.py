import json
from pathlib import Path

from solarsponge.config import load_config
from solarsponge.copilot.agents import Copilot
from solarsponge.copilot.tools import ToolLayer
from solarsponge.store import Store


GOLDEN = json.loads(Path("tests/copilot/golden.json").read_text())


def _bot():
    settings = load_config()
    settings.ops.demo_mode = False
    settings.ops.database_url = "sqlite:///:memory:"
    store = Store(settings)
    store.add_plan(
        {
            "plan_id": 7,
            "zone_id": settings.zone.id,
            "solver_status": "Optimal",
            "solve_ms": 120,
            "config_hash": settings.config_hash(),
            "risk_quantile": 0.4,
            "absorbed_kwh_expected": 410.5,
            "schedules": [
                {
                    "load_id": "pump_cluster_A",
                    "name": "Pump cluster A",
                    "kind": "pump",
                    "power_kw": 185,
                    "on": [0] * 40 + [1] * 8 + [0] * 48,
                    "energy_kwh": 370,
                    "unmet_kwh": 0,
                    "window": [24, 72],
                }
            ],
            "unmet_kwh": {"pump_cluster_A": 0},
        }
    )
    store.kpis = {
        "absorbed_kwh": 410.5,
        "curtailment_avoided_kwh": 380.0,
        "co2_avoided_t": 0.26,
        "constraint_violations": 0,
    }
    store.add_forecast(
        {
            "zone_id": settings.zone.id,
            "target": "surplus",
            "p10": [0] * 96,
            "p50": [100] * 96,
            "p90": [200] * 96,
        }
    )
    store.replay = {
        "schedules": store.latest_plan(settings.zone.id)["schedules"],
        "states": {},
        "day_start": "2026-04-15T00:00:00+00:00",
    }
    class FastTools(ToolLayer):
        def run_scenario(self, zone_id, horizon_hours=24, overrides=None):
            overrides = overrides or {}
            return {
                "dispatched": False,
                "kpis": dict(store.kpis),
                "plan_id": 8,
                "solver_status": "Optimal",
                "absorbed_kwh_expected": 300.0,
                "cloud_delta_pct": overrides.get("cloud_delta_pct") or 0,
                "disabled_load_ids": list(overrides.get("disabled_load_ids") or []),
                "risk_quantile": overrides.get("risk_quantile") or 0.4,
            }

    return Copilot(settings, FastTools(settings, store)), settings


def test_golden_set_routes_and_refuses():
    bot, _ = _bot()
    faithful = 0
    n_answer = 0
    for item in GOLDEN:
        out = bot.chat(item["q"])
        if item["expect"] == "refuse":
            assert out["refusal"] is True, item
            continue
        assert out["refusal"] is False, item
        assert out["role"] == item["expect"] or item["expect"] == "explain", item
        n_answer += 1
        if out.get("faithful"):
            faithful += 1
    assert len(GOLDEN) == 30
    assert n_answer >= 20
    assert faithful / max(n_answer, 1) >= 0.95


def test_plan_id_cache_hits():
    bot, _ = _bot()
    a = bot.chat("Summarize today's plan")
    b = bot.chat("Summarize today's plan")
    assert b.get("cached") is True
    assert a["answer"] == b["answer"]
