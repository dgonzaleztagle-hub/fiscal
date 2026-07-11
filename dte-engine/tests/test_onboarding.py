import pytest

from completo_dte.domain import ProductModule, onboarding_requirements


def keys(modules):
    return {item.key for item in onboarding_requirements(modules)}


def test_loyalty_can_be_the_only_module_without_forcing_pos() -> None:
    result = keys({ProductModule.LOYALTY})
    assert "loyalty_rules" in result
    assert "pos_branches" not in result
    assert "menu" not in result


def test_fiscal_adds_assisted_sensitive_requirements_without_restaurant_data() -> None:
    requirements = onboarding_requirements({ProductModule.FISCAL})
    result = {item.key: item for item in requirements}
    assert "digital_certificate" in result
    assert "caf_and_certification" in result
    assert result["digital_certificate"].sensitive
    assert "menu" not in result
    assert "employees" not in result


def test_shared_requirements_are_deduplicated_across_modules() -> None:
    requirements = onboarding_requirements(
        {ProductModule.ATTENDANCE, ProductModule.PAYROLL}
    )
    assert [item.key for item in requirements].count("employees") == 1


def test_onboarding_rejects_empty_subscription() -> None:
    with pytest.raises(ValueError, match="al menos un módulo"):
        onboarding_requirements(set())
