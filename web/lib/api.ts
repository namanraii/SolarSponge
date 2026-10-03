export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getReplay(zoneId = "zone-001") {
  try {
    const r = await fetch(`${API}/v1/zones/${zoneId}/replay`, { cache: "no-store" });
    if (r.ok) return r.json();
  } catch {
    /* fall through to the committed fixture */
  }
  const f = await fetch("/replay.json", { cache: "force-cache" });
  if (!f.ok) throw new Error("replay unavailable");
  const body = await f.json();
  return { ...body, _offline: true };
}

export async function setKillSwitch(enabled: boolean) {
  const r = await fetch(`${API}/v1/ops/kill-switch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  if (!r.ok) throw new Error("kill switch failed");
  return r.json();
}

export async function getOpsStatus() {
  const r = await fetch(`${API}/v1/ops/status`, { cache: "no-store" });
  if (!r.ok) return { kill_switch: false };
  return r.json();
}

export async function runScenario(
  zoneId: string,
  body: { cloud_delta_pct?: number; disabled_load_ids?: string[]; risk_quantile?: number }
) {
  const r = await fetch(`${API}/v1/zones/${zoneId}/scenario`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error("scenario failed");
  return r.json();
}

export async function chat(message: string, zoneId = "zone-001") {
  const r = await fetch(`${API}/v1/copilot/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, zone_id: zoneId }),
  });
  if (!r.ok) throw new Error("copilot failed");
  return r.json();
}
