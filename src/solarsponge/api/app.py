from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

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


@app.on_event("startup")
def _startup() -> None:
    get_ctx()


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
