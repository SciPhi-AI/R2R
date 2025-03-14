# type: ignore
import email
import logging
from base64 import b64decode
from datetime import datetime
from email.message import Message
from typing import AsyncGenerator

from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)

logger = logging.getLogger(__name__)


class P7SParser(AsyncParser[str | bytes]):
    """Parser for S/MIME messages containing a P7S (PKCS#7 Signature) file."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.x509 = x509
        self.pkcs7 = pkcs7
        self.NameOID = NameOID

    def _format_datetime(self, dt: datetime) -> str:
        """Format datetime in a readable way."""
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    def _get_name_attribute(self, name, oid):
        """Safely get name attribute."""
        try:
            return name.get_attributes_for_oid(oid)[0].value
        except (IndexError, ValueError):
            return None

    def _extract_cert_info(self, cert) -> dict:
        """Extract relevant information from a certificate."""
        try:
            subject = cert.subject
            issuer = cert.issuer

            info = {
                "common_name": self._get_name_attribute(
                    subject, self.NameOID.COMMON_NAME
                ),
                "organization": self._get_name_attribute(
                    subject, self.NameOID.ORGANIZATION_NAME
                ),
                "email": self._get_name_attribute(
                    subject, self.NameOID.EMAIL_ADDRESS
                ),
                "issuer_common_name": self._get_name_attribute(
                    issuer, self.NameOID.COMMON_NAME
                ),
                "issuer_organization": self._get_name_attribute(
                    issuer, self.NameOID.ORGANIZATION_NAME
                ),
                "serial_number": hex(cert.serial_number)[2:],
                "not_valid_before": self._format_datetime(
                    cert.not_valid_before
                ),
                "not_valid_after": self._format_datetime(cert.not_valid_after),
                "version": cert.version.name,
            }

            return {k: v for k, v in info.items() if v is not None}

        except Exception as e:
            logger.warning(f"Error extracting certificate info: {e}")
            return {}

    def _try_parse_signature(self, data: bytes):
        """Try to parse the signature data as PKCS7 containing certificates."""
        exceptions = []

        # Try DER format PKCS7
        try:
            certs = self.pkcs7.load_der_pkcs7_certificates(data)
            if certs is not None:
                return certs
        except Exception as e:
            exceptions.append(f"DER PKCS7 parsing failed: {str(e)}")

        # Try PEM format PKCS7
        try:
            certs = self.pkcs7.load_pem_pkcs7_certificates(data)
            if certs is not None:
                return certs
        except Exception as e:
            exceptions.append(f"PEM PKCS7 parsing failed: {str(e)}")

        raise ValueError(
            "Unable to parse signature file as PKCS7 with certificates. Attempted methods:\n"
            + "\n".join(exceptions)
        )

    def _extract_p7s_data_from_mime(self, raw_data: bytes) -> bytes:
        """Extract the raw PKCS#7 signature data from a MIME message."""
        msg: Message = email.message_from_bytes(raw_data)

        # If the message is multipart, find the part with application/x-pkcs7-signature
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "application/x-pkcs7-signature":
                    # Get the base64 encoded data from the payload
                    payload = part.get_payload(decode=False)
                    # payload at this stage is a base64 string
                    try:
                        return b64decode(payload)
                    except Exception as e:
                        raise ValueError(
                            f"Failed to decode base64 PKCS#7 signature: {str(e)}"
                        ) from e
            # If we reach here, no PKCS#7 part was found
            raise ValueError(
                "No application/x-pkcs7-signature part found in the MIME message."
            )
        else:
            # Not multipart, try to parse directly if it's just a raw P7S
            # This scenario is less common; usually it's multipart.
            if msg.get_content_type() == "application/x-pkcs7-signature":
                payload = msg.get_payload(decode=False)
                return b64decode(payload)

            raise ValueError(
                "The provided data does not contain a valid S/MIME signed message."
            )

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest an S/MIME message and extract the PKCS#7 signature
        information."""
        # If data is a string, it might be base64 encoded, or it might be the raw MIME text.
        # We should assume it's raw MIME text here because the input includes MIME headers.
        if isinstance(data, str):
            # Convert to bytes (raw MIME)
            data = data.encode("utf-8")

        try:
            # Extract the raw PKCS#7 data (der/pem) from the MIME message
            p7s_data = self._extract_p7s_data_from_mime(data)

            # Parse the PKCS#7 data for certificates
            certificates = self._try_parse_signature(p7s_data)

            if not certificates:
                yield "No certificates found in the provided P7S file."
                return

            # Process each certificate
            for i, cert in enumerate(certificates, 1):
                if cert_info := self._extract_cert_info(cert):
                    yield f"Certificate {i}:"
                    for key, value in cert_info.items():
                        if value:
                            yield f"{key.replace('_', ' ').title()}: {value}"
                    yield ""  # Empty line between certificates
                else:
                    yield f"Certificate {i}: No detailed information extracted."

        except Exception as e:
            raise ValueError(f"Error processing P7S file: {str(e)}") from e
