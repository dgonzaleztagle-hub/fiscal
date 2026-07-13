"use client";

import { useEffect, useState } from "react";

const filters = [["all", "Todos"], ["accepted", "Aceptados"], ["submitted", "En proceso"], ["attention", "Por resolver"], ["draft", "Borradores"]] as const;

export function DocumentFilters() {
  const [active, setActive] = useState("all");
  useEffect(() => { document.documentElement.dataset.documentFilter = active; return () => { delete document.documentElement.dataset.documentFilter; }; }, [active]);
  return <div className="filter-row" role="group" aria-label="Filtrar documentos">{filters.map(([id, label]) => <button className={active === id ? "active" : ""} aria-pressed={active === id} key={id} onClick={() => setActive(id)}>{label}</button>)}</div>;
}
