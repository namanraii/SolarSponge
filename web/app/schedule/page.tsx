"use client";
import { useReplay } from "@/components/ReplayContext";

const KIND_WHY: Record<string, string> = {
  pump: "Daily irrigation energy is a hard constraint; min-run avoids short-cycling pumps.",
  cold_store: "Room temperature stays inside the 2–6 °C band.",
  ev_depot: "Vehicles must reach target SoC before the depot window closes.",
  hvac: "Comfort band during occupancy; pre-cool is allowed before 09:00.",
};

export default function SchedulePage() {
  const { data } = useReplay();
  if (!data) return <p>Loading…</p>;
  const labels: string[] = data.labels;
  const surplus: number[] = data.surplus_kw;
  const maxS = Math.max(...surplus, 1);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl text-gold">Constraint-safe schedule</h1>
        <span className="px-3 py-1 rounded-full bg-sponge/20 text-sponge text-sm font-semibold">
          Constraint violations: {data.kpis.constraint_violations}
        </span>
      </div>
      <p className="text-white/60 text-sm">
        Each row is a flexible load. Gold ticks are ON slots. The heat strip is forecast surplus. Commands outside a
        load&apos;s window are illegal and blocked again in the dispatch gateway.
      </p>
      <div className="overflow-x-auto bg-panel rounded-2xl p-4 border border-white/10">
        <div className="flex gap-px h-6 mb-3">
          {surplus.map((s, i) => (
            <div key={i} className="flex-1" style={{ background: `rgba(232,184,109,${0.15 + 0.85 * (s / maxS)})` }} title={labels[i]} />
          ))}
        </div>
        {data.schedules.map((sch: any) => (
          <div key={sch.load_id} className="mb-4">
            <div className="flex justify-between text-sm mb-1">
              <span className="font-semibold">{sch.name}</span>
              <span className="text-white/50">
                {sch.power_kw} kW · unmet {sch.unmet_kwh?.toFixed?.(1) ?? sch.unmet_kwh} kWh
              </span>
            </div>
            <div className="flex gap-px h-8">
              {sch.on.map((v: number, i: number) => (
                <div
                  key={i}
                  className={`flex-1 ${v ? "bg-gold" : "bg-white/5"}`}
                  title={`${labels[i]} ${v ? "ON" : "off"}`}
                />
              ))}
            </div>
            <p className="text-xs text-white/45 mt-1">{KIND_WHY[sch.kind] || "Hard constraints from config."}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
