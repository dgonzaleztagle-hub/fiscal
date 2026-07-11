# Plan de trabajo — motor DTE directo para Completo

**Estado:** plan inicial para nueva sesión de Codex  
**Fecha:** 2026-07-08  
**Repositorio:** `C:\proyectos\pluscontableapisii`  
**Rama sugerida para implementar:** `codex/dte-direct`  
**Primer hito:** generar, firmar, validar y enviar una boleta afecta tipo 39 en el ambiente
de certificación del SII, sin tocar producción.

---

## 1. Objetivo

Convertir la investigación ya realizada en este repositorio en una integración tributaria
propia para Completo, evitando un costo permanente por documento o por tenant.

El producto final debe:

- emitir DTE válidos para cada RUT/tenant autorizado;
- mantener un ledger de folios imposible de duplicar;
- custodiar certificados y CAF sin exponerlos al navegador ni a operadores;
- enviar documentos al SII y seguir su estado de forma asíncrona;
- conservar XML, respuestas y representaciones durante el período exigido;
- soportar posteriormente una caja central offline con rangos de folios acotados;
- exponer una API estable para que Completo no dependa del protocolo interno del SII;
- permitir temporalmente un proveedor externo como adaptador de respaldo.

No se busca convertir este repositorio en el POS ni acoplarlo al schema de Completo. Este
repositorio será el laboratorio y servicio tributario; Completo lo consumirá mediante un
contrato versionado.

---

## 2. Punto de partida real

### 2.1 Lo que ya existe y funciona

El repositorio contiene dos generaciones de integración:

1. `backend/`
   - Flask + Playwright.
   - Login con clave tributaria.
   - Sincronización de resúmenes RCV de compras y ventas.
   - API usada por PlusContable mediante Railway.

2. `proyecto-api/`
   - Investigación posterior mucho más profunda.
   - Catálogo de endpoints del SII derivado en 31 rondas.
   - RCV con resumen y detalle.
   - F29, F22, declaraciones juradas y BHE.
   - Extracción y normalización de respuestas.
   - Panel de exploración y flujo SSE.

Documento clave que debe leer la nueva sesión:

- `proyecto-api/discovery/ENDPOINTS_CATALOG.md`

Otros archivos de entrada:

- `README.md`
- `backend/README.md`
- `proyecto-api/MODELO_NEGOCIO.md`
- `proyecto-api/extractor.py`
- `backend/services/sii_scraper.py`
- `proyecto-api/middleware/auth.py`

### 2.2 Lo que todavía no existe

No hay un motor de emisión DTE. Faltan:

- carga y validación criptográfica de CAF;
- asignación transaccional de folios;
- construcción del XML de DTE;
- TED/timbre electrónico;
- firma XMLDSig;
- creación y firma de `EnvioBOLETA` / `EnvioDTE`;
- autenticación por certificado ante servicios de emisión;
- envío del XML y captura de Track ID;
- consulta y normalización de estados/rechazos;
- generación de PDF/ticket con PDF417;
- Resumen de Ventas Diarias/consumo de folios;
- notas de crédito asociadas;
- almacenamiento y auditoría de documentos emitidos;
- certificación automatizada contra fixtures del SII.

La investigación de `bolcore` presente en el catálogo es de consulta/validación y no
reemplaza este motor.

---

## 3. Fuentes y regla de propiedad intelectual

### 3.1 Fuente normativa

La implementación se deriva de documentación oficial del SII:

- API oficial de Boleta Electrónica:
  `https://www4c.sii.cl/bolcoreinternetui/api/`
- Instructivo técnico de Boleta Electrónica:
  `https://www.sii.cl/servicios_online/3532-instructivo_tecnico_be-3811.html`
- Documentación técnica de Factura Electrónica:
  `https://www.sii.cl/factura_electronica/tecnica.htm`
- Esquemas XML oficiales:
  `https://www.sii.cl/servicios_online/1039-formato_xml-1184.html`
- Formato DTE vigente:
  `https://www.sii.cl/factura_electronica/factura_mercado/formato_dte_202602.pdf`
- Instructivo de emisión:
  `https://www.sii.cl/factura_electronica/instructivo_emision.pdf`
- Ambiente de certificación:
  `https://maullin.sii.cl/`

Antes de implementar se deben descargar y versionar, con fecha y hash, los XSD y documentos
normativos necesarios. Los binarios/documentos descargados no se agregan al repositorio si
su licencia no lo permite; sí se registra su URL, versión y checksum.

### 3.2 LibreDTE como referencia

Referencia:

- Repositorio: `https://github.com/libredte/libredte-lib-core`
- Documentación: `https://core.libredte.cl/docs`

LibreDTE Core está licenciado bajo AGPL-3.0 y sus términos señalan que integrar su
biblioteca en otro software obliga a publicar ese software bajo AGPL. Completo mantendrá
código e identidad propios.

Reglas para este proyecto:

- no copiar código, fixtures, builders ni tests de LibreDTE;
- no agregar la biblioteca PHP como dependencia;
- no traducir archivos o clases línea por línea;
- no usar nombres internos de sus clases como diseño obligatorio;
- usar sus documentos públicos solo para detectar responsabilidades, casos límite y
  preguntas que luego se resuelven con la especificación oficial del SII;
- implementar con contratos y tests propios;
- si se consume temporalmente la API web de LibreDTE, hacerlo detrás de un adaptador y
  respetando sus términos de servicio;
- cualquier uso futuro de código AGPL debe quedar en un servicio claramente separado,
  publicable y revisado legalmente. No es el plan primario.

### 3.3 Qué aprendemos de su arquitectura sin copiarla

La revisión pública de LibreDTE confirma que un motor maduro separa:

- partes comerciales: emisor, receptor, mandatario;
- identificación y autorización: CAF y rangos;
- documento: normalización, construcción, timbre, firma y validación;
- sobre de envío;
- intercambio: SII/email;
- libros y Resumen de Ventas Diarias;
- estados y validación remota.

También confirma el soporte mínimo relevante:

- 33 factura afecta;
- 34 factura exenta;
- 39 boleta afecta;
- 41 boleta exenta;
- 52 guía de despacho;
- 56 nota de débito;
- 61 nota de crédito.

Para Completo se implementará primero 39, luego 41 y 61. Facturas 33/34 vienen después de
cerrar completamente el ciclo de boletas.

---

## 4. Arquitectura propuesta

Crear un servicio nuevo dentro del repositorio, sin mezclarlo con el scraper:

```text
pluscontableapisii/
├── backend/                 # legado RCV
├── proyecto-api/            # lector SII e investigación actual
└── dte-engine/              # nuevo motor de emisión
    ├── src/
    │   ├── domain/
    │   ├── application/
    │   ├── adapters/
    │   │   ├── sii/
    │   │   ├── storage/
    │   │   └── crypto/
    │   └── api/
    ├── tests/
    │   ├── unit/
    │   ├── fixtures/
    │   ├── contract/
    │   └── certification/
    ├── migrations/
    ├── Dockerfile
    └── README.md
```

### 4.1 Decisión de lenguaje

No decidir por inercia.

Evaluar con un spike pequeño:

- **Python:** reutiliza el stack actual, buenas bibliotecas XML/crypto, rápido para
  investigación. Candidato preferido para el primer spike.
- **Go:** binario simple, concurrencia y despliegue excelentes; atractivo para el agente
  local/offline posterior.
- **TypeScript:** comparte tipos con Completo, pero XMLDSig y compatibilidad exacta con el
  SII pueden dar más fricción.

El spike debe probar, antes de elegir:

1. XML con encoding requerido por el SII;
2. validación XSD;
3. XMLDSig verificable;
4. firma de TED con la clave del CAF;
5. carga segura de PFX/P12;
6. PDF417 o representación térmica.

### 4.2 Contratos de dominio

Definir interfaces propias antes de integrar el SII:

```text
DteIssuer
  issue(command) -> FiscalDocument

FolioAllocator
  reserve(tenant, document_type, device?) -> FolioLease
  consume(lease, document_id)
  void(lease, reason)

CredentialVault
  store_certificate(...)
  sign(...)
  metadata(...)

CafRepository
  import(...)
  validate(...)
  reserve_range(...)

TaxAuthorityGateway
  authenticate(...)
  submit(envelope) -> tracking_id
  check_submission(tracking_id)
  validate_document(...)

FiscalRenderer
  render_ticket(...)
  render_pdf(...)
```

Completo no debe conocer XML, CAF, certificados ni endpoints del SII. Enviará un comando
canónico y recibirá estado + representación.

### 4.3 Modelo mínimo de datos

Tablas propuestas, todas con `tenant_id` y auditoría:

- `fiscal_taxpayers`
- `fiscal_credentials`
- `fiscal_cafs`
- `fiscal_caf_ranges`
- `fiscal_folio_leases`
- `fiscal_documents`
- `fiscal_document_lines`
- `fiscal_envelopes`
- `fiscal_submission_attempts`
- `fiscal_events`
- `fiscal_daily_summaries`
- `fiscal_device_ranges` (solo cuando se diseñe offline)

Invariantes:

- `(taxpayer_rut, document_type, folio)` es único;
- un folio pasa por una máquina de estados append-only;
- ningún retry crea un nuevo documento si conserva la misma idempotency key;
- XML emitido no se reescribe;
- correcciones posteriores son documentos nuevos, normalmente nota de crédito/débito;
- los estados locales y del SII se conservan por separado;
- cada transición registra actor, origen y timestamp.

---

## 5. Seguridad

### 5.1 Certificados

- Nunca almacenar PFX, contraseña o clave privada en columnas legibles por cliente.
- Cifrado envelope por tenant.
- Llave maestra fuera de PostgreSQL.
- Operación de firma dentro del worker, no en Next.js ni navegador.
- Exponer metadatos solamente: RUT, serial, emisor, vencimiento y estado.
- Alertas de vencimiento 60/30/15/7 días.
- Rotación sin invalidar documentos históricos.

### 5.2 CAF

- Validar firma, RUT, tipo, vigencia y rango antes de activar.
- Cifrar la clave privada incluida en el CAF.
- No entregar CAF completo al frontend.
- El allocator central debe usar transacción/bloqueo de fila.
- Nunca asignar el mismo rango simultáneamente a nube y caja offline.

### 5.3 API

- Reemplazar el API key fijo actual antes de conectar Completo.
- Autenticación servicio-a-servicio con claves rotables o JWT de corta vida.
- Idempotency key obligatoria en emisión.
- Rate limit por tenant y por RUT.
- Allowlist de acciones por entorno.
- Producción deshabilitada por defecto.
- No registrar XML completo, certificados, CAF o contraseñas en logs.

### 5.4 Scraper existente

El lector SII actual puede mantenerse, pero no se usa para emitir DTE. Debe evolucionar a
workers aislados y auditados. La sesión nueva debe registrar como deuda:

- credenciales tributarias actualmente transportadas en cada request;
- clave de API de desarrollo fija;
- scraping frágil frente a cambios de frontend;
- límites de sesiones concurrentes del SII;
- necesidad de logout garantizado;
- ausencia de test automatizado robusto.

Las credenciales de Transportes Roda son material de prueba autorizado por Daniel, pero no
se deben copiar a nuevos archivos, logs, fixtures o commits.

---

## 6. Máquina de estados

Estado local sugerido:

```text
draft
  -> folio_reserved
  -> built
  -> signed
  -> queued
  -> submitted
  -> accepted | observed | rejected
  -> credited | voided
```

Estados adicionales de operación:

- `retryable_error`
- `manual_review`
- `offline_pending`
- `unknown_remote_state`

Principio: una venta nunca se revierte automáticamente porque el SII no responda. La venta
y el DTE son máquinas de estado relacionadas, pero distintas.

---

## 7. Roadmap de implementación

### Fase A — Reproducibilidad y baseline

- Crear rama `codex/dte-direct`.
- Levantar ambos backends existentes.
- Documentar cuál está desplegado hoy.
- Agregar pytest y smoke tests sin credenciales.
- Crear un adaptador falso del SII.
- Capturar métricas de login, sesión, RCV y logout.
- Separar configuración de certificación y producción.

**Salida:** repositorio instalable y testeable por una sesión nueva.

### Fase B — Spike criptográfico local

- Cargar certificado PFX de prueba.
- Cargar CAF de certificación.
- Verificar firma y metadatos de ambos.
- Construir TED.
- Generar XML tipo 39 con datos mínimos.
- Firmar XML.
- Validar contra XSD oficial.
- Verificar la firma con una herramienta independiente.

**Salida:** XML local válido según schema, todavía sin enviar.

### Fase C — Envío de boleta 39 a certificación

- Obtener semilla/token por certificado.
- Construir `EnvioBOLETA`.
- Enviar al ambiente de certificación.
- Persistir Track ID.
- Consultar hasta estado terminal con backoff.
- Normalizar errores del SII.
- Guardar request/response sanitizados.

**Salida:** primera boleta 39 aceptada por el SII en certificación.

### Fase D — Producto mínimo de boletas

- API autenticada e idempotente.
- Importación segura de certificado y CAF.
- Allocator transaccional de folios.
- Tipos 39 y 41.
- Nota de crédito 61.
- Ticket térmico/PDF.
- Resumen de Ventas Diarias.
- Reconciliación con RCV usando el lector existente.
- Dashboard mínimo de documentos observados/rechazados.

**Salida:** ciclo completo de boleta, corrección y conciliación.

### Fase E — Facturas

- Tipo 33 y 34.
- Receptor obligatorio y validaciones B2B.
- Intercambio de XML con receptor.
- Acuse de recibo y respuesta comercial.
- Nota de débito 56.
- Guía 52 si el roadmap de Completo lo requiere.

### Fase F — Caja offline

Solo después de estabilizar emisión cloud:

- agente local de caja;
- SQLite;
- rango exclusivo y pequeño de folios;
- certificado protegido por keystore del SO;
- emisión, ticket y journal offline;
- sincronización idempotente;
- protocolo para equipo perdido/roto;
- bloqueo de nuevos rangos hasta reconciliar el anterior.

---

## 8. Estrategia de pruebas

### 8.1 Unitarias

- totales neto/IVA/exento;
- redondeos;
- descuentos y recargos;
- normalización de RUT y fechas;
- allocator bajo concurrencia;
- máquina de estados;
- idempotencia;
- validación de CAF y certificado;
- construcción determinista de TED/XML.

### 8.2 Contractuales

- XSD oficial;
- verificación XMLDSig con segunda implementación;
- fixtures propios creados desde el set oficial del SII;
- respuestas conocidas del ambiente de certificación;
- adaptador SimpleAPI opcional usado solo como comparación, no como fuente normativa.

### 8.3 Integración

- certificado inválido/vencido;
- CAF de otro RUT;
- folio fuera de rango;
- documento duplicado;
- timeout después de enviar pero antes de recibir Track ID;
- SII acepta envío y la respuesta local se pierde;
- rechazo recuperable y no recuperable;
- nota de crédito asociada;
- concurrencia de varias cajas/órdenes;
- caída del worker durante cada transición.

### 8.4 Regla para producción

No declarar un tipo DTE soportado hasta:

- pasar fixtures oficiales;
- pasar validación XSD y firma independiente;
- ser aceptado en certificación;
- soportar consulta de estado;
- soportar corrección/anulación correspondiente;
- tener runbook y alertas;
- haber ensayado restauración desde backup.

---

## 9. Primer backlog para la nueva sesión

La primera sesión dentro de este repo debe hacer, en orden:

1. Leer este documento completo.
2. Leer `README.md`, `backend/README.md` y `ENDPOINTS_CATALOG.md`.
3. Verificar `git status` y no tocar cambios ajenos.
4. Crear la rama `codex/dte-direct`.
5. Inventariar qué código de `backend/` quedó superado por `proyecto-api/`.
6. Confirmar qué servicio exacto está desplegado en Railway.
7. Crear `dte-engine/README.md` con el contrato del spike.
8. Elegir lenguaje mediante la prueba criptográfica, no por preferencia.
9. Descargar referencias oficiales y registrar versiones/checksums.
10. Diseñar fixtures sintéticos: nunca agregar credenciales reales al test suite.
11. Implementar primero el validador/cargador de CAF y certificado.
12. Construir el XML 39 local.

No conectar Completo ni emitir en producción durante este backlog.

---

## 10. Decisiones abiertas que se resolverán con evidencia

- Lenguaje definitivo de `dte-engine`.
- KMS administrado versus Vault propio.
- PostgreSQL del servicio versus schema aislado en Supabase.
- Proceso exacto de certificación/habilitación por tenant.
- Quién compra y renueva el certificado digital.
- Quién solicita/importa CAF.
- Si SimpleAPI se usa como fallback real o solo como oráculo temporal.
- Precio y cuota mensual de `facturacion`.
- Política de folios offline y recuperación de caja.
- Retención exacta de XML, PDF y eventos.

Cada decisión debe registrar:

- alternativas;
- evidencia;
- costo;
- riesgo operacional;
- impacto multi-tenant;
- reversibilidad.

---

## 11. Definición del primer éxito

El primer hito se considera logrado solo si existe evidencia reproducible de:

1. CAF de certificación validado.
2. Certificado de prueba cargado y verificado.
3. Folio reservado exactamente una vez.
4. XML DTE 39 generado con código propio.
5. XML validado contra XSD oficial.
6. TED y firma verificados independientemente.
7. Sobre enviado a certificación.
8. Track ID persistido.
9. Estado final consultado.
10. Prueba automatizada y procedimiento documentado.

“Generamos un XML que se ve bien” no cuenta como emisión terminada.

