from typing import Any, Optional


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
    def __init__(self, error_message, document_id):
        self.document_id = document_id
        super().__init__(error_message, 400, {"document_id": document_id})

    def to_dict(self):
        result = super().to_dict()
        result["document_id"] = self.document_id
        return result
