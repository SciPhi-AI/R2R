import asyncio
import contextlib
import functools
import inspect
from collections.abc import AsyncGenerator as AsyncGenType

# from typing import Any, Callable, Coroutine, TypeVar
from typing import Any, AsyncGenerator, Callable, Coroutine, Generator, TypeVar

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

    def _wrap_async_generator(
        self, async_gen: AsyncGenerator[T, None]
    ) -> Generator[T, None, None]:
        """
        Convert a real async generator (object) into a synchronous generator.
        """
        while True:
            try:
                yield self._loop.run_until_complete(async_gen.__anext__())
            except StopAsyncIteration:
                break

    def _wrap_async_method(
        self,
        async_method: Callable[..., Any],
    ) -> Callable[..., Any]:
        """
        Wraps a normal async method (returns awaitable) or an async method that
        *returns* an async generator into a synchronous method/generator.

        - If the method returns a normal object (like dict, str, etc.), just return it.
        - If the method returns an async generator, yield items in a sync generator.
        """

        @functools.wraps(async_method)
        def sync_wrapper(*args, **kwargs):
            # Call the async method in our event loop:
            result = self._loop.run_until_complete(
                async_method(*args, **kwargs)
            )

            # If the returned object is actually an async generator, wrap it:
            if isinstance(result, AsyncGenType):
                return self._wrap_async_generator(result)
            else:
                return result

        return sync_wrapper

    def _wrap_v3_methods(self) -> None:
        """
        Inspect the v3 SDK objects and replace all async methods
        (including those returning an async generator) with sync equivalents.
        """
        sdk_objects = [
            self.chunks,
            self.collections,
            self.conversations,
            self.documents,
            self.graphs,
            self.indices,
            self.prompts,
            self.retrieval,
            self.system,
            self.users,
        ]

        for sdk_obj in sdk_objects:
            for name in dir(sdk_obj):
                if name.startswith("_"):
                    continue
                attr = getattr(sdk_obj, name)

                # We only care about coroutine functions
                if inspect.iscoroutinefunction(attr):
                    # Wrap every async method with our unified wrapper:
                    wrapped = self._wrap_async_method(attr)
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
