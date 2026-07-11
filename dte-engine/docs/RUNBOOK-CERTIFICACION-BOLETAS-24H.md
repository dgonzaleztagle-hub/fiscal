# Runbook de certificación de boletas — TRANSPORTES RODA SPA

Este procedimiento comienza **después** de descargar el CAF de cinco folios. Antes de
eso no corre el plazo de 24 horas informado por el SII.

## Candado de inicio

No descargar el CAF hasta que todos estos puntos estén en verde:

- certificado digital PFX/P12 vigente, contraseña comprobada y respaldo seguro;
- los 69+ tests del motor pasan;
- los cinco casos de `Set Prueba BE (2).txt` generan un único `EnvioBOLETA`;
- ese sobre valida localmente y se conserva exactamente byte a byte;
- el RCOF del mismo día valida con el XSD oficial sin modificaciones;
- autenticación, envío, Track ID y consulta de estado pasan en el simulador;
- URL pública de consulta de boletas disponible por HTTPS;
- operador y equipo reservados para completar el ciclo sin interrupciones.

## Ventana de 24 horas

1. Registrar hora local y capturas; descargar un CAF tipo 39 con exactamente cinco folios.
2. Guardar el CAF fuera de Git y registrar SHA-256, rango, fecha y RUT.
3. Importarlo al ledger una sola vez y comprobar que el rango sea de cinco.
4. Emitir CASO-1 a CASO-5 en el orden del set. Cada idempotency key debe ser única y fija.
5. Verificar TED, XMLDSig, RUT, folios consecutivos, totales y referencias `SET/CASO-N`.
6. Construir un solo `EnvioBOLETA` con los cinco DTE y persistir sus bytes antes de enviar.
7. Construir el RCOF del día incluyendo exactamente los cinco folios utilizados.
8. Validar ambos XML localmente y guardar sus hashes.
9. Subir el sobre de boletas; registrar Track ID, fecha, respuesta íntegra y hash enviado.
10. Subir el RCOF por la vía de certificación habilitada por el SII y guardar evidencia.
11. Consultar el Track ID hasta estado terminal. Un resultado desconocido **no se reenvía**:
    primero se reconcilia, para evitar duplicados.
12. Solicitar revisión del set en el portal de certificación indicando el Track ID.

## Si algo falla

- Rechazo de esquema o contenido: conservar respuesta y XML; corregir y generar un nuevo
  sobre sólo según el diagnóstico del SII.
- Timeout después de enviar: marcar intento `UNKNOWN`; consultar estado antes de reintentar.
- Certificado/CAF incorrecto: detenerse. No improvisar ni editar XML firmado.
- Caída cerca del límite: usar la carga web permitida por el correo del SII, conservando
  las mismas evidencias y hashes.

## Evidencia mínima

CAF original, hash del CAF, cinco DTE, sobre, RCOF, hashes, timestamps, respuestas HTTP,
Track ID, estado final, captura de solicitud de revisión y correo de diagnóstico/V°B°.
Nunca guardar contraseña del PFX, token SII ni claves privadas en esta carpeta.
