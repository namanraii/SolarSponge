"use client";
import { useEffect, useMemo, useState } from "react";
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
import { Card, CHART, Loading, SustainabilityStrip } from "@/components/Ui";
import { PanelArray, SolarScene } from "@/components/SolarScene";

export default function Overview() {
  const { data, error, offline } = useReplay();
  const [sponge, setSponge] = useState(true);
  const [slot, setSlot] = useState(48);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  useEffect(() => {
    if (!playing || !data) return;
    const n = (data.labels as string[]).length;
    const id = window.setInterval(() => {
      setSlot((s) => (s + 1) % n);
    }, Math.max(80, 400 / speed));
    return () => window.clearInterval(id);
  }, [playing, speed, data]);

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
      <p className="text-terracotta">
        API not reachable at {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}. Start the backend with{" "}
        <code>python -m solarsponge.cli serve</code>.
      </p>
    );
  }
  if (!data) return <Loading />;

  const k = data.kpis;
  const shown = chart[Math.min(slot, chart.length - 1)];

  return (
    <div className="space-y-8">
      <section className="grid lg:grid-cols-[1.15fr_0.85fr] gap-6 items-stretch">
        <div className="relative overflow-hidden rounded-3xl min-h-[280px] shadow-lift">
          <img
            src="/art/farm-hero.jpg"
            alt="Rajasthan solar farm at golden hour"
            className="absolute inset-0 w-full h-full object-cover scale-[1.04]"
          />
          <div className="absolute inset-0 bg-gradient-to-tr from-ink/70 via-ink/25 to-transparent" />
          <div className="relative z-10 p-7 md:p-9 max-w-xl text-cream">
            <p className="text-xs uppercase tracking-[0.24em] text-sun font-semibold">Sustainable feeder ops</p>
            <h1 className="font-display text-4xl md:text-5xl mt-3 leading-tight">The midday dump</h1>
            <p className="mt-3 text-cream/90 leading-relaxed">
              {data.zone.name}. Weather class <span className="text-sun font-semibold">{data.weather_class}</span>.
              Toggle SolarSponge to see curtailed energy shrink when flexible loads move into the surplus window.
            </p>
          </div>
        </div>
        <div className="space-y-4">
          <SolarScene />
          <Card className="p-4 flex items-center justify-between gap-3">
            <span className="text-sm text-muted">Baseline</span>
            <button
              onClick={() => setSponge((v) => !v)}
              className={`w-14 h-8 rounded-full relative transition ${sponge ? "bg-leaf" : "bg-terracotta"}`}
              aria-pressed={sponge}
              aria-label="SolarSponge mode"
            >
              <span className={`absolute top-1 h-6 w-6 rounded-full bg-cream shadow transition ${sponge ? "right-1" : "left-1"}`} />
            </button>
            <span className="text-sm font-semibold text-ink">SolarSponge</span>
          </Card>
        </div>
      </section>

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

      <Card className="p-4 md:p-5">
        <p className="chart-summary">
          Chart of PV generation, local load, evacuation limit, and curtailed energy across 96 fifteen-minute slots.
        </p>
        <div className="flex flex-wrap items-center gap-4 text-xs text-muted mb-3">
          <Legend color={CHART.pv} label="PV" />
          <Legend color={CHART.load} label="Baseline load" />
          <Legend color={CHART.evac} label="Evacuation limit" dashed />
          <Legend color={CHART.flex} label="Flexible load" />
          <Legend color={CHART.curtailed} label="Curtailed" />
        </div>
        <div className="h-80">
          <ResponsiveContainer>
            <ComposedChart data={chart}>
              <CartesianGrid stroke={CHART.grid} />
              <XAxis dataKey="t" tick={{ fill: CHART.tick, fontSize: 11 }} interval={15} />
              <YAxis tick={{ fill: CHART.tick, fontSize: 11 }} unit=" kW" />
              <Tooltip contentStyle={CHART.tooltip} />
              <Area dataKey="curtailed" name="Curtailed" stroke={CHART.curtailed} fill="#c45c2688" isAnimationActive={false} />
              <Line dataKey="pv" name="PV" stroke={CHART.pv} dot={false} strokeWidth={2.4} isAnimationActive={false} />
              <Line dataKey="load" name="Baseline load" stroke={CHART.load} dot={false} isAnimationActive={false} />
              <Line dataKey="evac" name="Evacuation limit" stroke={CHART.evac} dot={false} strokeDasharray="4 4" isAnimationActive={false} />
              <Line dataKey="flex" name="Flexible load" stroke={CHART.flex} dot={false} strokeWidth={2} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setPlaying((p) => !p)}
            className="px-4 py-1.5 rounded-full bg-gold text-cream text-sm font-semibold shadow-sm"
            aria-pressed={playing}
          >
            {playing ? "Pause" : "Play"}
          </button>
          <label className="text-sm text-muted">
            Speed
            <select
              className="ml-2 bg-cream border border-sand rounded-full px-2 py-1 text-ink"
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
              aria-label="Replay speed"
            >
              <option value={0.5}>0.5×</option>
              <option value={1}>1×</option>
              <option value={2}>2×</option>
              <option value={4}>4×</option>
            </select>
          </label>
          <input
            type="range"
            min={0}
            max={chart.length - 1}
            value={slot}
            onChange={(e) => setSlot(Number(e.target.value))}
            className="flex-1 min-w-[140px]"
            aria-label="Replay slot"
          />
          <span className="text-sm text-gold font-semibold w-28">{shown?.t}</span>
          {offline ? <span className="text-xs text-muted">offline fixture</span> : null}
        </div>
      </Card>

      <div className="grid md:grid-cols-[0.9fr_1.1fr] gap-4 items-center">
        <PanelArray />
        <SustainabilityStrip />
      </div>
    </div>
  );
}

function Legend({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="w-6 h-0.5 rounded-full" style={{ background: dashed ? "transparent" : color, borderTop: dashed ? `2px dashed ${color}` : undefined }} />
      {label}
    </span>
  );
}

function Stat({ label, value, sub, good }: { label: string; value: string; sub: string; good?: boolean }) {
  return (
    <Card className="p-4">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${good ? "text-leaf" : "text-ink"}`}>{value}</div>
      <div className="text-xs text-muted mt-1">{sub}</div>
    </Card>
  );
}
