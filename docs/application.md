# Application write-up (300–500 words)

Challenge: **Grid Reliability**.

**SolarSponge: Turning Curtailed Solar into Productive Demand**

**The problem.** India is adding solar faster than the grid can absorb it. In April–June 2026 alone, about 8.1 TWh of solar generation was curtailed, roughly the annual electricity use of 1.4 million households. As of May 2026, only 33% of recently commissioned renewable capacity was being evacuated under temporary network access, with curtailment of 50–60% during solar hours. Clean energy is being wasted precisely when it is most abundant, which hurts developers' returns, slows the energy transition, and keeps coal plants running.

**Why it matters.** At the same time, large flexible loads run on schedules unrelated to the sun. Grid-connected agricultural pumps alone consume over 18% of India's electricity, and cold storage, EV depots, and commercial cooling can also shift timing without harming users. The missing piece is a coordination layer that tells flexible demand where and when surplus clean power will appear.

**Proposed solution.** SolarSponge is a software platform for DISCOMs and aggregators with four steps:
1. **Forecast:** probabilistic 24-hour forecasts of surplus solar at substation level, using weather forecasts and historical patterns, with calibrated uncertainty bands.
2. **Optimize:** a constraint-based scheduler moves flexible loads into forecast surplus windows while treating real-world needs as hard limits: a farmer's irrigation requirement, a cold room's temperature band, an EV's departure time.
3. **Dispatch:** simple signals, such as regional-language voice or WhatsApp messages for farmers and API signals for commercial loads.
4. **Verify and re-plan:** every 15 minutes, comparing forecast with reality.

**What is innovative.** First, it closes the loop from forecast to action instead of stopping at prediction. Second, it is locality-aware, because curtailment happens at specific nodes and shifting load elsewhere does not help. Third, it plans under uncertainty, scheduling against risk-adjusted forecasts and re-planning continuously. Fourth, safety-critical decisions come from a verifiable optimizer, while an AI copilot explains plans, answers what-if questions, and drafts user messages without controlling devices. A two-tier design scales from individually controlled devices to aggregated clusters of thousands of pumps.

**Expected impact and beneficiaries.** We will validate SolarSponge on a calibrated simulation of a curtailment zone, measuring curtailed energy avoided, CO₂ avoided, constraint violations (target: zero), and farmer cost savings. Beneficiaries include renewable developers (less curtailment), DISCOMs and grid operators (better midday balance without new infrastructure), farmers and cold-chain operators (cheaper power in return for flexibility), and the public (lower emissions). Because it needs software and incentives rather than new steel, it can be piloted quickly and complements batteries and transmission rather than competing with them.
