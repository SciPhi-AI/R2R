from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from pydantic import BaseModel


class InnerConfig(BaseModel, ABC):
    """A base provider configuration class."""

    extra_fields: dict[str, Any] = {}

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        ignore_extra = True

    @classmethod
    def create(cls: Type["InnerConfig"], **kwargs: Any) -> "InnerConfig":
        base_args = cls.model_fields.keys()
        filtered_kwargs = {
            k: v if v != "None" else None
            for k, v in kwargs.items()
            if k in base_args
        }
        instance = cls(**filtered_kwargs)  # type: ignore
        for k, v in kwargs.items():
            if k not in base_args:
                instance.extra_fields[k] = v
        return instance


class AppConfig(InnerConfig):
    project_name: Optional[str] = None
    default_max_documents_per_user: Optional[int] = 100
    default_max_chunks_per_user: Optional[int] = 10_000
    default_max_collections_per_user: Optional[int] = 5
    default_max_upload_size: int = 2_000_000  # e.g. ~2 MB
    quality_llm: Optional[str] = None
    fast_llm: Optional[str] = None
    vlm: Optional[str] = None
    audio_lm: Optional[str] = None
    reasoning_llm: Optional[str] = None
    planning_llm: Optional[str] = None

    # File extension to max-size mapping
    # These are examples; adjust sizes as needed.
    max_upload_size_by_type: dict[str, int] = {
        # Common text-based formats
        "txt": 2_000_000,
        "md": 2_000_000,
        "tsv": 2_000_000,
        "csv": 5_000_000,
        "xml": 2_000_000,
        "html": 5_000_000,
        # Office docs
        "doc": 10_000_000,
        "docx": 10_000_000,
        "ppt": 20_000_000,
        "pptx": 20_000_000,
        "xls": 10_000_000,
        "xlsx": 10_000_000,
        "odt": 5_000_000,
        # PDFs can expand quite a bit when converted to text
        "pdf": 30_000_000,
        # E-mail
        "eml": 5_000_000,
        "msg": 5_000_000,
        "p7s": 5_000_000,
        # Images
        "bmp": 5_000_000,
        "heic": 5_000_000,
        "jpeg": 5_000_000,
        "jpg": 5_000_000,
        "png": 5_000_000,
        "tiff": 5_000_000,
        # Others
        "epub": 10_000_000,
        "rtf": 5_000_000,
        "rst": 5_000_000,
        "org": 5_000_000,
    }


class ProviderConfig(BaseModel, ABC):
    """A base provider configuration class."""

    app: AppConfig  # Add an app_config field
    extra_fields: dict[str, Any] = {}
    provider: Optional[str] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        ignore_extra = True

    @abstractmethod
    def validate_config(self) -> None:
        pass

    @classmethod
    def create(cls: Type["ProviderConfig"], **kwargs: Any) -> "ProviderConfig":
        base_args = cls.model_fields.keys()
        filtered_kwargs = {
            k: v if v != "None" else None
            for k, v in kwargs.items()
            if k in base_args
        }
        instance = cls(**filtered_kwargs)  # type: ignore
        for k, v in kwargs.items():
            if k not in base_args:
                instance.extra_fields[k] = v
        return instance

    @property
    @abstractmethod
    def supported_providers(self) -> list[str]:
        """Define a list of supported providers."""
        pass

    @classmethod
    def from_dict(
        cls: Type["ProviderConfig"], data: dict[str, Any]
    ) -> "ProviderConfig":
        """Create a new instance of the config from a dictionary."""
        return cls.create(**data)


class Provider(ABC):
    """A base provider class to provide a common interface for all
    providers."""

    def __init__(self, config: ProviderConfig, *args, **kwargs):
        if config:
            config.validate_config()
        self.config = config
