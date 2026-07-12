"""Firma XMLDSig enveloped del DTE usando el certificado del emisor."""

import base64
import hashlib
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding
from lxml import etree

from .certificate import SigningCredential
from .dte import UnsignedDte


DS = "http://www.w3.org/2000/09/xmldsig#"
C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
RSA_SHA1 = f"{DS}rsa-sha1"
SHA1 = f"{DS}sha1"
SII = "http://www.sii.cl/SiiDte"


class XmlSignatureError(ValueError):
    """El DTE no pudo firmarse o su firma no es válida."""


@dataclass(frozen=True)
class SignedDte:
    xml: bytes
    document_id: str


class XmlSigner:
    def sign(self, dte: UnsignedDte, credential: SigningCredential) -> SignedDte:
        xml = self.sign_raw(
            dte.xml,
            target_tag=f"{{{SII}}}Documento",
            target_id=dte.document_id,
            credential=credential,
        )
        return SignedDte(xml=xml, document_id=dte.document_id)

    def sign_raw(
        self,
        xml: bytes,
        *,
        target_tag: str,
        target_id: str,
        credential: SigningCredential,
    ) -> bytes:
        parser = etree.XMLParser(
            resolve_entities=False, no_network=True, remove_blank_text=False
        )
        try:
            root = etree.fromstring(xml, parser)
        except etree.XMLSyntaxError as exc:
            raise XmlSignatureError("El documento no contiene XML válido") from exc

        target = root.find(target_tag)
        if target is None or target.get("ID") != target_id:
            raise XmlSignatureError("No se encontró el nodo con el ID esperado")

        digest = hashlib.sha1(_canonicalize(target)).digest()  # noqa: S324 - XMLDSig SII.
        signature_node, signed_info = self._signature_skeleton(
            target_id,
            digest,
            credential,
        )
        signed_info_bytes = _canonicalize(signed_info)
        signature = credential.private_key.sign(
            signed_info_bytes,
            padding.PKCS1v15(),
            hashes.SHA1(),  # noqa: S303 - algoritmo obligatorio de XMLDSig SII.
        )
        signature_node.find(f"{{{DS}}}SignatureValue").text = base64.b64encode(
            signature
        ).decode("ascii")
        signature_xml = etree.tostring(
            signature_node,
            encoding="ISO-8859-1",
            xml_declaration=False,
        )

        closing = b"</DTE>"
        root_local_name = etree.QName(root).localname.encode("ascii")
        closing = b"</" + root_local_name + b">"
        if not xml.endswith(closing):
            raise XmlSignatureError("El XML no tiene un cierre reconocible")
        return xml[: -len(closing)] + signature_xml + closing

    def verify(self, signed: SignedDte) -> bool:
        return self.verify_raw(
            signed.xml,
            target_tag=f"{{{SII}}}Documento",
            target_id=signed.document_id,
        )

    def verify_with_certificate(
        self,
        signed: SignedDte,
        expected_certificate,
    ) -> bool:
        return self.verify_raw(
            signed.xml,
            target_tag=f"{{{SII}}}Documento",
            target_id=signed.document_id,
            expected_certificate=expected_certificate,
        )

    def verify_raw(
        self,
        xml: bytes,
        *,
        target_tag: str,
        target_id: str,
        expected_certificate=None,
    ) -> bool:
        parser = etree.XMLParser(
            resolve_entities=False, no_network=True, remove_blank_text=False
        )
        try:
            root = etree.fromstring(xml, parser)
            document = root.find(target_tag)
            signatures = root.findall(f"{{{DS}}}Signature")
            signature = signatures[0] if len(signatures) == 1 else None
            matching_ids = root.xpath("//*[@ID=$target_id]", target_id=target_id)
            if (
                document is None
                or signature is None
                or document.get("ID") != target_id
                or len(matching_ids) != 1
                or matching_ids[0] is not document
            ):
                return False

            signed_info = signature.find(f"{{{DS}}}SignedInfo")
            signature_value = signature.findtext(f"{{{DS}}}SignatureValue")
            digest_value = signature.findtext(f".//{{{DS}}}DigestValue")
            certificate_value = signature.findtext(f".//{{{DS}}}X509Certificate")
            reference = signature.find(f".//{{{DS}}}Reference")
            if None in (
                signed_info,
                signature_value,
                digest_value,
                certificate_value,
                reference,
            ):
                return False
            if reference.get("URI") != f"#{target_id}":
                return False
            canonicalization = signed_info.find(f"{{{DS}}}CanonicalizationMethod")
            signature_method = signed_info.find(f"{{{DS}}}SignatureMethod")
            digest_method = reference.find(f"{{{DS}}}DigestMethod")
            transforms = reference.findall(f".//{{{DS}}}Transform")
            if (
                canonicalization is None
                or canonicalization.get("Algorithm") != C14N
                or signature_method is None
                or signature_method.get("Algorithm") != RSA_SHA1
                or digest_method is None
                or digest_method.get("Algorithm") != SHA1
                or len(transforms) != 1
                or transforms[0].get("Algorithm") != C14N
            ):
                return False

            expected_digest = base64.b64encode(
                hashlib.sha1(_canonicalize(document)).digest()  # noqa: S324
            ).decode("ascii")
            if digest_value != expected_digest:
                return False

            from cryptography import x509

            certificate = x509.load_der_x509_certificate(
                base64.b64decode(certificate_value)
            )
            if expected_certificate is not None and certificate.fingerprint(
                hashes.SHA256()
            ) != expected_certificate.fingerprint(hashes.SHA256()):
                return False
            public_key = certificate.public_key()
            if expected_certificate is not None:
                public_key = expected_certificate.public_key()
            if not isinstance(public_key, rsa.RSAPublicKey):
                return False
            public_key.verify(
                base64.b64decode(signature_value),
                _canonicalize(signed_info),
                padding.PKCS1v15(),
                hashes.SHA1(),  # noqa: S303 - algoritmo obligatorio de XMLDSig SII.
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _signature_skeleton(
        document_id: str,
        digest: bytes,
        credential: SigningCredential,
    ) -> tuple[etree._Element, etree._Element]:
        signature = etree.Element(etree.QName(DS, "Signature"), nsmap={None: DS})
        signed_info = etree.SubElement(signature, etree.QName(DS, "SignedInfo"))
        etree.SubElement(
            signed_info,
            etree.QName(DS, "CanonicalizationMethod"),
            Algorithm=C14N,
        )
        etree.SubElement(
            signed_info, etree.QName(DS, "SignatureMethod"), Algorithm=RSA_SHA1
        )
        reference = etree.SubElement(
            signed_info,
            etree.QName(DS, "Reference"),
            URI=f"#{document_id}",
        )
        transforms = etree.SubElement(reference, etree.QName(DS, "Transforms"))
        etree.SubElement(transforms, etree.QName(DS, "Transform"), Algorithm=C14N)
        etree.SubElement(reference, etree.QName(DS, "DigestMethod"), Algorithm=SHA1)
        etree.SubElement(
            reference, etree.QName(DS, "DigestValue")
        ).text = base64.b64encode(digest).decode("ascii")
        etree.SubElement(signature, etree.QName(DS, "SignatureValue"))

        key_info = etree.SubElement(signature, etree.QName(DS, "KeyInfo"))
        key_value = etree.SubElement(key_info, etree.QName(DS, "KeyValue"))
        rsa_key = etree.SubElement(key_value, etree.QName(DS, "RSAKeyValue"))
        numbers = credential.private_key.public_key().public_numbers()
        etree.SubElement(rsa_key, etree.QName(DS, "Modulus")).text = _integer_base64(
            numbers.n
        )
        etree.SubElement(rsa_key, etree.QName(DS, "Exponent")).text = _integer_base64(
            numbers.e
        )
        x509_data = etree.SubElement(key_info, etree.QName(DS, "X509Data"))
        etree.SubElement(
            x509_data, etree.QName(DS, "X509Certificate")
        ).text = base64.b64encode(
            credential.certificate.public_bytes(Encoding.DER)
        ).decode("ascii")
        return signature, signed_info


def _canonicalize(element: etree._Element) -> bytes:
    return etree.tostring(element, method="c14n", exclusive=False, with_comments=False)


def _integer_base64(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.b64encode(raw).decode("ascii")
