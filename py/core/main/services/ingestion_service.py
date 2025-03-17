import asyncio
import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Optional, Sequence
from uuid import UUID

from fastapi import HTTPException

from core.base import (
    Document,
    DocumentChunk,
    DocumentResponse,
    DocumentType,
    GenerationConfig,
    IngestionStatus,
    R2RException,
    RawChunk,
    UnprocessedChunk,
    Vector,
    VectorEntry,
    VectorType,
    generate_id,
)
from core.base.abstractions import (
    ChunkEnrichmentSettings,
    IndexMeasure,
    IndexMethod,
    R2RDocumentProcessingError,
    VectorTableName,
)
from core.base.api.models import User
from shared.abstractions import PDFParsingError, PopplerNotFoundError

from ..abstractions import R2RProviders
from ..config import R2RConfig

logger = logging.getLogger()
STARTING_VERSION = "v0"


class IngestionService:
    """A refactored IngestionService that inlines all pipe logic for parsing,
    embedding, and vector storage directly in its methods."""

    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
    ) -> None:
        self.config = config
        self.providers = providers

    async def ingest_file_ingress(
        self,
        file_data: dict,
        user: User,
        document_id: UUID,
        size_in_bytes,
        metadata: Optional[dict] = None,
        version: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> dict:
        """Pre-ingests a file by creating or validating the DocumentResponse
        entry.

        Does not actually parse/ingest the content. (See parse_file() for that
        step.)
        """
        try:
            if not file_data:
                raise R2RException(
                    status_code=400, message="No files provided for ingestion."
                )
            if not file_data.get("filename"):
                raise R2RException(
                    status_code=400, message="File name not provided."
                )

            metadata = metadata or {}
            version = version or STARTING_VERSION

            document_info = self.create_document_info_from_file(
                document_id,
                user,
                file_data["filename"],
                metadata,
                version,
                size_in_bytes,
            )

            existing_document_info = (
                await self.providers.database.documents_handler.get_documents_overview(
                    offset=0,
                    limit=100,
                    filter_user_ids=[user.id],
                    filter_document_ids=[document_id],
                )
            )["results"]

            # Validate ingestion status for re-ingestion
            if len(existing_document_info) > 0:
                existing_doc = existing_document_info[0]
                if existing_doc.ingestion_status == IngestionStatus.SUCCESS:
                    raise R2RException(
                        status_code=409,
                        message=(
                            f"Document {document_id} already exists. "
                            "Submit a DELETE request to `/documents/{document_id}` "
                            "to delete this document and allow for re-ingestion."
                        ),
                    )
                elif existing_doc.ingestion_status != IngestionStatus.FAILED:
                    raise R2RException(
                        status_code=409,
                        message=(
                            f"Document {document_id} is currently ingesting "
                            f"with status {existing_doc.ingestion_status}."
                        ),
                    )

            # Set to PARSING until we actually parse
            document_info.ingestion_status = IngestionStatus.PARSING
            await self.providers.database.documents_handler.upsert_documents_overview(
                document_info
            )

            return {
                "info": document_info,
            }
        except R2RException as e:
            logger.error(f"R2RException in ingest_file_ingress: {str(e)}")
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error during ingestion: {str(e)}"
            ) from e

    def create_document_info_from_file(
        self,
        document_id: UUID,
        user: User,
        file_name: str,
        metadata: dict,
        version: str,
        size_in_bytes: int,
    ) -> DocumentResponse:
        file_extension = (
            file_name.split(".")[-1].lower() if file_name != "N/A" else "txt"
        )
        if file_extension.upper() not in DocumentType.__members__:
            raise R2RException(
                status_code=415,
                message=f"'{file_extension}' is not a valid DocumentType.",
            )

        metadata = metadata or {}
        metadata["version"] = version

        return DocumentResponse(
            id=document_id,
            owner_id=user.id,
            collection_ids=metadata.get("collection_ids", []),
            document_type=DocumentType[file_extension.upper()],
            title=(
                metadata.get("title", file_name.split("/")[-1])
                if file_name != "N/A"
                else "N/A"
            ),
            metadata=metadata,
            version=version,
            size_in_bytes=size_in_bytes,
            ingestion_status=IngestionStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def _create_document_info_from_chunks(
        self,
        document_id: UUID,
        user: User,
        chunks: list[RawChunk],
        metadata: dict,
        version: str,
    ) -> DocumentResponse:
        metadata = metadata or {}
        metadata["version"] = version

        return DocumentResponse(
            id=document_id,
            owner_id=user.id,
            collection_ids=metadata.get("collection_ids", []),
            document_type=DocumentType.TXT,
            title=metadata.get("title", f"Ingested Chunks - {document_id}"),
            metadata=metadata,
            version=version,
            size_in_bytes=sum(
                len(chunk.text.encode("utf-8")) for chunk in chunks
            ),
            ingestion_status=IngestionStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    async def parse_file(
        self,
        document_info: DocumentResponse,
        ingestion_config: dict | None,
    ) -> AsyncGenerator[DocumentChunk, None]:
        """Inline replacement for the old parsing_pipe.run(...) Reads the file
        content from the DB, calls the ingestion provider to parse, and yields
        DocumentChunk objects."""
        version = document_info.version or "v0"
        ingestion_config_override = ingestion_config or {}

        # The ingestion config might specify a different provider, etc.
        override_provider = ingestion_config_override.pop("provider", None)
        if (
            override_provider
            and override_provider != self.providers.ingestion.config.provider
        ):
            raise ValueError(
                f"Provider '{override_provider}' does not match ingestion provider "
                f"'{self.providers.ingestion.config.provider}'."
            )

        try:
            # Pull file from DB
            retrieved = (
                await self.providers.database.files_handler.retrieve_file(
                    document_info.id
                )
            )
            if not retrieved:
                # No file found in the DB, can't parse
                raise R2RDocumentProcessingError(
                    document_id=document_info.id,
                    error_message="No file content found in DB for this document.",
                )

            file_name, file_wrapper, file_size = retrieved

            # Read the content
            with file_wrapper as file_content_stream:
                file_content = file_content_stream.read()

            # Build a barebones Document object
            doc = Document(
                id=document_info.id,
                collection_ids=document_info.collection_ids,
                owner_id=document_info.owner_id,
                metadata={
                    "document_type": document_info.document_type.value,
                    **document_info.metadata,
                },
                document_type=document_info.document_type,
            )

            # Delegate to the ingestion provider to parse
            async for extraction in self.providers.ingestion.parse(
                file_content,  # raw bytes
                doc,
                ingestion_config_override,
            ):
                # Adjust chunk ID to incorporate version
                # or any other needed transformations
                extraction.id = generate_id(f"{extraction.id}_{version}")
                extraction.metadata["version"] = version
                yield extraction

        except (PopplerNotFoundError, PDFParsingError) as e:
            raise R2RDocumentProcessingError(
                error_message=e.message,
                document_id=document_info.id,
                status_code=e.status_code,
            ) from None
        except Exception as e:
            if isinstance(e, R2RException):
                raise
            raise R2RDocumentProcessingError(
                document_id=document_info.id,
                error_message=f"Error parsing document: {str(e)}",
            ) from e

    async def augment_document_info(
        self,
        document_info: DocumentResponse,
        chunked_documents: list[dict],
    ) -> None:
        if not self.config.ingestion.skip_document_summary:
            document = f"Document Title: {document_info.title}\n"
            if document_info.metadata != {}:
                document += f"Document Metadata: {json.dumps(document_info.metadata)}\n"

            document += "Document Text:\n"
            for chunk in chunked_documents[
                : self.config.ingestion.chunks_for_document_summary
            ]:
                document += chunk["data"]

            messages = await self.providers.database.prompts_handler.get_message_payload(
                system_prompt_name=self.config.ingestion.document_summary_system_prompt,
                task_prompt_name=self.config.ingestion.document_summary_task_prompt,
                task_inputs={
                    "document": document[
                        : self.config.ingestion.document_summary_max_length
                    ]
                },
            )

            response = await self.providers.llm.aget_completion(
                messages=messages,
                generation_config=GenerationConfig(
                    model=self.config.ingestion.document_summary_model
                    or self.config.app.fast_llm
                ),
            )

            document_info.summary = response.choices[0].message.content  # type: ignore

            if not document_info.summary:
                raise ValueError("Expected a generated response.")

            embedding = await self.providers.embedding.async_get_embedding(
                text=document_info.summary,
            )
            document_info.summary_embedding = embedding
        return

    async def embed_document(
        self,
        chunked_documents: list[dict],
        embedding_batch_size: int = 8,
    ) -> AsyncGenerator[VectorEntry, None]:
        """Inline replacement for the old embedding_pipe.run(...).

        Batches the embedding calls and yields VectorEntry objects.
        """
        if not chunked_documents:
            return

        concurrency_limit = (
            self.providers.embedding.config.concurrent_request_limit or 5
        )
        extraction_batch: list[DocumentChunk] = []
        tasks: set[asyncio.Task] = set()

        async def process_batch(
            batch: list[DocumentChunk],
        ) -> list[VectorEntry]:
            # All text from the batch
            texts = [
                (
                    ex.data.decode("utf-8")
                    if isinstance(ex.data, bytes)
                    else ex.data
                )
                for ex in batch
            ]
            # Retrieve embeddings in bulk
            vectors = await self.providers.embedding.async_get_embeddings(
                texts,  # list of strings
            )
            # Zip them back together
            results = []
            for raw_vector, extraction in zip(vectors, batch, strict=False):
                results.append(
                    VectorEntry(
                        id=extraction.id,
                        document_id=extraction.document_id,
                        owner_id=extraction.owner_id,
                        collection_ids=extraction.collection_ids,
                        vector=Vector(data=raw_vector, type=VectorType.FIXED),
                        text=(
                            extraction.data.decode("utf-8")
                            if isinstance(extraction.data, bytes)
                            else str(extraction.data)
                        ),
                        metadata={**extraction.metadata},
                    )
                )
            return results

        async def run_process_batch(batch: list[DocumentChunk]):
            return await process_batch(batch)

        # Convert each chunk dict to a DocumentChunk
        for chunk_dict in chunked_documents:
            extraction = DocumentChunk.from_dict(chunk_dict)
            extraction_batch.append(extraction)

            # If we hit a batch threshold, spawn a task
            if len(extraction_batch) >= embedding_batch_size:
                tasks.add(
                    asyncio.create_task(run_process_batch(extraction_batch))
                )
                extraction_batch = []

            # If tasks are at concurrency limit, wait for the first to finish
            while len(tasks) >= concurrency_limit:
                done, tasks = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for t in done:
                    for vector_entry in await t:
                        yield vector_entry

        # Handle any leftover items
        if extraction_batch:
            tasks.add(asyncio.create_task(run_process_batch(extraction_batch)))

        # Gather remaining tasks
        for future_task in asyncio.as_completed(tasks):
            for vector_entry in await future_task:
                yield vector_entry

    async def store_embeddings(
        self,
        embeddings: Sequence[dict | VectorEntry],
        storage_batch_size: int = 128,
    ) -> AsyncGenerator[str, None]:
        """Inline replacement for the old vector_storage_pipe.run(...).

        Batches up the vector entries, enforces usage limits, stores them, and
        yields a success/error string (or you could yield a StorageResult).
        """
        if not embeddings:
            return

        vector_entries: list[VectorEntry] = []
        for item in embeddings:
            if isinstance(item, VectorEntry):
                vector_entries.append(item)
            else:
                vector_entries.append(VectorEntry.from_dict(item))

        vector_batch: list[VectorEntry] = []
        document_counts: dict[UUID, int] = {}

        # We'll track usage from the first user we see; if your scenario allows
        # multiple user owners in a single ingestion, you'd need to refine usage checks.
        current_usage = None
        user_id_for_usage_check: UUID | None = None

        count = 0

        for msg in vector_entries:
            # If we haven't set usage yet, do so on the first chunk
            if current_usage is None:
                user_id_for_usage_check = msg.owner_id
                usage_data = (
                    await self.providers.database.chunks_handler.list_chunks(
                        limit=1,
                        offset=0,
                        filters={"owner_id": msg.owner_id},
                    )
                )
                current_usage = usage_data["total_entries"]

            # Figure out the user's limit
            user = await self.providers.database.users_handler.get_user_by_id(
                msg.owner_id
            )
            max_chunks = (
                self.providers.database.config.app.default_max_chunks_per_user
            )
            if user.limits_overrides and "max_chunks" in user.limits_overrides:
                max_chunks = user.limits_overrides["max_chunks"]

            # Add to our local batch
            vector_batch.append(msg)
            document_counts[msg.document_id] = (
                document_counts.get(msg.document_id, 0) + 1
            )
            count += 1

            # Check usage
            if (
                current_usage is not None
                and (current_usage + len(vector_batch) + count) > max_chunks
            ):
                error_message = f"User {msg.owner_id} has exceeded the maximum number of allowed chunks: {max_chunks}"
                logger.error(error_message)
                yield error_message
                continue

            # Once we hit our batch size, store them
            if len(vector_batch) >= storage_batch_size:
                try:
                    await (
                        self.providers.database.chunks_handler.upsert_entries(
                            vector_batch
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to store vector batch: {e}")
                    yield f"Error: {e}"
                vector_batch.clear()

        # Store any leftover items
        if vector_batch:
            try:
                await self.providers.database.chunks_handler.upsert_entries(
                    vector_batch
                )
            except Exception as e:
                logger.error(f"Failed to store final vector batch: {e}")
                yield f"Error: {e}"

        # Summaries
        for doc_id, cnt in document_counts.items():
            info_msg = f"Successful ingestion for document_id: {doc_id}, with vector count: {cnt}"
            logger.info(info_msg)
            yield info_msg

    async def finalize_ingestion(
        self, document_info: DocumentResponse
    ) -> None:
        """Called at the end of a successful ingestion pipeline to set the
        document status to SUCCESS or similar final steps."""

        async def empty_generator():
            yield document_info

        await self.update_document_status(
            document_info, IngestionStatus.SUCCESS
        )
        return empty_generator()

    async def update_document_status(
        self,
        document_info: DocumentResponse,
        status: IngestionStatus,
        metadata: Optional[dict] = None,
    ) -> None:
        document_info.ingestion_status = status
        if metadata:
            document_info.metadata = {**document_info.metadata, **metadata}
        await self._update_document_status_in_db(document_info)

    async def _update_document_status_in_db(
        self, document_info: DocumentResponse
    ):
        try:
            await self.providers.database.documents_handler.upsert_documents_overview(
                document_info
            )
        except Exception as e:
            logger.error(
                f"Failed to update document status: {document_info.id}. Error: {str(e)}"
            )

    async def ingest_chunks_ingress(
        self,
        document_id: UUID,
        metadata: Optional[dict],
        chunks: list[RawChunk],
        user: User,
        *args: Any,
        **kwargs: Any,
    ) -> DocumentResponse:
        """Directly ingest user-provided text chunks (rather than from a
        file)."""
        if not chunks:
            raise R2RException(
                status_code=400, message="No chunks provided for ingestion."
            )
        metadata = metadata or {}
        version = STARTING_VERSION

        document_info = self._create_document_info_from_chunks(
            document_id,
            user,
            chunks,
            metadata,
            version,
        )

        existing_document_info = (
            await self.providers.database.documents_handler.get_documents_overview(
                offset=0,
                limit=100,
                filter_user_ids=[user.id],
                filter_document_ids=[document_id],
            )
        )["results"]
        if len(existing_document_info) > 0:
            existing_doc = existing_document_info[0]
            if existing_doc.ingestion_status != IngestionStatus.FAILED:
                raise R2RException(
                    status_code=409,
                    message=(
                        f"Document {document_id} was already ingested "
                        "and is not in a failed state."
                    ),
                )

        await self.providers.database.documents_handler.upsert_documents_overview(
            document_info
        )
        return document_info

    async def update_chunk_ingress(
        self,
        document_id: UUID,
        chunk_id: UUID,
        text: str,
        user: User,
        metadata: Optional[dict] = None,
        *args: Any,
        **kwargs: Any,
    ) -> dict:
        """Update an individual chunk's text and metadata, re-embed, and re-
        store it."""
        # Verify chunk exists and user has access
        existing_chunks = (
            await self.providers.database.chunks_handler.list_document_chunks(
                document_id=document_id,
                offset=0,
                limit=1,
            )
        )
        if not existing_chunks["results"]:
            raise R2RException(
                status_code=404,
                message=f"Chunk with chunk_id {chunk_id} not found.",
            )

        existing_chunk = (
            await self.providers.database.chunks_handler.get_chunk(chunk_id)
        )
        if not existing_chunk:
            raise R2RException(
                status_code=404,
                message=f"Chunk with id {chunk_id} not found",
            )

        if (
            str(existing_chunk["owner_id"]) != str(user.id)
            and not user.is_superuser
        ):
            raise R2RException(
                status_code=403,
                message="You don't have permission to modify this chunk.",
            )

        # Merge metadata
        merged_metadata = {**existing_chunk["metadata"]}
        if metadata is not None:
            merged_metadata |= metadata

        # Create updated chunk
        extraction_data = {
            "id": chunk_id,
            "document_id": document_id,
            "collection_ids": kwargs.get(
                "collection_ids", existing_chunk["collection_ids"]
            ),
            "owner_id": existing_chunk["owner_id"],
            "data": text or existing_chunk["text"],
            "metadata": merged_metadata,
        }
        extraction = DocumentChunk(**extraction_data).model_dump()

        # Re-embed
        embeddings_generator = self.embed_document(
            [extraction], embedding_batch_size=1
        )
        embeddings = []
        async for embedding in embeddings_generator:
            embeddings.append(embedding)

        # Re-store
        store_gen = self.store_embeddings(embeddings, storage_batch_size=1)
        async for _ in store_gen:
            pass

        return extraction

    async def _get_enriched_chunk_text(
        self,
        chunk_idx: int,
        chunk: dict,
        document_id: UUID,
        document_summary: str | None,
        chunk_enrichment_settings: ChunkEnrichmentSettings,
        list_document_chunks: list[dict],
    ) -> VectorEntry:
        """Helper for chunk_enrichment.

        Leverages an LLM to rewrite or expand chunk text, then re-embeds it.
        """
        preceding_chunks = [
            list_document_chunks[idx]["text"]
            for idx in range(
                max(0, chunk_idx - chunk_enrichment_settings.n_chunks),
                chunk_idx,
            )
        ]
        succeeding_chunks = [
            list_document_chunks[idx]["text"]
            for idx in range(
                chunk_idx + 1,
                min(
                    len(list_document_chunks),
                    chunk_idx + chunk_enrichment_settings.n_chunks + 1,
                ),
            )
        ]
        try:
            # Obtain the updated text from the LLM
            updated_chunk_text = (
                (
                    await self.providers.llm.aget_completion(
                        messages=await self.providers.database.prompts_handler.get_message_payload(
                            task_prompt_name=chunk_enrichment_settings.chunk_enrichment_prompt,
                            task_inputs={
                                "document_summary": document_summary or "None",
                                "chunk": chunk["text"],
                                "preceding_chunks": (
                                    "\n".join(preceding_chunks)
                                    if preceding_chunks
                                    else "None"
                                ),
                                "succeeding_chunks": (
                                    "\n".join(succeeding_chunks)
                                    if succeeding_chunks
                                    else "None"
                                ),
                                "chunk_size": self.config.ingestion.chunk_size
                                or 1024,
                            },
                        ),
                        generation_config=chunk_enrichment_settings.generation_config
                        or GenerationConfig(model=self.config.app.fast_llm),
                    )
                )
                .choices[0]
                .message.content
            )
        except Exception:
            updated_chunk_text = chunk["text"]
            chunk["metadata"]["chunk_enrichment_status"] = "failed"
        else:
            chunk["metadata"]["chunk_enrichment_status"] = (
                "success" if updated_chunk_text else "failed"
            )

        if not updated_chunk_text or not isinstance(updated_chunk_text, str):
            updated_chunk_text = str(chunk["text"])
            chunk["metadata"]["chunk_enrichment_status"] = "failed"

        # Re-embed
        data = await self.providers.embedding.async_get_embedding(
            updated_chunk_text
        )
        chunk["metadata"]["original_text"] = chunk["text"]

        return VectorEntry(
            id=generate_id(str(chunk["id"])),
            vector=Vector(data=data, type=VectorType.FIXED, length=len(data)),
            document_id=document_id,
            owner_id=chunk["owner_id"],
            collection_ids=chunk["collection_ids"],
            text=updated_chunk_text,
            metadata=chunk["metadata"],
        )

    async def chunk_enrichment(
        self,
        document_id: UUID,
        document_summary: str | None,
        chunk_enrichment_settings: ChunkEnrichmentSettings,
    ) -> int:
        """Example function that modifies chunk text via an LLM then re-embeds
        and re-stores all chunks for the given document."""
        list_document_chunks = (
            await self.providers.database.chunks_handler.list_document_chunks(
                document_id=document_id,
                offset=0,
                limit=-1,
            )
        )["results"]

        new_vector_entries: list[VectorEntry] = []
        tasks = []
        total_completed = 0

        for chunk_idx, chunk in enumerate(list_document_chunks):
            tasks.append(
                self._get_enriched_chunk_text(
                    chunk_idx=chunk_idx,
                    chunk=chunk,
                    document_id=document_id,
                    document_summary=document_summary,
                    chunk_enrichment_settings=chunk_enrichment_settings,
                    list_document_chunks=list_document_chunks,
                )
            )

            # Process in batches of e.g. 128 concurrency
            if len(tasks) == 128:
                new_vector_entries.extend(await asyncio.gather(*tasks))
                total_completed += 128
                logger.info(
                    f"Completed {total_completed} out of {len(list_document_chunks)} chunks for document {document_id}"
                )
                tasks = []

        # Finish any remaining tasks
        new_vector_entries.extend(await asyncio.gather(*tasks))
        logger.info(
            f"Completed enrichment of {len(list_document_chunks)} chunks for document {document_id}"
        )

        # Delete old chunks from vector db
        await self.providers.database.chunks_handler.delete(
            filters={"document_id": document_id}
        )

        # Insert the newly enriched entries
        await self.providers.database.chunks_handler.upsert_entries(
            new_vector_entries
        )
        return len(new_vector_entries)

    async def list_chunks(
        self,
        offset: int,
        limit: int,
        filters: Optional[dict[str, Any]] = None,
        include_vectors: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> dict:
        return await self.providers.database.chunks_handler.list_chunks(
            offset=offset,
            limit=limit,
            filters=filters,
            include_vectors=include_vectors,
        )

    async def get_chunk(
        self,
        chunk_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> dict:
        return await self.providers.database.chunks_handler.get_chunk(chunk_id)

    async def update_document_metadata(
        self,
        document_id: UUID,
        metadata: dict,
        user: User,
    ) -> None:
        # Verify document exists and user has access
        existing_document = await self.providers.database.documents_handler.get_documents_overview(
            offset=0,
            limit=100,
            filter_document_ids=[document_id],
            filter_user_ids=[user.id],
        )
        if not existing_document["results"]:
            raise R2RException(
                status_code=404,
                message=(
                    f"Document with id {document_id} not found "
                    "or you don't have access."
                ),
            )

        existing_document = existing_document["results"][0]

        # Merge metadata
        merged_metadata = {**existing_document.metadata, **metadata}  # type: ignore

        # Update document metadata
        existing_document.metadata = merged_metadata  # type: ignore
        await self.providers.database.documents_handler.upsert_documents_overview(
            existing_document  # type: ignore
        )


class IngestionServiceAdapter:
    @staticmethod
    def _parse_user_data(user_data) -> User:
        if isinstance(user_data, str):
            try:
                user_data = json.loads(user_data)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid user data format: {user_data}"
                ) from e
        return User.from_dict(user_data)

    @staticmethod
    def parse_ingest_file_input(data: dict) -> dict:
        return {
            "user": IngestionServiceAdapter._parse_user_data(data["user"]),
            "metadata": data["metadata"],
            "document_id": (
                UUID(data["document_id"]) if data["document_id"] else None
            ),
            "version": data.get("version"),
            "ingestion_config": data["ingestion_config"] or {},
            "file_data": data["file_data"],
            "size_in_bytes": data["size_in_bytes"],
            "collection_ids": data.get("collection_ids", []),
        }

    @staticmethod
    def parse_ingest_chunks_input(data: dict) -> dict:
        return {
            "user": IngestionServiceAdapter._parse_user_data(data["user"]),
            "metadata": data["metadata"],
            "document_id": data["document_id"],
            "chunks": [
                UnprocessedChunk.from_dict(chunk) for chunk in data["chunks"]
            ],
            "id": data.get("id"),
        }

    @staticmethod
    def parse_update_chunk_input(data: dict) -> dict:
        return {
            "user": IngestionServiceAdapter._parse_user_data(data["user"]),
            "document_id": UUID(data["document_id"]),
            "id": UUID(data["id"]),
            "text": data["text"],
            "metadata": data.get("metadata"),
            "collection_ids": data.get("collection_ids", []),
        }

    @staticmethod
    def parse_update_files_input(data: dict) -> dict:
        return {
            "user": IngestionServiceAdapter._parse_user_data(data["user"]),
            "document_ids": [UUID(doc_id) for doc_id in data["document_ids"]],
            "metadatas": data["metadatas"],
            "ingestion_config": data["ingestion_config"],
            "file_sizes_in_bytes": data["file_sizes_in_bytes"],
            "file_datas": data["file_datas"],
        }

    @staticmethod
    def parse_create_vector_index_input(data: dict) -> dict:
        return {
            "table_name": VectorTableName(data["table_name"]),
            "index_method": IndexMethod(data["index_method"]),
            "index_measure": IndexMeasure(data["index_measure"]),
            "index_name": data["index_name"],
            "index_column": data["index_column"],
            "index_arguments": data["index_arguments"],
            "concurrently": data["concurrently"],
        }

    @staticmethod
    def parse_list_vector_indices_input(input_data: dict) -> dict:
        return {"table_name": input_data["table_name"]}

    @staticmethod
    def parse_delete_vector_index_input(input_data: dict) -> dict:
        return {
            "index_name": input_data["index_name"],
            "table_name": input_data.get("table_name"),
            "concurrently": input_data.get("concurrently", True),
        }

    @staticmethod
    def parse_select_vector_index_input(input_data: dict) -> dict:
        return {
            "index_name": input_data["index_name"],
            "table_name": input_data.get("table_name"),
        }

    @staticmethod
    def parse_update_document_metadata_input(data: dict) -> dict:
        return {
            "document_id": data["document_id"],
            "metadata": data["metadata"],
            "user": IngestionServiceAdapter._parse_user_data(data["user"]),
        }
