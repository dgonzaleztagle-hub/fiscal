# Decisión futura — Completo QA Police

El piloto ya comenzó sobre Completo Fiscal después de estabilizar el flujo offline. La patrulla
inicial vive en `fiscal-console/tests/e2e/police.spec.ts` y corre en escritorio y móvil.

## Objetivo

Un sistema independiente que use navegador, API e invariantes para intentar romper los
productos como lo harían usuarios reales, torpes, concurrentes o maliciosos. Todo
hallazgo confirmado deberá convertirse en regresión determinista.

## Roles previstos

- inspector de recorrido y navegación;
- usuario confundido: doble clic, recarga, atrás y abandono;
- inspector multi-tenant y permisos;
- inspector de fallas de red y resultados ambiguos;
- inspector visual, responsive y accesibilidad;
- inspector de dominio fiscal/gastronómico;
- fiscal de evidencia, encargado de reproducir antes de aceptar un hallazgo.

## Operativos

- patrulla de PR rápida;
- ejecución nocturna exploratoria;
- operativo preproducción con cero P0/P1.

Cada parte deberá registrar producto, commit, ambiente, persona, misión, pasos,
resultado esperado/observado, severidad, captura, logs, request correlacionado y test
preventivo. Producción será sólo lectura; las pruebas destructivas vivirán en ambientes
reiniciables con datos sintéticos y allowlist de dominios.

La primera implementación piloto será Fiscal cuando consola, permisos, backend y
recorridos críticos sean estables. Luego se extraerá el núcleo para Completo Gastro.

## Patrulla inicial implementada — 2026-07-12

- shell y ambiente persistentes en cierre, expediente, pagos y F29;
- ausencia de overflow horizontal en escritorio y Pixel 7;
- botón de importación deshabilitado mientras sólo existe integración backend;
- descarga de expediente bloqueada si está incompleto;
- navegación cierre ↔ expediente y comportamiento del botón atrás;
- cockpit de certificación hidratado antes de aceptar clics;
- ensayo de timeout posterior al upload con resultado `unknown`;
- centro de ayuda contextual: búsqueda, soporte y cierre con teclado;
- persistencia del borrador ante navegación accidental;
- 24 recorridos Playwright verdes entre desktop y mobile.

La patrulla detectó y corrigió dos problemas reales: hidratación perdida al hacer clic temprano
en el cockpit y bloqueo de recursos dev al probar `127.0.0.1` contra un servidor levantado como
`localhost`.

La primera patrulla autónoma por roles encontró y dejó cubiertas regresiones adicionales:
ventas sin voucher, referencias DTE inexistentes, conciliaciones con diferencias aceptadas
por el expediente e identidad de auditoría controlada por el request. La patrulla visual quedó
pendiente por contención de la sesión Chrome; no se registraron hallazgos ficticios.
