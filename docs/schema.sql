-- TimescaleDB schema from the blueprint. SQLite used in local demo omits hypertables.

CREATE TABLE zone (
  zone_id          TEXT PRIMARY KEY,
  name             TEXT NOT NULL,
  lat              DOUBLE PRECISION NOT NULL,
  lon              DOUBLE PRECISION NOT NULL,
  pv_nameplate_kw  DOUBLE PRECISION NOT NULL,
  evac_limit_frac  DOUBLE PRECISION NOT NULL CHECK (evac_limit_frac BETWEEN 0 AND 1)
);

CREATE TABLE flex_load (
  load_id        TEXT PRIMARY KEY,
  zone_id        TEXT NOT NULL REFERENCES zone(zone_id),
  kind           TEXT NOT NULL CHECK (kind IN ('pump','cold_store','ev_depot','hvac')),
  power_kw       DOUBLE PRECISION NOT NULL,
  params         JSONB NOT NULL,
  enabled        BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE weather (
  ts TIMESTAMPTZ NOT NULL, zone_id TEXT NOT NULL,
  ghi_wm2 REAL, dni_wm2 REAL, dhi_wm2 REAL, temp_c REAL, cloud_pct REAL,
  wind_ms REAL, et0_mm REAL, issued_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (ts, zone_id, issued_at)
);

CREATE TABLE telemetry (
  ts TIMESTAMPTZ NOT NULL, zone_id TEXT NOT NULL,
  pv_kw REAL, baseline_load_kw REAL, flex_load_kw REAL,
  curtailed_kw REAL, evac_limit_kw REAL,
  PRIMARY KEY (ts, zone_id)
);

CREATE TABLE device_state (
  ts TIMESTAMPTZ NOT NULL, load_id TEXT NOT NULL,
  commanded_on BOOLEAN, actual_on BOOLEAN, power_kw REAL,
  state JSONB,
  PRIMARY KEY (ts, load_id)
);

CREATE TABLE forecast (
  issued_at TIMESTAMPTZ NOT NULL, ts TIMESTAMPTZ NOT NULL, zone_id TEXT NOT NULL,
  target TEXT NOT NULL CHECK (target IN ('pv','load','surplus')),
  p10 REAL, p50 REAL, p90 REAL, model_version TEXT NOT NULL,
  PRIMARY KEY (issued_at, ts, zone_id, target)
);

CREATE TABLE plan (
  plan_id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL, zone_id TEXT NOT NULL,
  solver_status TEXT NOT NULL, objective DOUBLE PRECISION, solve_ms INTEGER,
  risk_quantile REAL NOT NULL, config_hash TEXT NOT NULL,
  schedule JSONB NOT NULL,
  shortfalls JSONB
);

CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor TEXT NOT NULL, action TEXT NOT NULL, payload JSONB
);

-- SELECT create_hypertable('weather','ts');
-- SELECT create_hypertable('telemetry','ts');
-- SELECT create_hypertable('device_state','ts');
-- SELECT create_hypertable('forecast','ts');
