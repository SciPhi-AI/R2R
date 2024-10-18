import asyncio
import contextlib
from typing import Generator

from .async_client import R2RAsyncClient
from .utils import SyncClientMetaclass


class R2RClient(R2RAsyncClient, metaclass=SyncClientMetaclass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _make_request(self, method: str, endpoint: str, **kwargs):
        return asyncio.get_event_loop().run_until_complete(
            self.async_client._make_request(method, endpoint, **kwargs)
        )

    def _make_streaming_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Generator:
        async_gen = self.async_client._make_streaming_request(
            method, endpoint, **kwargs
        )
        return self._sync_generator(async_gen)

    def _sync_generator(self, async_gen):
        loop = asyncio.get_event_loop()
        with contextlib.suppress(StopAsyncIteration):
            while True:
                yield loop.run_until_complete(async_gen.__anext__())

    def __getattr__(self, name):
        async_attr = getattr(self.async_client, name)
        if callable(async_attr):

            def sync_wrapper(*args, **kwargs):
                result = asyncio.get_event_loop().run_until_complete(
                    async_attr(*args, **kwargs)
                )
                if isinstance(result, asyncio.AsyncGenerator):
                    return self._sync_generator(result)
                return result

            return sync_wrapper
        return async_attr

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        asyncio.get_event_loop().run_until_complete(self.async_client.close())
