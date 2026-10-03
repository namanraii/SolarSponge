# ADR 1 — Optimizer, not RL, drives actions

Status: accepted

The control action is a mixed-integer schedule with hard windows, min-run, start limits, thermal bands, soil deficit, and SoC. Those are naturally MILP constraints. RL would need a safety layer that re-implements the same constraints. The LLM is outside the loop and may only call read-only tools plus a sandboxed what-if.
