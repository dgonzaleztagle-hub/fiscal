from completo_dte.application import (
    EvidenceState,
    MonthlyDossierBuilder,
    MonthlyDocumentRow,
    MonthlyFiscalReport,
)


def report() -> MonthlyFiscalReport:
    return MonthlyFiscalReport(
        "2026-07",
        (
            MonthlyDocumentRow(
                "sale", 39, 1, "76.192.083-9", "2026-07-10", 10_000, 0, 1_900, 11_900, "a" * 64
            ),
        ),
    )


def test_dossier_explains_missing_and_disconnected_sources() -> None:
    dossier = MonthlyDossierBuilder().build(
        report=report(),
        close_snapshot_id=None,
        close_calculation_sha256=None,
        rcv_snapshot_id=None,
        rcv_payload_sha256=None,
    )
    states = {item.code: item.state for item in dossier.items}
    assert states["documents"] is EvidenceState.READY
    assert states["rcv"] is EvidenceState.MISSING
    assert states["close"] is EvidenceState.MISSING
    assert states["people"] is EvidenceState.NOT_CONNECTED
    assert dossier.ready is False
    assert len(dossier.evidence_hash) == 64


def test_dossier_is_deterministic_and_ready_when_required_evidence_exists() -> None:
    kwargs = dict(
        report=report(),
        close_snapshot_id="close-v1",
        close_calculation_sha256="b" * 64,
        rcv_snapshot_id="rcv-v2",
        rcv_payload_sha256="c" * 64,
    )
    first = MonthlyDossierBuilder().build(**kwargs)
    second = MonthlyDossierBuilder().build(**kwargs)
    assert first.ready is True
    assert first.evidence_hash == second.evidence_hash
    assert first.ready_count == 3


def test_dossier_blocks_payment_snapshot_with_differences() -> None:
    dossier = MonthlyDossierBuilder().build(
        report=report(), close_snapshot_id="close-v1", close_calculation_sha256="b" * 64,
        rcv_snapshot_id="rcv-v1", rcv_payload_sha256="c" * 64,
        payment_reconciliation_ref="payments-v1", payment_reconciliation_ready=False,
    )
    payments = next(item for item in dossier.items if item.code == "payments")
    assert payments.state is EvidenceState.REVIEW
    assert dossier.ready is False
