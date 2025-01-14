"""
Not currently being used due to some grossness with the way that the v2 SDK methods were structured, but
we can return to this once we remove v2 SDK methods.
"""

import asyncio
import functools
import inspect
from typing import Any, Callable


def sync_wrapper(async_func: Callable) -> Callable:
    if inspect.isasyncgenfunction(async_func):

        @functools.wraps(async_func)
        def generator_wrapper(*args: Any, **kwargs: Any) -> Any:
            async_gen = async_func(*args, **kwargs)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            def sync_gen():
                try:
                    while True:
                        yield loop.run_until_complete(async_gen.__anext__())
                except StopAsyncIteration:
                    pass
                finally:
                    loop.close()

            return sync_gen()

        return generator_wrapper
    else:

        @functools.wraps(async_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(async_func(*args, **kwargs))
            else:
                import threading

                def run_in_new_loop(loop, coro):
                    asyncio.set_event_loop(loop)
                    return loop.run_until_complete(coro)

                new_loop = asyncio.new_event_loop()
                return loop.run_in_executor(
                    None,
                    run_in_new_loop,
                    new_loop,
                    async_func(*args, **kwargs),
                )

        return wrapper


class SyncClientMetaclass(type):
    def __new__(cls, name, bases, dct):
        for attr_name, attr_value in dct.items():
            if asyncio.iscoroutinefunction(attr_value):
                dct[attr_name] = sync_wrapper(attr_value)

        for base in bases:
            for attr_name in dir(base):
                attr_value = getattr(base, attr_name)
                if asyncio.iscoroutinefunction(attr_value):
                    dct[attr_name] = sync_wrapper(attr_value)

        return super().__new__(cls, name, bases, dct)
