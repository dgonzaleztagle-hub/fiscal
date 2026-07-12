"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Boxes,
  Building2,
  ChevronDown,
  CircleHelp,
  ClipboardCheck,
  CloudCog,
  FileChartColumn,
  Landmark,
  FileInput,
  FileOutput,
  Gauge,
  ScanSearch,
  ReceiptText,
  Send,
  Settings,
  ShieldCheck,
  Tags,
  UsersRound,
} from "lucide-react";
import { EnvironmentBanner } from "./environment-banner";

const navigation = [
  { href: "/", label: "Inicio", icon: Gauge },
  { href: "/emitir", label: "Emitir", icon: FileOutput, accent: true },
  { href: "/documentos", label: "Documentos", icon: ReceiptText },
  { href: "/recibidos", label: "Recibidos", icon: FileInput, count: 3 },
  { divider: true, label: "Gestión" },
  { href: "/clientes", label: "Clientes", icon: UsersRound },
  { href: "/proveedores", label: "Proveedores", icon: Building2 },
  { href: "/productos", label: "Productos", icon: Tags },
  { divider: true, label: "Operación" },
  { href: "/folios", label: "Folios y CAF", icon: Boxes },
  { href: "/envios", label: "Envíos SII", icon: Send },
  { href: "/reportes", label: "Reportes", icon: ClipboardCheck },
  { divider: true, label: "SII conectado" },
  { href: "/rcv", label: "Registro compras/ventas", icon: ScanSearch },
  { href: "/f29", label: "Propuesta F29", icon: FileChartColumn },
  { href: "/bhe", label: "Boletas de honorarios", icon: ReceiptText },
  { href: "/situacion", label: "Situación tributaria", icon: Landmark },
  { href: "/sincronizaciones", label: "Sincronizaciones", icon: CloudCog },
  { href: "/certificacion", label: "Certificación", icon: ShieldCheck },
  { href: "/configuracion", label: "Configuración", icon: Settings },
] as const;

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/" className="brand" aria-label="Completo Fiscal, inicio">
          <span className="brand-mark"><ReceiptText size={20} /></span>
          <span><strong>Completo</strong><small>Fiscal</small></span>
        </Link>
        <button className="tenant-switch" type="button">
          <span className="tenant-avatar">ES</span>
          <span><strong>Empresa Sintética</strong><small>76.192.083-9</small></span>
          <ChevronDown size={15} />
        </button>
        <nav aria-label="Navegación fiscal">
          {navigation.map((item, index) => {
            if ("divider" in item) return <p className="nav-label" key={`${item.label}-${index}`}>{item.label}</p>;
            const Icon = item.icon;
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link className={`nav-link${active ? " active" : ""}${"accent" in item ? " nav-accent" : ""}`} href={item.href} key={item.href}>
                <Icon size={18} aria-hidden="true" /><span>{item.label}</span>
                {"count" in item && <em>{item.count}</em>}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <button type="button"><CircleHelp size={17} /> Centro de ayuda</button>
          <div className="operator"><span>DG</span><p><strong>Daniel González</strong><small>Administrador</small></p></div>
        </div>
      </aside>
      <div className="workspace">
        <EnvironmentBanner />
        <main>{children}</main>
      </div>
    </div>
  );
}
