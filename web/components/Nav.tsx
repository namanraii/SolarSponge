"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getOpsStatus, setKillSwitch } from "@/lib/api";
import { BrandMark } from "@/components/BrandMark";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/schedule", label: "Schedule" },
  { href: "/forecast", label: "Forecast" },
  { href: "/kpis", label: "KPIs" },
  { href: "/what-if", label: "What-if" },
  { href: "/copilot", label: "Copilot" },
  { href: "/farmer", label: "Farmer" },
];

export function Nav() {
  const path = usePathname();
  const [killed, setKilled] = useState(false);
  useEffect(() => {
    getOpsStatus()
      .then((s) => setKilled(Boolean(s.kill_switch)))
      .catch(() => undefined);
  }, []);
  return (
    <header className="sticky top-0 z-20 border-b border-sand/80 bg-cream/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col gap-2 lg:flex-row lg:items-center lg:gap-4">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2 shrink-0">
            <BrandMark className="w-9 h-9" />
            <span className="font-display text-xl text-ink tracking-tight">SolarSponge</span>
          </Link>
          <p className="hidden md:block text-xs text-muted max-w-xs">
            Turning curtailed solar into productive demand
          </p>
        </div>
        <nav className="flex flex-wrap gap-1 lg:ml-auto lg:flex-nowrap">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`px-3 py-1.5 rounded-full text-sm transition shrink-0 ${
                path === l.href
                  ? "bg-leaf text-cream font-semibold shadow-sm"
                  : "text-muted hover:text-ink hover:bg-sand/60"
              }`}
            >
              {l.label}
            </Link>
          ))}
          <button
            type="button"
            className={`px-3 py-1.5 rounded-full text-sm shrink-0 ${
              killed ? "bg-terracotta text-cream font-semibold" : "text-muted hover:text-ink hover:bg-sand/60"
            }`}
            onClick={async () => {
              try {
                const r = await setKillSwitch(!killed);
                setKilled(Boolean(r.kill_switch));
              } catch {
                /* API down: fixture-only mode */
              }
            }}
            aria-pressed={killed}
          >
            {killed ? "Kill switch ON" : "Kill switch"}
          </button>
        </nav>
      </div>
    </header>
  );
}
