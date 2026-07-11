from pathlib import Path


SCHEMA = (
    Path(__file__).parents[1]
    / "postgres"
    / "migrations"
    / "001_fiscal_core.sql"
).read_text(encoding="utf-8")


def test_postgres_schema_is_private_and_contains_no_secret_bytes() -> None:
    assert "CREATE SCHEMA IF NOT EXISTS fiscal" in SCHEMA
    assert "REVOKE ALL ON SCHEMA fiscal FROM PUBLIC, anon, authenticated" in SCHEMA
    assert "GRANT USAGE ON SCHEMA fiscal TO service_role" in SCHEMA
    assert "pfx" not in SCHEMA.lower()
    assert "password" not in SCHEMA.lower()
    assert "private_key" not in SCHEMA.lower()
    assert "secret_ref" in SCHEMA


def test_postgres_schema_separates_immutable_payload_from_state() -> None:
    assert "CREATE TABLE fiscal.documents" in SCHEMA
    assert "CREATE TABLE fiscal.document_state" in SCHEMA
    assert "CREATE TABLE fiscal.envelopes" in SCHEMA
    assert "CREATE TABLE fiscal.envelope_state" in SCHEMA
    assert "CREATE TRIGGER fiscal_documents_immutable" in SCHEMA
    assert "CREATE TRIGGER fiscal_envelopes_immutable" in SCHEMA
