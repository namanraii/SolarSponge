"""Pydantic master configuration + reproducibility hash."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class TimeCfg(BaseModel):
    slot_minutes: int = 15
    horizon_hours: int = 24
    replan_every_minutes: int = 15
    timezone_display: str = "Asia/Kolkata"
    timezone_internal: str = "UTC"

    @property
    def slots_per_day(self) -> int:
        return int(self.horizon_hours * 60 / self.slot_minutes)

    @property
    def dt_h(self) -> float:
        return self.slot_minutes / 60.0


class ZoneCfg(BaseModel):
    id: str = "zone-001"
    name: str = "zone"
    lat: float = 26.9
    lon: float = 70.9
    pv_nameplate_kw: float = 5000
    pv_tilt_deg: float = 25
    pv_azimuth_deg: float = 180
    pv_system_losses_pct: float = 14
    temp_coeff_pct_per_c: float = -0.4
    evac_limit_frac: float = 0.5
    baseline_load_kw_peak: float = 1200
    baseline_load_noise_pct: float = 5

    @property
    def evac_limit_kw(self) -> float:
        return self.pv_nameplate_kw * self.evac_limit_frac


class WeatherCfg(BaseModel):
    provider: str = "open-meteo"
    cache_ttl_minutes: int = 30
    history_years: int = 3
    variables: list[str] = Field(default_factory=lambda: ["ghi", "dni", "dhi", "temperature"])
    use_synthetic_if_offline: bool = True


class LgbmCfg(BaseModel):
    n_estimators: int = 200
    learning_rate: float = 0.05
    num_leaves: int = 31
    min_child_samples: int = 40
    subsample: float = 0.8
    colsample_bytree: float = 0.8


class BacktestCfg(BaseModel):
    train_min_days: int = 14
    test_window_days: int = 7
    step_days: int = 7


class ForecastCfg(BaseModel):
    quantiles: list[float] = Field(default_factory=lambda: [0.1, 0.5, 0.9])
    scenario_samples: int = 200
    pv_load_corr_rho: float = 0.0
    model: str = "lightgbm_quantile"
    lgbm: LgbmCfg = Field(default_factory=LgbmCfg)
    conformal_calibration: bool = True
    backtest: BacktestCfg = Field(default_factory=BacktestCfg)
    seed: int = 7


class WeightsCfg(BaseModel):
    w_switch: float = 0.5
    w_late: float = 0.0
    w_shortfall: float = 1000.0


class OptimizerCfg(BaseModel):
    solver: str = "cbc"
    time_limit_s: int = 10
    mip_gap: float = 0.01
    threads: int = 2
    warm_start: bool = True
    risk_quantile: float = 0.4
    weights: WeightsCfg = Field(default_factory=WeightsCfg)
    surplus_floor_kw: float = 30
    fallback: list[str] = Field(default_factory=lambda: ["incumbent", "greedy", "default_schedule"])


class PumpCfg(BaseModel):
    count_clusters: int = 2
    pumps_per_cluster: int = 50
    pump_kw: float = 3.7
    head_m: float = 30
    wire_to_water_eff: float = 0.45
    irrigation_eff: float = 0.7
    area_ha_per_pump: float = 2
    kc_crop_coeff: float = 1.0
    max_depletion_mm: float = 30
    allowed_window: list[str] = Field(default_factory=lambda: ["06:00", "18:00"])
    min_run_slots: int = 8
    max_starts_per_day: int = 2
    default_window: list[str] = Field(default_factory=lambda: ["06:00", "10:00"])


class ColdStoreCfg(BaseModel):
    compressor_kw: float = 200
    temp_band_c: list[float] = Field(default_factory=lambda: [2.0, 6.0])
    thermal_mass_kwh_per_c: float = 400
    ua_kw_per_c: float = 12
    cop: float = 2.5
    min_run_slots: int = 4
    max_starts_per_day: int = 6
    t_init_c: float = 4.0


class EvDepotCfg(BaseModel):
    vehicles: int = 30
    charger_kw: float = 7.4
    battery_kwh: float = 30
    arrival_soc: float = 0.3
    target_soc: float = 0.9
    departure_window: list[str] = Field(default_factory=lambda: ["05:30", "07:30"])
    charging_eff: float = 0.92
    default_window: list[str] = Field(default_factory=lambda: ["20:00", "24:00"])


class HvacCfg(BaseModel):
    flexible_kw: float = 100
    comfort_band_c: list[float] = Field(default_factory=lambda: [23.0, 26.0])
    occupancy: list[str] = Field(default_factory=lambda: ["09:00", "18:00"])
    building_tau_hours: float = 6
    t_init_c: float = 24.5
    ua_kw_per_c: float = 8
    thermal_mass_kwh_per_c: float = 80


class LoadsCfg(BaseModel):
    pump_cluster: PumpCfg = Field(default_factory=PumpCfg)
    cold_store: ColdStoreCfg = Field(default_factory=ColdStoreCfg)
    ev_depot: EvDepotCfg = Field(default_factory=EvDepotCfg)
    hvac_precool: HvacCfg = Field(default_factory=HvacCfg)


class DevicesCfg(BaseModel):
    response_delay_slots: int = 1
    noncompliance_prob: float = 0.05
    telemetry_noise_pct: float = 2


class CopilotCfg(BaseModel):
    enabled: bool = True
    model_explainer: str = "claude-haiku-4-5"
    model_whatif: str = "claude-sonnet-4-5"
    max_tool_calls: int = 6
    max_output_tokens: int = 800
    cache_by_plan_id: bool = True
    language_templates: list[str] = Field(default_factory=lambda: ["en", "hi", "ta"])


class EvaluationCfg(BaseModel):
    sim_days: int = 14
    seeds: int = 5
    bootstrap_resamples: int = 2000
    weather_classes: list[str] = Field(
        default_factory=lambda: ["clear", "partly_cloudy", "overcast", "monsoon"]
    )
    replay_days: int = 1


class EconomicsCfg(BaseModel):
    grid_emission_factor_t_per_mwh: float = 0.675
    grid_emission_factor_source: str = (
        "CEA CO2 Baseline Database v22.0, Table S, FY 2025-26 weighted average incl. RES & captive"
    )
    farmer_tariff_discount_per_kwh_inr: float = 1.0
    baseline_ag_tariff_inr_per_kwh: float = 0.0


class OpsCfg(BaseModel):
    log_level: str = "INFO"
    metrics_port: int = 9100
    audit_log: bool = True
    api_rate_limit_per_min: int = 120
    kill_switch: bool = False
    demo_mode: bool = True
    database_url: str = "sqlite:///./solarsponge.db"


class Settings(BaseModel):
    time: TimeCfg = Field(default_factory=TimeCfg)
    zone: ZoneCfg = Field(default_factory=ZoneCfg)
    weather: WeatherCfg = Field(default_factory=WeatherCfg)
    forecast: ForecastCfg = Field(default_factory=ForecastCfg)
    optimizer: OptimizerCfg = Field(default_factory=OptimizerCfg)
    loads: LoadsCfg = Field(default_factory=LoadsCfg)
    devices: DevicesCfg = Field(default_factory=DevicesCfg)
    copilot: CopilotCfg = Field(default_factory=CopilotCfg)
    evaluation: EvaluationCfg = Field(default_factory=EvaluationCfg)
    economics: EconomicsCfg = Field(default_factory=EconomicsCfg)
    ops: OpsCfg = Field(default_factory=OpsCfg)

    def config_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | Path | None = None, overlay: dict[str, Any] | None = None) -> Settings:
    if path is None:
        here = Path(__file__).resolve().parents[2]
        path = here / "config" / "default.yaml"
    data = yaml.safe_load(Path(path).read_text()) or {}
    if overlay:
        data = _deep_merge(data, overlay)
    return Settings.model_validate(data)


def load_scenario(scenario_path: str | Path, base: Settings | None = None) -> tuple[Settings, dict[str, Any]]:
    spec = yaml.safe_load(Path(scenario_path).read_text()) or {}
    overlay: dict[str, Any] = {}
    if "risk_quantile" in spec:
        overlay["optimizer"] = {"risk_quantile": spec["risk_quantile"]}
    settings = load_config(overlay=overlay) if base is None else base.model_copy(deep=True)
    if overlay:
        settings = Settings.model_validate(_deep_merge(settings.model_dump(), overlay))
    return settings, spec
