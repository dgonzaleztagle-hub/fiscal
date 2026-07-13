"use client";
import {useState} from "react";
import {Plus,Repeat2} from "lucide-react";
type Agreement={id:string;counterparty_name:string;description:string;amount:number;day_of_month:number;next_run_on:string;active:number};
export function RecurringCenter({initial,source}:{initial:Agreement[];source:"engine"|"demo"}){
 const[rows,setRows]=useState(initial),[open,setOpen]=useState(false),[name,setName]=useState(""),[description,setDescription]=useState(""),[amount,setAmount]=useState(0);
 async function submit(e:React.FormEvent){
  e.preventDefault();const payload={branch_id:"main",counterparty_ref:`manual:${name}`,counterparty_name:name,description,amount,day_of_month:15,next_run_on:"2026-08-15"};
  const response=await fetch("/api/recurring-agreements",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  if(response.ok){const record=await response.json() as Agreement;setRows(old=>[...old,record])}
  else if(response.status===503){setRows(old=>[...old,{...payload,id:`demo-${Date.now()}`,active:1}]);sessionStorage.setItem(`completo-fiscal:recurring:${Date.now()}`,JSON.stringify(payload))}
  setOpen(false);
 }
 return <div className="page section-page"><header className="page-header"><div><p className="eyebrow">Facturación recurrente</p><h1>Acuerdos mensuales</h1><p>Generan borradores revisables; nunca emiten automáticamente por defecto.</p></div><button className="primary-button" onClick={()=>setOpen(true)}><Plus/>Nuevo acuerdo</button></header>{open&&<form className="panel wizard-form compact-form" onSubmit={submit}><label>Cliente<input required value={name} onChange={e=>setName(e.target.value)}/></label><label>Concepto<input required value={description} onChange={e=>setDescription(e.target.value)}/></label><label>Monto<input required min="1" type="number" value={amount||""} onChange={e=>setAmount(Number(e.target.value))}/></label><button className="primary-button">Guardar acuerdo</button></form>}<section className="panel approvals-list">{rows.length?rows.map(row=><article key={row.id}><div><strong>{row.counterparty_name}</strong><p>{row.description}</p></div><b>${row.amount.toLocaleString("es-CL")}</b><em className="received-status neutral">Día {row.day_of_month}</em><span><Repeat2/></span></article>):<div className="empty-inline"><Repeat2/><p>No existen acuerdos todavía · {source==="engine"?"motor conectado":"demo"}</p></div>}</section></div>;
}
