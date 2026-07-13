import Link from "next/link";
import { AlertTriangle,ArrowDownRight,ArrowRight,ArrowUpRight,Boxes,Building2,CalendarClock,CheckCircle2,CircleDollarSign,ClipboardCheck,FileText,PackagePlus,Plus,TrendingUp } from "lucide-react";
import { fiscalSection } from "@/lib/fiscal-api";

type Area="ventas"|"compras"|"inventario"|"caja";
type CommercialApiRow={number:number;counterparty_name:string;valid_until:string|null;total:number;status:string};
type Projection={incoming:number;outgoing:number;net:number;from_on:string;to_on:string};
type ProductApiRow={id:string;sku:string;name:string;unit:string};
type Row={code:string;name:string;detail:string;amount:number;state:string;tone:string};
const money=new Intl.NumberFormat("es-CL",{style:"currency",currency:"CLP",maximumFractionDigits:0});
const demoSales:Row[]=[
 {code:"COT-0018",name:"Arquitectura Norte SpA",detail:"Vence 20 jul",amount:475000,state:"Esperando cliente",tone:"warning"},
 {code:"OV-0007",name:"Comercial La Plaza Ltda.",detail:"Aceptada · lista para facturar",amount:892500,state:"Aceptada",tone:"success"},
];
const demoPurchases:Row[]=[
 {code:"OC-0031",name:"Distribuidora Central SpA",detail:"Entrega esperada 16 jul",amount:428400,state:"Aprobada",tone:"success"},
 {code:"OC-0032",name:"Servicios Frío Sur Ltda.",detail:"Supera límite de aprobación",amount:1260000,state:"Por aprobar",tone:"warning"},
];

export async function CommercialCenter({section}:{section:Area}){
 if(section==="inventario")return <Inventory result={await fiscalSection<ProductApiRow[]>("/v1/inventory/products")}/>;
 if(section==="caja")return <CashFlow result={await fiscalSection<Projection>("/v1/cash-flow/projection?from_on=2026-07-13&to_on=2026-08-09")}/>;
 const isSales=section==="ventas";
 const result=await fiscalSection<CommercialApiRow[]>(`/v1/commercial-documents?kind=${isSales?"quote":"purchase_order"}`);
 const rows:Row[]=result.data?.length?result.data.map(row=>({code:`${isSales?"COT":"OC"}-${String(row.number).padStart(4,"0")}`,name:row.counterparty_name,detail:row.valid_until?`Vence ${row.valid_until}`:"Sin vencimiento",amount:row.total,state:row.status,tone:row.status==="accepted"?"success":"neutral"})):(isSales?demoSales:demoPurchases);
 return <div className="page section-page commercial-page">
  <header className="page-header"><div><p className="eyebrow">{isSales?"Ciclo comercial":"Abastecimiento"}</p><h1>{isSales?"Ventas y cotizaciones":"Órdenes de compra"}</h1><p>{isSales?"Convierte una aceptación en orden, guía o factura sin volver a escribir.":"Cada solicitud conserva su aprobación, recepción, factura y pago."}</p></div><Link className="primary-button" href={isSales?"/ventas/nueva":"/compras/nueva"}><Plus size={17}/>{isSales?"Nueva cotización":"Nueva orden"}</Link></header>
  <div className="summary-grid"><Metric icon={isSales?FileText:ClipboardCheck} label={isSales?"Cotizaciones abiertas":"Órdenes abiertas"} value={String(rows.length)} detail={result.source==="engine"?"Motor conectado":"Datos sintéticos"}/><Metric icon={CheckCircle2} label="Requieren acción" value="2" detail="Revisión pendiente"/><Metric icon={CalendarClock} label="Esta semana" value="3" detail="Sin atrasos críticos"/></div>
  <section className="panel commercial-list"><div className="table-toolbar"><div><h2>{isSales?"Actividad comercial":"Compras en curso"}</h2><p>{result.source==="engine"?"Motor conectado":"Modo demostración · tenant sintético"}</p></div></div>{rows.map(row=><article key={row.code}><span className="commercial-code">{row.code}</span><div><strong>{row.name}</strong><p>{row.detail}</p></div><b>{money.format(row.amount)}</b><em className={`received-status ${row.tone}`}>{row.state}</em><button aria-label={`Revisar ${row.code}`} disabled><ArrowRight size={17}/></button></article>)}</section>
  <section className="tip-card"><CheckCircle2 size={21}/><div><strong>Nada de esto consume un folio</strong><p>El DTE nace sólo al confirmar la conversión.</p></div></section>
 </div>;
}

function Inventory({result}:{result:Awaited<ReturnType<typeof fiscalSection<ProductApiRow[]>>>}){
 const demo=[{name:"Café grano 1 kg",sku:"Bodega Central",unit:"18 un."},{name:"Vaso térmico 12 oz",sku:"Sucursal Centro",unit:"7 un."}];
 const items=result.data?.length?result.data:demo;
 return <div className="page section-page commercial-page"><header className="page-header"><div><p className="eyebrow">Existencias por sucursal</p><h1>Inventario</h1><p>Cada cambio conserva su causa.</p></div><Link className="primary-button" href="/inventario/movimiento"><PackagePlus size={17}/>Registrar movimiento</Link></header><div className="summary-grid"><Metric icon={Boxes} label="Productos controlados" value={String(items.length)} detail={result.source==="engine"?"Motor conectado":"Datos sintéticos"}/><Metric icon={AlertTriangle} label="Bajo mínimo" value="9" detail="2 sin existencia"/><Metric icon={Building2} label="Sucursales" value="3" detail="Vista consolidada"/></div><section className="panel commercial-list"><div className="table-toolbar"><div><h2>Existencias</h2><p>{result.source==="engine"?"Catálogo real":"Muestra demostrativa"}</p></div></div>{items.map(item=><article key={item.sku}><span className="stock-icon"><Boxes size={17}/></span><div><strong>{item.name}</strong><p>{item.sku}</p></div><b>{item.unit}</b><span>Movimiento trazable</span><em className="received-status neutral">Activo</em></article>)}</section></div>;
}

function CashFlow({result}:{result:Awaited<ReturnType<typeof fiscalSection<Projection>>>}){
 const weeks=[["Esta semana",2380000,1640000],["20–26 julio",3180000,3760000],["27 jul–2 ago",2410000,1890000]];
 const projected=result.data?.net??1420000;
 return <div className="page section-page commercial-page">
  <header className="page-header"><div><p className="eyebrow">Tesorería simple</p><h1>Caja proyectada</h1><p>Lo comprometido para cobrar y pagar, separado del dinero real.</p></div><Link className="secondary-button" href="/caja/importar"><CircleDollarSign size={17}/>Importar cartola</Link></header>
  <div className="treasury-actions"><Link className="primary-button" href="/caja/obligacion"><Plus size={16}/>Registrar cuenta</Link><Link className="secondary-button" href="/caja/pago">Registrar pago parcial</Link></div>
  <div className="projection-banner"><TrendingUp size={22}/><div><small>Resultado del período · {result.source==="engine"?"motor conectado":"demo"}</small><strong>{money.format(projected)}</strong><p>No es saldo bancario en línea</p></div></div>
  <section className="panel cash-weeks"><div className="table-toolbar"><div><h2>Próximas semanas</h2><p>Cobros y pagos con fecha registrada</p></div></div>{weeks.map(([label,income,outcome])=>{const net=Number(income)-Number(outcome);return <article key={String(label)}><strong>{label}</strong><span className="cash-in"><ArrowDownRight size={15}/>{money.format(Number(income))}</span><span className="cash-out"><ArrowUpRight size={15}/>{money.format(Number(outcome))}</span><b className={net<0?"negative":"positive"}>{money.format(net)}</b></article>})}</section>
  <section className="tip-card"><AlertTriangle size={21}/><div><strong>Hay una semana estrecha</strong><p>Puedes adelantar cobranza o reprogramar compromisos.</p></div></section>
 </div>;
}
function Metric({icon:Icon,label,value,detail}:{icon:typeof Boxes;label:string;value:string;detail:string}){return <article className="panel summary-card"><Icon/><div><small>{label}</small><strong>{value}</strong><p>{detail}</p></div></article>}
