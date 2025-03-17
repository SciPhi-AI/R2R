import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import IO, Any, BinaryIO, Optional, Tuple
from uuid import UUID

import toml

from core.base import (
    CollectionResponse,
    ConversationResponse,
    DocumentResponse,
    GenerationConfig,
    GraphConstructionStatus,
    Message,
    MessageResponse,
    Prompt,
    R2RException,
    StoreType,
    User,
)

from ..abstractions import R2RProviders
from ..config import R2RConfig
from .base import Service

logger = logging.getLogger()


class ManagementService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
    ):
        super().__init__(
            config,
            providers,
        )

    async def app_settings(self):
        prompts = (
            await self.providers.database.prompts_handler.get_all_prompts()
        )
        config_toml = self.config.to_toml()
        config_dict = toml.loads(config_toml)
        try:
            project_name = os.environ["R2R_PROJECT_NAME"]
        except KeyError:
            project_name = ""
        return {
            "config": config_dict,
            "prompts": prompts,
            "r2r_project_name": project_name,
        }

    async def users_overview(
        self,
        offset: int,
        limit: int,
        user_ids: Optional[list[UUID]] = None,
    ):
        return await self.providers.database.users_handler.get_users_overview(
            offset=offset,
            limit=limit,
            user_ids=user_ids,
        )

    async def delete_documents_and_chunks_by_filter(
        self,
        filters: dict[str, Any],
    ):
        """Delete chunks matching the given filters. If any documents are now
        empty (i.e., have no remaining chunks), delete those documents as well.

        Args:
            filters (dict[str, Any]): Filters specifying which chunks to delete.
            chunks_handler (PostgresChunksHandler): The handler for chunk operations.
            documents_handler (PostgresDocumentsHandler): The handler for document operations.
            graphs_handler: Handler for entity and relationship operations in the Graph.

        Returns:
            dict: A summary of what was deleted.
        """

        def transform_chunk_id_to_id(
            filters: dict[str, Any],
        ) -> dict[str, Any]:
            """Example transformation function if your filters use `chunk_id`
            instead of `id`.

            Recursively transform `chunk_id` to `id`.
            """
            if isinstance(filters, dict):
                transformed = {}
                for key, value in filters.items():
                    if key == "chunk_id":
                        transformed["id"] = value
                    elif key in ["$and", "$or"]:
                        transformed[key] = [
                            transform_chunk_id_to_id(item) for item in value
                        ]
                    else:
                        transformed[key] = transform_chunk_id_to_id(value)
                return transformed
            return filters

        # Transform filters if needed.
        transformed_filters = transform_chunk_id_to_id(filters)

        # Find chunks that match the filters before deleting
        interim_results = (
            await self.providers.database.chunks_handler.list_chunks(
                filters=transformed_filters,
                offset=0,
                limit=1_000,
                include_vectors=False,
            )
        )

        results = interim_results["results"]
        while interim_results["total_entries"] == 1_000:
            # If we hit the limit, we need to paginate to get all results

            interim_results = (
                await self.providers.database.chunks_handler.list_chunks(
                    filters=transformed_filters,
                    offset=interim_results["offset"] + 1_000,
                    limit=1_000,
                    include_vectors=False,
                )
            )
            results.extend(interim_results["results"])

        document_ids = set()
        owner_id = None

        if "$and" in filters:
            for condition in filters["$and"]:
                if "owner_id" in condition and "$eq" in condition["owner_id"]:
                    owner_id = condition["owner_id"]["$eq"]
                elif (
                    "document_id" in condition
                    and "$eq" in condition["document_id"]
                ):
                    document_ids.add(UUID(condition["document_id"]["$eq"]))
        elif "document_id" in filters:
            doc_id = filters["document_id"]
            if isinstance(doc_id, str):
                document_ids.add(UUID(doc_id))
            elif isinstance(doc_id, UUID):
                document_ids.add(doc_id)
            elif isinstance(doc_id, dict) and "$eq" in doc_id:
                value = doc_id["$eq"]
                document_ids.add(
                    UUID(value) if isinstance(value, str) else value
                )

        # Delete matching chunks from the database
        delete_results = await self.providers.database.chunks_handler.delete(
            transformed_filters
        )

        # Extract the document_ids that were affected.
        affected_doc_ids = {
            UUID(info["document_id"])
            for info in delete_results.values()
            if info.get("document_id")
        }
        document_ids.update(affected_doc_ids)

        # Check if the document still has any chunks left
        docs_to_delete = []
        for doc_id in document_ids:
            documents_overview_response = await self.providers.database.documents_handler.get_documents_overview(
                offset=0, limit=1, filter_document_ids=[doc_id]
            )
            if not documents_overview_response["results"]:
                raise R2RException(
                    status_code=404, message="Document not found"
                )

            document = documents_overview_response["results"][0]

            for collection_id in document.collection_ids:
                await self.providers.database.collections_handler.decrement_collection_document_count(
                    collection_id=collection_id
                )

            if owner_id and str(document.owner_id) != owner_id:
                raise R2RException(
                    status_code=404,
                    message="Document not found or insufficient permissions",
                )
            docs_to_delete.append(doc_id)

        # Delete documents that no longer have associated chunks
        for doc_id in docs_to_delete:
            # Delete related entities & relationships if needed:
            await self.providers.database.graphs_handler.entities.delete(
                parent_id=doc_id,
                store_type=StoreType.DOCUMENTS,
            )
            await self.providers.database.graphs_handler.relationships.delete(
                parent_id=doc_id,
                store_type=StoreType.DOCUMENTS,
            )

            # Finally, delete the document from documents_overview:
            await self.providers.database.documents_handler.delete(
                document_id=doc_id
            )

        return {
            "success": True,
            "deleted_chunks_count": len(delete_results),
            "deleted_documents_count": len(docs_to_delete),
            "deleted_document_ids": [str(d) for d in docs_to_delete],
        }

    async def download_file(
        self, document_id: UUID
    ) -> Optional[Tuple[str, BinaryIO, int]]:
        if result := await self.providers.database.files_handler.retrieve_file(
            document_id
        ):
            return result
        return None

    async def export_files(
        self,
        document_ids: Optional[list[UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[str, BinaryIO, int]:
        return (
            await self.providers.database.files_handler.retrieve_files_as_zip(
                document_ids=document_ids,
                start_date=start_date,
                end_date=end_date,
            )
        )

    async def export_collections(
        self,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        return await self.providers.database.collections_handler.export_to_csv(
            columns=columns,
            filters=filters,
            include_header=include_header,
        )

    async def export_documents(
        self,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        return await self.providers.database.documents_handler.export_to_csv(
            columns=columns,
            filters=filters,
            include_header=include_header,
        )

    async def export_document_entities(
        self,
        id: UUID,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        return await self.providers.database.graphs_handler.entities.export_to_csv(
            parent_id=id,
            store_type=StoreType.DOCUMENTS,
            columns=columns,
            filters=filters,
            include_header=include_header,
        )

    async def export_document_relationships(
        self,
        id: UUID,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        return await self.providers.database.graphs_handler.relationships.export_to_csv(
            parent_id=id,
            store_type=StoreType.DOCUMENTS,
            columns=columns,
            filters=filters,
            include_header=include_header,
        )

    async def export_conversations(
        self,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        return await self.providers.database.conversations_handler.export_conversations_to_csv(
            columns=columns,
            filters=filters,
            include_header=include_header,
        )

    async def export_graph_entities(
        self,
        id: UUID,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        return await self.providers.database.graphs_handler.entities.export_to_csv(
            parent_id=id,
            store_type=StoreType.GRAPHS,
            columns=columns,
            filters=filters,
            include_header=include_header,
        )

    async def export_graph_relationships(
        self,
        id: UUID,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        return await self.providers.database.graphs_handler.relationships.export_to_csv(
            parent_id=id,
            store_type=StoreType.GRAPHS,
            columns=columns,
            filters=filters,
            include_header=include_header,
        )

    async def export_graph_communities(
        self,
        id: UUID,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        return await self.providers.database.graphs_handler.communities.export_to_csv(
            parent_id=id,
            store_type=StoreType.GRAPHS,
            columns=columns,
            filters=filters,
            include_header=include_header,
        )

    async def export_messages(
        self,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        return await self.providers.database.conversations_handler.export_messages_to_csv(
            columns=columns,
            filters=filters,
            include_header=include_header,
        )

    async def export_users(
        self,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        return await self.providers.database.users_handler.export_to_csv(
            columns=columns,
            filters=filters,
            include_header=include_header,
        )

    async def documents_overview(
        self,
        offset: int,
        limit: int,
        user_ids: Optional[list[UUID]] = None,
        collection_ids: Optional[list[UUID]] = None,
        document_ids: Optional[list[UUID]] = None,
    ):
        return await self.providers.database.documents_handler.get_documents_overview(
            offset=offset,
            limit=limit,
            filter_document_ids=document_ids,
            filter_user_ids=user_ids,
            filter_collection_ids=collection_ids,
        )

    async def list_document_chunks(
        self,
        document_id: UUID,
        offset: int,
        limit: int,
        include_vectors: bool = False,
    ):
        return (
            await self.providers.database.chunks_handler.list_document_chunks(
                document_id=document_id,
                offset=offset,
                limit=limit,
                include_vectors=include_vectors,
            )
        )

    async def assign_document_to_collection(
        self, document_id: UUID, collection_id: UUID
    ):
        await self.providers.database.chunks_handler.assign_document_chunks_to_collection(
            document_id, collection_id
        )
        await self.providers.database.collections_handler.assign_document_to_collection_relational(
            document_id, collection_id
        )
        await self.providers.database.documents_handler.set_workflow_status(
            id=collection_id,
            status_type="graph_sync_status",
            status=GraphConstructionStatus.OUTDATED,
        )
        await self.providers.database.documents_handler.set_workflow_status(
            id=collection_id,
            status_type="graph_cluster_status",
            status=GraphConstructionStatus.OUTDATED,
        )

        return {"message": "Document assigned to collection successfully"}

    async def remove_document_from_collection(
        self, document_id: UUID, collection_id: UUID
    ):
        await self.providers.database.collections_handler.remove_document_from_collection_relational(
            document_id, collection_id
        )
        await self.providers.database.chunks_handler.remove_document_from_collection_vector(
            document_id, collection_id
        )
        # await self.providers.database.graphs_handler.delete_node_via_document_id(
        #     document_id, collection_id
        # )
        return None

    def _process_relationships(
        self, relationships: list[Tuple[str, str, str]]
    ) -> Tuple[dict[str, list[str]], dict[str, dict[str, list[str]]]]:
        graph = defaultdict(list)
        grouped: dict[str, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for subject, relation, obj in relationships:
            graph[subject].append(obj)
            grouped[subject][relation].append(obj)
            if obj not in graph:
                graph[obj] = []
        return dict(graph), dict(grouped)

    def generate_output(
        self,
        grouped_relationships: dict[str, dict[str, list[str]]],
        graph: dict[str, list[str]],
        descriptions_dict: dict[str, str],
        print_descriptions: bool = True,
    ) -> list[str]:
        output = []
        # Print grouped relationships
        for subject, relations in grouped_relationships.items():
            output.append(f"\n== {subject} ==")
            if print_descriptions and subject in descriptions_dict:
                output.append(f"\tDescription: {descriptions_dict[subject]}")
            for relation, objects in relations.items():
                output.append(f"  {relation}:")
                for obj in objects:
                    output.append(f"    - {obj}")
                    if print_descriptions and obj in descriptions_dict:
                        output.append(
                            f"      Description: {descriptions_dict[obj]}"
                        )

        # Print basic graph statistics
        output.extend(
            [
                "\n== Graph Statistics ==",
                f"Number of nodes: {len(graph)}",
                f"Number of edges: {sum(len(neighbors) for neighbors in graph.values())}",
                f"Number of connected components: {self._count_connected_components(graph)}",
            ]
        )

        # Find central nodes
        central_nodes = self._get_central_nodes(graph)
        output.extend(
            [
                "\n== Most Central Nodes ==",
                *(
                    f"  {node}: {centrality:.4f}"
                    for node, centrality in central_nodes
                ),
            ]
        )

        return output

    def _count_connected_components(self, graph: dict[str, list[str]]) -> int:
        visited = set()
        components = 0

        def dfs(node):
            visited.add(node)
            for neighbor in graph[node]:
                if neighbor not in visited:
                    dfs(neighbor)

        for node in graph:
            if node not in visited:
                dfs(node)
                components += 1

        return components

    def _get_central_nodes(
        self, graph: dict[str, list[str]]
    ) -> list[Tuple[str, float]]:
        degree = {node: len(neighbors) for node, neighbors in graph.items()}
        total_nodes = len(graph)
        centrality = {
            node: deg / (total_nodes - 1) for node, deg in degree.items()
        }
        return sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]

    async def create_collection(
        self,
        owner_id: UUID,
        name: Optional[str] = None,
        description: str | None = None,
    ) -> CollectionResponse:
        result = await self.providers.database.collections_handler.create_collection(
            owner_id=owner_id,
            name=name,
            description=description,
        )
        await self.providers.database.graphs_handler.create(
            collection_id=result.id,
            name=name,
            description=description,
        )
        return result

    async def update_collection(
        self,
        collection_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        generate_description: bool = False,
    ) -> CollectionResponse:
        if generate_description:
            description = await self.summarize_collection(
                id=collection_id, offset=0, limit=100
            )
        return await self.providers.database.collections_handler.update_collection(
            collection_id=collection_id,
            name=name,
            description=description,
        )

    async def delete_collection(self, collection_id: UUID) -> bool:
        await self.providers.database.collections_handler.delete_collection_relational(
            collection_id
        )
        await self.providers.database.chunks_handler.delete_collection_vector(
            collection_id
        )
        try:
            await self.providers.database.graphs_handler.delete(
                collection_id=collection_id,
            )
        except Exception as e:
            logger.warning(
                f"Error deleting graph for collection {collection_id}: {e}"
            )
        return True

    async def collections_overview(
        self,
        offset: int,
        limit: int,
        user_ids: Optional[list[UUID]] = None,
        document_ids: Optional[list[UUID]] = None,
        collection_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[CollectionResponse] | int]:
        return await self.providers.database.collections_handler.get_collections_overview(
            offset=offset,
            limit=limit,
            filter_user_ids=user_ids,
            filter_document_ids=document_ids,
            filter_collection_ids=collection_ids,
        )

    async def add_user_to_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> bool:
        return (
            await self.providers.database.users_handler.add_user_to_collection(
                user_id, collection_id
            )
        )

    async def remove_user_from_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> bool:
        return await self.providers.database.users_handler.remove_user_from_collection(
            user_id, collection_id
        )

    async def get_users_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = 100
    ) -> dict[str, list[User] | int]:
        return await self.providers.database.users_handler.get_users_in_collection(
            collection_id, offset=offset, limit=limit
        )

    async def documents_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = 100
    ) -> dict[str, list[DocumentResponse] | int]:
        return await self.providers.database.collections_handler.documents_in_collection(
            collection_id, offset=offset, limit=limit
        )

    async def summarize_collection(
        self, id: UUID, offset: int, limit: int
    ) -> str:
        documents_in_collection_response = await self.documents_in_collection(
            collection_id=id,
            offset=offset,
            limit=limit,
        )

        document_summaries = [
            document.summary
            for document in documents_in_collection_response["results"]  # type: ignore
        ]

        logger.info(
            f"Summarizing collection {id} with {len(document_summaries)} of {documents_in_collection_response['total_entries']} documents."
        )

        formatted_summaries = "\n\n".join(document_summaries)  # type: ignore

        messages = await self.providers.database.prompts_handler.get_message_payload(
            system_prompt_name=self.config.database.collection_summary_system_prompt,
            task_prompt_name=self.config.database.collection_summary_prompt,
            task_inputs={"document_summaries": formatted_summaries},
        )

        response = await self.providers.llm.aget_completion(
            messages=messages,
            generation_config=GenerationConfig(
                model=self.config.ingestion.document_summary_model
                or self.config.app.fast_llm
            ),
        )

        if collection_summary := response.choices[0].message.content:
            return collection_summary
        else:
            raise ValueError("Expected a generated response.")

    async def add_prompt(
        self, name: str, template: str, input_types: dict[str, str]
    ) -> dict:
        try:
            await self.providers.database.prompts_handler.add_prompt(
                name, template, input_types
            )
            return f"Prompt '{name}' added successfully."  # type: ignore
        except ValueError as e:
            raise R2RException(status_code=400, message=str(e)) from e

    async def get_cached_prompt(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        prompt_override: Optional[str] = None,
    ) -> dict:
        try:
            return {
                "message": (
                    await self.providers.database.prompts_handler.get_cached_prompt(
                        prompt_name=prompt_name,
                        inputs=inputs,
                        prompt_override=prompt_override,
                    )
                )
            }
        except ValueError as e:
            raise R2RException(status_code=404, message=str(e)) from e

    async def get_prompt(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        prompt_override: Optional[str] = None,
    ) -> dict:
        try:
            return await self.providers.database.prompts_handler.get_prompt(  # type: ignore
                name=prompt_name,
                inputs=inputs,
                prompt_override=prompt_override,
            )
        except ValueError as e:
            raise R2RException(status_code=404, message=str(e)) from e

    async def get_all_prompts(self) -> dict[str, Prompt]:
        return await self.providers.database.prompts_handler.get_all_prompts()

    async def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> dict:
        try:
            await self.providers.database.prompts_handler.update_prompt(
                name, template, input_types
            )
            return f"Prompt '{name}' updated successfully."  # type: ignore
        except ValueError as e:
            raise R2RException(status_code=404, message=str(e)) from e

    async def delete_prompt(self, name: str) -> dict:
        try:
            await self.providers.database.prompts_handler.delete_prompt(name)
            return {"message": f"Prompt '{name}' deleted successfully."}
        except ValueError as e:
            raise R2RException(status_code=404, message=str(e)) from e

    async def get_conversation(
        self,
        conversation_id: UUID,
        user_ids: Optional[list[UUID]] = None,
    ) -> list[MessageResponse]:
        return await self.providers.database.conversations_handler.get_conversation(
            conversation_id=conversation_id,
            filter_user_ids=user_ids,
        )

    async def create_conversation(
        self,
        user_id: Optional[UUID] = None,
        name: Optional[str] = None,
    ) -> ConversationResponse:
        return await self.providers.database.conversations_handler.create_conversation(
            user_id=user_id,
            name=name,
        )

    async def conversations_overview(
        self,
        offset: int,
        limit: int,
        conversation_ids: Optional[list[UUID]] = None,
        user_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[dict] | int]:
        return await self.providers.database.conversations_handler.get_conversations_overview(
            offset=offset,
            limit=limit,
            filter_user_ids=user_ids,
            conversation_ids=conversation_ids,
        )

    async def add_message(
        self,
        conversation_id: UUID,
        content: Message,
        parent_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
    ) -> MessageResponse:
        return await self.providers.database.conversations_handler.add_message(
            conversation_id=conversation_id,
            content=content,
            parent_id=parent_id,
            metadata=metadata,
        )

    async def edit_message(
        self,
        message_id: UUID,
        new_content: Optional[str] = None,
        additional_metadata: Optional[dict] = None,
    ) -> dict[str, Any]:
        return (
            await self.providers.database.conversations_handler.edit_message(
                message_id=message_id,
                new_content=new_content,
                additional_metadata=additional_metadata or {},
            )
        )

    async def update_conversation(
        self, conversation_id: UUID, name: str
    ) -> ConversationResponse:
        return await self.providers.database.conversations_handler.update_conversation(
            conversation_id=conversation_id, name=name
        )

    async def delete_conversation(
        self,
        conversation_id: UUID,
        user_ids: Optional[list[UUID]] = None,
    ) -> None:
        await (
            self.providers.database.conversations_handler.delete_conversation(
                conversation_id=conversation_id,
                filter_user_ids=user_ids,
            )
        )

    async def get_user_max_documents(self, user_id: UUID) -> int | None:
        # Fetch the user to see if they have any overrides stored
        user = await self.providers.database.users_handler.get_user_by_id(
            user_id
        )
        if user.limits_overrides and "max_documents" in user.limits_overrides:
            return user.limits_overrides["max_documents"]
        return self.config.app.default_max_documents_per_user

    async def get_user_max_chunks(self, user_id: UUID) -> int | None:
        user = await self.providers.database.users_handler.get_user_by_id(
            user_id
        )
        if user.limits_overrides and "max_chunks" in user.limits_overrides:
            return user.limits_overrides["max_chunks"]
        return self.config.app.default_max_chunks_per_user

    async def get_user_max_collections(self, user_id: UUID) -> int | None:
        user = await self.providers.database.users_handler.get_user_by_id(
            user_id
        )
        if (
            user.limits_overrides
            and "max_collections" in user.limits_overrides
        ):
            return user.limits_overrides["max_collections"]
        return self.config.app.default_max_collections_per_user

    async def get_max_upload_size_by_type(
        self, user_id: UUID, file_type_or_ext: str
    ) -> int:
        """Return the maximum allowed upload size (in bytes) for the given
        user's file type/extension. Respects user-level overrides if present,
        falling back to the system config.

        ```json
        {
            "limits_overrides": {
                "max_file_size": 20_000_000,
                "max_file_size_by_type":
                {
                "pdf": 50_000_000,
                "docx": 30_000_000
                },
                ...
            }
        }
        ```
        """
        # 1. Normalize extension
        ext = file_type_or_ext.lower().lstrip(".")

        # 2. Fetch user from DB to see if we have any overrides
        user = await self.providers.database.users_handler.get_user_by_id(
            user_id
        )
        user_overrides = user.limits_overrides or {}

        # 3. Check if there's a user-level override for "max_file_size_by_type"
        user_file_type_limits = user_overrides.get("max_file_size_by_type", {})
        if ext in user_file_type_limits:
            return user_file_type_limits[ext]

        # 4. If not, check if there's a user-level fallback "max_file_size"
        if "max_file_size" in user_overrides:
            return user_overrides["max_file_size"]

        # 5. If none exist at user level, use system config
        #    Example config paths:
        system_type_limits = self.config.app.max_upload_size_by_type
        if ext in system_type_limits:
            return system_type_limits[ext]

        # 6. Otherwise, return the global default
        return self.config.app.default_max_upload_size

    async def get_all_user_limits(self, user_id: UUID) -> dict[str, Any]:
        """
        Return a dictionary containing:
        - The system default limits (from self.config.limits)
        - The user's overrides (from user.limits_overrides)
        - The final 'effective' set of limits after merging (overall)
        - The usage for each relevant limit (per-route usage, etc.)
        """
        # 1) Fetch the user
        user = await self.providers.database.users_handler.get_user_by_id(
            user_id
        )
        user_overrides = user.limits_overrides or {}

        # 2) Grab system defaults
        system_defaults = {
            "global_per_min": self.config.database.limits.global_per_min,
            "route_per_min": self.config.database.limits.route_per_min,
            "monthly_limit": self.config.database.limits.monthly_limit,
            # Add additional fields if your LimitSettings has them
        }

        # 3) Build the overall (global) "effective limits" ignoring any specific route
        overall_effective = (
            self.providers.database.limits_handler.determine_effective_limits(
                user, route=""
            )
        )

        # 4) Build usage data. We'll do top-level usage for global_per_min/monthly,
        #    then do route-by-route usage in a loop.
        usage: dict[str, Any] = {}
        now = datetime.now(timezone.utc)
        one_min_ago = now - timedelta(minutes=1)

        # (a) Global usage (per-minute)
        global_per_min_used = (
            await self.providers.database.limits_handler._count_requests(
                user_id, route=None, since=one_min_ago
            )
        )
        # (a2) Global usage (monthly) - i.e. usage across ALL routes
        global_monthly_used = await self.providers.database.limits_handler._count_monthly_requests(
            user_id, route=None
        )

        usage["global_per_min"] = {
            "used": global_per_min_used,
            "limit": overall_effective.global_per_min,
            "remaining": (
                overall_effective.global_per_min - global_per_min_used
                if overall_effective.global_per_min is not None
                else None
            ),
        }
        usage["monthly_limit"] = {
            "used": global_monthly_used,
            "limit": overall_effective.monthly_limit,
            "remaining": (
                overall_effective.monthly_limit - global_monthly_used
                if overall_effective.monthly_limit is not None
                else None
            ),
        }

        # (b) Route-level usage. We'll gather all routes from system + user overrides
        system_route_limits = (
            self.config.database.route_limits
        )  # dict[str, LimitSettings]
        user_route_overrides = user_overrides.get("route_overrides", {})
        route_keys = set(system_route_limits.keys()) | set(
            user_route_overrides.keys()
        )

        usage["routes"] = {}
        for route in route_keys:
            # 1) Get the final merged limits for this specific route
            route_effective = self.providers.database.limits_handler.determine_effective_limits(
                user, route
            )

            # 2) Count requests for the last minute on this route
            route_per_min_used = (
                await self.providers.database.limits_handler._count_requests(
                    user_id, route, one_min_ago
                )
            )

            # 3) Count route-specific monthly usage
            route_monthly_used = await self.providers.database.limits_handler._count_monthly_requests(
                user_id, route
            )

            usage["routes"][route] = {
                "route_per_min": {
                    "used": route_per_min_used,
                    "limit": route_effective.route_per_min,
                    "remaining": (
                        route_effective.route_per_min - route_per_min_used
                        if route_effective.route_per_min is not None
                        else None
                    ),
                },
                "monthly_limit": {
                    "used": route_monthly_used,
                    "limit": route_effective.monthly_limit,
                    "remaining": (
                        route_effective.monthly_limit - route_monthly_used
                        if route_effective.monthly_limit is not None
                        else None
                    ),
                },
            }

        max_documents = await self.get_user_max_documents(user_id)
        used_documents = (
            await self.providers.database.documents_handler.get_documents_overview(
                limit=1, offset=0, filter_user_ids=[user_id]
            )
        )["total_entries"]
        max_chunks = await self.get_user_max_chunks(user_id)
        used_chunks = (
            await self.providers.database.chunks_handler.list_chunks(
                limit=1, offset=0, filters={"owner_id": user_id}
            )
        )["total_entries"]

        max_collections = await self.get_user_max_collections(user_id)
        used_collections: int = (  # type: ignore
            await self.providers.database.collections_handler.get_collections_overview(
                limit=1, offset=0, filter_user_ids=[user_id]
            )
        )["total_entries"]

        storage_limits = {
            "chunks": {
                "limit": max_chunks,
                "used": used_chunks,
                "remaining": (
                    max_chunks - used_chunks
                    if max_chunks is not None
                    else None
                ),
            },
            "documents": {
                "limit": max_documents,
                "used": used_documents,
                "remaining": (
                    max_documents - used_documents
                    if max_documents is not None
                    else None
                ),
            },
            "collections": {
                "limit": max_collections,
                "used": used_collections,
                "remaining": (
                    max_collections - used_collections
                    if max_collections is not None
                    else None
                ),
            },
        }
        # 5) Return a structured response
        return {
            "storage_limits": storage_limits,
            "system_defaults": system_defaults,
            "user_overrides": user_overrides,
            "effective_limits": {
                "global_per_min": overall_effective.global_per_min,
                "route_per_min": overall_effective.route_per_min,
                "monthly_limit": overall_effective.monthly_limit,
            },
            "usage": usage,
        }
