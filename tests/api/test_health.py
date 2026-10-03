from fastapi.testclient import TestClient

from solarsponge.config import load_config
from solarsponge import runtime


def test_healthz(monkeypatch, tmp_path):
    settings = load_config()
    settings.ops.demo_mode = False
    settings.ops.database_url = f"sqlite:///{tmp_path}/t.db"
    runtime._CTX = None
    runtime.bootstrap(settings)
    from solarsponge.api.app import app

    c = TestClient(app)
    r = c.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    z = c.get("/v1/zones")
    assert z.status_code == 200
    assert z.json()[0]["id"] == settings.zone.id
