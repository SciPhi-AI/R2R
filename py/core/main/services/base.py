from abc import ABC

from core.base import RunLoggingSingleton, RunManager

from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from ..config import R2RConfig


class Service(ABC):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipes: R2RPipes,
        pipelines: R2RPipelines,
        agents: R2RAgents,
        run_manager: RunManager,
        logging_connection: RunLoggingSingleton,
    ):
        self.config = config
        self.providers = providers
        self.pipes = pipes
        self.pipelines = pipelines
        self.agents = agents
        self.run_manager = run_manager
        self.logging_connection = logging_connection
