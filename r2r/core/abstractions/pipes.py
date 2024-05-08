import asyncio
import logging
from abc import ABC, abstractmethod
from copy import copy
from enum import Enum
from typing import (
    Any,
    AsyncGenerator,
    Generic,
    Optional,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import ValidationError

from ..utils import generate_run_id

logger = logging.getLogger(__name__)


class PipeType(Enum):
    EMBEDDING = "embedding"
    GENERATION = "generation"
    PARSING = "parsing"
    QUERY_TRANSFORM = "query_transform"
    SEARCH = "search"
    AGGREGATOR = "aggregator"
    STORAGE = "storage"
    OTHER = "other"


class PipeFlow(Enum):
    STANDARD = "standard"
    FAN_OUT = "fan_out"
    FAN_IN = "fan_in"


class PipeRunInfo:
    def __init__(self, run_id: str, type: PipeType) -> None:
        self.run_id = run_id
        self.type = type


class PipeConfig(ABC):
    """A base pipe configuration class"""

    name: str


class Context:
    def __init__(self):
        self.data = {}
        self.lock = asyncio.Lock()

    async def update(self, outer_key: str, values: dict):
        async with self.lock:
            if not isinstance(values, dict):
                raise ValueError("Values must be contained in a dictionary.")
            if outer_key not in self.data:
                self.data[outer_key] = {}
            for inner_key, inner_value in values.items():
                self.data[outer_key][inner_key] = inner_value

    async def get(self, outer_key: str, inner_key: str, default=None):
        async with self.lock:
            if outer_key not in self.data:
                raise ValueError(
                    f"Key {outer_key} does not exist in the context."
                )
            if inner_key not in self.data[outer_key]:
                return default or {}
            return self.data[outer_key][inner_key]

    async def delete(self, outer_key: str, inner_key: Optional[str] = None):
        async with self.lock:
            if outer_key in self.data and not inner_key:
                del self.data[outer_key]
            else:
                if inner_key not in self.data[outer_key]:
                    raise ValueError(
                        f"Key {inner_key} does not exist in the context."
                    )
                del self.data[outer_key][inner_key]


TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class AsyncPipe(Generic[TInput, TOutput], ABC):
    def __init__(self, config: PipeConfig, *args, **kwargs):
        self.__class__.CONFIG_TYPE = type(config)
        self._config = config

        self.pipe_run_info: Optional[PipeRunInfo] = None
        self.is_async = True

        type_hints = get_type_hints(self.run)
        self.INPUT_TYPE = type_hints.get("input")
        self.OUTPUT_TYPE = type_hints.get("return")

    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        if isinstance(attr, property):
            return attr

        # Skip wrapping for these specific attributes or any non-callable attributes
        if name in [
            "INPUT_TYPE",
            "OUTPUT_TYPE",
            "__dict__",
            "__class__",
        ] or not callable(attr):
            return attr

        if callable(attr) and name not in [
            "__init__",
            "__getattribute__",
            "_check_pipe_initialized",
            "_initialize_pipe",
            "close",
            "run",
        ]:

            def newfunc(*args, **kwargs):
                self._check_pipe_initialized()
                return attr(*args, **kwargs)

            return newfunc
        else:
            return attr

    def _check_pipe_initialized(self) -> None:
        if self.pipe_run_info is None:
            raise ValueError(
                "The pipe has not been initialized. Please call `_initialize_pipe` before running the pipe."
            )

    async def _initialize_pipe(
        self, input: TInput, context: Context, *args, **kwargs
    ) -> None:
        self.pipe_run_info = PipeRunInfo(
            generate_run_id(),
            self.type,
        )
        settings = await context.get(self.config.name, "settings")
        self._update_config(**settings)

    def _update_config(self, config_overrides: Optional[dict] = None) -> None:
        config_overrides = config_overrides or {}
        try:
            # Update the existing config dictionary with the new overrides
            # Use the setter to apply the updated configuration
            self.config = {**self.config.dict(), **config_overrides}
        except ValidationError as e:
            logger.error(f"Configuration validation error: {e}")
            raise

    @property
    def config(self) -> PipeConfig:
        return self._config

    @config.setter
    def config(self, value: Union[dict, PipeConfig]):
        if isinstance(value, dict):
            # Dynamically create an instance of CONFIG_TYPE from a dictionary
            if self.__class__.CONFIG_TYPE is not None:
                self._config = self.__class__.CONFIG_TYPE(**value)
            else:
                raise ValueError("CONFIG_TYPE is not set for this class.")
        elif isinstance(value, PipeConfig):
            # Check if the instance type is compatible
            if isinstance(value, self.__class__.CONFIG_TYPE):
                self._config = value
            else:
                raise TypeError(
                    f"Config must be an instance of {self.__class__.CONFIG_TYPE.__name__}"
                )
        else:
            raise TypeError(
                "Config must be a dictionary or an instance of the defined CONFIG_TYPE"
            )

    @property
    @abstractmethod
    def flow(self) -> PipeFlow:
        pass

    @property
    @abstractmethod
    def type(self) -> PipeType:
        pass

    @abstractmethod
    async def run(self, input: TInput, context: Context) -> TOutput:
        pass


class ConfigurationAggregator:
    def __init__(self):
        self.configs: dict[str, PipeConfig] = {}
        self.global_config = {}

    def register_pipe(self, pipe: AsyncPipe):
        """Register or update a pipe's configuration with default and overridden settings."""
        if pipe.config.name in self.configs:
            raise ValueError(
                f"Pipe with name {pipe.config.name} already exists."
            )
        config = copy(pipe.config.dict())
        self.configs[config.pop("name")] = config

    def get_config(self, pipe_name: str) -> PipeConfig:
        """Get the configuration for a specific pipe."""
        return self.configs.get(pipe_name, PipeConfig())


class Pipeline:
    INPUT_TYPE = Type[Any]
    OUTPUT_TYPE = Type[Any]

    def __init__(
        self,
        context: Optional[Context] = None,
        config_aggregator: Optional[ConfigurationAggregator] = None,
        *args,
        **kwargs,
    ):
        if not config_aggregator:
            config_aggregator = ConfigurationAggregator()
        if not context:
            context = Context()

        self.pipes = []
        self.context = context
        self.config_aggregator = config_aggregator
        self.flow = PipeFlow.STANDARD

    async def add_pipe(self, pipe: AsyncPipe):
        # if self.pipes and self.pipes[-1].OUTPUT_TYPE != pipe.INPUT_TYPE:
        #     raise TypeError(
        #         "Output type of the last pipe does not match input type of the new pipe."
        #     )
        self.pipes.append(pipe)
        self.config_aggregator.register_pipe(pipe)
        await self.context.update(pipe.config.name, {"settings": {}})

    async def run(self, input: Any) -> Any:
        current_input = input
        for pipe in self.pipes:
            current_input = await self.execute_pipe(pipe, current_input)
        if isinstance(current_input, AsyncGenerator):
            collection = []
            async for item in current_input:
                collection.append(item)
            return collection
        else:
            return await current_input

    async def execute_pipe(self, pipe, current_input):
        if self.flow == PipeFlow.FAN_OUT:
            if pipe.flow == PipeFlow.STANDARD:
                # Process each item concurrently if the current flow is FAN_OUT
                if hasattr(current_input, "__aiter__"):
                    return [
                        pipe.run(item, self.context)
                        async for item in current_input
                    ]
                else:
                    return [
                        pipe.run(item, self.context) for item in current_input
                    ]
            elif pipe.flow == PipeFlow.FAN_IN:
                # Collect the results of the FAN_OUT flow
                pipe.run(current_input)
                self.flow = PipeFlow.STANDARD

        elif self.flow == PipeFlow.STANDARD:
            return pipe.run(current_input, self.context)
        else:
            raise ValueError("Invalid flow state.")
