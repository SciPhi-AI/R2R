from abc import ABC

from r2r.base import KVLoggingSingleton, RunManager

from ..abstractions import R2RPipelines, R2RProviders
from ..assembly.config import R2RConfig


class Service(ABC):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
        run_manager: RunManager,
        logging_connection: KVLoggingSingleton,
    ):
        self.config = config
        self.providers = providers
        self.pipelines = pipelines
        self.run_manager = run_manager
        self.logging_connection = logging_connection
