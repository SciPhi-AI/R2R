import asyncio
import functools
from typing import Callable, Any


def sync_wrapper(async_func: Callable) -> Callable:
    @functools.wraps(async_func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.get_event_loop().run_until_complete(
            async_func(*args, **kwargs)
        )

    return wrapper


class SyncClientMetaclass(type):
    def __new__(cls, name, bases, dct):
        for attr_name, attr_value in dct.items():
            if asyncio.iscoroutinefunction(attr_value):
                dct[attr_name] = sync_wrapper(attr_value)
        return super().__new__(cls, name, bases, dct)
