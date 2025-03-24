from abc import abstractmethod

from .base import Provider, ProviderConfig


class SchedulerConfig(ProviderConfig):
    """Configuration for scheduler provider"""
    provider: str = "apscheduler"

    def validate_config(self):
        if self.provider not in self.supported_providers:
            raise ValueError(f"Scheduler provider {self.provider} is not supported.")
    
    @property
    def supported_providers(self) -> list[str]:
        return ["apscheduler"]
    
class SchedulerProvider(Provider):
    """Base class for scheduler providers"""

    def __init__(self, config: SchedulerConfig):
        super().__init__(config)
        self.config = config
    
    @abstractmethod
    async def add_job(self, func, trigger, **kwargs):
        pass
    
    @abstractmethod
    async def start(self):
        pass
    
    @abstractmethod
    async def shutdown(self):
        pass
