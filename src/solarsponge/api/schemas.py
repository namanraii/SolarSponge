from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class QuantileForecast(BaseModel):
    ts: datetime
    p10: float
    p50: float
    p90: float


class LoadSchedule(BaseModel):
    load_id: str
    on: list[int] = Field(description="0/1 per slot")
    energy_kwh: float
    unmet_kwh: float = 0.0


class Plan(BaseModel):
    plan_id: int
    created_at: datetime | str
    zone_id: str
    solver_status: Literal["Optimal", "Feasible", "Fallback", "Infeasible"] | str
    risk_quantile: float
    objective: float | None = None
    solve_ms: int
    config_hash: str
    schedules: list[dict[str, Any]]
    absorbed_kwh_expected: float
    unmet_kwh: dict[str, float] | None = None
    fallback_reason: str | None = None


class ScenarioRequest(BaseModel):
    horizon_hours: int = Field(24, ge=1, le=48)
    cloud_delta_pct: float = Field(0, ge=-50, le=50)
    disabled_load_ids: list[str] = []
    risk_quantile: float | None = Field(None, ge=0.1, le=0.9)


class ChatRequest(BaseModel):
    message: str
    zone_id: str | None = None


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
