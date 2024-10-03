"""Base pipeline class for running a sequence of pipes."""

import asyncio
import logging
import traceback
from typing import Any, AsyncGenerator, Optional

from ..logging.run_logger import RunLoggingSingleton
from ..logging.run_manager import RunManager, manage_run
from ..pipes.base_pipe import AsyncPipe, AsyncState

logger = logging.getLogger(__name__)


class AsyncPipeline:
    """Pipeline class for running a sequence of pipes."""

    def __init__(
        self,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        run_manager: Optional[RunManager] = None,
    ):
        self.pipes: list[AsyncPipe] = []
        self.upstream_outputs: list[list[dict[str, str]]] = []
        self.pipe_logger = pipe_logger or RunLoggingSingleton()
        self.run_manager = run_manager or RunManager(self.pipe_logger)
        self.futures: dict[str, asyncio.Future] = {}
        self.level = 0

    def add_pipe(
        self,
        pipe: AsyncPipe,
        add_upstream_outputs: Optional[list[dict[str, str]]] = None,
        *args,
        **kwargs,
    ) -> None:
        """Add a pipe to the pipeline."""
        self.pipes.append(pipe)
        if not add_upstream_outputs:
            add_upstream_outputs = []
        self.upstream_outputs.append(add_upstream_outputs)

    async def run(
        self,
        input: Any,
        state: Optional[AsyncState] = None,
        stream: bool = False,
        run_manager: Optional[RunManager] = None,
        *args: Any,
        **kwargs: Any,
    ):
        """Run the pipeline."""
        run_manager = run_manager or self.run_manager
        self.state = state or AsyncState()
        current_input = input
        async with manage_run(run_manager):
            try:
                for pipe_num in range(len(self.pipes)):
                    config_name = self.pipes[pipe_num].config.name
                    self.futures[config_name] = asyncio.Future()

                    current_input = self._run_pipe(
                        pipe_num,
                        current_input,
                        run_manager,
                        *args,
                        **kwargs,
                    )
                    self.futures[config_name].set_result(current_input)

            except Exception as error:
                # TODO: improve error handling here
                error_trace = traceback.format_exc()
                logger.error(
                    f"Pipeline failed with error: {error}\n\nStack trace:\n{error_trace}"
                )
                raise error

            return (
                current_input
                if stream
                else await self._consume_all(current_input)
            )

    async def _consume_all(self, gen: AsyncGenerator) -> list[Any]:
        result = []
        async for item in gen:
            if hasattr(
                item, "__aiter__"
            ):  # Check if the item is an async generator
                sub_result = await self._consume_all(item)
                result.extend(sub_result)
            else:
                result.append(item)
        return result

    async def _run_pipe(
        self,
        pipe_num: int,
        input: Any,
        run_manager: RunManager,
        *args: Any,
        **kwargs: Any,
    ):
        # Collect inputs, waiting for the necessary futures
        pipe = self.pipes[pipe_num]
        add_upstream_outputs = self.sort_upstream_outputs(
            self.upstream_outputs[pipe_num]
        )
        input_dict = {"message": input}

        # Collection upstream outputs by prev_pipe_name
        grouped_upstream_outputs: dict[str, list] = {}
        for upstream_input in add_upstream_outputs:
            upstream_pipe_name = upstream_input["prev_pipe_name"]
            if upstream_pipe_name not in grouped_upstream_outputs:
                grouped_upstream_outputs[upstream_pipe_name] = []
            grouped_upstream_outputs[upstream_pipe_name].append(upstream_input)

        for (
            upstream_pipe_name,
            upstream_inputs,
        ) in grouped_upstream_outputs.items():

            async def resolve_future_output(future):
                result = future.result()
                # consume the async generator
                return [item async for item in result]

            async def replay_items_as_async_gen(items):
                for item in items:
                    yield item

            temp_results = await resolve_future_output(
                self.futures[upstream_pipe_name]
            )
            if upstream_pipe_name == self.pipes[pipe_num - 1].config.name:
                input_dict["message"] = replay_items_as_async_gen(temp_results)

            for upstream_input in upstream_inputs:
                outputs = await self.state.get(upstream_pipe_name, "output")
                prev_output_field = upstream_input.get(
                    "prev_output_field", None
                )
                if not prev_output_field:
                    raise ValueError(
                        "`prev_output_field` must be specified in the upstream_input"
                    )
                input_dict[upstream_input["input_field"]] = outputs[
                    prev_output_field
                ]
        async for ele in await pipe.run(
            pipe.Input(**input_dict),
            self.state,
            run_manager,
            *args,
            **kwargs,
        ):
            yield ele

    def sort_upstream_outputs(
        self, add_upstream_outputs: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        pipe_name_to_index = {
            pipe.config.name: index for index, pipe in enumerate(self.pipes)
        }

        def get_pipe_index(upstream_output):
            return pipe_name_to_index[upstream_output["prev_pipe_name"]]

        sorted_outputs = sorted(
            add_upstream_outputs, key=get_pipe_index, reverse=True
        )
        return sorted_outputs


async def dequeue_requests(queue: asyncio.Queue) -> AsyncGenerator:
    """Create an async generator to dequeue requests."""
    while True:
        request = await queue.get()
        if request is None:
            break
        yield request
