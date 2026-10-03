"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

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
  return (
    <header className="border-b border-white/10 bg-ink/80 backdrop-blur sticky top-0 z-20">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-6">
        <Link href="/" className="font-display text-xl text-gold tracking-tight">
          SolarSponge
        </Link>
        <p className="hidden md:block text-xs text-white/50">Turning curtailed solar into productive demand</p>
        <nav className="ml-auto flex flex-wrap gap-1">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`px-3 py-1.5 rounded-full text-sm ${
                path === l.href ? "bg-gold text-ink font-semibold" : "text-white/70 hover:text-white"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
