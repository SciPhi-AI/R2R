import asyncio
import json
from typing import Optional, Union
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from core.base import (
    DocumentInfo,
    DocumentType,
    IngestionStatus,
    RestructureStatus,
)

from .base import DatabaseMixin


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

        max_retries = 10
        for document_info in documents_overview:
            retries = 0
            while retries < max_retries:
                try:
                    async with self.AsyncSession() as session:
                        async with session.begin():
                            print(
                                f"Upserting document {document_info.id} with version {document_info.version}"
                            )

                            # Check if the document exists
                            stmt = (
                                select(self.document_info_table)
                                .where(
                                    self.document_info_table.c.document_id
                                    == document_info.id
                                )
                                .with_for_update(nowait=True)
                            )
                            result = await session.execute(stmt)
                            existing_doc = result.first()

                            db_entry = document_info.convert_to_db_entry()

                            if existing_doc:
                                # Update existing document
                                print(
                                    f"Document {document_info.id} already exists. Updating."
                                )
                                if (
                                    existing_doc.version_number
                                    != db_entry["version_number"]
                                ):
                                    raise StaleDataError(
                                        "Document version mismatch"
                                    )

                                new_version_number = (
                                    db_entry["version_number"] + 1
                                )
                                db_entry["version_number"] = new_version_number
                                stmt = (
                                    update(self.document_info_table)
                                    .where(
                                        self.document_info_table.c.document_id
                                        == document_info.id,
                                        self.document_info_table.c.version_number
                                        == db_entry["version_number"] - 1,
                                    )
                                    .values(**db_entry)
                                )
                            else:
                                # Insert new document
                                print(
                                    f"Document {document_info.id} does not exist. Inserting."
                                )
                                stmt = insert(self.document_info_table).values(
                                    **db_entry
                                )

                            result = await session.execute(stmt)
                            if result.rowcount == 0:
                                raise StaleDataError(
                                    "No rows updated, possible version conflict"
                                )

                            await session.commit()
                            break  # Success, exit the retry loop
                except (IntegrityError, StaleDataError) as e:
                    await session.rollback()
                    retries += 1
                    if retries == max_retries:
                        print(
                            f"Failed to update document {document_info.id} after {max_retries} attempts. Error: {str(e)}"
                        )
                    else:
                        wait_time = 1.1**retries  # Exponential backoff
                        print(
                            f"Retry {retries}/{max_retries} for document {document_info.id}. Waiting {wait_time} seconds."
                        )
                        await asyncio.sleep(wait_time)

    async def delete_from_documents_overview(
        self, document_id: str, version: Optional[str] = None
    ) -> None:
        query = f"""
            DELETE FROM {self._get_table_name('document_info')}
            WHERE document_id = :document_id
        """
        params = {"document_id": document_id}

        if version is not None:
            query += " AND version = :version"
            params["version"] = version

        await self.execute_query(query, params)

    async def get_documents_overview(
        self,
        filter_user_ids: Optional[list[UUID]] = None,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_group_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = 100,
    ):
        conditions = []
        params = {"offset": offset}
        if limit != -1:
            params["limit"] = limit

        if filter_document_ids:
            conditions.append("document_id = ANY(:document_ids)")
            params["document_ids"] = filter_document_ids

        if filter_user_ids:
            conditions.append("user_id = ANY(:user_ids)")
            params["user_ids"] = filter_user_ids

        if filter_group_ids:
            conditions.append("group_ids && :group_ids")
            params["group_ids"] = filter_group_ids

        query = f"""
            SELECT document_id, group_ids, user_id, type, metadata, title, version, size_in_bytes, ingestion_status, created_at, updated_at, restructuring_status
            FROM {self._get_table_name('document_info')}
        """
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        limit_clause = "" if limit == -1 else f"LIMIT {limit}"
        query += f"""
            ORDER BY created_at DESC
            OFFSET :offset
            {limit_clause}
        """

        results = await (await self.execute_query(query, params)).fetchall()
        documents = [
            DocumentInfo(
                id=row[0],
                group_ids=row[1],
                user_id=row[2],
                type=DocumentType(row[3]),
                metadata=json.loads(row[4]) if row[4] else {},
                title=row[5],
                version=row[6],
                size_in_bytes=row[7],
                ingestion_status=IngestionStatus(row[8]),
                created_at=row[9],
                updated_at=row[10],
                restructuring_status=RestructureStatus(row[11]),
            )
            for row in results
        ]

        # Get total count for pagination metadata
        count_query = f"""
            SELECT COUNT(*)
            FROM {self._get_table_name('document_info')}
        """
        if conditions:
            count_query += " WHERE " + " ANDs ".join(conditions)

        return documents
