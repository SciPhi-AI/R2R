import logging

from sqlalchemy import exc, text

from core.providers.database.base import DatabaseMixin, execute_query
from core.providers.database.document import DocumentMixin
from core.providers.database.group import GroupMixin
from core.providers.database.tokens import BlacklistedTokensMixin
from core.providers.database.user import UserMixin

logger = logging.getLogger(__name__)


class PostgresRelationalDBProvider(
    GroupMixin, UserMixin, BlacklistedTokensMixin, DocumentMixin
):
    def __init__(self, config, vx, crypto_provider, collection_name):
        self.config = config
        self.vx = vx
        self.crypto_provider = crypto_provider
        self.collection_name = collection_name
        self._initialize_relational_db()

    def _get_table_name(self, base_name: str) -> str:
        return f"{base_name}_{self.collection_name}"

    def execute_query(self, query, params=None):
        return execute_query(self.vx, query, params)

    def _initialize_relational_db(self):
        with self.vx.Session() as sess:
            with sess.begin():
                sess.execute(
                    text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
                )
                sess.commit()

            with sess.begin():
                # Call create_table for each mixin
                for base_class in self.__class__.__bases__:
                    if issubclass(base_class, DatabaseMixin):
                        base_class.create_table(self)

                sess.commit()
