import textwrap
from typing import Any, Optional
from uuid import UUID


class R2RException(Exception):
    def __init__(
        self, message: str, status_code: int, detail: Optional[Any] = None
    ):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self):
        return {
            "message": self.message,
            "status_code": self.status_code,
            "detail": self.detail,
            "error_type": self.__class__.__name__,
        }


class R2RDocumentProcessingError(R2RException):
    def __init__(
        self, error_message: str, document_id: UUID, status_code: int = 500
    ):
        detail = {
            "document_id": str(document_id),
            "error_type": "document_processing_error",
        }
        super().__init__(error_message, status_code, detail)

    def to_dict(self):
        result = super().to_dict()
        result["document_id"] = self.document_id
        return result


class PDFParsingError(R2RException):
    """Custom exception for PDF parsing errors."""

    def __init__(
        self,
        message: str,
        original_error: Exception | None = None,
        status_code: int = 500,
    ):
        detail = {
            "original_error": str(original_error) if original_error else None
        }
        super().__init__(message, status_code, detail)


class PopplerNotFoundError(PDFParsingError):
    """Specific error for when Poppler is not installed."""

    def __init__(self):
        installation_instructions = textwrap.dedent("""
            PDF processing requires Poppler to be installed. Please install Poppler and ensure it's in your system PATH.

            Installing poppler:
            - Ubuntu: sudo apt-get install poppler-utils
            - Archlinux: sudo pacman -S poppler
            - MacOS: brew install poppler
            - Windows:
              1. Download poppler from @oschwartz10612
              2. Move extracted directory to desired location
              3. Add bin/ directory to PATH
              4. Test by running 'pdftoppm -h' in terminal
        """)
        super().__init__(
            message=installation_instructions,
            status_code=422,
            original_error=None,
        )
