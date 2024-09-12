import asyncio
import json
import logging
from typing import Optional, Union
from uuid import UUID

import asyncpg
from sqlalchemy import (
    ARRAY,
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID

from core.base import (
    DocumentInfo,
    DocumentType,
    IngestionStatus,
    R2RException,
    RestructureStatus,
)

from .base import DatabaseMixin

logger = logging.getLogger(__name__)


class DocumentMixin(DatabaseMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metadata = MetaData()
        self.document_info_table = Table(
            self._get_table_name("document_info"),
            self.metadata,
            Column("document_id", UUID, primary_key=True),
            Column("group_ids", ARRAY(UUID)),
            Column("user_id", UUID),
            Column("type", String),
            Column("metadata", JSON),
            Column("title", String),
            Column("version", String),
            Column("size_in_bytes", Integer),
            Column("ingestion_status", String),
            Column("restructuring_status", String),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
            Column("version_number", Integer),
        )

    async def create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name('document_info')} (
            document_id UUID PRIMARY KEY,
            group_ids UUID[],
            user_id UUID,
            type TEXT,
            metadata JSONB,
            title TEXT,
            version TEXT,
            size_in_bytes INT,
            ingestion_status TEXT DEFAULT 'pending',
            restructuring_status TEXT DEFAULT 'pending',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            version_number INT DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_group_ids_{self.collection_name}
        ON {self._get_table_name('document_info')} USING GIN (group_ids);
        """
        await self.execute_query(query)

    async def upsert_documents_overview(
        self, documents_overview: Union[DocumentInfo, list[DocumentInfo]]
    ) -> None:
        if isinstance(documents_overview, DocumentInfo):
            documents_overview = [documents_overview]

        max_retries = 20
        for document_info in documents_overview:
            retries = 0
            while retries < max_retries:
                try:
                    async with self.pool.acquire() as conn:
                        async with conn.transaction():
                            # Lock the row for update
                            check_query = f"""
                            SELECT version_number, ingestion_status FROM {self._get_table_name('document_info')}
                            WHERE document_id = $1 FOR UPDATE
                            """
                            existing_doc = await conn.fetchrow(
                                check_query, document_info.id
                            )

                            db_entry = document_info.convert_to_db_entry()

                            if existing_doc:
                                db_version = existing_doc["version_number"]
                                db_status = existing_doc["ingestion_status"]
                                new_version = db_entry["version_number"]

                                # Only increment version if status is changing to 'success' or if it's a new version
                                if (
                                    db_status != "success"
                                    and db_entry["ingestion_status"]
                                    == "success"
                                ) or (new_version > db_version):
                                    new_version_number = db_version + 1
                                else:
                                    new_version_number = db_version

                                db_entry["version_number"] = new_version_number

                                update_query = f"""
                                UPDATE {self._get_table_name('document_info')}
                                SET group_ids = $1, user_id = $2, type = $3, metadata = $4,
                                    title = $5, version = $6, size_in_bytes = $7, ingestion_status = $8,
                                    restructuring_status = $9, updated_at = $10, version_number = $11
                                WHERE document_id = $12
                                """
                                await conn.execute(
                                    update_query,
                                    db_entry["group_ids"],
                                    db_entry["user_id"],
                                    db_entry["type"],
                                    db_entry["metadata"],
                                    db_entry["title"],
                                    db_entry["version"],
                                    db_entry["size_in_bytes"],
                                    db_entry["ingestion_status"],
                                    db_entry["restructuring_status"],
                                    db_entry["updated_at"],
                                    new_version_number,
                                    document_info.id,
                                )
                            else:
                                insert_query = f"""
                                INSERT INTO {self._get_table_name('document_info')}
                                (document_id, group_ids, user_id, type, metadata, title, version,
                                size_in_bytes, ingestion_status, restructuring_status, created_at,
                                updated_at, version_number)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                                """
                                await conn.execute(
                                    insert_query,
                                    db_entry["document_id"],
                                    db_entry["group_ids"],
                                    db_entry["user_id"],
                                    db_entry["type"],
                                    db_entry["metadata"],
                                    db_entry["title"],
                                    db_entry["version"],
                                    db_entry["size_in_bytes"],
                                    db_entry["ingestion_status"],
                                    db_entry["restructuring_status"],
                                    db_entry["created_at"],
                                    db_entry["updated_at"],
                                    db_entry["version_number"],
                                )

                    break  # Success, exit the retry loop
                except (
                    asyncpg.exceptions.UniqueViolationError,
                    asyncpg.exceptions.DeadlockDetectedError,
                ) as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(
                            f"Failed to update document {document_info.id} after {max_retries} attempts. Error: {str(e)}"
                        )
                        raise
                    else:
                        wait_time = 0.1 * (2**retries)  # Exponential backoff
                        await asyncio.sleep(wait_time)

    async def get_documents_overview(
        self,
        filter_user_ids: Optional[list[UUID]] = None,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_group_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[DocumentInfo]:
        conditions = []
        params = []
        param_index = 1

        if filter_document_ids:
            conditions.append(f"document_id = ANY(${param_index})")
            params.append(filter_document_ids)
            param_index += 1

        if filter_user_ids:
            conditions.append(f"user_id = ANY(${param_index})")
            params.append(filter_user_ids)
            param_index += 1

        if filter_group_ids:
            conditions.append(f"group_ids && ${param_index}")
            params.append(filter_group_ids)
            param_index += 1

        base_query = f"""
            FROM {self._get_table_name('document_info')}
        """

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT document_id, group_ids, user_id, type, metadata, title, version,
                size_in_bytes, ingestion_status, created_at, updated_at, restructuring_status
            {base_query}
            ORDER BY created_at DESC
            OFFSET ${param_index}
        """
        params.append(offset)
        param_index += 1

        if limit != -1:
            query += f" LIMIT ${param_index}"
            params.append(limit)

        try:
            results = await self.fetch_query(query, params)

            return [
                DocumentInfo(
                    id=row["document_id"],
                    group_ids=row["group_ids"],
                    user_id=row["user_id"],
                    type=DocumentType(row["type"]),
                    metadata=json.loads(row["metadata"]),
                    title=row["title"],
                    version=row["version"],
                    size_in_bytes=row["size_in_bytes"],
                    ingestion_status=IngestionStatus(row["ingestion_status"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    restructuring_status=RestructureStatus(
                        row["restructuring_status"]
                    ),
                )
                for row in results
            ]
        except Exception as e:
            logger.error(f"Error in get_documents_overview: {str(e)}")
            raise R2RException(
                status_code=500, message="Database query failed"
            )
