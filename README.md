# Completo Fiscal

Producto fiscal autónomo y multi-tenant para pymes chilenas. Comparte contratos de
integración con Completo Gastro, pero se despliega, audita y versiona de forma independiente.

## Componentes

- `dte-engine`: dominio tributario, API, ledger, representaciones y conectores oficiales SII.
- `fiscal-console`: consola Next.js para emisión, recepción, conciliación y certificación.
- `sii-reader`: consultas de solo lectura mediante sesión SII para superficies sin alternativa
  oficial documentada (RCV, F29, BHE, F22 y perfil tributario).

## Límites de seguridad

- El navegador nunca recibe PFX, contraseñas SII, claves CAF ni tokens internos duraderos.
- `sii-reader` no puede firmar, emitir, presentar ni rectificar documentos o declaraciones.
- Certificados, CAF y credenciales reales no pertenecen al repositorio.
- Demo, certificación y producción son ambientes visual y operacionalmente separados.

## Estado

La base fue extraída de forma no destructiva el 11 de julio de 2026. Antes del primer commit
se exige escaneo de secretos, 199+ pruebas del motor, typecheck y build de la consola.
