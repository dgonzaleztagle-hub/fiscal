# Decisión futura — Completo QA Police

Se construirá después de estabilizar Completo Fiscal. No forma parte del camino crítico
actual y no debe retrasar los hitos 4/5 ni la preparación de certificación.

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
