"use client";

import { useMemo, useState } from "react";
import { Building2, CirclePlus, Mail, MapPin, PackageSearch, Search } from "lucide-react";

const clients = [
  { name: "Cliente Sintético SpA", rut: "11.111.111-1", activity: "Servicios empresariales", commune: "Providencia", email: "facturas@cliente.demo" },
  { name: "Eventos Cordillera Ltda.", rut: "76.192.083-9", activity: "Producción de eventos", commune: "Las Condes", email: "dte@eventos.demo" },
  { name: "Fundación Mesa Abierta", rut: "65.123.456-7", activity: "Actividades sin fines de lucro", commune: "Santiago", email: "administracion@fundacion.demo" },
];

const products = [
  { sku: "SERV-MENSUAL", name: "Servicio mensual Completo", tax: "Afecto", mode: "Precio neto", price: 59990 },
  { sku: "ONBOARDING", name: "Configuración y puesta en marcha", tax: "Afecto", mode: "Precio neto", price: 89990 },
  { sku: "CAP-EXENTA", name: "Capacitación exenta", tax: "Exento", mode: "Precio neto", price: 45000 },
];

export function ClientsSection() {
  const [query, setQuery] = useState("");
  const visible = useMemo(() => clients.filter((client) => `${client.name} ${client.rut}`.toLowerCase().includes(query.toLowerCase())), [query]);
  return <div className="page section-page"><header className="page-header"><div><p className="eyebrow">Maestros · Receptores</p><h1>Clientes listos para facturar</h1><p>Guarda una vez los antecedentes tributarios y evita reescribirlos en cada documento.</p></div><button className="primary-button" type="button"><CirclePlus size={17} /> Nuevo cliente</button></header><div className="catalog-toolbar"><label><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por nombre o RUT" /></label><span>{visible.length} receptores sintéticos</span></div><div className="client-grid">{visible.map((client) => <article className="panel client-card" key={client.rut}><div className="client-title"><span><Building2 size={19} /></span><div><h2>{client.name}</h2><p>{client.rut}</p></div></div><dl><div><dt>Giro</dt><dd>{client.activity}</dd></div><div><dt><MapPin size={13} /> Comuna</dt><dd>{client.commune}</dd></div><div><dt><Mail size={13} /> Intercambio</dt><dd>{client.email}</dd></div></dl><button type="button">Usar en una factura</button></article>)}</div></div>;
}

export function ProductsSection() {
  return <div className="page section-page"><header className="page-header"><div><p className="eyebrow">Maestros · Catálogo tributario</p><h1>Productos con reglas claras</h1><p>Cada ítem conserva su clasificación y evita que quien factura deba decidir el IVA manualmente.</p></div><button className="primary-button" type="button"><CirclePlus size={17} /> Nuevo producto</button></header><section className="panel product-catalog"><div className="catalog-explainer"><PackageSearch size={20} /><div><strong>Precio fiscal explícito</strong><p>Las facturas trabajan con precio neto; las boletas muestran el precio final al consumidor.</p></div></div><div className="product-head"><span>Producto</span><span>Tributación</span><span>Modo</span><span>Precio de referencia</span></div>{products.map((product) => <div className="product-row" key={product.sku}><div><small>{product.sku}</small><strong>{product.name}</strong></div><span className={product.tax === "Exento" ? "tax-exempt" : "tax-affected"}>{product.tax}</span><span>{product.mode}</span><b>{formatCurrency(product.price)}</b></div>)}</section></div>;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(value);
}
