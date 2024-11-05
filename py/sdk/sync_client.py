import asyncio

from .async_client import R2RAsyncClient
from .utils import SyncClientMetaclass
from .v3.chunks import SyncChunkSDK
from .v3.collections import SyncCollectionsSDK
from .v3.documents import SyncDocumentSDK
from .v3.indices import SyncIndexSDK
from .v3.retrieval import SyncRetrievalSDK
from .v3.users import SyncUsersSDK


class R2RClient(R2RAsyncClient, metaclass=SyncClientMetaclass):
    """
    Synchronous client for the R2R API.

    Args:
        base_url (str, optional): The base URL of the R2R API. Defaults to "http://localhost:7272".
        prefix (str, optional): The prefix for the API. Defaults to "/v2".
        custom_client (httpx.AsyncClient, optional): A custom HTTP client. Defaults to None.
        timeout (float, optional): The timeout for requests. Defaults to 300.0.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.documents = SyncDocumentSDK(self.documents)
        self.chunks = SyncChunkSDK(self.chunks)
        self.retrieval = SyncRetrievalSDK(self.retrieval)
        self.indices = SyncIndexSDK(self.indices)
        self.users = SyncUsersSDK(self.users)
        self.collections = SyncCollectionsSDK(self.collections)

    def _make_streaming_request(self, method: str, endpoint: str, **kwargs):
        async_gen = super()._make_streaming_request(method, endpoint, **kwargs)
        return self._sync_generator(async_gen)

    def _sync_generator(self, async_gen):
        loop = asyncio.get_event_loop()
        try:
            while True:
                yield loop.run_until_complete(async_gen.__anext__())
        except StopAsyncIteration:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.close())
