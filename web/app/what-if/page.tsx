"use client";
import { useState } from "react";
import { runScenario } from "@/lib/api";
import { useReplay } from "@/components/ReplayContext";
import { Card, Loading, PageHeader } from "@/components/Ui";

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
  if (!data) return <Loading />;
  return (
    <div className="space-y-6">
      <PageHeader kicker="Sandbox" title="Sandboxed what-if">
        Runs a new plan. Does not dispatch. Compare KPIs against the live replay.
      </PageHeader>
      <div className="grid md:grid-cols-2 gap-6">
        <Card className="p-5 space-y-4">
          <label className="block">
            <span className="text-sm text-muted">Cloud delta {cloud}%</span>
            <input type="range" min={-30} max={40} value={cloud} onChange={(e) => setCloud(Number(e.target.value))} className="w-full mt-2" />
          </label>
          <label className="block">
            <span className="text-sm text-muted">Risk quantile {risk.toFixed(2)} (lower = more conservative)</span>
            <input
              type="range"
              min={10}
              max={90}
              value={risk * 100}
              onChange={(e) => setRisk(Number(e.target.value) / 100)}
              className="w-full mt-2"
            />
          </label>
          <div>
            <div className="text-sm text-muted mb-2">Disable a load</div>
            <div className="flex flex-wrap gap-2">
              {loads.map((s: any) => (
                <button
                  key={s.load_id}
                  onClick={() =>
                    setDisabled((d) => (d.includes(s.load_id) ? d.filter((x) => x !== s.load_id) : [...d, s.load_id]))
                  }
                  className={`px-3 py-1 rounded-full text-sm ${
                    disabled.includes(s.load_id) ? "bg-terracotta text-cream" : "bg-sand text-ink"
                  }`}
                >
                  {s.name}
                </button>
              ))}
            </div>
          </div>
          <button onClick={go} disabled={busy} className="bg-gold text-cream font-semibold px-4 py-2 rounded-full">
            {busy ? "Solving…" : "Re-plan (sandbox)"}
          </button>
        </Card>
        <Card className="p-5">
          {!result ? (
            <p className="text-muted">No sandbox run yet.</p>
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
        </Card>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-muted">{k}</dt>
      <dd className="font-medium">{v}</dd>
    </div>
  );
}
