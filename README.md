# SolarSponge

Turning curtailed solar into productive demand.

A DISCOM/aggregator control loop: **forecast surplus → constraint-safe MILP → dispatch adapter → verify every 15 minutes**. An LLM copilot explains plans and runs sandboxed what-ifs. It never commands a load.

This is a **calibrated digital twin of one curtailment zone**, not a live grid. Feeder-level telemetry is not public. Impact numbers from this repo are simulation results.

## What is built

| Piece | Status |
|---|---|
| Digital twin (PV, 4 feeders-worth of baseline load, 4 flex classes) | Built |
| Weather (Open-Meteo + synthetic fallback) | Built |
| Forecast baselines B0/B1 + quantile model (LightGBM if installed, else slot-of-day empirical) | Built |
| Surplus quantiles via joint PV–load scenarios | Built |
| MILP scheduler with energy slack, thermal / soil / SoC constraints, warm start | Built |
| Fallbacks: incumbent → greedy → default farmer schedule | Built |
| Simulated dispatch (delay, non-compliance) + kill switch | Built |
| FastAPI + WebSocket replay | Built |
| Copilot with read-only tools and actuation refusal | Built |
| Next.js dashboard (overview, schedule, forecast, KPIs, what-if, copilot, farmer) | Built |
| Evaluation S0–S5 + bootstrap CIs | Built |
| Rolling 15-min re-plan, warm start, APScheduler tick (`--tick`) | Built |
| Forecast persist, parquet feature store, leakage guard, backtest artifact | Built |
| Postgres/Redis/Timescale + Grafana in Compose (SQLite fallback) | Built |
| Copilot tool-calling loop, 30-question golden set, plan_id cache | Built |
| Dashboard play/pause/speed, offline `public/replay.json`, kill switch | Built |
| API key (`X-API-Key`) + per-IP rate limit | Built |
| Virtual-battery path, MQTT/OpenADR/WhatsApp/IEX stubs, neighbor blend | Built |

**Not a field result.** A toy run of the reference scheduler on synthetic surplus is mechanically useful and must not appear in the pitch.

## Version pin

`pulp==2.9.0`. PuLP 4.x changed `LpVariable` and the scheduler fails. CI asserts the pin.

PuLP 2.9 ships an **x86_64** CBC binary. On Apple Silicon the solver layer catches that `OSError` and uses **HiGHS** (`highspy`). Linux CI uses bundled CBC. A `cbc` binary on `PATH` always wins.

## Emission factor

CO₂ avoided uses **0.675 tCO₂/MWh**, the Central Electricity Authority *CO₂ Baseline Database for the Indian Power Sector*, Version **22.0** (August 2026), Table S: weighted-average Indian grid factor for FY 2025-26, including RES and captive injection, adjusted for cross-border transfers. Combined margin in that table is 0.705 tCO₂/MWh. Change `economics.grid_emission_factor_t_per_mwh` in `config/default.yaml` if you need a different CEA series.

## Quick start

```bash
cd solarsponge
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make test
make demo          # writes artifacts/replay.json
make serve         # API on :8000  (first request trains the twin, ~15–40s)
```

Dashboard:

```bash
cd web
npm install
npm run dev        # :3000, talks to :8000
```

One-command stack: `docker compose up --build`.

```bash
python -m solarsponge.cli eval --quick --out artifacts   # 8 days × 3 seeds
python -m solarsponge.cli eval --full --out artifacts    # 30 days × 20 seeds
python -m solarsponge.cli backtest
python -m solarsponge.cli serve --tick   # APScheduler re-plans on the configured interval
```

`make eval` regenerates tables from config + seed. Every plan stores `config_hash`.

## Architecture

```
weather / telemetry → ingest → forecast (p10/p50/p90)
                                 ↓
                         surplus at the node
                                 ↓
                    optimizer (MILP, then fallbacks)
                                 ↓
                    dispatch gateway → device sim
                                 ↓
                         15-minute re-plan
```

Copilot tools: `get_plan`, `get_forecast`, `get_kpis`, `diff_plans`, `get_load_info`, `run_scenario` (sandbox, `dispatched: false`).

## Config

Single file: `config/default.yaml`, validated by Pydantic. Sweep ranges are in comments. Scenarios S0–S5 live in `config/scenarios/`.

## Honest limits

- One zone, synthetic feeder data, simulated devices.
- Load parameters (pump head, thermal mass, SoC, tariffs) are placeholders until calibrated.
- National 8.1 TWh curtailment is context, not a claim that SolarSponge absorbs it.
- Real deployment needs DISCOM/regulator cooperation and an incentive tariff.

## License

Hackathon prototype. Team: fill in before submission.
