"""Carga local de credenciales PKCS#12 sin persistir secretos."""

from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12


class CertificateError(ValueError):
    """El contenedor PKCS#12 no es apto para firmar DTE."""


@dataclass(frozen=True)
class SigningCredential:
    certificate: x509.Certificate
    private_key: rsa.RSAPrivateKey

    @property
    def serial_number(self) -> str:
        return format(self.certificate.serial_number, "X")

    @property
    def subject(self) -> str:
        return self.certificate.subject.rfc4514_string()


class CertificateLoader:
    def load(
        self,
        payload: bytes,
        password: str,
        *,
        at: datetime | None = None,
    ) -> SigningCredential:
        if not payload:
            raise CertificateError("El archivo PKCS#12 está vacío")
        try:
            private_key, certificate, _chain = pkcs12.load_key_and_certificates(
                payload,
                password.encode("utf-8"),
            )
        except (TypeError, ValueError) as exc:
            raise CertificateError("No fue posible abrir el PKCS#12; revise archivo y contraseña") from exc

        if certificate is None or private_key is None:
            raise CertificateError("El PKCS#12 debe contener certificado y clave privada")
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise CertificateError("El certificado debe usar una clave privada RSA")
        if private_key.public_key().public_numbers() != certificate.public_key().public_numbers():
            raise CertificateError("La clave privada no corresponde al certificado")

        instant = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if instant < certificate.not_valid_before_utc:
            raise CertificateError("El certificado todavía no es válido")
        if instant > certificate.not_valid_after_utc:
            raise CertificateError("El certificado está vencido")

        return SigningCredential(certificate=certificate, private_key=private_key)

