import pytest

from completo_dte.domain import CafError, CafLoader
from factories import make_synthetic_caf


def test_loads_synthetic_type_39_caf() -> None:
    source = make_synthetic_caf()
    caf = CafLoader().load(source)
    assert caf.data.issuer_rut == "12345678-5"
    assert caf.data.document_type == 39
    assert (caf.data.folio_from, caf.data.folio_to) == (1, 100)
    assert caf.caf_xml == source[source.index(b"<CAF "):source.index(b"</CAF>") + len(b"</CAF>")]


def test_rejects_invalid_range() -> None:
    with pytest.raises(CafError, match="Rango"):
        CafLoader().load(make_synthetic_caf(folio_to=0))


def test_rejects_unsupported_document_type() -> None:
    with pytest.raises(CafError, match="no soportado"):
        CafLoader().load(make_synthetic_caf(document_type=110))


def test_rejects_private_key_from_another_caf() -> None:
    first = make_synthetic_caf()
    second = make_synthetic_caf()
    private = second.split(b"<RSASK>")[1].split(b"</RSASK>")[0]
    altered = first.split(b"<RSASK>")[0] + b"<RSASK>" + private + b"</RSASK></AUTORIZACION>"
    with pytest.raises(CafError, match="no corresponde"):
        CafLoader().load(altered)
