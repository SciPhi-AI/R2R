import json
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from core.base import Handler

from .base import PostgresConnectionManager

logger = logging.getLogger()


class PostgresPIIEntitiesHandler(Handler):
    TABLE_NAME = "pii_entities"

    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
    ):
        super().__init__(project_name, connection_manager)

    async def create_tables(self):
        """Create the pii_entities table if it doesn't exist."""
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name(self.TABLE_NAME)} (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chunk_id UUID NOT NULL,
            document_id UUID NOT NULL,
            entity_type TEXT NOT NULL,
            start_pos INT NOT NULL,
            end_pos INT NOT NULL,
            score FLOAT NOT NULL,
            original_text_hash TEXT,
            anonymized_text TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_pii_entities_chunk_id ON {self._get_table_name(self.TABLE_NAME)} (chunk_id);
        CREATE INDEX IF NOT EXISTS idx_pii_entities_document_id ON {self._get_table_name(self.TABLE_NAME)} (document_id);
        CREATE INDEX IF NOT EXISTS idx_pii_entities_entity_type ON {self._get_table_name(self.TABLE_NAME)} (entity_type);
        """
        await self.connection_manager.execute_query(query)

    async def insert_entities(
        self,
        chunk_id: UUID,
        document_id: UUID,
        entities: list[dict[str, Any]],
    ) -> None:
        """Insert PII entities for a chunk."""
        if not entities:
            return

        query = f"""
        INSERT INTO {self._get_table_name(self.TABLE_NAME)}
        (chunk_id, document_id, entity_type, start_pos, end_pos, score, original_text_hash, anonymized_text)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """

        params = [
            (
                chunk_id,
                document_id,
                entity["entity_type"],
                entity["start"],
                entity["end"],
                entity["score"],
                entity.get("original_text_hash"),
                entity.get("anonymized_text"),
            )
            for entity in entities
        ]

        await self.connection_manager.execute_many(query, params)

    async def get_entities_by_chunk(
        self, chunk_id: UUID
    ) -> list[dict[str, Any]]:
        """Get all PII entities for a specific chunk."""
        query = f"""
        SELECT id, chunk_id, document_id, entity_type, start_pos, end_pos, score,
               original_text_hash, anonymized_text, created_at
        FROM {self._get_table_name(self.TABLE_NAME)}
        WHERE chunk_id = $1
        ORDER BY start_pos
        """

        results = await self.connection_manager.fetch_query(query, [chunk_id])

        return [
            {
                "id": str(result["id"]),
                "chunk_id": str(result["chunk_id"]),
                "document_id": str(result["document_id"]),
                "entity_type": result["entity_type"],
                "start_pos": result["start_pos"],
                "end_pos": result["end_pos"],
                "score": float(result["score"]),
                "original_text_hash": result["original_text_hash"],
                "anonymized_text": result["anonymized_text"],
                "created_at": result["created_at"].isoformat(),
            }
            for result in results
        ]

    async def get_entities_by_document(
        self,
        document_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get all PII entities for a specific document with pagination."""
        query = f"""
        SELECT id, chunk_id, document_id, entity_type, start_pos, end_pos, score,
               original_text_hash, anonymized_text, created_at,
               COUNT(*) OVER() AS total
        FROM {self._get_table_name(self.TABLE_NAME)}
        WHERE document_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        OFFSET $3
        """

        results = await self.connection_manager.fetch_query(
            query, [document_id, limit, offset]
        )

        entities = []
        total = 0

        if results:
            total = results[0]["total"]
            entities = [
                {
                    "id": str(result["id"]),
                    "chunk_id": str(result["chunk_id"]),
                    "document_id": str(result["document_id"]),
                    "entity_type": result["entity_type"],
                    "start_pos": result["start_pos"],
                    "end_pos": result["end_pos"],
                    "score": float(result["score"]),
                    "original_text_hash": result["original_text_hash"],
                    "anonymized_text": result["anonymized_text"],
                    "created_at": result["created_at"].isoformat(),
                }
                for result in results
            ]

        return {"results": entities, "total_entries": total}

    async def get_pii_stats_by_document(
        self, document_id: UUID
    ) -> dict[str, Any]:
        """Get PII statistics for a document."""
        query = f"""
        SELECT
            entity_type,
            COUNT(*) as count,
            AVG(score) as avg_score
        FROM {self._get_table_name(self.TABLE_NAME)}
        WHERE document_id = $1
        GROUP BY entity_type
        ORDER BY count DESC
        """

        results = await self.connection_manager.fetch_query(
            query, [document_id]
        )

        stats = {
            "document_id": str(document_id),
            "total_entities": sum(r["count"] for r in results),
            "entity_types": [
                {
                    "type": result["entity_type"],
                    "count": result["count"],
                    "avg_confidence": float(result["avg_score"]),
                }
                for result in results
            ],
        }

        return stats

    async def delete_by_document(self, document_id: UUID) -> None:
        """Delete all PII entities for a document."""
        query = f"""
        DELETE FROM {self._get_table_name(self.TABLE_NAME)}
        WHERE document_id = $1
        """
        await self.connection_manager.execute_query(query, [document_id])

    async def delete_by_chunk(self, chunk_id: UUID) -> None:
        """Delete all PII entities for a chunk."""
        query = f"""
        DELETE FROM {self._get_table_name(self.TABLE_NAME)}
        WHERE chunk_id = $1
        """
        await self.connection_manager.execute_query(query, [chunk_id])
