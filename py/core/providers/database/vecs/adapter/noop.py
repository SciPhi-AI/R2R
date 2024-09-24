"""
The `vecs.experimental.adapter.noop` module provides a default no-op (no operation) adapter
that passes the inputs through without any modification. This can be useful when no specific
adapter processing is required.

All public classes, enums, and functions are re-exported by `vecs.adapters` module.
"""

from typing import Generator, Iterable, Optional

from .base import AdapterContext, AdapterStep, Record


class NoOp(AdapterStep):
    """
    NoOp is a no-operation AdapterStep. It is a default adapter that passes through
    the input records without any modifications.
    """

    def __init__(self, dimension: int):
        """
        Initializes the NoOp adapter with a dimension.

        Args:
            dimension (int): The dimension of the input vectors.
        """
        self._dimension = dimension

    @property
    def exported_dimension(self) -> Optional[int]:
        """
        Returns the dimension of the adapter.

        Returns:
            int: The dimension of the input vectors.
        """
        return self._dimension

    def __call__(
        self,
        records: Iterable[Record],
        adapter_context: AdapterContext,
    ) -> Generator[Record, None, None]:
        for record in records:
            (
                fragment_id,
                extraction_id,
                document_id,
                user_id,
                collection_ids,
                vec,
                text,
                metadata,
            ) = record
            yield (
                str(fragment_id),
                str(extraction_id),
                str(document_id),
                str(user_id),
                [str(gid) for gid in collection_ids],
                vec,
                text,
                metadata or {},
            )
