"use client";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useReplay } from "@/components/ReplayContext";
import { Card, CHART, Loading, PageHeader } from "@/components/Ui";

export default function ForecastPage() {
  const { data } = useReplay();
  if (!data) return <Loading />;
  const rows = data.labels.map((t: string, i: number) => ({
    t,
    actual: data.surplus_kw[i],
    p10: data.forecast_surplus.p10[i],
    p50: data.forecast_surplus.p50[i],
    p90: data.forecast_surplus.p90[i],
  }));
  return (
    <div className="space-y-5">
      <PageHeader kicker="Probabilistic surplus" title="Forecast quality">
        Schedules are built against a risk quantile of the surplus band, not a point forecast. Shaded region is p10–p90.
        Model: {data.plan && data.forecast_surplus ? "quantile surplus via joint PV–load scenarios" : "—"}.
      </PageHeader>
      <Card className="p-4 h-96">
        <ResponsiveContainer>
          <ComposedChart data={rows}>
            <CartesianGrid stroke={CHART.grid} />
            <XAxis dataKey="t" tick={{ fill: CHART.tick, fontSize: 11 }} interval={15} />
            <YAxis tick={{ fill: CHART.tick, fontSize: 11 }} />
            <Tooltip contentStyle={CHART.tooltip} />
            <Area dataKey="p90" stroke="none" fill={CHART.band} isAnimationActive={false} />
            <Area dataKey="p10" stroke="none" fill="#faf6ee" isAnimationActive={false} />
            <Line dataKey="p50" stroke={CHART.pv} dot={false} name="p50 surplus" strokeWidth={2} isAnimationActive={false} />
            <Line dataKey="actual" stroke={CHART.flex} dot={false} name="actual surplus" strokeWidth={2} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}
