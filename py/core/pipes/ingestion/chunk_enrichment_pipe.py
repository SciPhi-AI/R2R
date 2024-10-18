# import asyncio
# import logging
# from typing import Any, AsyncGenerator, Optional, Union

# from core.base import (
#     AsyncPipe,
#     PipeType,
#     R2RLoggingProvider,
# )



# class ChunkEnrichmentPipe(AsyncPipe):
#     """
#     Enriches chunks using a specified embedding model.
#     """

#     class Input(AsyncPipe.Input):
#         message: list[DocumentExtraction]


#     def __init__(self, config: AsyncPipe.PipeConfig, type: PipeType = PipeType.INGESTOR, pipe_logger: Optional[R2RLoggingProvider] = None):
#         super().__init__(config, type, pipe_logger)

#     async def run(self, input: Input, state: Optional[AsyncState] = None, run_manager: Optional[RunManager] = None) -> AsyncGenerator[DocumentExtraction, None]:
#         pass



    
