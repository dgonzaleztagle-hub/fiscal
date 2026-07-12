"""Validación XSD fail-closed para artefactos XML tributarios."""

from pathlib import Path

from lxml import etree


class SchemaValidationError(ValueError):
    """El XML no satisface el schema tributario configurado."""


class XmlSchemaValidator:
    def __init__(self, schema_path: str | Path) -> None:
        path = Path(schema_path).expanduser().resolve()
        if not path.is_file():
            raise SchemaValidationError(f"El schema no existe: {path}")
        parser = etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            remove_blank_text=False,
        )
        try:
            schema_document = etree.parse(str(path), parser)
            self._schema = etree.XMLSchema(schema_document)
        except (etree.XMLSyntaxError, etree.XMLSchemaParseError) as exc:
            raise SchemaValidationError(
                f"No fue posible cargar el schema {path.name}"
            ) from exc

    def validate(self, xml: bytes) -> None:
        parser = etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            remove_blank_text=False,
        )
        try:
            document = etree.fromstring(xml, parser)
        except etree.XMLSyntaxError as exc:
            raise SchemaValidationError(
                "El artefacto tributario no es XML válido"
            ) from exc
        if self._schema.validate(document):
            return
        errors = "; ".join(
            entry.message for entry in tuple(self._schema.error_log)[-5:]
        )
        raise SchemaValidationError(f"El XML no cumple el schema: {errors}")
