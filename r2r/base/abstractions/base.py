import asyncio
import uuid
from typing import List

from pydantic import BaseModel


class UserStats(BaseModel):
    user_id: uuid.UUID
    num_files: int
    total_size_in_bytes: int
    document_ids: List[uuid.UUID]


class AsyncSyncMeta(type):
    _event_loop = None  # Class-level shared event loop

    @classmethod
    def get_event_loop(cls):
        if cls._event_loop is None or cls._event_loop.is_closed():
            cls._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(cls._event_loop)
        return cls._event_loop

    def __new__(cls, name, bases, dct):
        new_cls = super().__new__(cls, name, bases, dct)
        for attr_name, attr_value in dct.items():
            if asyncio.iscoroutinefunction(attr_value) and getattr(
                attr_value, "_syncable", False
            ):
                sync_method_name = attr_name[
                    1:
                ]  # Remove leading 'a' for sync method
                async_method = attr_value

                def make_sync_method(async_method):
                    def sync_wrapper(self, *args, **kwargs):
                        loop = cls.get_event_loop()
                        if not loop.is_running():
                            # Setup to run the loop in a background thread if necessary
                            # to prevent blocking the main thread in a synchronous call environment
                            from threading import Thread

                            result = None
                            exception = None

                            def run():
                                nonlocal result, exception
                                try:
                                    asyncio.set_event_loop(loop)
                                    result = loop.run_until_complete(
                                        async_method(self, *args, **kwargs)
                                    )
                                except Exception as e:
                                    exception = e
                                finally:
                                    generation_config = kwargs.get(
                                        "rag_generation_config", None
                                    )
                                    if (
                                        not generation_config
                                        or not generation_config.stream
                                    ):
                                        loop.run_until_complete(
                                            loop.shutdown_asyncgens()
                                        )
                                        loop.close()

                            thread = Thread(target=run)
                            thread.start()
                            thread.join()
                            if exception:
                                raise exception
                            return result
                        else:
                            # If there's already a running loop, schedule and execute the coroutine
                            future = asyncio.run_coroutine_threadsafe(
                                async_method(self, *args, **kwargs), loop
                            )
                            return future.result()

                    return sync_wrapper

                setattr(
                    new_cls, sync_method_name, make_sync_method(async_method)
                )
        return new_cls


def syncable(func):
    """Decorator to mark methods for synchronous wrapper creation."""
    func._syncable = True
    return func
