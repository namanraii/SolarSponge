"""In-memory store plus optional SQLite persistence. Schema matches the blueprint."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from solarsponge.config import Settings


def _connect_postgres(url: str):
    try:
        from sqlalchemy import create_engine, text

        eng = create_engine(url, pool_pre_ping=True)
        with eng.begin() as c:
            c.execute(text("SELECT 1"))
        return eng
    except Exception:
        return None


def _connect_redis(url: str):
    try:
        import redis

        client = redis.Redis.from_url(url, socket_connect_timeout=0.4)
        client.ping()
        return client
    except Exception:
        return None


def _connect(url: str) -> sqlite3.Connection | None:
    if not url.startswith("sqlite"):
        return None
    path = url.split("///")[-1]
    if path == ":memory:":
        conn = sqlite3.connect(":memory:", check_same_thread=False)
    else:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _init_sqlite(conn)
    return conn


def _init_sqlite(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS zone (
          zone_id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          lat REAL NOT NULL,
          lon REAL NOT NULL,
          pv_nameplate_kw REAL NOT NULL,
          evac_limit_frac REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS plan (
          plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL,
          zone_id TEXT NOT NULL,
          solver_status TEXT NOT NULL,
          objective REAL,
          solve_ms INTEGER,
          risk_quantile REAL NOT NULL,
          config_hash TEXT NOT NULL,
          schedule TEXT NOT NULL,
          shortfalls TEXT,
          absorbed_kwh REAL,
          fallback_reason TEXT,
          slot_start TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts TEXT NOT NULL,
          actor TEXT NOT NULL,
          action TEXT NOT NULL,
          payload TEXT
        );
        CREATE TABLE IF NOT EXISTS telemetry (
          ts TEXT NOT NULL,
          zone_id TEXT NOT NULL,
          pv_kw REAL, baseline_load_kw REAL, flex_load_kw REAL,
          curtailed_kw REAL, evac_limit_kw REAL,
          PRIMARY KEY (ts, zone_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS plan_idem ON plan(zone_id, slot_start);
        """
    )
    conn.commit()


@dataclass
class Store:
    settings: Settings
    plans: list[dict] = field(default_factory=list)
    forecasts: list[dict] = field(default_factory=list)
    telemetry: list[dict] = field(default_factory=list)
    device_state: list[dict] = field(default_factory=list)
    audit: list[dict] = field(default_factory=list)
    replay: dict[str, Any] = field(default_factory=dict)
    kpis: dict[str, Any] = field(default_factory=dict)
    conn: sqlite3.Connection | None = None

    engine: Any = None
    redis: Any = None

    def __post_init__(self) -> None:
        url = self.settings.ops.database_url
        if url.startswith("sqlite"):
            self.conn = _connect(url)
        elif url.startswith("postgres"):
            self.engine = _connect_postgres(url)
        if self.settings.ops.redis_url:
            self.redis = _connect_redis(self.settings.ops.redis_url)

    def log(self, actor: str, action: str, payload: dict) -> None:
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "actor": actor, "action": action, "payload": payload}
        self.audit.append(rec)
        if self.conn is not None:
            self.conn.execute(
                "INSERT INTO audit_log(ts, actor, action, payload) VALUES (?,?,?,?)",
                (rec["ts"], actor, action, json.dumps(payload, default=str)),
            )
            self.conn.commit()

    def add_plan(self, plan: dict) -> dict:
        plan = dict(plan)
        plan.setdefault("plan_id", len(self.plans) + 1)
        # idempotent by (zone_id, slot_start)
        key = (plan.get("zone_id"), plan.get("slot_start"))
        for i, existing in enumerate(self.plans):
            if (existing.get("zone_id"), existing.get("slot_start")) == key and key[1] is not None:
                plan["plan_id"] = existing["plan_id"]
                self.plans[i] = plan
                return plan
        self.plans.append(plan)
        if self.conn is not None:
            try:
                self.conn.execute(
                    """INSERT OR REPLACE INTO plan
                    (created_at, zone_id, solver_status, objective, solve_ms, risk_quantile,
                     config_hash, schedule, shortfalls, absorbed_kwh, fallback_reason, slot_start)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        str(plan.get("created_at")),
                        plan.get("zone_id"),
                        plan.get("solver_status"),
                        plan.get("objective"),
                        plan.get("solve_ms"),
                        plan.get("risk_quantile"),
                        plan.get("config_hash"),
                        json.dumps(plan.get("schedules"), default=str),
                        json.dumps(plan.get("unmet_kwh"), default=str),
                        plan.get("absorbed_kwh_expected"),
                        plan.get("fallback_reason"),
                        str(plan.get("slot_start")),
                    ),
                )
                self.conn.commit()
            except sqlite3.Error:
                pass
        return plan

    def latest_plan(self, zone_id: str) -> dict | None:
        for p in reversed(self.plans):
            if p.get("zone_id") == zone_id:
                return p
        return None

    def add_forecast(self, rec: dict) -> None:
        self.forecasts.append(rec)
        if self.redis is not None:
            try:
                key = f"fc:{rec.get('zone_id')}:{rec.get('target')}"
                self.redis.setex(key, 3600, json.dumps(rec, default=str))
            except Exception:
                pass

    def latest_forecast(self, zone_id: str, target: str = "surplus") -> dict | None:
        if self.redis is not None:
            try:
                raw = self.redis.get(f"fc:{zone_id}:{target}")
                if raw:
                    return json.loads(raw)
            except Exception:
                pass
        for f in reversed(self.forecasts):
            if f.get("zone_id") == zone_id and f.get("target") == target:
                return f
        return None
