"""
The `vecs.experimental.adapter.base` module provides abstract classes and utilities
for creating and handling adapters in vecs. Adapters allow users to interact with
a collection using media types other than vectors.

All public classes, enums, and functions are re-exported by `vecs.adapters` module.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Generator, Iterable, Optional, Tuple, Union
from uuid import UUID

from vecs.exc import ArgError

MetadataValues = Union[str, int, float, bool, list[str]]
Metadata = Dict[str, MetadataValues]
Numeric = Union[int, float, complex]

Record = Tuple[
    UUID,
    UUID,
    UUID,
    UUID,
    list[UUID],
    Iterable[Numeric],
    str,
    Metadata,
]


class AdapterContext(str, Enum):
    """
    An enum representing the different contexts in which a Pipeline
    will be invoked.

    Attributes:
        upsert (str): The Collection.upsert method
        query (str): The Collection.query method
    """

    upsert = "upsert"
    query = "query"


class AdapterStep(ABC):
    """
    Abstract class representing a step in the adapter pipeline.

    Each adapter step should adapt a user media into a tuple of:
     - id (str)
     - media (unknown type)
     - metadata (dict)

    If the user provides id or metadata, default production is overridden.
    """

    @property
    def exported_dimension(self) -> Optional[int]:
        """
        Property that should be overridden by subclasses to provide the output dimension
        of the adapter step.
        """
        return None

    @abstractmethod
    def __call__(
        self,
        records: Iterable[Tuple[str, Any, Optional[Dict]]],
        adapter_context: AdapterContext,
    ) -> Generator[Tuple[str, Any, Dict], None, None]:
        """
        Abstract method that should be overridden by subclasses to handle each record.
        """


class Adapter:
    """
    Class representing a sequence of AdapterStep instances forming a pipeline.
    """

    def __init__(self, steps: list[AdapterStep]):
        """
        Initialize an Adapter instance with a list of AdapterStep instances.

        Args:
            steps: list of AdapterStep instances.

        Raises:
            ArgError: Raised if the steps list is empty.
        """
        self.steps = steps
        if len(steps) < 1:
            raise ArgError("Adapter must contain at least 1 step")

    @property
    def exported_dimension(self) -> Optional[int]:
        """
        The output dimension of the adapter. Returns the exported dimension of the last
        AdapterStep that provides one (from end to start of the steps list).
        """
        for step in reversed(self.steps):
            step_dim = step.exported_dimension
            if step_dim is not None:
                return step_dim
        return None

    def __call__(
        self,
        records: Iterable[Tuple[str, Any, Optional[Dict]]],
        adapter_context: AdapterContext,
    ) -> Generator[Tuple[str, Any, Dict], None, None]:
        """
        Invokes the adapter pipeline on an iterable of records.

        Args:
            records: Iterable of tuples each containing an id, a media and an optional dict.
            adapter_context: Context of the adapter.

        Yields:
            Tuples each containing an id, a media and a dict.
        """
        pipeline = records
        for step in self.steps:
            pipeline = step(pipeline, adapter_context)

        yield from pipeline  # type: ignore
