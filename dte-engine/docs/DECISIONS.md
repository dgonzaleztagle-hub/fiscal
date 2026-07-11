# Registro inicial de decisiones

## Separación respecto de Completo

El motor vive como servicio independiente. Completo no conocerá XML, CAF, certificados
ni endpoints internos del SII. La frontera futura será una API versionada e idempotente.

## Fuente normativa

La fuente de verdad es el SII. El baseline inicial es:

- Formato DTE 2.5, febrero de 2026.
- Instructivo de emisión DTE.
- Instructivo técnico de boleta electrónica.
- XSD oficiales de DTE, EnvioBOLETA y Registro de Ventas Diario.
- Validaciones DTE, junio de 2026.

Antes de implementar builders se registrará URL, fecha de descarga y SHA-256 de cada
artefacto normativo.

## Uso de LibreDTE

LibreDTE Core se consulta para reconocer responsabilidades y casos límite, no como fuente
de código. No se copiarán implementaciones, fixtures, nombres internos ni tests; tampoco
se agregará su biblioteca AGPL como dependencia. Toda regla se verificará contra una
fuente oficial del SII y se implementará con contratos propios.

La revisión del árbol público del 2026-07-08 confirmó como fronteras útiles —sin adoptar
su implementación— documento, normalización, construcción, sanitización, validación,
render, sobre de envío y Resumen de Ventas Diarias. Para nuestro caso se mantendrán menos
capas al principio: dominio puro, criptografía, persistencia y gateway SII. El repositorio
consultado declara licencia `AGPL-3.0`; no se descargó ni incorporó su código al proyecto.

## Validación de CAF

`CafLoader` comprueba estructura obligatoria, RUT, tipo DTE conocido, rango, fecha,
Base64 y correspondencia matemática entre RSASK y RSAPK.

`CafAuthenticityValidator` verifica además `FRMA` sobre `DA` canonicalizado, usando un
certificado público histórico del SII fijado explícitamente por `IDK` y fingerprint
SHA-256. Los certificados históricos pueden estar vencidos hoy: su vigencia actual no
determina la autenticidad de una firma creada cuando eran las claves operativas del SII.
Lo relevante es obtenerlos de una fuente oficial y fijar su identidad.

Para impedir omisiones accidentales, el validador entrega `TrustedCafAuthorization` y el
constructor de TED rechaza un `CafAuthorization` meramente parseado.

## Compatibilidad heredada

TED y XMLDSig usan RSA/SHA-1 porque así lo exige el protocolo DTE vigente, no como una
elección criptográfica nueva. Las claves se mantienen encapsuladas y el uso de SHA-1 se
limita estrictamente a estas firmas interoperables. La API interna, almacenamiento y
autenticación del servicio no deben reutilizar SHA-1.

Los precios del primer flujo tipo 39 son brutos. Por ello no se emite `IndMntNeto`; el
total corresponde a la suma redondeada de líneas después de descuentos. Se limita a 60
detalles, el máximo conservador observado en schemas DTE, aunque documentación histórica
de boletas menciona un máximo mayor.

## Ledger de folios

La primera implementación usa SQLite para probar invariantes y concurrencia sin introducir
infraestructura externa. Cada reserva ocurre dentro de `BEGIN IMMEDIATE`; existen índices
únicos para folio fiscal e idempotencia, y las transiciones generan eventos append-only.

Estados iniciales:

```text
reserved -> consumed
reserved -> voided
```

No existe transición para liberar o reutilizar un folio. Un retry de reserva, consumo o
anulación con el mismo payload es idempotente. Un retry con datos distintos falla.

El allocator está conectado a `DteBuilder` mediante `IssueBoletaService`. La tabla
`fiscal_documents` conserva los bytes firmados y su SHA-256. Insertar el documento,
marcar el folio como consumido y agregar el evento ocurre en una sola transacción.

El servicio nunca devuelve XML antes de persistirlo. Un retry posterior devuelve los
mismos bytes almacenados. Si falla la construcción o el acceso al vault antes de
persistir, la reserva permanece en estado `reserved` para que la misma idempotency key
continúe con el mismo folio.

La reserva guarda además `request_sha256`, calculado sobre una representación JSON
canónica del comando tributario. La misma key con una huella diferente no es un retry:
es un conflicto y se rechaza.

Antes de persistir, el documento firmado se inserta en un `EnvioBOLETA` de validación y
se valida contra el XSD configurado. El callback es obligatorio en
`IssueBoletaService`; el bootstrap no inicia si falta el schema.

La credencial no pertenece al singleton del servicio. Se resuelve por
`(tenant_id, taxpayer_rut)` en cada emisión. La verificación posterior exige el
certificado esperado y una única referencia al ID firmado, mitigando sustitución de
certificado y XML signature wrapping. Validar la cadena contra entidades certificadoras
acreditadas continúa pendiente de contar con el bundle oficial correspondiente.
