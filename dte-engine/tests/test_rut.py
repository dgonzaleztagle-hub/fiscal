import pytest

from completo_dte.domain import RutError, normalize_rut, validate_rut


def test_normalizes_punctuation_and_case() -> None:
    assert normalize_rut("12.345.678-5") == "12345678-5"
    assert normalize_rut("6.927.045-k") == "6927045-K"


def test_rejects_wrong_verifier() -> None:
    assert not validate_rut("12345678-9")
    with pytest.raises(RutError):
        normalize_rut("12345678-9")

