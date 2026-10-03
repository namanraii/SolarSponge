"use client";
import { useReplay } from "@/components/ReplayContext";

export default function KpisPage() {
  const { data } = useReplay();
  if (!data) return <p>Loading…</p>;
  const k = data.kpis;
  const rows = [
    ["Curtailment avoided", `${k.curtailment_avoided_kwh.toFixed(0)} kWh (${k.curtailment_avoided_pct.toFixed(1)}%)`],
    ["Absorbed surplus", `${k.absorbed_kwh.toFixed(0)} kWh`],
    ["Absorption efficiency", k.absorption_efficiency.toFixed(3)],
    ["Wasted load (ran with no surplus)", `${k.wasted_load_kwh.toFixed(0)} kWh`],
    ["CO₂ avoided", `${k.co2_avoided_t.toFixed(3)} t`],
    ["Emission factor", `${data.emission_factor_t_per_mwh} t/MWh`],
    ["Factor source", data.emission_factor_source],
    ["Farmer incentive (scenario)", `₹${k.farmer_saving_inr.toFixed(0)}`],
    ["Hard constraint violations", String(k.constraint_violations)],
    ["Solve time", `${k.solve_ms} ms`],
    ["Fallback used", String(k.fallback)],
    ["Config hash", data.config_hash],
  ];
  return (
    <div className="space-y-4">
      <h1 className="font-display text-3xl text-gold">Impact on this simulated day</h1>
      <p className="text-white/60 max-w-2xl">
        Digital twin, one curtailment zone. These are not national-scale results. CO₂ uses the official CEA FY 2025-26
        weighted-average grid factor, not a placeholder.
      </p>
      <div className="bg-panel rounded-2xl border border-white/10 divide-y divide-white/10">
        {rows.map(([l, v]) => (
          <div key={l} className="flex justify-between gap-4 px-4 py-3 text-sm">
            <span className="text-white/60">{l}</span>
            <span className="text-right">{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
