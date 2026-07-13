"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Boxes,
  Building2,
  ChevronDown,
  ClipboardCheck,
  CalendarCheck2,
  FolderArchive,
  CreditCard,
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
  HandCoins,
  ShoppingCart,
  Warehouse,
  ChartNoAxesCombined,
  Menu,
  X,
} from "lucide-react";
import { EnvironmentBanner } from "./environment-banner";
import { HelpCenter } from "./help-center";

const navigation = [
  { href: "/dashboard", label: "Inicio", icon: Gauge },
  { href: "/emitir", label: "Emitir", icon: FileOutput, accent: true },
  { href: "/documentos", label: "Documentos", icon: ReceiptText },
  { href: "/recibidos", label: "Recibidos", icon: FileInput, count: 3 },
  { divider: true, label: "Gestión" },
  { href: "/ventas", label: "Ventas y cotizaciones", icon: HandCoins },
  { href: "/compras", label: "Órdenes de compra", icon: ShoppingCart },
  { href: "/inventario", label: "Inventario", icon: Warehouse },
  { href: "/inventario/control", label: "Control de stock", icon: Boxes },
  { href: "/caja", label: "Caja proyectada", icon: ChartNoAxesCombined },
  { href: "/aprobaciones", label: "Aprobaciones", icon: ClipboardCheck },
  { href: "/recurrencia", label: "Acuerdos mensuales", icon: CalendarCheck2 },
  { href: "/clientes", label: "Clientes", icon: UsersRound },
  { href: "/proveedores", label: "Proveedores", icon: Building2 },
  { href: "/productos", label: "Productos", icon: Tags },
  { divider: true, label: "Operación" },
  { href: "/folios", label: "Folios y CAF", icon: Boxes },
  { href: "/envios", label: "Envíos SII", icon: Send },
  { href: "/reportes", label: "Reportes", icon: ClipboardCheck },
  { href: "/cierre", label: "Cierre mensual", icon: CalendarCheck2 },
  { href: "/expediente", label: "Expediente mensual", icon: FolderArchive },
  { href: "/pagos", label: "Pagos y vouchers", icon: CreditCard },
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/dashboard" className="brand" aria-label="Completo Fiscal, inicio">
          <span className="brand-mark"><ReceiptText size={20} /></span>
          <span><strong>Completo</strong><small>Fiscal</small></span>
        </Link>
        <button className="tenant-switch" type="button">
          <span className="tenant-avatar">ES</span>
          <span><strong>Empresa Sintética</strong><small>76.192.083-9</small></span>
          <ChevronDown size={15} />
        </button>
        <nav aria-label="Navegación fiscal" className={mobileMenuOpen ? "mobile-open" : ""}>
          {navigation.map((item, index) => {
            if ("divider" in item) return <p className="nav-label" key={`${item.label}-${index}`}>{item.label}</p>;
            const Icon = item.icon;
            const active = pathname.startsWith(item.href);
            return (
              <Link onClick={() => setMobileMenuOpen(false)} aria-label={item.label} className={`nav-link${active ? " active" : ""}${"accent" in item ? " nav-accent" : ""}`} href={item.href} key={item.href}>
                <Icon size={18} aria-hidden="true" /><span>{item.label}</span>
                {"count" in item && <em>{item.count}</em>}
              </Link>
            );
          })}
          <button aria-expanded={mobileMenuOpen} aria-label={mobileMenuOpen ? "Cerrar menú" : "Más secciones"} className="mobile-more" onClick={() => setMobileMenuOpen(value => !value)} type="button">{mobileMenuOpen ? <X size={21}/> : <Menu size={21}/>}<span>Más</span></button>
        </nav>
        <div className="sidebar-foot">
          <div className="operator"><span>DG</span><p><strong>Daniel González</strong><small>Administrador</small></p></div>
        </div>
      </aside>
      <div className="workspace">
        <EnvironmentBanner />
        <main>{children}</main>
      </div>
      <HelpCenter />
    </div>
  );
}
