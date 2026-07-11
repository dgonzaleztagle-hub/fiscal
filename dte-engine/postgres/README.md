# Persistencia PostgreSQL fiscal

Este esquema es el destino cloud del ledger. No se aplica automáticamente y no contiene
secretos: PFX, contraseñas y claves privadas CAF viven en un vault; PostgreSQL conserva
únicamente referencias opacas, fingerprints, hashes, estados y metadatos.

La migración crea el esquema privado `fiscal`, revoca acceso a `anon` y `authenticated`,
y separa payloads inmutables de sus proyecciones de estado. Los XML/PDF viven cifrados en
object storage privado; `xml_object_key` y SHA-256 permiten recuperarlos y verificar su
integridad.

Antes de aplicar en Supabase se debe:

1. probar en PostgreSQL local;
2. revisar roles y políticas del proyecto real;
3. configurar backups y restauración;
4. recibir aprobación explícita del operador.
