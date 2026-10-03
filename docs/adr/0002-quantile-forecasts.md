# ADR 2 — Quantile forecasts, not point forecasts

Status: accepted

Curtailment windows are uncertain. Planning against p50 alone over-commits load. The MVP interpolates p10/p50/p90 to a `risk_quantile` (default 0.4). Surplus quantiles are taken from joint PV–load scenario samples, because `p10(pv) − p90(load)` is not `p10(surplus)`.
