from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

from solarsponge import __version__
from solarsponge.api.schemas import ChatRequest, ScenarioRequest
from solarsponge.runtime import get_ctx

PLAN_COUNTER = Counter("solarsponge_plans_total", "Plans created", ["status"])
SOLVE_HIST = Histogram("solarsponge_solve_seconds", "Optimizer solve time")

app = FastAPI(
    title="SolarSponge API",
    version=__version__,
    description="Forecast → optimize → dispatch → verify. The LLM never controls a load.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


_HITS: dict[str, deque] = defaultdict(deque)
_SCHEDULER = None


class KillBody(BaseModel):
    enabled: bool


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "local"


@app.middleware("http")
async def auth_and_limit(request: Request, call_next):
    path = request.url.path
    open_paths = {"/healthz", "/metrics", "/docs", "/openapi.json", "/redoc"}
    if path in open_paths:
        return await call_next(request)
    ctx = get_ctx()
    key = (ctx.settings.ops.api_key or os.environ.get("SOLARSPONGE_API_KEY") or "").strip()
    if key and request.headers.get("x-api-key") != key:
        return JSONResponse(
            status_code=401,
            content={"type": "about:blank", "title": "unauthorized", "status": 401, "detail": "missing or invalid X-API-Key"},
            media_type="application/problem+json",
        )
    limit = ctx.settings.ops.api_rate_limit_per_min
    if limit > 0:
        ip = _client_ip(request)
        now = time.time()
        q = _HITS[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            return JSONResponse(
                status_code=429,
                content={"type": "about:blank", "title": "rate limited", "status": 429, "detail": "too many requests"},
                media_type="application/problem+json",
            )
        q.append(now)
    return await call_next(request)


def _tick() -> None:
    ctx = get_ctx()
    if ctx.settings.ops.kill_switch:
        ctx.store.log("scheduler", "tick_skipped_kill_switch", {})
        return
    from solarsponge.loop import build_demo

    build_demo(ctx.settings, ctx.store, rolling=True)
    ctx.store.log("scheduler", "replan_tick", {"plan_id": (ctx.store.latest_plan(ctx.settings.zone.id) or {}).get("plan_id")})


@app.on_event("startup")
def _startup() -> None:
    global _SCHEDULER
    get_ctx()
    tick = os.environ.get("SOLARSPONGE_TICK", "").lower() in {"1", "true", "yes"}
    if tick:
        from apscheduler.schedulers.background import BackgroundScheduler

        minutes = max(1, get_ctx().settings.time.replan_every_minutes)
        _SCHEDULER = BackgroundScheduler()
        _SCHEDULER.add_job(_tick, "interval", minutes=minutes, id="replan", replace_existing=True)
        _SCHEDULER.start()


@app.on_event("shutdown")
def _shutdown() -> None:
    if _SCHEDULER is not None:
        _SCHEDULER.shutdown(wait=False)


@app.get("/healthz")
def healthz():
    ctx = get_ctx()
    return {"ok": True, "ready": ctx.ready, "version": __version__, "config_hash": ctx.settings.config_hash()}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/v1/zones")
def list_zones():
    z = get_ctx().settings.zone
    return [
        {
            "id": z.id,
            "name": z.name,
            "lat": z.lat,
            "lon": z.lon,
            "pv_nameplate_kw": z.pv_nameplate_kw,
            "evac_limit_kw": z.evac_limit_kw,
        }
    ]


@app.get("/v1/zones/{zone_id}/forecast")
def get_forecast(zone_id: str, target: str = Query("surplus")):
    ctx = get_ctx()
    rec = ctx.store.latest_forecast(zone_id, target)
    if not rec:
        raise HTTPException(status_code=404, detail="forecast not found")
    return rec


@app.get("/v1/zones/{zone_id}/plan/latest")
def latest_plan(zone_id: str):
    ctx = get_ctx()
    p = ctx.store.latest_plan(zone_id)
    if not p:
        raise HTTPException(status_code=404, detail="plan not found")
    return p


@app.post("/v1/zones/{zone_id}/plan")
def trigger_plan(zone_id: str):
    ctx = get_ctx()
    from solarsponge.loop import build_demo

    replay = build_demo(ctx.settings, ctx.store)
    PLAN_COUNTER.labels(replay["plan"]["solver_status"]).inc()
    return replay["plan"]


@app.get("/v1/zones/{zone_id}/kpis")
def kpis(zone_id: str):
    ctx = get_ctx()
    if not ctx.store.kpis:
        raise HTTPException(status_code=404, detail="no kpis")
    return ctx.store.kpis


@app.get("/v1/zones/{zone_id}/replay")
def replay(zone_id: str):
    ctx = get_ctx()
    if not ctx.store.replay:
        raise HTTPException(status_code=404, detail="no replay")
    return ctx.store.replay


@app.post("/v1/zones/{zone_id}/scenario")
def scenario(zone_id: str, req: ScenarioRequest):
    ctx = get_ctx()
    result = ctx.tools.run_scenario(
        zone_id,
        horizon_hours=req.horizon_hours,
        overrides={
            "cloud_delta_pct": req.cloud_delta_pct,
            "disabled_load_ids": req.disabled_load_ids,
            "risk_quantile": req.risk_quantile,
        },
    )
    return result


@app.get("/v1/loads/{load_id}")
def load_info(load_id: str):
    ctx = get_ctx()
    info = ctx.tools.get_load_info(load_id)
    if info.get("error"):
        raise HTTPException(status_code=404, detail=info["error"])
    return info


@app.post("/v1/copilot/chat")
def copilot_chat(req: ChatRequest):
    ctx = get_ctx()
    return ctx.copilot.chat(req.message, req.zone_id)


@app.get("/v1/ops/status")
def ops_status():
    ctx = get_ctx()
    return {
        "kill_switch": ctx.settings.ops.kill_switch,
        "demo_mode": ctx.settings.ops.demo_mode,
        "tick_enabled": _SCHEDULER is not None,
        "config_hash": ctx.settings.config_hash(),
        "ready": ctx.ready,
    }


@app.post("/v1/ops/kill-switch")
def set_kill_switch(body: KillBody):
    ctx = get_ctx()
    ctx.settings.ops.kill_switch = bool(body.enabled)
    ctx.store.log("ops", "kill_switch", {"enabled": body.enabled})
    if ctx.store.replay:
        ctx.store.replay["kill_switch"] = ctx.settings.ops.kill_switch
    return {"kill_switch": ctx.settings.ops.kill_switch}


@app.get("/v1/zones/{zone_id}/prices")
def dam_prices(zone_id: str):
    from solarsponge.markets.iex import dam_price_inr_per_kwh

    prices = dam_price_inr_per_kwh(get_ctx().settings.time.slots_per_day)
    return {"zone_id": zone_id, "source": "iex-dam-stub", "inr_per_kwh": prices.tolist()}


@app.websocket("/v1/stream/{zone_id}")
async def stream(websocket: WebSocket, zone_id: str):
    await websocket.accept()
    ctx = get_ctx()
    replay = ctx.store.replay or {}
    labels = replay.get("labels") or []
    try:
        for i, label in enumerate(labels):
            payload = {
                "slot": i,
                "label": label,
                "pv_kw": (replay.get("pv_kw") or [0])[i],
                "curtailed_s0_kw": (replay.get("curtailed_s0_kw") or [0])[i],
                "curtailed_sx_kw": (replay.get("curtailed_sx_kw") or [0])[i],
                "flex_sx_kw": (replay.get("flex_sx_kw") or [0])[i],
            }
            await websocket.send_text(json.dumps(payload))
        await websocket.send_text(json.dumps({"done": True}))
    except WebSocketDisconnect:
        return


@app.exception_handler(HTTPException)
async def rfc7807(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "about:blank",
            "title": exc.detail if isinstance(exc.detail, str) else "error",
            "status": exc.status_code,
            "detail": str(exc.detail),
            "instance": str(request.url.path),
        },
        media_type="application/problem+json",
    )
