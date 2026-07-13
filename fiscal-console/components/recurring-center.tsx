"use client";

import { useState } from "react";
import { Loader2, Plus, Repeat2 } from "lucide-react";

type Agreement = { id: string; counterparty_name: string; description: string; amount: number; day_of_month: number; next_run_on: string; active: number };

export function RecurringCenter({ initial, source }: { initial: Agreement[]; source: "engine" | "sandbox" | "demo" }) {
  const [rows, setRows] = useState(initial);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const payload = { branch_id: "main", counterparty_ref: `manual:${name}`, counterparty_name: name, description, amount, day_of_month: 15, next_run_on: "2026-08-15" };
    try {
      const response = await fetch("/api/recurring-agreements", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const record = await response.json() as Agreement & { detail?: string };
      if (!response.ok) throw new Error(record.detail ?? "No fue posible guardar el acuerdo");
      setRows(current => [record, ...current]);
      setOpen(false);
      setName("");
      setDescription("");
      setAmount(0);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No fue posible guardar el acuerdo");
    } finally {
      setSaving(false);
    }
  }

  return <div className="page section-page">
    <header className="page-header"><div><p className="eyebrow">Facturación recurrente</p><h1>Acuerdos mensuales</h1><p>Generan borradores revisables; nunca emiten automáticamente por defecto.</p></div><button className="primary-button" type="button" onClick={() => setOpen(true)}><Plus />Nuevo acuerdo</button></header>
    {open && <form className="panel wizard-form compact-form" onSubmit={submit}>
      <label>Cliente<input required value={name} onChange={event => setName(event.target.value)} /></label>
      <label>Concepto<input required value={description} onChange={event => setDescription(event.target.value)} /></label>
      <label>Monto<input required min="1" type="number" value={amount || ""} onChange={event => setAmount(Number(event.target.value))} /></label>
      <button className="primary-button" disabled={saving}>{saving ? <><Loader2 className="spin" /> Guardando…</> : "Guardar acuerdo"}</button>
      {error && <p className="field-error">{error}</p>}
    </form>}
    <section className="panel approvals-list">{rows.length ? rows.map(row => <article key={row.id}><div><strong>{row.counterparty_name}</strong><p>{row.description}</p></div><b>${row.amount.toLocaleString("es-CL")}</b><em className="received-status neutral">Día {row.day_of_month}</em><span><Repeat2 /></span></article>) : <div className="empty-inline"><Repeat2 /><p>No existen acuerdos todavía · {source === "engine" ? "motor conectado" : "demo"}</p></div>}</section>
  </div>;
}
