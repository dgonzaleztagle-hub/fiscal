import { ArrowUpRight, MoreHorizontal } from "lucide-react";
import Link from "next/link";
import { fiscalDocuments } from "@/lib/fiscal-api";
import { clp } from "@/lib/format";
import { StatusPill } from "./status-pill";

export async function DocumentTable({ limit }: { limit?: number }) {
  const { rows, source, warning } = await fiscalDocuments(limit);
  return (
    <div className="table-wrap">
      <div className={`data-source ${source}`}>{source === "engine" ? "Motor fiscal conectado" : source === "sandbox" ? "Backend sandbox conectado · persistencia aislada" : "Datos demostrativos"}{warning ? ` · ${warning}` : ""}</div>
      <table className="documents-table">
        <thead><tr><th>Documento</th><th>Receptor</th><th>Emisión</th><th>Monto</th><th>Estado</th><th><span className="sr-only">Acciones</span></th></tr></thead>
        <tbody>{rows.map((row) => (
          <tr key={row.id} data-document-status={row.status}>
            <td><div className="document-cell"><span className="document-code">{row.kind}</span><span><strong>{row.label}</strong><small>Folio {row.folio}</small></span></div></td>
            <td>{row.receiver}</td><td className="muted-cell">{row.issuedAt}</td>
            <td className="amount">{row.amount ? clp(row.amount) : "—"}</td>
            <td><StatusPill status={row.status}>{row.statusLabel}</StatusPill></td>
            <td><Link className="icon-button" href={`/documentos/${row.id}`} aria-label={`Abrir ${row.label} ${row.folio}`}><MoreHorizontal size={18} /></Link></td>
          </tr>
        ))}</tbody>
      </table>
      <div className="table-mobile">{rows.map((row) => (
        <Link href={`/documentos/${row.id}`} key={row.id} data-document-status={row.status}><article><div className="document-cell"><span className="document-code">{row.kind}</span><span><strong>{row.label}</strong><small>Folio {row.folio} · {row.issuedAt}</small></span></div><strong>{row.amount ? clp(row.amount) : "—"}</strong><StatusPill status={row.status}>{row.statusLabel}</StatusPill><ArrowUpRight size={18} /></article></Link>
      ))}</div>
    </div>
  );
}
