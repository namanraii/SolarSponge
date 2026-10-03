"use client";
import { useMemo, useState } from "react";
import { useReplay } from "@/components/ReplayContext";

const COPY: Record<string, Record<string, string>> = {
  en: {
    title: "Today’s irrigation window",
    why: "Cheap clean power is available on your feeder around midday. Running now covers today’s crop water without extra starts.",
    run: "Run",
    badge: "Crop need protected",
  },
  hi: {
    title: "आज की सिंचाई खिड़की",
    why: "आपके फीडर पर दोपहर के आसपास सस्ती स्वच्छ बिजली उपलब्ध है। अभी चलाने से आज की फसल की पानी की जरूरत पूरी होगी।",
    run: "चलाएँ",
    badge: "फसल की जरूरत सुरक्षित",
  },
  ta: {
    title: "இன்றைய நீர்ப்பாசன நேரம்",
    why: "உங்கள் ஃபீடரில் மதிய நேரத்தில் மலிவான சுத்தமான மின்சாரம் உள்ளது. இப்போது இயக்கினால் பயிருக்கு வேண்டிய நீர் கிடைக்கும்.",
    run: "இயக்கு",
    badge: "பயிர் தேவை பாதுகாக்கப்பட்டது",
  },
};

function runs(on: number[], labels: string[]) {
  const out: string[] = [];
  let start: number | null = null;
  const arr = [...on, 0];
  for (let i = 0; i < arr.length; i++) {
    if (arr[i] && start === null) start = i;
    if (!arr[i] && start !== null) {
      out.push(`${labels[start]}–${labels[i] || labels[labels.length - 1]}`);
      start = null;
    }
  }
  return out.join(", ");
}

export default function Farmer() {
  const { data } = useReplay();
  const [lang, setLang] = useState<"en" | "hi" | "ta">("hi");
  const pump = data?.schedules?.find((s: any) => s.kind === "pump");
  const window = useMemo(() => (pump && data ? runs(pump.on, data.labels) : "—"), [pump, data]);
  const t = COPY[lang];
  return (
    <div className="max-w-md mx-auto">
      <div className="flex justify-center gap-2 mb-4">
        {(["en", "hi", "ta"] as const).map((l) => (
          <button
            key={l}
            onClick={() => setLang(l)}
            className={`px-3 py-1 rounded-full text-sm ${lang === l ? "bg-gold text-ink" : "bg-white/10"}`}
          >
            {l.toUpperCase()}
          </button>
        ))}
      </div>
      <div className="bg-[#f4efe4] text-[#1a1208] rounded-3xl p-6 min-h-[70vh] shadow-2xl">
        <p className="text-xs uppercase tracking-widest text-[#8a6a32]">SolarSponge · farmer</p>
        <h1 className="font-display text-3xl mt-3">{t.title}</h1>
        <p className="text-4xl font-semibold mt-6">
          {t.run} {window || "—"}
        </p>
        <p className="mt-4 text-lg leading-relaxed">{t.why}</p>
        <div className="mt-8 inline-block bg-[#d9f99d] text-[#14532d] px-3 py-1 rounded-full text-sm font-semibold">
          {t.badge}
        </div>
        <p className="mt-10 text-sm text-[#6b5a3e]">
          {pump?.name} · {pump?.power_kw} kW · plan {data?.plan?.plan_id}
        </p>
      </div>
    </div>
  );
}
