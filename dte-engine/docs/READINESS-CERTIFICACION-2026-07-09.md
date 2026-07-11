# Readiness para certificación SII

## Veredicto

El flujo está listo para un **ensayo integrado con credenciales reales, sin descargar aún
el CAF de cinco folios**. No está autorizado para producción ni para iniciar la ventana
de 24 horas.

## Cerrado y verificado

- cinco casos oficiales modelados con sus referencias `SET/CASO-N`;
- CAF autenticado, TED, DTE 39, XMLDSig y EnvioBOLETA;
- RCOF con rangos, anulaciones, firma y XSD oficial;
- ledger transaccional de folios, sobres, intentos y Track ID;
- REST de boletas y vía DTE heredada del RCOF, sin reintentos ciegos;
- clasificación conservadora de estados SII;
- ticket térmico, PDF417 decodificado independientemente al TED original y consulta opaca;
- dry-run: cinco DTE, un sobre, un RCOF y dos Track ID simulados;
- 79 pruebas y `pip check` limpios;
- Completo compila con outbox, perfil tributario, clasificación de productos y vista operativa.

## Bloqueos antes de descargar el CAF

1. Obtener PFX/P12 acreditado y probar contraseña, vigencia, identidad y firma.
2. Obtener el certificado público SII/IDK oficial aplicable al CAF de certificación.
3. Aplicar y probar la migración de Completo en una base de staging; hoy está sólo versionada.
4. Desplegar el motor y la consulta pública bajo HTTPS estable.
5. Configurar el perfil real de Roda y comprobar que la URL impresa responde.
6. Ejecutar una autenticación real de certificación (semilla/token) sin emitir folios.
7. Confirmar con el portal/Mesa de Ayuda que el RCOF del set usa el upload DTE documentado.
8. Preparar respaldo, reloj sincronizado, operador y evidencia del runbook.

## Bloqueos antes de producción multi-tenant

- worker cloud que reclame la outbox y gestione credencial del motor por tenant;
- almacenamiento cifrado y respaldo de XML por al menos el período legal aplicable;
- validación de cadena, uso de clave y revocación del certificado;
- monitoreo de RCOF diario, pendientes, rechazos y `unknown`;
- rate limiting y auditoría de acceso a representaciones;
- notas de crédito/anulación y boleta 41 si se comercializan;
- pruebas de carga, recuperación, rotación de certificados/CAF y continuidad;
- aplicación RLS verificada en Supabase, no sólo revisión estática del SQL.

## Regla de salida

El CAF de cinco folios se descarga únicamente cuando los ocho bloqueos de certificación
estén resueltos y el runbook pueda ejecutarse seguido. Descargarlo antes no aporta una
prueba adicional y sí inicia el plazo comunicado por el SII.
