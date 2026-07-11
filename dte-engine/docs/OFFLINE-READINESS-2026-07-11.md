# Corte de preparación offline — 2026-07-11

Este documento separa desarrollo pendiente de infraestructura/identidad pendiente.

## Verde local

- DTE 33, 34, 39, 41, 52, 56 y 61;
- CAF sintético, folios, TED, XMLDSig, XSD, sobres, RCOF y workers;
- PDF/ticket, intercambio, notas, guías y relaciones inmutables;
- recepción XML, cinco acciones del Registro Reclamo y SOAP puro;
- correo por adjuntos simulado, detalle de compras, clasificación y asignación por línea;
- snapshots RCV, conciliación y vistas;
- reportes CSV/XLSX/PDF y paquete ZIP con XML/manifiesto;
- backup/restore SQLite con hash e integrity check;
- SSO de un uso y onboarding modular;
- referencias de certificado y rotación sin almacenar secretos;
- OpenAPI y cliente TypeScript sincronizados;
- 197 pruebas, Ruff y build Next.js verdes.

## Bloqueado deliberadamente hasta contar con empresa/infraestructura

- PFX real y proveedor de vault;
- CAF reales y ventana de certificación;
- endpoints SII autenticados, Track IDs y respuestas reales;
- formato real descargado de RCV y timestamp oficial de recepción;
- PostgreSQL/Supabase privado y prueba administrada de backup/restore;
- HTTPS público, correo y observabilidad;
- despliegues reales para probar SSO Gastro ↔ Fiscal;
- carga de 100 tenants sobre PostgreSQL;
- Hoja Cero como tenant cero y Roda para certificación de boletas.

## No hacer todavía

- descargar CAF de cinco folios;
- cargar certificados en archivos del repositorio;
- aplicar migraciones al Supabase remoto;
- habilitar producción o enviar decisiones tributarias;
- afirmar certificación basándose sólo en simuladores.

El próximo paso útil antes de infraestructura es una auditoría final de seguridad/contratos
y completar runbooks. La Policía de Calidad se implementará después de estabilizar los
despliegues y recorridos reales.
