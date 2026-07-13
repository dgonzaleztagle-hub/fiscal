"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, ArrowUpDown, Ban, CheckCircle2, FilePenLine, Info, Loader2, ShieldAlert } from "lucide-react";

type Intent = "void" | "text" | "amount";
type Issued = { id: string; folio: string; label: string };

const choices = [
  { id: "void" as const, icon: Ban, title: "Anular completamente", detail: "La operación no debió existir o corresponde anular una nota de débito." },
  { id: "text" as const, icon: FilePenLine, title: "Corregir datos del receptor", detail: "Corrige giro, dirección o comuna sin cambiar montos." },
  { id: "amount" as const, icon: ArrowUpDown, title: "Corregir cantidades o montos", detail: "Disminuye o aumenta el valor de la operación original." },
];

export function CorrectionWizard() {
  const [intent, setIntent] = useState<Intent>("void");
  const [direction, setDirection] = useState<"down" | "up">("down");
  const [reference, setReference] = useState("FACTURA 33 · FOLIO 8.412");
  const [reason, setReason] = useState("Corrección solicitada por el cliente");
  const [amount, setAmount] = useState(10000);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [issued, setIssued] = useState<Issued | null>(null);
  const result = correctionResult(intent, direction);

  async function issue() {
    setLoading(true); setError(""); setIssued(null);
    try {
      const response = await fetch("/api/demo/fiscal-documents", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        documentType: Number(result.code), receiver: "CLIENTE SINTÉTICO SPA", itemName: result.title,
        quantity: 1, unitPrice: intent === "text" ? 0 : amount, referenceId: reference, reason,
      }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "No fue posible emitir la corrección");
      setIssued(body);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No fue posible emitir la corrección"); }
    finally { setLoading(false); }
  }

  return <div className="page section-page wizard-page">
    <Link href="/emitir" className="back-link"><ArrowLeft size={15} /> Volver a tipos de documento</Link>
    <header className="page-header"><div><p className="eyebrow">Asistente legal · Sandbox</p><h1>¿Qué necesitas corregir?</h1><p>Primero define la intención. Completo elegirá el documento y bloqueará combinaciones incompatibles.</p></div><span className="demo-action">Builders 56/61 activos · backend sandbox</span></header>
    <div className="correction-layout">
      <section className="panel correction-choices">{choices.map(({ id, icon: Icon, title, detail }) => <button className={intent === id ? "selected" : ""} key={id} type="button" onClick={() => { setIntent(id); setIssued(null); }}><span><Icon size={19} /></span><div><strong>{title}</strong><p>{detail}</p></div>{intent === id && <CheckCircle2 size={17} />}</button>)}{intent === "amount" && <div className="direction-choice"><button className={direction === "down" ? "active" : ""} type="button" onClick={() => setDirection("down")}>Disminuir monto</button><button className={direction === "up" ? "active" : ""} type="button" onClick={() => setDirection("up")}>Aumentar monto</button></div>}</section>
      <aside className="panel legal-result">
        <p className="eyebrow">Resultado documental</p><div className="result-code"><span>{result.code}</span><div><strong>{result.title}</strong><p>{result.reference}</p></div></div>
        <label>Documento original<input value={reference} onChange={(event) => setReference(event.target.value)} /></label>
        <label>Motivo<input value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        {intent !== "text" && <label>Monto de la corrección<input type="number" min="1" value={amount} onChange={(event) => setAmount(Number(event.target.value))} /></label>}
        <ul>{result.rules.map((rule) => <li key={rule}><CheckCircle2 size={14} /> {rule}</li>)}</ul>
        <div className="legal-warning"><ShieldAlert size={18} /><p>{result.warning}</p></div>
        <div className="form-notice"><Info size={16} /><p>El simulador crea folio, firma, eventos y relación inmutable. No llama al SII ni consume CAF.</p></div>
        <button className="primary-button" type="button" disabled={loading || !reference.trim() || !reason.trim()} onClick={issue}>{loading ? <><Loader2 size={16} className="spin" /> Emitiendo…</> : "Emitir corrección en sandbox"}</button>
        {error && <p className="field-error">{error}</p>}
        {issued && <div className="validation-success"><CheckCircle2 size={18} /><div><strong>{issued.label} · folio {issued.folio}</strong><p>Persistida y aceptada por el simulador. <Link href={`/documentos/${issued.id}`}>Ver documento</Link></p></div></div>}
      </aside>
    </div>
  </div>;
}

function correctionResult(intent: Intent, direction: "down" | "up") {
  if (intent === "void") return { code: "61", title: "Nota de crédito de anulación", reference: "Código de referencia 1", rules: ["Selecciona la factura 33/34 o nota de débito 56 original", "Completo copiará automáticamente los montos del documento", "La relación quedará visible y el original no se borrará"], warning: "La anulación de una factura debe respetar el período tributario aplicable. Antes de confirmar se verificará la fecha original." };
  if (intent === "text") return { code: "61", title: "Nota de crédito que corrige texto", reference: "Código de referencia 2", rules: ["Sólo corrige giro, dirección o comuna del receptor", "No modifica neto, IVA, exento ni total", "Requiere un único documento de referencia"], warning: "Si además cambia un monto, debes realizar una corrección separada. El asistente no permitirá mezclar ambas acciones." };
  if (direction === "up") return { code: "56", title: "Nota de débito por diferencia", reference: "Código de referencia 3", rules: ["Aumenta cantidades o montos de una factura 33/34", "La razón de referencia es obligatoria", "Sólo se cargará la diferencia adicional"], warning: "Una nota de débito no anula una factura. Para anular una nota de crédito se usa un flujo específico con referencia única." };
  return { code: "61", title: "Nota de crédito por diferencia", reference: "Código de referencia 3", rules: ["Disminuye cantidades o montos de una factura 33/34", "Nunca podrá acreditar más que el saldo vigente", "La razón de referencia es obligatoria"], warning: "Completo calculará lo ya acreditado por notas anteriores antes de permitir una nueva disminución." };
}
