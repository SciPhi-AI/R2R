from typing import Optional

import pytest

from fuse import FUSEException


class BaseTest:
    """Base class for all test classes with common utilities."""

    @staticmethod
    async def cleanup_resource(
        cleanup_func, resource_id: Optional[str] = None
    ) -> None:
        """Generic cleanup helper that won't fail the test if cleanup fails."""
        if resource_id:
            try:
                await cleanup_func(id=resource_id)
            except FUSEException:
                pass
