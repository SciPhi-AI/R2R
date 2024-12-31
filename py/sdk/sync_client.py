import asyncio
import contextlib
import functools
import inspect
from typing import Any, Callable, Coroutine, TypeVar

from .async_client import R2RAsyncClient

T = TypeVar("T")


class R2RClient(R2RAsyncClient):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # Store async version of _make_request
        self._async_make_request = self._make_request

        # Only wrap v3 methods since they're already working
        self._wrap_v3_methods()

    def _make_sync_request(self, *args, **kwargs):
        """Sync version of _make_request for v2 methods"""
        return self._loop.run_until_complete(
            self._async_make_request(*args, **kwargs)
        )

    def _wrap_v3_methods(self) -> None:
        """Wraps only v3 SDK object methods"""
        sdk_objects = [
            self.chunks,
            self.collections,
            self.conversations,
            self.documents,
            self.graphs,
            self.indices,
            self.prompts,
            self.retrieval,
            self.users,
            self.system,
        ]

        for sdk_obj in sdk_objects:
            for name in dir(sdk_obj):
                if name.startswith("_"):
                    continue

                attr = getattr(sdk_obj, name)
                if inspect.iscoroutinefunction(attr):
                    wrapped = self._make_sync_method(attr)
                    setattr(sdk_obj, name, wrapped)

    # def _make_sync_method(self, async_method):
    def _make_sync_method(
        self, async_method: Callable[..., Coroutine[Any, Any, T]]
    ) -> Callable[..., T]:
        @functools.wraps(async_method)
        def wrapped(*args, **kwargs):
            return self._loop.run_until_complete(async_method(*args, **kwargs))

        return wrapped

    def __del__(self):
        if hasattr(self, "_loop") and self._loop is not None:
            with contextlib.suppress(Exception):
                if not self._loop.is_closed():
                    try:
                        self._loop.run_until_complete(self._async_close())
                    except RuntimeError:
                        # If the event loop is already running, we can't use run_until_complete
                        if self._loop.is_running():
                            self._loop.call_soon_threadsafe(self._sync_close)
                        else:
                            asyncio.run_coroutine_threadsafe(
                                self._async_close(), self._loop
                            )
                    finally:
                        self._loop.close()
