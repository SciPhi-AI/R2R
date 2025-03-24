import logging
from datetime import datetime
from typing import Any

from .base import Service
from ..abstractions import R2RProviders
from ..config import R2RConfig

logger = logging.getLogger(__name__)

class MaintenanceService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
    ):
        super().__init__(
            config,
            providers,
        )
        self.scheduled_jobs: list[Any] = []
        
    async def initialize(self):
        """Initialize and schedule maintenance tasks from configuration"""
        logger.info("Initializing database maintenance service")
        await self.providers.scheduler.start()
        
        maintenance_config = self.config.database.maintenance
            
        # Parse the cron schedule
        schedule_parts = self._parse_cron_schedule(maintenance_config.vacuum_schedule)
        
        # Schedule the vacuum job
        job = await self.providers.scheduler.add_job(
            self.vacuum_database,
            trigger="cron",
            **schedule_parts,
            kwargs={
                "full": maintenance_config.vacuum_full,
                "analyze": maintenance_config.vacuum_analyze
            }
        )
        
        self.scheduled_jobs.append(job)
        
    def _parse_cron_schedule(self, cron_schedule: str) -> dict:
        """Parse a cron schedule string into kwargs for APScheduler"""
        parts = cron_schedule.split()
        
        # Handle both 5-part and 6-part cron expressions
        if len(parts) == 6:
            # With seconds field
            second, minute, hour, day, month, day_of_week = parts
            return {
                "second": second,
                "minute": minute, 
                "hour": hour,
                "day": day,
                "month": month,
                "day_of_week": day_of_week
            }
        elif len(parts) == 5:
            # Standard cron (no seconds)
            minute, hour, day, month, day_of_week = parts
            return {
                "minute": minute, 
                "hour": hour,
                "day": day,
                "month": month,
                "day_of_week": day_of_week
            }
        else:
            logger.warning(f"Invalid cron format: {cron_schedule}. Using defaults.")
            return {"hour": 3, "minute": 0}
    
    async def vacuum_database(self, full: bool = False, analyze: bool = True):
        """Run vacuum on the entire database"""
        start_time = datetime.now()
        
        try:
            await self.providers.database.maintenance_handler.vacuum_all_tables(
                analyze=analyze, 
                full=full
            )
            
            duration = datetime.now() - start_time
            logger.info(f"Database vacuum completed successfully in {duration.total_seconds():.2f} seconds")
        except Exception as e:
            logger.error(f"Database vacuum failed: {str(e)}")
    
    async def vacuum_table(self, table_name: str, full: bool = False, analyze: bool = True):
        """Run vacuum on a specific table"""
        start_time = datetime.now()
        logger.info(f"Running vacuum on table {table_name} (full={full}, analyze={analyze})")
        
        try:
            await self.providers.database.maintenance_handler.vacuum_table(
                table_name=table_name,
                analyze=analyze,
                full=full
            )
            
            duration = datetime.now() - start_time
            logger.info(f"Table vacuum completed successfully in {duration.total_seconds():.2f} seconds")
        except Exception as e:
            logger.error(f"Table vacuum failed for {table_name}: {str(e)}")