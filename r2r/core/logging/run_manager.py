import asyncio
import contextvars
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

from .kv_logger import KVLoggingConnectionSingleton

run_id_var = contextvars.ContextVar("run_id")


class RunManager:
    def __init__(self, logger: KVLoggingConnectionSingleton):
        self.logger = logger
        self.run_info = {}

    def generate_run_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def set_run_info(self, pipeline_id: uuid.UUID, pipeline_type: str):
        run_id = self.generate_run_id()
        token = run_id_var.set(run_id)
        self.run_info[run_id] = {"pipeline_type": pipeline_type}
        return run_id, token

    async def get_run_info(self):
        run_id = run_id_var.get()
        return self.run_info.get(run_id, None)

    async def log_run_info(
        self, key: str, value: Any, is_info_log: bool = False
    ):
        run_id = run_id_var.get()
        if run_id:
            await self.logger.log(
                log_id=run_id, key=key, value=value, is_info_log=is_info_log
            )

    async def clear_run_info(self, token: contextvars.Token):
        run_id = run_id_var.get()
        run_id_var.reset(token)
        if run_id and run_id in self.run_info:
            del self.run_info[run_id]


@asynccontextmanager
async def manage_run(run_manager: RunManager, pipeline_type: str):
    pipeline_id = uuid.uuid4()
    run_id, token = await run_manager.set_run_info(pipeline_id, pipeline_type)
    try:
        yield run_id
    finally:
        await run_manager.clear_run_info(token)


# import uuid
# import asyncio
# from contextlib import asynccontextmanager
# from typing import Optional, Any
# from .kv_logger import KVLoggingConnectionSingleton


# class RunManager:
#     def __init__(self, logger: KVLoggingConnectionSingleton):
#         self.logger = logger
#         self.run_info = {}
#         self.current_run_ids = {}
#         self.run_id_queue = asyncio.Queue()

#     def generate_run_id(self) -> uuid.UUID:
#         return uuid.uuid4()

#     async def set_run_info(self, pipeline_id: uuid.UUID, pipeline_type: str):
#         run_id = self.generate_run_id()
#         await self.run_id_queue.put(run_id)
#         self.current_run_ids[pipeline_id] = run_id
#         self.run_info[run_id] = {"pipeline_type": pipeline_type}
#         return run_id

#     async def get_run_info(self, run_id: uuid.UUID):
#         return self.run_info.get(run_id, None)

#     async def log_run_info(self, pipeline_id: uuid.UUID, key: str, value: Any, is_info_log: bool = False):
#         run_id = self.current_run_ids.get(pipeline_id)
#         if run_id:
#             await self.logger.log(key=key, value=value, is_info_log=is_info_log)

#     async def clear_run_info(self, pipeline_id: uuid.UUID):
#         run_id = self.current_run_ids.pop(pipeline_id, None)
#         if run_id and run_id in self.run_info:
#             del self.run_info[run_id]

# @asynccontextmanager
# async def manage_run(run_manager: RunManager, pipeline_id: uuid.UUID, pipeline_type: str):
#     run_id = await run_manager.set_run_info(pipeline_id, pipeline_type)
#     try:
#         yield run_id
#     finally:
#         await run_manager.clear_run_info(pipeline_id)

# # import uuid
# # from contextlib import asynccontextmanager
# # from typing import Optional, Any
# # from .kv_logger import KVLoggingConnectionSingleton


# # class RunManager:
# #     def __init__(self, logger: KVLoggingConnectionSingleton):
# #         self.logger = logger
# #         self.run_info = {}

# #     def generate_run_id(self) -> uuid.UUID:
# #         return uuid.uuid4()

# #     def set_run_info(self, run_id: uuid.UUID, pipeline_type: str):
# #         self.run_info[run_id] = {"pipeline_type": pipeline_type}

# #     def get_run_info(self, run_id: uuid.UUID):
# #         return self.run_info.get(run_id, None)

# #     async def log_run_info(
# #         self, key: str, value: Any, is_info_log: bool = False
# #     ):
# #         await self.logger.log(
# #             key=key, value=value, is_info_log=is_info_log
# #         )


# # @asynccontextmanager
# # async def manage_run(run_manager: RunManager, pipeline_type: str):
# #     run_id = run_manager.generate_run_id()
# #     run_manager.set_run_info(run_id, pipeline_type)
# #     try:
# #         yield run_id
# #     finally:
# #         run_manager.run_info.pop(run_id, None)
