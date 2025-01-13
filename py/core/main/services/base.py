from abc import ABC

from core.base import RunManager

from ..abstractions import FUSEAgents, FUSEPipelines, FUSEPipes, FUSEProviders
from ..config import FUSEConfig


class Service(ABC):
    def __init__(
        self,
        config: FUSEConfig,
        providers: FUSEProviders,
        pipes: FUSEPipes,
        pipelines: FUSEPipelines,
        agents: FUSEAgents,
        run_manager: RunManager,
    ):
        self.config = config
        self.providers = providers
        self.pipes = pipes
        self.pipelines = pipelines
        self.agents = agents
        self.run_manager = run_manager
