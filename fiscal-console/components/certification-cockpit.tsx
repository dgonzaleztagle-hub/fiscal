"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, ShieldAlert, UploadCloud } from "lucide-react";

type Gate = { code: string; title: string; completed: boolean; detail: string };
type Readiness = { completed: number; total: number; gates: Gate[] };
type Result = { document_count: number; final_state: string; evidence_sha256: string; source: string };
const initialReadiness: Readiness = { completed: 2, total: 5, gates: [
  { code: "offline_engine", title: "Motor y regresión documental", completed: true, detail: "DTE y firmas locales cubiertos" },
  { code: "dry_run", title: "Ensayo de cinco folios", completed: true, detail: "Sobre, RCOF, fallas y evidencia sintética" },
] };

export function CertificationCockpit() {
  const [ready, setReady] = useState<Readiness>(initialReadiness);
  const [scenario, setScenario] = useState("accepted");
  const [result, setResult] = useState<Result>();
  const [running, setRunning] = useState(false);
  useEffect(() => { fetch("/api/certification").then((r) => r.json()).then(setReady); }, []);
  async function run() { setRunning(true); const response = await fetch("/api/certification", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario }) }); setResult(await response.json()); setRunning(false); }
  const completed = ready.completed; const total = ready.total;
  return <div className="page section-page"><header className="page-header"><div><p className="eyebrow">Certificación asistida</p><h1>Cockpit de preparación SII</h1><p>Ensaya la ventana completa sin consumir CAF ni contactar al SII.</p></div><span className="lock-badge">CAF real bloqueado</span></header><section className="certification-grid"><div className="panel"><p className="eyebrow">Compuerta calculada</p><h2>{completed} de {total} controles listos</h2><div className="completion"><span style={{ width: `${completed / total * 100}%` }} /></div>{ready?.gates.map((gate) => <div className="check-row" key={gate.code}><span className={gate.completed ? "done" : "pending"}>{gate.completed ? "✓" : "·"}</span><div><strong>{gate.title}</strong><p>{gate.detail}</p></div></div>)}</div><div className="panel evidence-card"><UploadCloud size={25} /><p className="eyebrow">Ensayo de cinco folios</p><h2>Paquete de evidencia</h2><select aria-label="Escenario de ensayo" value={scenario} onChange={(event) => setScenario(event.target.value)}><option value="accepted">Aceptación completa</option><option value="timeout_after_upload">Timeout después del upload</option><option value="envelope_rejected">Sobre rechazado</option><option value="rcof_rejected">RCOF rechazado</option></select><button className="secondary-button" disabled={running || !ready} onClick={run}>{running ? "Generando…" : "Ejecutar ensayo offline"}</button>{result && <div className={result.final_state === "accepted" ? "validation-success" : "legal-warning"}>{result.final_state === "accepted" ? <CheckCircle2 size={18} /> : <ShieldAlert size={18} />}<div><strong>Estado final: {result.final_state}</strong><p>{result.document_count} DTE · origen {result.source}</p><code>{result.evidence_sha256}</code></div></div>}<p>Nunca habilita producción ni descarga folios reales.</p></div></section></div>;
}
