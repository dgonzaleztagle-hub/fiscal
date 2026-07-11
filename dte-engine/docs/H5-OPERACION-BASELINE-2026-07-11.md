# Baseline Hito 5 — operación e integración local

Estado local al 2026-07-11, sin servicios ni credenciales externas.

## Implementado

- reporte mensual derivado de XML inmutables para ventas y compras;
- CSV UTF-8, XLSX tipado y PDF reproducibles, paginados y acompañados por SHA-256;
- ZIP para contador con reportes, XML originales y manifiesto de hashes verificable;
- backup SQLite mediante API transaccional de SQLite, no copia en caliente;
- `PRAGMA integrity_check`, manifiesto con tamaño/hash y restauración en destino vacío;
- prueba de restauración que compara XML, hashes y eventos del ledger;
- SSO HMAC de un solo uso, máximo 60 segundos, ligado a usuario, tenant y destino;
- nonce consumido atómicamente y protegido contra reutilización, cambio de destino,
  expiración y manipulación;
- checklist de onboarding por entitlements sin POS obligatorio;
- registro de certificados por referencias `vault://`, fingerprint y rotación atómica;
- prueba que verifica que el schema no contiene PFX ni contraseña;
- requisitos sensibles Fiscal identificados para carga privada y acompañamiento;
- consola de onboarding, RCV, recibidos y decisión tributaria.

## Pendiente sin infraestructura real

- adaptador PostgreSQL/Supabase privado y prueba de restore administrado;
- vault real y prueba con PFX/certificado próximo a vencer;
- SSO entre despliegues HTTPS de Gastro y Fiscal;
- correo real, portal público desplegado y proveedor de observabilidad;
- prueba de carga de 100 tenants sobre PostgreSQL;
- operacionalizar alertas y runbooks;
- Policía de Calidad después de estabilizar todos los recorridos.

Ningún resultado de este documento equivale a certificación ni autorización del SII.
