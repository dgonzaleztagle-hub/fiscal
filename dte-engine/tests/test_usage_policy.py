from completo_dte.domain.usage_policy import FairUsePolicy
def test_fair_use_has_no_small_document_quota():
 policy=FairUsePolicy();assert policy.decide(operation="commercial_document",monthly_count=50).allowed;assert policy.decide(operation="commercial_document",monthly_count=99_999).allowed;decision=policy.decide(operation="commercial_document",monthly_count=100_000);assert not decision.allowed and decision.classification=="enterprise_review"
