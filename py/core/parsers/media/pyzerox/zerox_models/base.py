from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Optional, Type, TypeVar

if TYPE_CHECKING:
    from ..zerox_models import CompletionResponse

T = TypeVar("T", bound="BaseModel")


class BaseModel(ABC):
    """
    Base class for all models.
    """

    @abstractmethod
    async def completion(
        self,
    ) -> "CompletionResponse":
        raise NotImplementedError("Subclasses must implement this method")

    @abstractmethod
    def validate_access(
        self,
    ) -> None:
        raise NotImplementedError("Subclasses must implement this method")

    @abstractmethod
    def validate_model(
        self,
    ) -> None:
        raise NotImplementedError("Subclasses must implement this method")

    def __init__(
        self,
        model: Optional[str] = None,
        **kwargs,
    ):
        self.model = model
        self.kwargs = kwargs

        ## validations
        # self.validate_model()
        # self.validate_access()
