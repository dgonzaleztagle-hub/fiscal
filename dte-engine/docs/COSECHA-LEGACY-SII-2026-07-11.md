# Cosecha del repositorio legacy SII — 2026-07-11

## Decisión

Completo Fiscal conservará un conector de lectura basado en navegador/sesión SII para las
consultas sin alternativa oficial documentada. No se portará literalmente el servidor
Flask/Playwright original: se reescribirá como adaptador aislado, durable y auditable. Queda
fuera del camino de firma, emisión, certificación y persistencia tributaria autoritativa.

## Activos que sí aportan

1. **RCV compras y ventas.** El discovery documenta resumen, detalle y exportación por
   período, tipo documental y estado contable. Sirve para construir fixtures sanitizados,
   mapear columnas reales y validar el importador/snapshot RCV ya existente.
2. **F29.** Existen trazas de propuesta, historial de declaraciones, BHE asociadas y PPMO.
   Sirven para un futuro cockpit de conciliación: comparar lo calculado desde XML/RCV con la
   propuesta del SII. No autorizan a presentar ni rectificar declaraciones automáticamente.
3. **BHE emitidas y recibidas.** El parser mensual/anual y sus totales pueden convertirse en
   fixtures para integrar Completo Personas (honorarios/retenciones) con Fiscal/F29.
4. **F22 y situación del contribuyente.** El catálogo de estados, eventos y declaraciones
   puede apoyar una futura vista de cumplimiento para pymes y un onboarding asistido. Queda
   fuera de la primera versión vendible de Fiscal.
5. **Metadatos de onboarding.** Actividades económicas, régimen, direcciones y atributos del
   contribuyente podrían reducir digitación, siempre mediante una fuente permitida y con
   confirmación del usuario.

## Lo que no se trasladará

- credenciales, cookies, RUT, domicilios, folios o declaraciones capturados de contribuyentes;
- HTML/JSON crudo que contenga datos reales;
- técnicas para ocultar automatización o evadir controles del sitio;
- supuestos de CAPTCHA o tokens observados en una sesión tratados como contrato estable;
- rutas internas del SII tratadas como API estable u oficial;
- servidor Flask, parsers monetarios con `float`, excepciones silenciadas o credenciales en
  cada request;
- código que permita presentar F29/F22 o realizar cambios en el SII.

## Trabajo antes de la mudanza

1. La credencial versionada corresponde a Transportes Roda, tenant de prueba autorizado por
   su titular y actualmente sin movimiento. Aun así, no debe copiarse ni quedar hardcodeada:
   se trasladará a un vault y deberá rotarse antes de cualquier operación productiva. Borrarla
   del último commit no la elimina de la historia legacy.
2. No copiar el `.git`, `.env*`, DOM, JSON ni capturas del repositorio legacy.
3. Crear fixtures propios sin identificadores reales para RCV, F29 y BHE.
4. Definir mapeos tipados legacy → dominio Fiscal y probar montos como enteros CLP.
5. Mantener precedencia: servicios/documentación oficial cuando existan → importación de
   archivos → conector de lectura por sesión. El SII sigue siendo la autoridad; el scraper
   captura una vista y ésta se conserva como snapshot con origen, fecha y hash.

## Arquitectura fijada para el conector

- proceso/worker separado del `dte-engine`, sin acceso a claves CAF ni firma DTE;
- credenciales por tenant resueltas desde vault y nunca recibidas por el frontend;
- sesión efímera, logout y destrucción del contexto al terminar;
- lectura idempotente por tenant, período y recurso, con rate limit y backoff;
- intervención humana explícita ante CAPTCHA, cambio de flujo o autenticación adicional;
- respuestas crudas cifradas y snapshots normalizados con hash, sin reescribir versiones;
- selectores/endpoints versionados y pruebas de contrato para detectar cambios del SII;
- prohibido presentar F29/F22 o realizar mutaciones desde el conector inicial.

## Backlog aprovechable

- **Ahora:** fixture realista RCV y prueba diferencial contra `RcvRepository`/conciliación.
- **Después de emisión completa:** reporte de diferencias XML ↔ RCV ↔ propuesta F29.
- **Integración Personas:** BHE recibidas, retención y total informativo para F29.
- **Futuro:** estado F22 y situación tributaria como producto de cumplimiento, tras revisión
  legal/técnica específica.
