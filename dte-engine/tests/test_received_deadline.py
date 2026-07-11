from datetime import datetime, timezone

from completo_dte.domain import DecisionDeadlineStatus, calculate_decision_deadline


def test_deadline_uses_eight_calendar_days_from_authoritative_sii_receipt() -> None:
    received = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    deadline = calculate_decision_deadline(
        received, now=datetime(2026, 7, 8, 9, 0, tzinfo=timezone.utc)
    )
    assert deadline.status is DecisionDeadlineStatus.OPEN
    assert deadline.expires_at == datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc)


def test_deadline_becomes_urgent_during_last_24_hours_and_then_expires() -> None:
    received = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    urgent = calculate_decision_deadline(
        received, now=datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    )
    expired = calculate_decision_deadline(
        received, now=datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc)
    )
    assert urgent.status is DecisionDeadlineStatus.URGENT
    assert expired.status is DecisionDeadlineStatus.EXPIRED
    assert expired.remaining_seconds == 0


def test_uploaded_xml_without_sii_receipt_timestamp_has_unknown_deadline() -> None:
    deadline = calculate_decision_deadline(
        None, now=datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    )
    assert deadline.status is DecisionDeadlineStatus.UNKNOWN
    assert deadline.expires_at is None
