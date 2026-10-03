# Three-minute demo script

Backup: `artifacts/replay.json` is deterministic for a given config hash. The dashboard needs no live weather API.

| Time | Action |
|---|---|
| 0:00 | Overview, baseline mode: curtailed energy shaded orange |
| 0:30 | Toggle SolarSponge on: orange shrinks; KPIs update |
| 1:00 | Schedule: pump clusters and cold store in the surplus window; **violations: 0** |
| 1:30 | What-if: cloud +20%; sandbox re-plan; `dispatched: false` |
| 2:00 | Copilot: "Why did pump cluster B start when it did?" Grounded in plan_id |
| 2:30 | Farmer view: Hindi/Tamil/English notice |
| 2:50 | KPIs: CEA 0.675 t/MWh, config hash, honest "one-zone twin" caveat |

Do not quote the toy reference-scheduler absorption percentage. That run is a formulation check on synthetic surplus, not a result.
