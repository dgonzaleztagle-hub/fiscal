"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { CircleHelp, X } from "lucide-react";
import { FISCAL_HELP, helpKeyForPath } from "@/lib/help-content";

const SUPPORT = "56972739105";
const DIACRITICS = new RegExp("[\\u0300-\\u036f]", "g");
const normalize = (value: string) => value.normalize("NFD").replace(DIACRITICS, "").toLowerCase();

export function HelpCenter() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [view, setView] = useState<string | null>(null);
  const currentKey = helpKeyForPath(pathname);
  const key = view && FISCAL_HELP[view] ? view : currentKey;
  const guide = FISCAL_HELP[key];
  const terms = normalize(query).trim().split(/\s+/).filter(Boolean);
  const results = terms.length ? Object.entries(FISCAL_HELP).filter(([entryKey, entry]) => terms.every((term) => normalize([entryKey, entry.summary, ...entry.steps, ...entry.examples.flatMap((item) => [item.q, item.a])].join(" ")).includes(term))) : [];
  const close = () => { setOpen(false); setQuery(""); setView(null); };
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);
  const whatsapp = `https://wa.me/${SUPPORT}?text=${encodeURIComponent(`Hola, tengo un problema en ${key} de Completo Fiscal.`)}`;
  return <>
    <button className="help-sidebar-button" type="button" onClick={() => setOpen(true)}><CircleHelp size={17} /> Centro de ayuda</button>
    <button className="help-fab" type="button" onClick={() => setOpen(true)} aria-label="Centro de ayuda"><CircleHelp size={22} /></button>
    {open && <div className="help-overlay" role="dialog" aria-modal="true" aria-label="Centro de ayuda"><button className="help-scrim" type="button" aria-label="Cerrar al hacer clic fuera" onClick={close} /><section className="help-panel"><header><h2><CircleHelp size={19} /> Ayuda · {key}</h2><button type="button" onClick={close} aria-label="Cerrar centro de ayuda"><X size={18} /></button></header><div className="help-search"><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Busca: anular boleta, cierre, voucher…" aria-label="Buscar en el centro de ayuda" /></div><div className="help-body">{terms.length ? results.length ? <div className="help-results">{results.map(([resultKey, result]) => <button type="button" key={resultKey} onClick={() => { setView(resultKey); setQuery(""); }}><strong>{resultKey}</strong><span>{result.summary}</span></button>)}</div> : <p>Sin resultados. Puedes reportarlo abajo.</p> : <>{view && view !== currentKey && <button className="help-back" type="button" onClick={() => setView(null)}>← Volver a esta pantalla</button>}<h3>Ejemplos</h3>{guide.examples.map((item) => <div className="help-example" key={item.q}><strong>{item.q}</strong><p>{item.a}</p></div>)}<h3>Cómo funciona</h3><ul>{guide.steps.map((step) => <li key={step}>{step}</li>)}</ul><p className="help-summary">{guide.summary}</p></>}</div><footer><span>¿Algo no funciona?</span><a className="primary-button" href={whatsapp} target="_blank" rel="noreferrer" onClick={close}>Reportar por WhatsApp</a></footer></section></div>}
  </>;
}
