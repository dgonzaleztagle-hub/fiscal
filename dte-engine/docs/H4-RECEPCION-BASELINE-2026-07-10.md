# Baseline Hito 4 — recepción, decisiones y compras

## Autoridad y plazo

Fuentes verificadas el 2026-07-10:

- Ley 19.983 vigente, artículo 3:
  https://www.bcn.cl/leychile/navegar?idNorma=233421
- Guía SII Registro de Aceptación o Reclamo DTE 2.0:
  https://www.sii.cl/factura_electronica/GUIA_aceptacion_reclamo_dte.pdf
- Web Service Registro Reclamo DTE 1.1:
  https://www.sii.cl/factura_electronica/Webservice_Registro_Reclamo_DTE_V1.1.pdf

La factura puede reclamarse dentro de ocho días corridos desde su recepción. Una
aceptación expresa la vuelve irrevocablemente aceptada. Completo sólo calcula alertas
desde el timestamp autoritativo de recepción del SII; una carga manual de XML deja el
plazo como desconocido. El motor no ejecuta aceptación automática.

## Implementado sin conexión externa

- parser XML endurecido, límite de tamaño y entidades externas deshabilitadas;
- XSD oficial fijado, XMLDSig, RUT receptor y unicidad del Documento;
- XML recibido inmutable, SHA-256 y deduplicación por identidad tributaria;
- aislamiento multi-tenant;
- cinco acciones oficiales: ACD (acepta contenido), ERM (recibo de mercaderías o
  servicios), RCD, RFP y RFT como intenciones inmutables;
- ACD y ERM pueden coexistir; cualquiera bloquea reclamos posteriores;
- un reclamo previo bloquea ACD/ERM, mientras reclamos distintos pueden quedar como
  eventos separados según la matriz publicada por el SII;
- intentos durables y resultado `unknown` ante timeout posterior al envío;
- reconciliación mediante consulta, sin reenvío ciego;
- gateway completamente simulado, reemplazable por el WS oficial más adelante;
- codec SOAP puro para las cinco acciones, historial y fecha de recepción, sin red;
- canal de ingestión común para upload, correo y futuro conector oficial;
- lotes de adjuntos de correo aislados: un XML malo no descarta los válidos y PDF se
  ignora como fuente tributaria;
- observaciones SII append-only para enriquecer una carga previa sin reescribirla;
- detalle de líneas recibido e inmutable;
- clasificación versionada hacia gasto, inventario, activo fijo, mixto o pendiente;
- asignación por línea a gasto, inventario o activo fijo con referencias al control plane;
- referencias opacas a proveedores/categorías del control plane, sin duplicarlos.

RCV local:

- snapshots mensuales inmutables, versionados e idempotentes;
- importación canónica sintética/CSV preparada para futuro conector oficial;
- conciliación por identidad tributaria y montos: coincide, diferencia, sólo XML o sólo
  RCV;
- contrato HTTP y vista mensual de diferencias.

## Pendiente

- autenticar y probar el WS oficial con certificado real;
- importar timestamp de recepción desde conector oficial;
- persistir respuestas XML/SOAP exactas obtenidas en certificación;
- conectar un buzón real y proveedor de correo;
- OCR auxiliar para clasificación visual, nunca como fuente tributaria;
- confirmar formatos exactos de descarga RCV con muestras reales.

No se ejecutó ninguna acción en el SII ni se usaron credenciales reales.
