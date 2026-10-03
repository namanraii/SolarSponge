"use client";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useReplay } from "@/components/ReplayContext";

export default function ForecastPage() {
  const { data } = useReplay();
  if (!data) return <p>Loading…</p>;
  const rows = data.labels.map((t: string, i: number) => ({
    t,
    actual: data.surplus_kw[i],
    p10: data.forecast_surplus.p10[i],
    p50: data.forecast_surplus.p50[i],
    p90: data.forecast_surplus.p90[i],
  }));
  return (
    <div className="space-y-4">
      <h1 className="font-display text-3xl text-gold">Forecast quality</h1>
      <p className="text-white/60 max-w-2xl">
        Schedules are built against a risk quantile of the surplus band, not a point forecast. Shaded region is p10–p90.
        Model: {data.plan && data.forecast_surplus ? "quantile surplus via joint PV–load scenarios" : "—"}.
      </p>
      <div className="bg-panel rounded-2xl p-4 h-96 border border-white/10">
        <ResponsiveContainer>
          <ComposedChart data={rows}>
            <CartesianGrid stroke="#ffffff14" />
            <XAxis dataKey="t" tick={{ fill: "#9aa3b5", fontSize: 11 }} interval={7} />
            <YAxis tick={{ fill: "#9aa3b5", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#141c2e", border: "1px solid #ffffff22" }} />
            <Area dataKey="p90" stroke="none" fill="#e8b86d33" />
            <Area dataKey="p10" stroke="none" fill="#0c1220" />
            <Line dataKey="p50" stroke="#e8b86d" dot={false} name="p50 surplus" />
            <Line dataKey="actual" stroke="#2dd4bf" dot={false} name="actual surplus" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
