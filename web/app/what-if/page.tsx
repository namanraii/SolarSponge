"use client";
import { useState } from "react";
import { runScenario } from "@/lib/api";
import { useReplay } from "@/components/ReplayContext";

export default function WhatIf() {
  const { data } = useReplay();
  const [cloud, setCloud] = useState(0);
  const [risk, setRisk] = useState(0.4);
  const [disabled, setDisabled] = useState<string[]>([]);
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  async function go() {
    setBusy(true);
    try {
      const r = await runScenario("zone-001", {
        cloud_delta_pct: cloud,
        risk_quantile: risk,
        disabled_load_ids: disabled,
      });
      setResult(r);
    } finally {
      setBusy(false);
    }
  }

  const loads = data?.schedules || [];
  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl text-gold">Sandboxed what-if</h1>
      <p className="text-white/60">Runs a new plan. Does not dispatch. Compare KPIs against the live replay.</p>
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-panel rounded-2xl p-5 border border-white/10 space-y-4">
          <label className="block">
            <span className="text-sm text-white/60">Cloud delta {cloud}%</span>
            <input type="range" min={-30} max={40} value={cloud} onChange={(e) => setCloud(Number(e.target.value))} className="w-full" />
          </label>
          <label className="block">
            <span className="text-sm text-white/60">Risk quantile {risk.toFixed(2)} (lower = more conservative)</span>
            <input
              type="range"
              min={10}
              max={90}
              value={risk * 100}
              onChange={(e) => setRisk(Number(e.target.value) / 100)}
              className="w-full"
            />
          </label>
          <div>
            <div className="text-sm text-white/60 mb-2">Disable a load</div>
            <div className="flex flex-wrap gap-2">
              {loads.map((s: any) => (
                <button
                  key={s.load_id}
                  onClick={() =>
                    setDisabled((d) => (d.includes(s.load_id) ? d.filter((x) => x !== s.load_id) : [...d, s.load_id]))
                  }
                  className={`px-3 py-1 rounded-full text-sm ${
                    disabled.includes(s.load_id) ? "bg-waste text-ink" : "bg-white/10"
                  }`}
                >
                  {s.name}
                </button>
              ))}
            </div>
          </div>
          <button onClick={go} disabled={busy} className="bg-gold text-ink font-semibold px-4 py-2 rounded-full">
            {busy ? "Solving…" : "Re-plan (sandbox)"}
          </button>
        </div>
        <div className="bg-panel rounded-2xl p-5 border border-white/10">
          {!result ? (
            <p className="text-white/50">No sandbox run yet.</p>
          ) : (
            <dl className="space-y-2 text-sm">
              <Row k="Dispatched?" v={String(result.dispatched)} />
              <Row k="Solver" v={result.solver_status} />
              <Row k="Absorbed kWh" v={result.kpis.absorbed_kwh.toFixed(0)} />
              <Row k="Curtailment avoided kWh" v={result.kpis.curtailment_avoided_kwh.toFixed(0)} />
              <Row k="CO₂ t" v={result.kpis.co2_avoided_t.toFixed(3)} />
              <Row k="Violations" v={String(result.kpis.constraint_violations)} />
            </dl>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-white/50">{k}</dt>
      <dd>{v}</dd>
    </div>
  );
}
