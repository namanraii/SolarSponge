# SolarSponge evaluation

Config hash `5d0394443738b54a`

CO₂ factor: **0.675 t/MWh** (CEA CO2 Baseline Database v22.0, Table S, FY 2025-26 weighted average incl. RES & captive)

| Scenario | Absorbed kWh (mean) | Curtailment avoided kWh | CO₂ t | Violations |
|---|---:|---:|---:|---:|
| S0 baseline | 0 | 0 | 0.00 | 2 |
| S1 oracle | 0 | 0 | 0.00 | 0 |
| S2 solarsponge_p50 | 0 | 0 | 0.00 | 0 |
| S3 solarsponge_risk_aware | 0 | 0 | 0.00 | 0 |
| S4 greedy_heuristic | 0 | 0 | 0.00 | 2 |
| S5 naive_noon_shift | 0 | 0 | 0.00 | 0 |

These figures are from a calibrated digital twin, not a real feeder. Do not quote toy single-day scheduler results as field performance.


Mode `quick` · days 2 · seeds 1

## Ablations

| Variant | Absorbed kWh mean |
|---|---:|
| risk_milp | 0 |
| greedy | 0 |
| p50 | 0 |
| oracle | 0 |
| virtual_battery | 0 |

## Sensitivity

Evacuation limit fraction:
- 0.3: 2507 kWh
- 0.35: 2128 kWh
- 0.5: 889 kWh
- 0.7: 0 kWh
Risk quantile:
- q=0.1: 0 kWh
- q=0.4: 0 kWh
- q=0.7: 0 kWh