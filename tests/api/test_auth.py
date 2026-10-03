from fastapi.testclient import TestClient

from solarsponge.config import load_config
from solarsponge import runtime


def _client(tmp_path, api_key="", limit=120):
    settings = load_config()
    settings.ops.demo_mode = False
    settings.ops.database_url = f"sqlite:///{tmp_path}/t.db"
    settings.ops.api_key = api_key
    settings.ops.api_rate_limit_per_min = limit
    runtime._CTX = None
    runtime.bootstrap(settings)
    from solarsponge.api.app import _HITS, app

    _HITS.clear()
    return TestClient(app), settings


def test_healthz_open_without_key(tmp_path):
    c, _ = _client(tmp_path, api_key="secret")
    r = c.get("/healthz")
    assert r.status_code == 200


def test_api_key_required(tmp_path):
    c, _ = _client(tmp_path, api_key="secret")
    r = c.get("/v1/zones")
    assert r.status_code == 401
    r2 = c.get("/v1/zones", headers={"X-API-Key": "secret"})
    assert r2.status_code == 200


def test_kill_switch_roundtrip(tmp_path):
    c, settings = _client(tmp_path)
    r = c.post("/v1/ops/kill-switch", json={"enabled": True})
    assert r.status_code == 200
    assert r.json()["kill_switch"] is True
    st = c.get("/v1/ops/status")
    assert st.json()["kill_switch"] is True


def test_rate_limit(tmp_path):
    c, _ = _client(tmp_path, limit=3)
    codes = [c.get("/v1/zones").status_code for _ in range(5)]
    assert 429 in codes
