import asyncio
import contextlib
import functools
import inspect
from typing import Any

from .async_client import R2RAsyncClient
from .v2 import (
    SyncAuthMixins,
    SyncIngestionMixins,
    SyncKGMixins,
    SyncManagementMixins,
    SyncRetrievalMixins,
    SyncServerMixins,
)


class R2RClient(R2RAsyncClient):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # Store async version of _make_request
        self._async_make_request = self._make_request

        # Only wrap v3 methods since they're already working
        self._wrap_v3_methods()

        # Override v2 methods with sync versions
        self._override_v2_methods()

    def _make_sync_request(self, *args, **kwargs):
        """Sync version of _make_request for v2 methods"""
        return self._loop.run_until_complete(
            self._async_make_request(*args, **kwargs)
        )

    def _override_v2_methods(self):
        """
        Replace async v2 methods with sync versions
        This is really ugly, but it's the only way to make it work once we
        remove v2, we can just resort to the metaclass approach that is in utils
        """
        sync_mixins = {
            SyncAuthMixins: ["auth_methods"],
            SyncIngestionMixins: ["ingestion_methods"],
            SyncKGMixins: ["kg_methods"],
            SyncManagementMixins: ["management_methods"],
            SyncRetrievalMixins: ["retrieval_methods"],
            SyncServerMixins: ["server_methods"],
        }

        for sync_class in sync_mixins:
            for name, method in sync_class.__dict__.items():
                if not name.startswith("_") and inspect.isfunction(method):
                    # Create a wrapper that uses sync _make_request
                    def wrap_method(m):
                        def wrapped(self, *args, **kwargs):
                            # Temporarily swap _make_request
                            original_make_request = self._make_request
                            self._make_request = self._make_sync_request
                            try:
                                return m(self, *args, **kwargs)
                            finally:
                                # Restore original _make_request
                                self._make_request = original_make_request

                        return wrapped

                    bound_method = wrap_method(method).__get__(
                        self, self.__class__
                    )
                    setattr(self, name, bound_method)

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
        ]

        for sdk_obj in sdk_objects:
            for name in dir(sdk_obj):
                if name.startswith("_"):
                    continue

                attr = getattr(sdk_obj, name)
                if inspect.iscoroutinefunction(attr):
                    wrapped = self._make_sync_method(attr)
                    setattr(sdk_obj, name, wrapped)

    def _make_sync_method(self, async_method):
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
