import json
from pathlib import Path


BASELINE = Path(__file__).parents[1] / "comparison" / "baseline.json"


def test_comparison_baseline_covers_sellable_document_family() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    assert baseline["libredte"]["role"] == "secondary_audit_reference"
    assert set(baseline["document_matrix"]) == {"33", "34", "39", "41", "52", "56", "61"}
    assert baseline["authority_order"][0] == "sii_documentation_xsd_and_certification"
    assert all(len(source["sha256"]) == 64 for source in baseline["official_sources"])
