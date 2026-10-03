"use client";
import { useReplay } from "@/components/ReplayContext";
import { Card, Loading, PageHeader } from "@/components/Ui";

const KIND_WHY: Record<string, string> = {
  pump: "Daily irrigation energy is a hard constraint; min-run avoids short-cycling pumps.",
  cold_store: "Room temperature stays inside the 2–6 °C band.",
  ev_depot: "Vehicles must reach target SoC before the depot window closes.",
  hvac: "Comfort band during occupancy; pre-cool is allowed before 09:00.",
};

export default function SchedulePage() {
  const { data } = useReplay();
  if (!data) return <Loading />;
  const labels: string[] = data.labels;
  const surplus: number[] = data.surplus_kw;
  const maxS = Math.max(...surplus, 1);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <PageHeader kicker="Dispatch" title="Constraint-safe schedule">
          Each row is a flexible load. Gold ticks are ON slots. The heat strip is forecast surplus. Commands outside a
          load&apos;s window are illegal and blocked again in the dispatch gateway.
        </PageHeader>
        <span className="px-3 py-1 rounded-full bg-leaf/15 text-leaf text-sm font-semibold">
          Constraint violations: {data.kpis.constraint_violations}
        </span>
      </div>
      <Card className="overflow-x-auto p-4 md:p-5">
        <div className="flex gap-px h-6 mb-3 rounded-full overflow-hidden">
          {surplus.map((s, i) => (
            <div key={i} className="flex-1" style={{ background: `rgba(196,138,26,${0.12 + 0.88 * (s / maxS)})` }} title={labels[i]} />
          ))}
        </div>
        {data.schedules.map((sch: any) => (
          <div key={sch.load_id} className="mb-4">
            <div className="flex justify-between text-sm mb-1">
              <span className="font-semibold text-ink">{sch.name}</span>
              <span className="text-muted">
                {sch.power_kw} kW · unmet {sch.unmet_kwh?.toFixed?.(1) ?? sch.unmet_kwh} kWh
              </span>
            </div>
            <div className="flex gap-px h-8 rounded-md overflow-hidden">
              {sch.on.map((v: number, i: number) => (
                <div
                  key={i}
                  className={`flex-1 ${v ? "bg-gold" : "bg-sand"}`}
                  title={`${labels[i]} ${v ? "ON" : "off"}`}
                />
              ))}
            </div>
            <p className="text-xs text-muted mt-1">{KIND_WHY[sch.kind] || "Hard constraints from config."}</p>
          </div>
        ))}
      </Card>
    </div>
  );
}
