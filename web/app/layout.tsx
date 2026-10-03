import "./globals.css";
import type { Metadata } from "next";
import { Nav } from "@/components/Nav";
import { ReplayProvider } from "@/components/ReplayContext";

export const metadata: Metadata = {
  title: "SolarSponge",
  description: "Shift flexible loads into curtailed-solar windows",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans text-ink antialiased">
        <ReplayProvider>
          <Nav />
          <main className="relative z-10 max-w-7xl mx-auto px-4 py-8">{children}</main>
          <footer className="relative z-10 max-w-7xl mx-auto px-4 pb-10 pt-4 text-sm text-muted">
            <div className="border-t border-sand pt-6 flex flex-wrap items-center justify-between gap-3">
              <p>SolarSponge · one-zone digital twin · curtailed solar into productive demand</p>
              <p className="text-clay">Rajasthan illustrative feeder · SDG 7 · SDG 13</p>
            </div>
          </footer>
        </ReplayProvider>
      </body>
    </html>
  );
}
