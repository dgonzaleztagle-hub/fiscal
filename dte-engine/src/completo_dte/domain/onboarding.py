"""Checklist modular: ningún producto obliga a contratar POS como base."""

from dataclasses import dataclass
from enum import StrEnum


class ProductModule(StrEnum):
    FISCAL = "fiscal"
    POS = "pos"
    LOYALTY = "loyalty"
    ATTENDANCE = "attendance"
    PAYROLL = "payroll"


class RequirementOwner(StrEnum):
    CLIENT = "client"
    COMPLETO = "completo"
    JOINT = "joint"


@dataclass(frozen=True)
class OnboardingRequirement:
    key: str
    label: str
    owner: RequirementOwner
    sensitive: bool = False


def onboarding_requirements(
    modules: set[ProductModule],
) -> tuple[OnboardingRequirement, ...]:
    if not modules:
        raise ValueError("El onboarding requiere al menos un módulo contratado")
    requirements = {
        item.key: item
        for item in (
            OnboardingRequirement(
                "organization", "Identificar organización", RequirementOwner.CLIENT
            ),
            OnboardingRequirement(
                "administrator",
                "Crear administrador principal",
                RequirementOwner.CLIENT,
            ),
            OnboardingRequirement(
                "terms", "Aceptar contrato y privacidad", RequirementOwner.CLIENT
            ),
        )
    }
    module_requirements = {
        ProductModule.FISCAL: (
            OnboardingRequirement(
                "tax_profile",
                "Razón social, RUT, giro y actividades",
                RequirementOwner.CLIENT,
            ),
            OnboardingRequirement(
                "legal_representative",
                "Representante y usuarios autorizados SII",
                RequirementOwner.JOINT,
                True,
            ),
            OnboardingRequirement(
                "sii_eligibility",
                "Verificar habilitación tributaria",
                RequirementOwner.JOINT,
            ),
            OnboardingRequirement(
                "digital_certificate",
                "Instalar certificado en vault",
                RequirementOwner.JOINT,
                True,
            ),
            OnboardingRequirement(
                "fiscal_branches",
                "Configurar sucursales y códigos SII",
                RequirementOwner.CLIENT,
            ),
            OnboardingRequirement(
                "public_verification",
                "Publicar consulta HTTPS",
                RequirementOwner.COMPLETO,
            ),
            OnboardingRequirement(
                "caf_and_certification",
                "CAF y certificación por contribuyente",
                RequirementOwner.JOINT,
                True,
            ),
        ),
        ProductModule.POS: (
            OnboardingRequirement(
                "pos_branches", "Locales, cajas y dispositivos", RequirementOwner.JOINT
            ),
            OnboardingRequirement(
                "menu", "Carta, precios e impuestos", RequirementOwner.CLIENT
            ),
            OnboardingRequirement(
                "payments", "Medios de pago y cierres", RequirementOwner.CLIENT
            ),
        ),
        ProductModule.LOYALTY: (
            OnboardingRequirement(
                "loyalty_rules",
                "Reglas de puntos y beneficios",
                RequirementOwner.CLIENT,
            ),
            OnboardingRequirement(
                "loyalty_privacy",
                "Consentimientos y comunicaciones",
                RequirementOwner.JOINT,
            ),
        ),
        ProductModule.ATTENDANCE: (
            OnboardingRequirement(
                "attendance_sites",
                "Centros y métodos de marcación",
                RequirementOwner.JOINT,
            ),
            OnboardingRequirement(
                "employees", "Trabajadores y jornadas", RequirementOwner.CLIENT, True
            ),
        ),
        ProductModule.PAYROLL: (
            OnboardingRequirement(
                "employees", "Trabajadores y jornadas", RequirementOwner.CLIENT, True
            ),
            OnboardingRequirement(
                "payroll_rules",
                "Contratos, haberes y descuentos",
                RequirementOwner.JOINT,
                True,
            ),
            OnboardingRequirement(
                "payroll_payment",
                "Ciclo y datos de pago",
                RequirementOwner.CLIENT,
                True,
            ),
        ),
    }
    for module in sorted(modules, key=lambda value: value.value):
        for requirement in module_requirements[module]:
            requirements.setdefault(requirement.key, requirement)
    return tuple(requirements.values())
