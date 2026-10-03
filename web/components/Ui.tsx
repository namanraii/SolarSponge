export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`card rounded-2xl ${className}`}>{children}</div>;
}

export function PageHeader({
  kicker,
  title,
  children,
}: {
  kicker?: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="space-y-2 max-w-2xl">
      {kicker ? (
        <p className="text-xs uppercase tracking-[0.22em] text-clay font-semibold">{kicker}</p>
      ) : null}
      <h1 className="font-display text-4xl md:text-[2.6rem] text-ink leading-tight">{title}</h1>
      {children ? <div className="text-muted leading-relaxed">{children}</div> : null}
    </div>
  );
}

export function Loading({ label = "Loading replay…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-muted py-16">
      <span className="inline-block w-8 h-8 rounded-full bg-gradient-to-br from-sun to-terracotta animate-pulse shadow-[0_0_20px_rgba(232,163,23,0.5)]" />
      <p>{label}</p>
    </div>
  );
}

export function SustainabilityStrip() {
  const items = [
    { label: "SDG 7", detail: "Affordable and clean energy" },
    { label: "SDG 13", detail: "Climate action on the feeder" },
    { label: "CEA v22.0", detail: "0.675 tCO₂ / MWh grid factor" },
  ];
  return (
    <div className="grid sm:grid-cols-3 gap-3">
      {items.map((it) => (
        <div key={it.label} className="rounded-xl border border-sand bg-cream/70 px-4 py-3">
          <div className="text-xs uppercase tracking-widest text-clay font-semibold">{it.label}</div>
          <div className="text-sm text-ink mt-1">{it.detail}</div>
        </div>
      ))}
    </div>
  );
}

export const CHART = {
  grid: "#e0d2b8",
  tick: "#6b5e4e",
  tooltip: { background: "#fffaf2", border: "1px solid #e6d7bf", color: "#1f1810" },
  pv: "#c48a1a",
  load: "#5b7c8a",
  evac: "#8a7a64",
  flex: "#3d6b45",
  curtailed: "#c45c26",
  band: "#c48a1a33",
};
