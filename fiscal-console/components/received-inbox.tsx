"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, FileCheck2, Filter, Search } from "lucide-react";
import { receivedDemo } from "@/lib/received-demo-data";

type Received = { id: string; type: number; folio: number; issuer: string; rut: string; date: string; total: string; status: string; tone: string };
const initial: Received[] = receivedDemo.map(row => ({ ...row }));

export function ReceivedInbox() {
  const [rows, setRows] = useState(initial);
  const [importOpen, setImportOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [pendingOnly, setPendingOnly] = useState(false);
  const [message, setMessage] = useState("");
  const visible = useMemo(() => rows.filter(row => (!pendingOnly || row.tone !== "success") && `${row.issuer} ${row.rut} ${row.folio}`.toLowerCase().includes(query.toLowerCase())), [rows, pendingOnly, query]);

  async function importXml(file: File) {
    const response = await fetch("/api/demo/activities?area=received_xml_import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ file_name: file.name, size: file.size, mime_type: file.type }) });
    if (!response.ok) return setMessage("No fue posible importar el XML de prueba");
    setRows(current => [{ id: "demo-33-7841?imported=1", type: 33, folio: 9901, issuer: "PROVEEDOR IMPORTADO DEMO SPA", rut: "77.777.777-7", date: "Hoy", total: "$119.000", status: "Por revisar", tone: "warning" }, ...current]);
    setMessage("XML sintético validado y persistido en sandbox");
  }

  return <div className="page section-page">
    <header className="page-header"><div><p className="eyebrow">Compras y recepción fiscal</p><h1>Documentos recibidos</h1><p>XML validados contra firma, esquema y RUT antes de entrar a tu operación.</p></div><button className="primary-button" type="button" onClick={() => setImportOpen(value => !value)}><FileCheck2 size={17} /> Importar XML</button></header>
    {importOpen && <section className="panel import-card"><strong>Importación segura de demostración</strong><p>El archivo se registra como evidencia sintética y nunca se envía al SII.</p><label>Seleccionar XML<input aria-label="Seleccionar XML recibido" type="file" accept=".xml,application/xml,text/xml" onChange={event => event.target.files?.[0] && importXml(event.target.files[0])} /></label>{message && <p className="simulation-success">{message}</p>}</section>}
    <div className="summary-grid"><article className="panel summary-card"><Clock3 size={19} /><div><small>Requieren revisión</small><strong>1</strong><p>Antes de aceptar o reclamar</p></div></article><article className="panel summary-card"><CheckCircle2 size={19} /><div><small>Aceptados este mes</small><strong>18</strong><p>$4.281.900 documentados</p></div></article><article className="panel summary-card"><AlertTriangle size={19} /><div><small>Diferencias RCV</small><strong>0</strong><p>Sin discrepancias detectadas</p></div></article></div>
    <section className="panel documents-panel"><div className="table-toolbar"><div><h2>Bandeja tributaria</h2><p>Modo demostración · datos sintéticos</p></div><div><button className="secondary-button" type="button" onClick={() => setSearchOpen(value => !value)}><Search size={15} /> Buscar</button><button className="secondary-button" type="button" onClick={() => setPendingOnly(value => !value)}><Filter size={15} /> {pendingOnly ? "Ver todos" : "Sólo pendientes"}</button></div></div>{searchOpen && <div className="catalog-toolbar"><label><Search size={16}/><input aria-label="Buscar documentos recibidos" autoFocus value={query} onChange={event => setQuery(event.target.value)} placeholder="Emisor, RUT o folio" /></label><span>{visible.length} resultados</span></div>}<div className="received-list">{visible.map(item => <article className="received-row" key={item.id}><span className="document-code">{item.type}</span><div className="received-main"><strong>{item.issuer}</strong><p>{item.rut} · Folio {item.folio} · {item.date}</p></div><strong className="received-total">{item.total}</strong><span className={`received-status ${item.tone}`}>{item.status}</span><Link className="secondary-button" href={`/recibidos/${item.id}`}>Revisar</Link></article>)}</div></section>
    <section className="tip-card"><FileCheck2 size={21} /><div><strong>El PDF no reemplaza al XML</strong><p>OCR puede ayudar a clasificar una compra, pero las decisiones tributarias se basan siempre en el XML firmado.</p></div></section>
  </div>;
}
