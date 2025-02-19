from abc import ABC

from ..abstractions import R2RProviders
from ..config import R2RConfig


class Service(ABC):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
    ):
        self.config = config
        self.providers = providers
