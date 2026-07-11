import pytest

from completo_dte.domain import SchemaValidationError, XmlSchemaValidator


def test_schema_validator_accepts_and_rejects_using_configured_xsd(tmp_path) -> None:
    schema = tmp_path / "amount.xsd"
    schema.write_text(
        """<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Amount">
    <xs:simpleType>
      <xs:restriction base="xs:decimal">
        <xs:fractionDigits value="2"/>
        <xs:totalDigits value="5"/>
      </xs:restriction>
    </xs:simpleType>
  </xs:element>
</xs:schema>""",
        encoding="utf-8",
    )
    validator = XmlSchemaValidator(schema)
    validator.validate(b"<Amount>123.45</Amount>")
    with pytest.raises(SchemaValidationError, match="fractionDigits"):
        validator.validate(b"<Amount>1.234</Amount>")


def test_schema_validator_fails_closed_for_missing_schema(tmp_path) -> None:
    with pytest.raises(SchemaValidationError, match="no existe"):
        XmlSchemaValidator(tmp_path / "missing.xsd")

