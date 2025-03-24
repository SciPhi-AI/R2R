import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.base import SchedulerConfig, SchedulerProvider

logger = logging.getLogger(__name__)


class APSchedulerProvider(SchedulerProvider):
    """Implementation using APScheduler"""

    def __init__(self, config: SchedulerConfig):
        super().__init__(config)
        self.scheduler = AsyncIOScheduler()

    async def add_job(self, func, trigger, **kwargs):
        logger.info(
            f"Adding job {func.__name__} with trigger {trigger} and kwargs {kwargs}"
        )
        self.scheduler.add_job(func, trigger, **kwargs)

    async def start(self):
        self.scheduler.start()
        logger.info("Scheduler started")

    async def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shutdown")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.shutdown()
