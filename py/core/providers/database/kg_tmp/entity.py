from core.base.providers.database import Handler
from core.providers.database.kg import PostgresConnectionManager


class PostgresEntityHandler(Handler):
    def __init__(
        self, project_name: str, connection_manager: PostgresConnectionManager
    ):
        super().__init__(project_name, connection_manager)
