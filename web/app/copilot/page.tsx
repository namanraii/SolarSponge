"use client";
import { useState } from "react";
import { chat } from "@/lib/api";
import { Card, PageHeader } from "@/components/Ui";

const STARTERS = [
  "Why did pump cluster B start when it did?",
  "What if cloud cover is +20%?",
  "Just turn pump B on now",
  "Draft a farmer message for pump cluster A",
];

export default function CopilotPage() {
  const [q, setQ] = useState(STARTERS[0]);
  const [log, setLog] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);

  async function send(text: string) {
    setBusy(true);
    setLog((l) => [...l, { role: "user", text }]);
    try {
      const r = await chat(text);
      setLog((l) => [...l, r]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <PageHeader kicker="Read-only" title="Operator copilot">
        Explains plans and runs sandboxed what-ifs. It has no write path to devices. Every figure is supposed to come from
        a tool.
      </PageHeader>
      <div className="flex flex-wrap gap-2">
        {STARTERS.map((s) => (
          <button key={s} onClick={() => setQ(s)} className="text-xs px-3 py-1 rounded-full bg-sand text-ink hover:bg-clay/30">
            {s}
          </button>
        ))}
      </div>
      <Card className="p-4 min-h-64 space-y-3">
        {log.length === 0 ? <p className="text-muted text-sm">Ask why a pump ran, or try a refused actuation.</p> : null}
        {log.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-gold" : "text-ink"}>
            <div className="text-xs uppercase tracking-wide text-muted mb-1">
              {m.role === "user" ? "you" : m.role}
              {m.refusal ? " · refused" : ""}
            </div>
            <p>{m.text || m.answer}</p>
            {m.tool_calls?.length ? (
              <p className="text-xs text-leaf mt-1">tools: {m.tool_calls.map((t: any) => t.name).join(", ")}</p>
            ) : null}
          </div>
        ))}
      </Card>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send(q);
        }}
      >
        <input
          className="flex-1 bg-cream border border-sand rounded-full px-4 py-2 outline-none focus:border-gold"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button disabled={busy} className="bg-gold text-cream font-semibold px-4 rounded-full">
          Ask
        </button>
      </form>
    </div>
  );
}
