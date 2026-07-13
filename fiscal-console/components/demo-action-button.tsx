"use client";

import { useState, type ReactNode } from "react";
import { CheckCircle2 } from "lucide-react";

export function DemoActionButton({ area, children, className = "primary-button", done = "Actualizado en sandbox" }: { area: string; children: ReactNode; className?: string; done?: string }) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  async function run() {
    setState("loading");
    const response = await fetch(`/api/demo/activities?area=${encodeURIComponent(area)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ requested_at: new Date().toISOString() }) });
    setState(response.ok ? "done" : "error");
  }
  return <button className={className} type="button" onClick={run} disabled={state === "loading"}>{state === "done" ? <><CheckCircle2 size={16} /> {done}</> : state === "error" ? "Reintentar" : state === "loading" ? "Procesando…" : children}</button>;
}
