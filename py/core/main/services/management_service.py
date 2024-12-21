import logging
import os
from collections import defaultdict
from typing import Any, BinaryIO, Optional, Tuple
from uuid import UUID

import toml

from core.base import (
    CollectionResponse,
    DocumentResponse,
    GenerationConfig,
    KGEnrichmentStatus,
    Message,
    Prompt,
    R2RException,
    RunManager,
    User,
    ConversationResponse,
)
from core.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from ..config import R2RConfig
from .base import Service

logger = logging.getLogger()


class ManagementService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipes: R2RPipes,
        pipelines: R2RPipelines,
        agents: R2RAgents,
        run_manager: RunManager,
    ):
        super().__init__(
            config,
            providers,
            pipes,
            pipelines,
            agents,
            run_manager,
        )

    @telemetry_event("AppSettings")
    async def app_settings(self):
        prompts = (
            await self.providers.database.prompts_handler.get_all_prompts()
        )
        config_toml = self.config.to_toml()
        config_dict = toml.loads(config_toml)
        return {
            "config": config_dict,
            "prompts": prompts,
            "r2r_project_name": os.environ["R2R_PROJECT_NAME"],
            # "r2r_version": get_version("r2r"),
        }

    @telemetry_event("UsersOverview")
    async def users_overview(
        self,
        offset: int,
        limit: int,
        user_ids: Optional[list[UUID]] = None,
        *args,
        **kwargs,
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
        """
        Delete chunks matching the given filters. If any documents are now empty
        (i.e., have no remaining chunks), delete those documents as well.

        Args:
            filters (dict[str, Any]): Filters specifying which chunks to delete.
            chunks_handler (PostgresChunksHandler): The handler for chunk operations.
            documents_handler (PostgresDocumentsHandler): The handler for document operations.
            graphs_handler: Handler for entity and relationship operations in the KG.

        Returns:
            dict: A summary of what was deleted.
        """

        def transform_chunk_id_to_id(
            filters: dict[str, Any]
        ) -> dict[str, Any]:
            """
            Example transformation function if your filters use `chunk_id` instead of `id`.
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

        # 1. (Optional) Validate the input filters based on your rules.
        #    E.g., check if filters is not empty, allowed fields, etc.
        # validate_filters(filters)

        # 2. Transform filters if needed.
        #    For example, if `chunk_id` is used, map it to `id`, or similar transformations.
        transformed_filters = transform_chunk_id_to_id(filters)

        # 3. First, find out which chunks match these filters *before* deleting, so we know which docs are affected.
        #    You can do a list operation on chunks to see which chunk IDs and doc IDs would be hit.
        interim_results = (
            await self.providers.database.chunks_handler.list_chunks(
                filters=transformed_filters,
                offset=0,
                limit=1_000,  # Arbitrary large limit or pagination logic
                include_vectors=False,
            )
        )

        if interim_results["page_info"]["total_entries"] == 0:
            raise R2RException(
                status_code=404, message="No entries found for deletion."
            )

        results = interim_results["results"]
        while interim_results["page_info"]["total_entries"] == 1_000:
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
        matched_chunk_docs = {UUID(chunk["document_id"]) for chunk in results}

        # If no chunks match, raise or return a no-op result
        if not matched_chunk_docs:
            return {
                "success": False,
                "message": "No chunks match the given filters.",
            }

        # 4. Delete the matching chunks from the database.
        delete_results = await self.providers.database.chunks_handler.delete(
            transformed_filters
        )

        # 5. From `delete_results`, extract the document_ids that were affected.
        #    The delete_results should map chunk_id to details including `document_id`.
        affected_doc_ids = {
            UUID(info["document_id"])
            for info in delete_results.values()
            if info.get("document_id")
        }

        # 6. For each affected document, check if the document still has any chunks left.
        docs_to_delete = []
        for doc_id in affected_doc_ids:
            remaining = await self.providers.database.chunks_handler.list_document_chunks(
                document_id=doc_id,
                offset=0,
                limit=1,  # Just need to know if there's at least one left
                include_vectors=False,
            )
            # If no remaining chunks, we should delete the document.
            if remaining["total_entries"] == 0:
                docs_to_delete.append(doc_id)

        # 7. Delete documents that no longer have associated chunks.
        #    Also update graphs if needed (entities/relationships).
        for doc_id in docs_to_delete:
            # Delete related entities & relationships if needed:
            await self.providers.database.graphs_handler.entities.delete(
                parent_id=doc_id, store_type="documents"
            )
            await self.providers.database.graphs_handler.relationships.delete(
                parent_id=doc_id, store_type="documents"
            )

            # Finally, delete the document from documents_overview:
            await self.providers.database.documents_handler.delete(
                document_id=doc_id
            )

        # 8. Return a summary of what happened.
        return {
            "success": True,
            "deleted_chunks_count": len(delete_results),
            "deleted_documents_count": len(docs_to_delete),
            "deleted_document_ids": [str(d) for d in docs_to_delete],
        }

    # @telemetry_event("Delete")
    # async def delete(
    #     self,
    #     filters: dict[str, Any],
    #     *args,
    #     **kwargs,
    # ):
    #     """
    #     Takes a list of filters like
    #     "{key: {operator: value}, key: {operator: value}, ...}"
    #     and deletes entries matching the given filters from both vector and relational databases.

    #     NOTE: This method is not atomic and may result in orphaned entries in the documents overview table.
    #     NOTE: This method assumes that filters delete entire contents of any touched documents.
    #     """
    #     ### TODO - FIX THIS, ENSURE THAT DOCUMENTS OVERVIEW IS CLEARED

    #     def validate_filters(filters: dict[str, Any]) -> None:
    #         ALLOWED_FILTERS = {
    #             "id",
    #             "collection_ids",
    #             "chunk_id",
    #             # TODO - Modify these checks such that they can be used PROPERLY for nested filters
    #             "$and",
    #             "$or",
    #         }

    #         if not filters:
    #             raise R2RException(
    #                 status_code=422, message="No filters provided"
    #             )

    #         for field in filters:
    #             if field not in ALLOWED_FILTERS:
    #                 raise R2RException(
    #                     status_code=422,
    #                     message=f"Invalid filter field: {field}",
    #                 )

    #         for field in ["document_id", "owner_id", "chunk_id"]:
    #             if field in filters:
    #                 op = next(iter(filters[field].keys()))
    #                 try:
    #                     validate_uuid(filters[field][op])
    #                 except ValueError:
    #                     raise R2RException(
    #                         status_code=422,
    #                         message=f"Invalid UUID: {filters[field][op]}",
    #                     )

    #         if "collection_ids" in filters:
    #             op = next(iter(filters["collection_ids"].keys()))
    #             for id_str in filters["collection_ids"][op]:
    #                 try:
    #                     validate_uuid(id_str)
    #                 except ValueError:
    #                     raise R2RException(
    #                         status_code=422, message=f"Invalid UUID: {id_str}"
    #                     )

    #     validate_filters(filters)

    #     logger.info(f"Deleting entries with filters: {filters}")

    #     try:

    #         def transform_chunk_id_to_id(
    #             filters: dict[str, Any]
    #         ) -> dict[str, Any]:
    #             if isinstance(filters, dict):
    #                 transformed = {}
    #                 for key, value in filters.items():
    #                     if key == "chunk_id":
    #                         transformed["id"] = value
    #                     elif key in ["$and", "$or"]:
    #                         transformed[key] = [
    #                             transform_chunk_id_to_id(item)
    #                             for item in value
    #                         ]
    #                     else:
    #                         transformed[key] = transform_chunk_id_to_id(value)
    #                 return transformed
    #             return filters

    #         filters_xf = transform_chunk_id_to_id(copy(filters))

    #         await self.providers.database.chunks_handler.delete(filters)

    #         vector_delete_results = (
    #             await self.providers.database.chunks_handler.delete(filters_xf)
    #         )
    #     except Exception as e:
    #         logger.error(f"Error deleting from vector database: {e}")
    #         vector_delete_results = {}

    #     document_ids_to_purge: set[UUID] = set()
    #     if vector_delete_results:
    #         document_ids_to_purge.update(
    #             UUID(result.get("document_id"))
    #             for result in vector_delete_results.values()
    #             if result.get("document_id")
    #         )

    #     # TODO: This might be appropriate to move elsewhere and revisit filter logic in other methods
    #     def extract_filters(filters: dict[str, Any]) -> dict[str, list[str]]:
    #         relational_filters: dict = {}

    #         def process_filter(filter_dict: dict[str, Any]):
    #             if "document_id" in filter_dict:
    #                 relational_filters.setdefault(
    #                     "filter_document_ids", []
    #                 ).append(filter_dict["document_id"]["$eq"])
    #             if "owner_id" in filter_dict:
    #                 relational_filters.setdefault(
    #                     "filter_user_ids", []
    #                 ).append(filter_dict["owner_id"]["$eq"])
    #             if "collection_ids" in filter_dict:
    #                 relational_filters.setdefault(
    #                     "filter_collection_ids", []
    #                 ).extend(filter_dict["collection_ids"]["$in"])

    #         # Handle nested conditions
    #         if "$and" in filters:
    #             for condition in filters["$and"]:
    #                 process_filter(condition)
    #         elif "$or" in filters:
    #             for condition in filters["$or"]:
    #                 process_filter(condition)
    #         else:
    #             process_filter(filters)

    #         return relational_filters

    #     relational_filters = extract_filters(filters)
    #     if relational_filters:
    #         try:
    #             documents_overview = (
    #                 await self.providers.database.documents_handler.get_documents_overview(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
    #                     offset=0,
    #                     limit=1000,
    #                     **relational_filters,  # type: ignore
    #                 )
    #             )["results"]
    #         except Exception as e:
    #             logger.error(
    #                 f"Error fetching documents from relational database: {e}"
    #             )
    #             documents_overview = []

    #         if documents_overview:
    #             document_ids_to_purge.update(
    #                 doc.id for doc in documents_overview
    #             )

    #         if not document_ids_to_purge:
    #             raise R2RException(
    #                 status_code=404, message="No entries found for deletion."
    #             )

    #         for document_id in document_ids_to_purge:
    #             remaining_chunks = await self.providers.database.chunks_handler.list_document_chunks(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
    #                 document_id=document_id,
    #                 offset=0,
    #                 limit=1000,
    #             )
    #             if remaining_chunks["total_entries"] == 0:
    #                 try:
    #                     await self.providers.database.chunks_handler.delete(
    #                         {"document_id": {"$eq": document_id}}
    #                     )
    #                     logger.info(
    #                         f"Deleted document ID {document_id} from documents_overview."
    #                     )
    #                 except Exception as e:
    #                     logger.error(
    #                         f"Error deleting document ID {document_id} from documents_overview: {e}"
    #                     )
    #             await self.providers.database.graphs_handler.entities.delete(
    #                 parent_id=document_id,
    #                 store_type="documents",  # type: ignore
    #             )
    #             await self.providers.database.graphs_handler.relationships.delete(
    #                 parent_id=document_id,
    #                 store_type="documents",  # type: ignore
    #             )
    #             await self.providers.database.documents_handler.delete(
    #                 document_id=document_id
    #             )

    #             collections = await self.providers.database.collections_handler.get_collections_overview(
    #                 offset=0, limit=1000, filter_document_ids=[document_id]
    #             )
    #             # TODO - Loop over all collections
    #             for collection in collections["results"]:
    #                 await self.providers.database.documents_handler.set_workflow_status(
    #                     id=collection.id,
    #                     status_type="graph_sync_status",
    #                     status=KGEnrichmentStatus.OUTDATED,
    #                 )
    #                 await self.providers.database.documents_handler.set_workflow_status(
    #                     id=collection.id,
    #                     status_type="graph_cluster_status",
    #                     status=KGEnrichmentStatus.OUTDATED,
    #                 )

    #     return None

    @telemetry_event("DownloadFile")
    async def download_file(
        self, document_id: UUID
    ) -> Optional[Tuple[str, BinaryIO, int]]:
        if result := await self.providers.database.files_handler.retrieve_file(
            document_id
        ):
            return result
        return None

    @telemetry_event("DocumentsOverview")
    async def documents_overview(
        self,
        offset: int,
        limit: int,
        user_ids: Optional[list[UUID]] = None,
        collection_ids: Optional[list[UUID]] = None,
        document_ids: Optional[list[UUID]] = None,
        *args: Any,
        **kwargs: Any,
    ):
        return await self.providers.database.documents_handler.get_documents_overview(
            offset=offset,
            limit=limit,
            filter_document_ids=document_ids,
            filter_user_ids=user_ids,
            filter_collection_ids=collection_ids,
        )

    @telemetry_event("DocumentChunks")
    async def list_document_chunks(
        self,
        document_id: UUID,
        offset: int,
        limit: int,
        include_vectors: bool = False,
        *args,
        **kwargs,
    ):
        return (
            await self.providers.database.chunks_handler.list_document_chunks(
                document_id=document_id,
                offset=offset,
                limit=limit,
                include_vectors=include_vectors,
            )
        )

    @telemetry_event("AssignDocumentToCollection")
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
            status=KGEnrichmentStatus.OUTDATED,
        )
        await self.providers.database.documents_handler.set_workflow_status(
            id=collection_id,
            status_type="graph_cluster_status",
            status=KGEnrichmentStatus.OUTDATED,
        )

        return {"message": "Document assigned to collection successfully"}

    @telemetry_event("RemoveDocumentFromCollection")
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

    @telemetry_event("CreateCollection")
    async def create_collection(
        self,
        owner_id: UUID,
        name: Optional[str] = None,
        description: str = "",
    ) -> CollectionResponse:
        result = await self.providers.database.collections_handler.create_collection(
            owner_id=owner_id,
            name=name,
            description=description,
        )
        graph_result = await self.providers.database.graphs_handler.create(
            collection_id=result.id,
            name=name,
            description=description,
        )
        return result

    @telemetry_event("UpdateCollection")
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

    @telemetry_event("DeleteCollection")
    async def delete_collection(self, collection_id: UUID) -> bool:
        await self.providers.database.collections_handler.delete_collection_relational(
            collection_id
        )
        await self.providers.database.chunks_handler.delete_collection_vector(
            collection_id
        )
        return True

    @telemetry_event("ListCollections")
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

    @telemetry_event("AddUserToCollection")
    async def add_user_to_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> bool:
        return (
            await self.providers.database.users_handler.add_user_to_collection(
                user_id, collection_id
            )
        )

    @telemetry_event("RemoveUserFromCollection")
    async def remove_user_from_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> bool:

        x = await self.providers.database.users_handler.remove_user_from_collection(
            user_id, collection_id
        )
        return x

    @telemetry_event("GetUsersInCollection")
    async def get_users_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = 100
    ) -> dict[str, list[User] | int]:
        return await self.providers.database.users_handler.get_users_in_collection(
            collection_id, offset=offset, limit=limit
        )

    @telemetry_event("GetDocumentsInCollection")
    async def documents_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = 100
    ) -> dict[str, list[DocumentResponse] | int]:
        return await self.providers.database.collections_handler.documents_in_collection(
            collection_id, offset=offset, limit=limit
        )

    @telemetry_event("SummarizeCollection")
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
            for document in documents_in_collection_response["results"]
        ]

        logger.info(
            f"Summarizing collection {id} with {len(document_summaries)} of {documents_in_collection_response['total_entries']} documents."
        )

        formatted_summaries = "\n\n".join(document_summaries)

        messages = await self.providers.database.prompts_handler.get_message_payload(
            system_prompt_name=self.config.database.collection_summary_system_prompt,
            task_prompt_name=self.config.database.collection_summary_task_prompt,
            task_inputs={"document_summaries": formatted_summaries},
        )

        response = await self.providers.llm.aget_completion(
            messages=messages,
            generation_config=GenerationConfig(
                model=self.config.ingestion.document_summary_model
            ),
        )

        collection_summary = response.choices[0].message.content
        if not collection_summary:
            raise ValueError("Expected a generated response.")
        return collection_summary

    @telemetry_event("AddPrompt")
    async def add_prompt(
        self, name: str, template: str, input_types: dict[str, str]
    ) -> dict:
        try:
            await self.providers.database.prompts_handler.add_prompt(
                name, template, input_types
            )
            return f"Prompt '{name}' added successfully."  # type: ignore
        except ValueError as e:
            raise R2RException(status_code=400, message=str(e))

    @telemetry_event("GetPrompt")
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
                        prompt_name, inputs, prompt_override
                    )
                )
            }
        except ValueError as e:
            raise R2RException(status_code=404, message=str(e))

    @telemetry_event("GetPrompt")
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
            raise R2RException(status_code=404, message=str(e))

    @telemetry_event("GetAllPrompts")
    async def get_all_prompts(self) -> dict[str, Prompt]:
        return await self.providers.database.prompts_handler.get_all_prompts()

    @telemetry_event("UpdatePrompt")
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
            raise R2RException(status_code=404, message=str(e))

    @telemetry_event("DeletePrompt")
    async def delete_prompt(self, name: str) -> dict:
        try:
            await self.providers.database.prompts_handler.delete_prompt(name)
            return {"message": f"Prompt '{name}' deleted successfully."}
        except ValueError as e:
            raise R2RException(status_code=404, message=str(e))

    @telemetry_event("GetConversation")
    async def get_conversation(
        self,
        conversation_id: UUID,
        auth_user=None,
    ) -> Tuple[str, list[Message], list[dict]]:
        return await self.providers.database.conversations_handler.get_conversation(  # type: ignore
            conversation_id=conversation_id
        )

    async def verify_conversation_access(
        self, conversation_id: UUID, user_id: UUID
    ) -> bool:
        return await self.providers.database.conversations_handler.verify_conversation_access(
            conversation_id=conversation_id,
            user_id=user_id,
        )

    @telemetry_event("CreateConversation")
    async def create_conversation(
        self,
        user_id: Optional[UUID] = None,
        name: Optional[str] = None,
    ) -> ConversationResponse:
        return await self.providers.database.conversations_handler.create_conversation(
            user_id=user_id,
            name=name,
        )

    @telemetry_event("ConversationsOverview")
    async def conversations_overview(
        self,
        offset: int,
        limit: int,
        conversation_ids: Optional[list[UUID]] = None,
        user_ids: Optional[UUID | list[UUID]] = None,
        auth_user=None,
    ) -> dict[str, list[dict] | int]:
        return await self.providers.database.conversations_handler.get_conversations_overview(
            offset=offset,
            limit=limit,
            user_ids=user_ids,
            conversation_ids=conversation_ids,
        )

    @telemetry_event("AddMessage")
    async def add_message(
        self,
        conversation_id: UUID,
        content: Message,
        parent_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
        auth_user=None,
    ) -> str:
        return await self.providers.database.conversations_handler.add_message(
            conversation_id=conversation_id,
            content=content,
            parent_id=parent_id,
            metadata=metadata,
        )

    @telemetry_event("EditMessage")
    async def edit_message(
        self,
        message_id: UUID,
        new_content: Optional[str] = None,
        additional_metadata: Optional[dict] = None,
        auth_user=None,
    ) -> dict[str, Any]:
        return (
            await self.providers.database.conversations_handler.edit_message(
                message_id=message_id,
                new_content=new_content,
                additional_metadata=additional_metadata or {},
            )
        )

    @telemetry_event("UpdateConversation")
    async def update_conversation(
        self, conversation_id: UUID, name: str
    ) -> ConversationResponse:
        return await self.providers.database.conversations_handler.update_conversation(
            conversation_id=conversation_id, name=name
        )

    @telemetry_event("DeleteConversation")
    async def delete_conversation(self, conversation_id: UUID) -> None:
        await self.providers.database.conversations_handler.delete_conversation(
            conversation_id=conversation_id
        )

    async def get_user_max_documents(self, user_id: UUID) -> int:
        return self.config.app.default_max_documents_per_user

    async def get_user_max_chunks(self, user_id: UUID) -> int:
        return self.config.app.default_max_chunks_per_user

    async def get_user_max_collections(self, user_id: UUID) -> int:
        return self.config.app.default_max_collections_per_user
