"""Normalización y validación del RUT chileno."""

import re


class RutError(ValueError):
    """El RUT no tiene una representación o dígito verificador válido."""


def normalize_rut(value: str) -> str:
    compact = re.sub(r"[.\s]", "", value).upper()
    if not re.fullmatch(r"\d{1,8}-?[\dK]", compact):
        raise RutError("RUT inválido: use el formato 12345678-9")
    body, verifier = compact.replace("-", "")[:-1], compact[-1]
    normalized = f"{int(body)}-{verifier}"
    if not validate_rut(normalized):
        raise RutError("RUT inválido: el dígito verificador no coincide")
    return normalized


def validate_rut(value: str) -> bool:
    compact = re.sub(r"[.\s-]", "", value).upper()
    if not re.fullmatch(r"\d{1,8}[\dK]", compact):
        return False

    body, supplied = compact[:-1], compact[-1]
    total = sum(int(digit) * (2 + index % 6) for index, digit in enumerate(reversed(body)))
    expected_value = 11 - total % 11
    expected = "0" if expected_value == 11 else "K" if expected_value == 10 else str(expected_value)
    return supplied == expected

