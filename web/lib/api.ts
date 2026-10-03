export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getReplay(zoneId = "zone-001") {
  const r = await fetch(`${API}/v1/zones/${zoneId}/replay`, { cache: "no-store" });
  if (!r.ok) throw new Error("replay unavailable");
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
