"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { getReplay } from "@/lib/api";

const Ctx = createContext<any>(null);

export function ReplayProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getReplay()
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);
  return <Ctx.Provider value={{ data, error, setData }}>{children}</Ctx.Provider>;
}

export function useReplay() {
  return useContext(Ctx);
}
