from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Union


@dataclass
class ZeroxArgs:
    """
    Dataclass to store the arguments for the Zerox class.
    """

    file_path: str
    cleanup: bool = True
    concurrency: int = 10
    maintain_format: bool = False
    model: str = ("gpt-4o-mini",)
    output_dir: Optional[str] = None
    temp_dir: Optional[str] = None
    custom_system_prompt: Optional[str] = None
    kwargs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Page:
    """
    Dataclass to store the page content.
    """

    content: str
    content_length: int
    page: int


@dataclass
class ZeroxOutput:
    """
    Dataclass to store the output of the Zerox class.
    """

    completion_time: float
    input_tokens: int
    output_tokens: int
    pages: List[Page]
