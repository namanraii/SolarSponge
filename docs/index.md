# SolarSponge

Forecast surplus solar at a node, schedule flexible loads into that window, dispatch through an adapter, and re-plan every 15 minutes. The optimizer is the only thing that may command a load. The copilot explains.

This repository is the MVP described in the implementation blueprint. The digital twin is calibrated to public curtailment reports; it is not a real feeder.

## Emission factor

`economics.grid_emission_factor_t_per_mwh` is **0.675 tCO2/MWh**, the CEA CO2 Baseline Database Version 22.0 (August 2026) weighted-average Indian grid factor for FY 2025-26, including RES and captive injection, adjusted for cross-border transfers (User Guide Table S). Combined margin in the same table is 0.705; operating margin is 0.963. Impact math uses the weighted average unless you change config.
