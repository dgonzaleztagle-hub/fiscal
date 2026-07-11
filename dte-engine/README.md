# Motor DTE de Completo

Servicio tributario independiente que será consumido por la aplicación de restaurantes
Completo. Completo enviará una venta canónica; este servicio administrará CAF, folios,
XML, timbre, firma, envío al SII y seguimiento. Ningún secreto tributario debe llegar al
navegador ni al repositorio de Completo.

## Alcance del primer spike

El primer hito es generar localmente una boleta afecta tipo 39:

1. validar RUT, certificado PFX/P12 y CAF;
2. reservar un folio una sola vez;
3. construir y firmar el TED con la clave del CAF;
4. construir y firmar el DTE;
5. validar el resultado con los XSD oficiales;
6. verificar ambas firmas con una implementación independiente.

No se enviará a producción. El envío a certificación se implementará recién cuando el
XML local sea reproducible y válido.

## Estado actual

Ya se implementó localmente:

- modelo conservador de boleta afecta con precios brutos y hasta 60 detalles;
- cálculo y redondeo comercial de totales en pesos;
- carga de CAF preservando el bloque original byte a byte;
- verificación de `FRMA` contra un certificado público SII fijado por `IDK`;
- TED firmado con RSA/SHA-1 y verificación de adulteraciones;
- DTE tipo 39 con firma XMLDSig sobre `Documento`;
- sobre `EnvioBOLETA` con firma XMLDSig independiente sobre `SetDTE`;
- validaciones cruzadas de RUT, tipo, folio, rango, fecha y total.
- ledger transaccional de folios con idempotencia y eventos append-only;
- reserva concurrente, consumo irreversible y anulación sin reutilización.

La suite usa solamente identidades, certificados y CAF sintéticos. El RCOF valida contra
el XSD oficial sin modificar. El paquete oficial de `EnvioBOLETA_v11.xsd` fue fijado por
hash; contiene una contradicción interna en `DescuentoPct` que libxml moderno rechaza.
La compatibilidad exacta y sus hashes están documentados en `docs/OFFICIAL-SOURCES.md`;
el original oficial nunca se parchea silenciosamente.

El set oficial asignado en certificación ya está cubierto por una matriz de cinco casos:
servicios, cantidades, venta gastronómica, mezcla afecta/exenta y unidad de medida `Kg`.
Cada documento incluye la referencia `SET` y su `CASO-N`.

También están implementados y probados el RCOF, el ledger inmutable de sobres/intentos,
la firma de semilla, autenticación con token, upload de boletas y consulta por Track ID.
El procedimiento operativo está en `docs/RUNBOOK-CERTIFICACION-BOLETAS-24H.md`.
La auditoría cruzada más reciente está en
`docs/AUDIT-CRUZADA-LIBREDTE-2026-07-09-SOL.md`.

Un CAF cargado no puede usarse directamente para timbrar. Primero debe pasar por
`CafAuthenticityValidator`, que devuelve un `TrustedCafAuthorization`; `TedBuilder`
rechaza explícitamente cualquier CAF que no tenga ese estado.

## Ledger de folios

El adaptador de laboratorio usa SQLite con `BEGIN IMMEDIATE`, restricciones únicas y
WAL. La combinación `(taxpayer_rut, document_type, folio)` no puede repetirse y una
`idempotency_key` devuelve siempre la misma reserva. Un folio anulado no vuelve al rango.

```python
from completo_dte.infrastructure import FolioLedger

ledger = FolioLedger("folio-ledger.sqlite3")
ledger.migrate()
ledger.import_caf("tenant-id", trusted_caf)
lease = ledger.reserve(
    tenant_id="tenant-id",
    taxpayer_rut="12345678-5",
    document_type=39,
    idempotency_key="venta-completo-123",
)
```

SQLite sirve para el spike local y una futura caja offline. El servicio cloud deberá usar
PostgreSQL conservando el mismo contrato y las mismas restricciones.

## Emisión local integrada

`IssueBoletaService` ejecuta el ciclo local completo:

```text
idempotency key
  -> reserva de folio
  -> TED
  -> DTE
  -> XMLDSig
  -> persistencia inmutable + consumo del folio
```

La última transición ocurre en una sola transacción. Si el proceso cae antes de guardar,
el retry conserva el folio reservado y reconstruye el documento. Si la respuesta se
pierde después de guardar, el retry devuelve exactamente el XML persistido y no vuelve a
firmar.

## API local

### Demo local sin certificados ni CAF reales

```powershell
.\.venv\Scripts\python.exe scripts\run_demo_api.py
```

Expone sólo en `127.0.0.1:8081`, genera material criptográfico efímero, siembra boletas
39/41 sintéticas y usa el token local `completo-fiscal-demo-local-token-only`. Al detener
el proceso se descarta su base temporal. Este arranque no lee variables de certificación,
PFX, CAF reales ni endpoints del SII.

La API se inicia cerrada por defecto y escucha solamente en `127.0.0.1`:

```powershell
cd dte-engine
Copy-Item .env.example .env
# Cargue las variables de .env mediante su gestor de secretos o sesión de PowerShell.
.\.venv\Scripts\python -m completo_dte.api
```

No se incluye un `.env` funcional: el arranque exige CAF, certificado público SII con
fingerprint fijado, PFX del emisor, contraseña, token, resolución, XSD `EnvioBOLETA` y
base de datos. El XSD es obligatorio y debe provenir del paquete oficial del SII.

La idempotencia incluye una huella SHA-256 canónica de toda la solicitud. Reusar una key
con contenido diferente responde conflicto; reusar la misma key con contenido equivalente
devuelve los mismos bytes persistidos.

La credencial de firma se resuelve por tenant y RUT. Después de firmar, el XML se verifica
contra el certificado esperado; no basta con que sea consistente con cualquier
certificado incrustado en el propio documento.

Emisión:

```http
POST /v1/fiscal-documents
Authorization: Bearer <token-del-tenant>
Idempotency-Key: <id-unico-de-la-venta-en-completo>
Content-Type: application/json

{
  "document_type": 39,
  "issued_on": "2026-07-08",
  "issuer": {
    "rut": "12345678-5",
    "legal_name": "RESTAURANTE EJEMPLO SPA",
    "business_activity": "RESTAURANTES",
    "activity_code": 561000,
    "address": "CALLE 123",
    "commune": "SANTIAGO"
  },
  "lines": [
    {
      "name": "Menú del día",
      "quantity": "1",
      "unit_price_gross": "7990",
      "discount_gross": "0",
      "is_exempt": false,
      "unit_measure": null
    }
  ],
  "reference": {
    "code": "SET",
    "reason": "CASO-1"
  }
}
```

Endpoints:

- `GET /health`
- `POST /v1/fiscal-documents`
- `GET /v1/fiscal-documents/{id}`
- `GET /v1/fiscal-documents/{id}/xml`
- `GET /public/v1/boletas/{public_id}`
- `GET /public/v1/boletas/{public_id}/pdf`

El XML requiere la misma autenticación y sólo es visible para el tenant propietario.
La consulta pública usa un identificador opaco de 128 bits y muestra una representación
mínima; no publica el XML ni permite enumerar folios. El PDF térmico se deriva del XML
firmado y su PDF417 contiene el TED original.

## Decisión técnica provisional

El spike usa Python 3.12 por proximidad con el repositorio y por la disponibilidad de
bibliotecas XML y criptográficas maduras. La decisión se confirma solamente si permite:

- conservar el orden y la codificación exigidos por el SII;
- validar XSD sin modificar el documento;
- generar XMLDSig interoperable;
- cargar PFX/P12 y firmar TED con RSA;
- producir PDF417 verificable.

## Desarrollo

```powershell
cd dte-engine
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
```

Los tests generan claves y CAF sintéticos en memoria. No se deben agregar certificados,
CAF, contraseñas ni XML reales a `tests/fixtures`.
