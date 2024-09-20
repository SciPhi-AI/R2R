import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Any, Type, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T", bound="R2RSerializable")


class R2RSerializable(BaseModel):
    @classmethod
    def from_dict(cls: Type[T], data: Union[dict[str, Any], str]) -> T:
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump(exclude_unset=True)
        return self._serialize_values(data)

    def to_json(self) -> str:
        data = self.to_dict()
        return json.dumps(data)

    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        return cls.model_validate_json(json_str)

    @staticmethod
    def _serialize_values(data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: R2RSerializable._serialize_values(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [R2RSerializable._serialize_values(v) for v in data]
        elif isinstance(data, UUID):
            return str(data)
        elif isinstance(data, Enum):
            return data.value
        elif isinstance(data, datetime):
            return data.isoformat()
        else:
            return data

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            bytes: lambda v: v.decode("utf-8", errors="ignore"),
        }


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
