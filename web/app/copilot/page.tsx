"use client";
import { useState } from "react";
import { chat } from "@/lib/api";

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
      <h1 className="font-display text-3xl text-gold">Operator copilot</h1>
      <p className="text-white/60">
        Explains plans and runs sandboxed what-ifs. It has no write path to devices. Every figure is supposed to come from
        a tool.
      </p>
      <div className="flex flex-wrap gap-2">
        {STARTERS.map((s) => (
          <button key={s} onClick={() => setQ(s)} className="text-xs px-3 py-1 rounded-full bg-white/10">
            {s}
          </button>
        ))}
      </div>
      <div className="bg-panel rounded-2xl border border-white/10 p-4 min-h-64 space-y-3">
        {log.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-gold" : "text-white/90"}>
            <div className="text-xs uppercase tracking-wide text-white/40 mb-1">
              {m.role === "user" ? "you" : m.role}
              {m.refusal ? " · refused" : ""}
            </div>
            <p>{m.text || m.answer}</p>
            {m.tool_calls?.length ? (
              <p className="text-xs text-sponge mt-1">tools: {m.tool_calls.map((t: any) => t.name).join(", ")}</p>
            ) : null}
          </div>
        ))}
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send(q);
        }}
      >
        <input
          className="flex-1 bg-panel border border-white/10 rounded-full px-4 py-2"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button disabled={busy} className="bg-gold text-ink font-semibold px-4 rounded-full">
          Ask
        </button>
      </form>
    </div>
  );
}
