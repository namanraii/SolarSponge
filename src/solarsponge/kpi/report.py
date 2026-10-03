"""Evaluation driver: S0–S5 on simulated days, plus sensitivity sweeps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from solarsponge.config import Settings, load_config
from solarsponge.forecasting.service import ForecastService, build_history
from solarsponge.kpi.metrics import bootstrap_ci, compute_day_kpis
from solarsponge.optimizer.service import plan_day, risk_surplus
from solarsponge.twin.simulator import apply_schedule, simulate_day
from solarsponge.twin.surplus import curtailed_kw
from solarsponge.optimizer.heuristic import default_schedule, naive_noon_schedule
from solarsponge.optimizer.validate import validate_plan


def _run_one(settings: Settings, twin, fc, spec: dict) -> dict:
    dt = settings.time.dt_h
    T = len(twin.surplus_kw)
    on_default = default_schedule(twin.loads, T)
    s0 = apply_schedule(twin, on_default, settings)

    if spec.get("optimizer_disabled") and spec.get("naive_noon"):
        on = naive_noon_schedule(twin.loads, T, dt)
        reason = "naive"
        status = "Fallback"
        solve_ms = 0
    elif spec.get("optimizer_disabled"):
        on = on_default
        reason = "baseline"
        status = "Fallback"
        solve_ms = 0
    else:
        if spec.get("oracle"):
            surplus = twin.surplus_kw
        else:
            q = spec.get("risk_quantile", settings.optimizer.risk_quantile)
            surplus = risk_surplus(fc.surplus, q)
            surplus[surplus < settings.optimizer.surplus_floor_kw] = 0.0
        result = plan_day(
            surplus,
            twin.loads,
            settings,
            force_fallback=spec.get("force_fallback"),
            naive_noon=spec.get("naive_noon", False),
            optimizer_disabled=False,
        )
        on = result["on"]
        reason = result.get("fallback_reason")
        status = result["status"]
        solve_ms = result["solve_ms"]

    sx = apply_schedule(twin, on, settings)
    val = validate_plan(twin.surplus_kw, twin.loads, on, float(sx["absorbed_kw"].sum() * dt), dt)
    violations = 0 if val.window_ok and val.min_run_ok and val.max_starts_ok else 1
    shiftable = sum(L.energy_kwh for L in twin.loads)
    kpis = compute_day_kpis(
        settings,
        twin.surplus_kw,
        s0["curtailed_kw"],
        sx["curtailed_kw"],
        sx["flex_load_kw"],
        sx["absorbed_kw"],
        shiftable,
        violations,
        solve_ms,
        status == "Fallback",
        twin.weather_class,
    )
    return {
        "status": status,
        "fallback_reason": reason,
        "kpis": kpis.__dict__,
        "on": on,
        "s0": {k: v.tolist() for k, v in s0.items()},
        "sx": {k: v.tolist() for k, v in sx.items()},
        "validation_notes": val.notes,
    }


def _summarize(settings: Settings, specs: list[dict], by_scenario: dict[str, list]) -> dict:
    summary = {}
    for sid, rows in by_scenario.items():
        absorbed = [r["kpis"]["absorbed_kwh"] for r in rows]
        avoided = [r["kpis"]["curtailment_avoided_kwh"] for r in rows]
        co2 = [r["kpis"]["co2_avoided_t"] for r in rows]
        viol = sum(r["kpis"]["constraint_violations"] for r in rows)
        mean_a, lo_a, hi_a = bootstrap_ci(absorbed, settings.evaluation.bootstrap_resamples, settings.forecast.seed)
        mean_v, lo_v, hi_v = bootstrap_ci(avoided, settings.evaluation.bootstrap_resamples, settings.forecast.seed)
        by_wx: dict[str, list] = {}
        for r in rows:
            by_wx.setdefault(r.get("weather_class") or "unknown", []).append(r["kpis"]["absorbed_kwh"])
        wx = {k: float(np.mean(v)) for k, v in by_wx.items()}
        summary[sid] = {
            "name": next(s["name"] for s in specs if s["scenario_id"] == sid),
            "absorbed_kwh_mean": mean_a,
            "absorbed_kwh_ci95": [lo_a, hi_a],
            "curtailment_avoided_kwh_mean": mean_v,
            "curtailment_avoided_kwh_ci95": [lo_v, hi_v],
            "co2_avoided_t_mean": float(np.mean(co2)),
            "hard_constraint_violations": viol,
            "n_days": len(rows),
            "by_weather_class": wx,
        }
    if "S1" in summary and "S2" in summary and summary["S1"]["absorbed_kwh_mean"]:
        summary["S2"]["capture_ratio_vs_oracle"] = (
            summary["S2"]["absorbed_kwh_mean"] / summary["S1"]["absorbed_kwh_mean"]
        )
    return summary


def run_evaluation(
    settings: Settings | None = None,
    n_days: int | None = None,
    n_seeds: int | None = None,
    full: bool = False,
    quick: bool = True,
    ablations: bool = True,
    sensitivity: bool = True,
) -> dict:
    settings = settings or load_config()
    ev = settings.evaluation
    if full:
        n_days = n_days or ev.full_days
        n_seeds = n_seeds or ev.full_seeds
        quick = False
    elif quick:
        n_days = n_days or ev.quick_days
        n_seeds = n_seeds or ev.quick_seeds
    else:
        n_days = n_days or ev.sim_days
        n_seeds = n_seeds or ev.seeds

    history = build_history(settings, max(n_days + 2, settings.forecast.backtest.train_min_days + n_days))
    train = history[: settings.forecast.backtest.train_min_days]
    test = history[-n_days:]
    fc_svc = ForecastService(settings)
    fc_svc.fit_from_history(train)

    scenario_dir = Path(__file__).resolve().parents[3] / "config" / "scenarios"
    specs = [yaml.safe_load(p.read_text()) for p in sorted(scenario_dir.glob("s*.yaml"))]

    by_scenario: dict[str, list] = {}
    for spec in specs:
        sid = spec["scenario_id"]
        by_scenario[sid] = []
        for seed in range(n_seeds):
            for i, twin in enumerate(test):
                fc = fc_svc.predict_day(twin, oracle=bool(spec.get("oracle")))
                rec = _run_one(settings, twin, fc, spec)
                rec["day_index"] = i
                rec["seed"] = seed
                rec["weather_class"] = twin.weather_class
                by_scenario[sid].append(rec)

    summary = _summarize(settings, specs, by_scenario)
    result = {
        "config_hash": settings.config_hash(),
        "mode": "full" if full else "quick" if quick else "custom",
        "n_days": n_days,
        "n_seeds": n_seeds,
        "emission_factor_t_per_mwh": settings.economics.grid_emission_factor_t_per_mwh,
        "emission_factor_source": settings.economics.grid_emission_factor_source,
        "summary": summary,
        "by_scenario": {
            sid: [{k: v for k, v in r.items() if k not in {"on", "s0", "sx"}} for r in rows]
            for sid, rows in by_scenario.items()
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if ablations:
        result["ablations"] = _ablations(settings, test[: min(3, len(test))], fc_svc)
    if sensitivity:
        result["sensitivity"] = _sensitivity(settings, test[: min(2, len(test))], fc_svc)
    return result


def _ablations(settings: Settings, days, fc_svc: ForecastService) -> dict:
    out = {}
    spec = {"scenario_id": "S3", "risk_quantile": settings.optimizer.risk_quantile}
    variants = {
        "risk_milp": {},
        "greedy": {"force_fallback": "greedy"},
        "p50": {"risk_quantile": 0.5},
        "oracle": {"oracle": True},
        "virtual_battery": {"virtual_battery": True},
    }
    for name, extra in variants.items():
        s = settings.model_copy(deep=True)
        if extra.get("virtual_battery"):
            s.optimizer.use_virtual_battery = True
        rows = []
        for twin in days:
            fc = fc_svc.predict_day(twin, oracle=bool(extra.get("oracle")))
            rec = _run_one(s, twin, fc, {**spec, **extra})
            rows.append(rec["kpis"]["absorbed_kwh"])
        out[name] = {"absorbed_kwh_mean": float(np.mean(rows) if rows else 0), "n": len(rows)}
    if out.get("oracle", {}).get("absorbed_kwh_mean"):
        out["risk_milp"]["capture_ratio_vs_oracle"] = out["risk_milp"]["absorbed_kwh_mean"] / out["oracle"]["absorbed_kwh_mean"]
    return out


def _sensitivity(settings: Settings, days, fc_svc: ForecastService) -> dict:
    spec = {"risk_quantile": settings.optimizer.risk_quantile}
    table = {"evac_limit_frac": [], "risk_quantile": []}
    for frac in (0.30, 0.35, 0.50, 0.70):
        s = settings.model_copy(deep=True)
        s.zone.evac_limit_frac = frac
        absorbed = []
        for twin in days:
            from solarsponge.twin.simulator import simulate_day

            t2 = simulate_day(s, twin.day_start, day_index=0)
            fc = fc_svc.predict_day(t2)
            rec = _run_one(s, t2, fc, spec)
            absorbed.append(rec["kpis"]["absorbed_kwh"])
        table["evac_limit_frac"].append({"frac": frac, "absorbed_kwh_mean": float(np.mean(absorbed) if absorbed else 0)})
    for q in (0.1, 0.4, 0.7):
        absorbed = []
        for twin in days:
            fc = fc_svc.predict_day(twin)
            rec = _run_one(settings, twin, fc, {"risk_quantile": q})
            absorbed.append(rec["kpis"]["absorbed_kwh"])
        table["risk_quantile"].append({"q": q, "absorbed_kwh_mean": float(np.mean(absorbed) if absorbed else 0)})
    return table


def write_report(result: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "eval.json"
    json_path.write_text(json.dumps(result, indent=2, default=str))
    md = ["# SolarSponge evaluation\n"]
    md.append(f"Config hash `{result['config_hash']}`\n")
    md.append(
        f"CO₂ factor: **{result['emission_factor_t_per_mwh']} t/MWh** "
        f"({result['emission_factor_source']})\n"
    )
    md.append("| Scenario | Absorbed kWh (mean) | Curtailment avoided kWh | CO₂ t | Violations |")
    md.append("|---|---:|---:|---:|---:|")
    for sid, s in result["summary"].items():
        md.append(
            f"| {sid} {s['name']} | {s['absorbed_kwh_mean']:.0f} | "
            f"{s['curtailment_avoided_kwh_mean']:.0f} | {s['co2_avoided_t_mean']:.2f} | "
            f"{s['hard_constraint_violations']} |"
        )
    md.append(
        "\nThese figures are from a calibrated digital twin, not a real feeder. "
        "Do not quote toy single-day scheduler results as field performance.\n"
    )
    md.append(f"\nMode `{result.get('mode')}` · days {result.get('n_days')} · seeds {result.get('n_seeds')}\n")
    if result.get("ablations"):
        md.append("## Ablations\n")
        md.append("| Variant | Absorbed kWh mean |")
        md.append("|---|---:|")
        for k, v in result["ablations"].items():
            extra = ""
            if "capture_ratio_vs_oracle" in v:
                extra = f" (capture {v['capture_ratio_vs_oracle']:.2f} vs oracle)"
            md.append(f"| {k} | {v['absorbed_kwh_mean']:.0f}{extra} |")
    if result.get("sensitivity"):
        md.append("\n## Sensitivity\n")
        md.append("Evacuation limit fraction:")
        for row in result["sensitivity"].get("evac_limit_frac", []):
            md.append(f"- {row['frac']}: {row['absorbed_kwh_mean']:.0f} kWh")
        md.append("Risk quantile:")
        for row in result["sensitivity"].get("risk_quantile", []):
            md.append(f"- q={row['q']}: {row['absorbed_kwh_mean']:.0f} kWh")
    (out_dir / "eval.md").write_text("\n".join(md))
    return json_path
