"use client";
import { useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useReplay } from "@/components/ReplayContext";

export default function Overview() {
  const { data, error } = useReplay();
  const [sponge, setSponge] = useState(true);
  const [slot, setSlot] = useState(48);

  const chart = useMemo(() => {
    if (!data) return [];
    return (data.labels as string[]).map((label: string, i: number) => ({
      t: label,
      pv: data.pv_kw[i],
      load: data.baseline_load_kw[i],
      evac: data.evac_limit_kw[i],
      curtailed: sponge ? data.curtailed_sx_kw[i] : data.curtailed_s0_kw[i],
      flex: sponge ? data.flex_sx_kw[i] : data.flex_s0_kw[i],
    }));
  }, [data, sponge]);

  if (error) {
    return (
      <p className="text-waste">
        API not reachable at {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}. Start the backend with{" "}
        <code>python -m solarsponge.cli serve</code>.
      </p>
    );
  }
  if (!data) return <p className="text-white/60">Loading replay…</p>;

  const k = data.kpis;
  const shown = chart[Math.min(slot, chart.length - 1)];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl text-gold">The midday dump</h1>
          <p className="text-white/70 max-w-2xl mt-2">
            {data.zone.name}. Weather class <span className="text-gold">{data.weather_class}</span>. Toggle SolarSponge to
            see curtailed energy shrink when flexible loads move into the surplus window.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-white/60">Baseline</span>
          <button
            onClick={() => setSponge((v) => !v)}
            className={`w-14 h-8 rounded-full relative ${sponge ? "bg-sponge" : "bg-waste"}`}
            aria-pressed={sponge}
          >
            <span className={`absolute top-1 h-6 w-6 rounded-full bg-white transition ${sponge ? "right-1" : "left-1"}`} />
          </button>
          <span className="text-sm text-white/60">SolarSponge</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Curtailment avoided" value={`${k.curtailment_avoided_kwh.toFixed(0)} kWh`} sub={`${k.curtailment_avoided_pct.toFixed(1)}%`} />
        <Stat label="CO₂ avoided" value={`${k.co2_avoided_t.toFixed(2)} t`} sub="CEA v22.0 · 0.675 t/MWh" />
        <Stat
          label="Constraint violations"
          value={String(k.constraint_violations)}
          sub={k.constraint_violations === 0 ? "hard limits held" : "review plan"}
          good={k.constraint_violations === 0}
        />
        <Stat label="Solve time" value={`${k.solve_ms} ms`} sub={data.plan.solver_status} />
      </div>

      <div className="bg-panel rounded-2xl p-4 border border-white/10">
        <p className="chart-summary">
          Chart of PV generation, local load, evacuation limit, and curtailed energy across 96 fifteen-minute slots.
        </p>
        <div className="h-80">
          <ResponsiveContainer>
            <ComposedChart data={chart}>
              <CartesianGrid stroke="#ffffff14" />
              <XAxis dataKey="t" tick={{ fill: "#9aa3b5", fontSize: 11 }} interval={7} />
              <YAxis tick={{ fill: "#9aa3b5", fontSize: 11 }} unit=" kW" />
              <Tooltip contentStyle={{ background: "#141c2e", border: "1px solid #ffffff22" }} />
              <Area dataKey="curtailed" name="Curtailed" stroke="#f97316" fill="#f9731688" />
              <Line dataKey="pv" name="PV" stroke="#e8b86d" dot={false} strokeWidth={2} />
              <Line dataKey="load" name="Baseline load" stroke="#7dd3fc" dot={false} />
              <Line dataKey="evac" name="Evacuation limit" stroke="#94a3b8" dot={false} strokeDasharray="4 4" />
              <Line dataKey="flex" name="Flexible load" stroke="#2dd4bf" dot={false} strokeWidth={2} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <input
            type="range"
            min={0}
            max={chart.length - 1}
            value={slot}
            onChange={(e) => setSlot(Number(e.target.value))}
            className="flex-1"
            aria-label="Replay slot"
          />
          <span className="text-sm text-gold w-28">{shown?.t}</span>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, sub, good }: { label: string; value: string; sub: string; good?: boolean }) {
  return (
    <div className="bg-panel rounded-xl p-4 border border-white/10">
      <div className="text-xs uppercase tracking-wide text-white/50">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${good ? "text-sponge" : "text-white"}`}>{value}</div>
      <div className="text-xs text-white/50 mt-1">{sub}</div>
    </div>
  );
}
