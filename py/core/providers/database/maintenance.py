import logging
from core.base import Handler
from .base import PostgresConnectionManager

logger = logging.getLogger(__name__)


class PostgresMaintenanceHandler(Handler):
    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
    ):
        """
        Initialize the PostgresMaintenanceHandler with the given project name and connection manager.

        Args:
            project_name (str): The name of the project.
            connection_manager (PostgresConnectionManager): The connection manager to use.
        """
        super().__init__(project_name, connection_manager)

        logger.debug(
            f"Initialized PostgresMaintenanceHandler for project: {project_name}"
        )
    
    async def create_tables(self):
        pass
    
    async def vacuum_table(
            self,
            table_name: str,
            analyze: bool = False,
            full: bool = False,
    ):
        """
        VACUUM reclaims storage occupied by dead tuples. In normal PostgreSQL operation,
        tuples that are deleted or obsoleted by an update are not physically removed from
        their table; they remain present until a VACUUM is done.
        
        Therefore it's necessary to do VACUUM periodically, especially on frequently-updated
        tables.
        
        VACUUM ANALYZE performs a VACUUM and then an ANALYZE for each selected table.

        Plain VACUUM (without FULL) simply reclaims space and makes it available for re-use.
        This form of the command can operate in parallel with normal reading and writing of the
        table, as an exclusive lock is not obtained. However, extra space is not returned to
        the operating system (in most cases); it's just kept available for re-use within the same
        table.
        
        VACUUM FULL rewrites the entire contents of the table into a new disk file with no extra
        space, allowing unused space to be returned to the operating system. This form is much
        slower and requires an ACCESS EXCLUSIVE lock on each table while it is being processed.

        TODO: Implement VACUUM FULL
        """

        vacuum_query = "VACUUM"
        if analyze:
            vacuum_query += " ANALYZE"
        if full:
            logger.warning("VACUUM FULL not implemented yet. Running plain VACUUM instead.")

        try:
            await self.connection_manager.execute_query(f"{vacuum_query} {table_name}")
        except Exception as e:
            logger.error(f"Error vacuuming table {table_name}: {str(e)}")
            raise e
    
    async def vacuum_all_tables(
            self,
            analyze: bool = False,
            full: bool = False,
    ):
        """ Vacuum all tables in the database """

        vacuum_query = "VACUUM"
        if analyze:
            vacuum_query += " ANALYZE"
        if full:
            logger.warning("VACUUM FULL not implemented yet. Running plain VACUUM instead.")
        try:
            await self.connection_manager.execute_query(vacuum_query)
        except Exception as e:
            logger.error(f"Error vacuuming all tables: {str(e)}")
            raise e

