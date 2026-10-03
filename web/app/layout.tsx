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
      <body className="font-sans">
        <ReplayProvider>
          <Nav />
          <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
        </ReplayProvider>
      </body>
    </html>
  );
}
