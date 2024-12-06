import logging
import os
from collections import defaultdict
from typing import Any, BinaryIO, Optional, Tuple
from uuid import UUID

import toml
from fastapi.responses import StreamingResponse

from core.base import (
    AnalysisTypes,
    CollectionResponse,
    DocumentResponse,
    KGEnrichmentStatus,
    LogFilterCriteria,
    LogProcessor,
    Message,
    Prompt,
    R2RException,
    RunManager,
    User,
)
from core.base.logger.base import RunType
from core.base.utils import validate_uuid
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider
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
        logging_connection: SqlitePersistentLoggingProvider,
    ):
        super().__init__(
            config,
            providers,
            pipes,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )

    @telemetry_event("Logs")
    async def logs(
        self,
        offset: int,
        limit: int,
        run_type_filter: Optional[RunType] = None,
    ):
        if self.logging_connection is None:
            raise R2RException(
                status_code=404, message="Logging provider not found."
            )

        run_info = await self.logging_connection.get_info_logs(
            offset=offset,
            limit=limit,
            run_type_filter=run_type_filter,
        )
        run_ids = [run.run_id for run in run_info]
        if not run_ids:
            return []
        logs = await self.logging_connection.get_logs(run_ids)

        aggregated_logs = []

        for run in run_info:
            run_logs = [log for log in logs if log["run_id"] == run.run_id]
            entries = [
                {
                    "key": log["key"],
                    "value": log["value"],
                    "timestamp": log["timestamp"],
                }
                for log in run_logs
            ][
                ::-1
            ]  # Reverse order so that earliest logged values appear first.

            log_entry = {
                "run_id": str(run.run_id),
                "run_type": run.run_type,
                "entries": entries,
            }

            if run.timestamp:
                log_entry["timestamp"] = run.timestamp.isoformat()

            if hasattr(run, "user_id") and run.user_id is not None:
                log_entry["user_id"] = str(run.user_id)

            aggregated_logs.append(log_entry)

        return aggregated_logs

    @telemetry_event("Analytics")
    async def analytics(
        self,
        filter_criteria: LogFilterCriteria,
        analysis_types: AnalysisTypes,
        *args,
        **kwargs,
    ):
        run_info = await self.logging_connection.get_info_logs(limit=100)
        run_ids = [info.run_id for info in run_info]

        if not run_ids:
            return {
                "analytics_data": "No logs found.",
                "filtered_logs": {},
            }
        logs = await self.logging_connection.get_logs(run_ids=run_ids)

        filters = {}
        if filter_criteria.filters:
            for key, value in filter_criteria.filters.items():
                filters[key] = lambda log, value=value: (
                    any(
                        entry.get("key") == value
                        for entry in log.get("entries", [])
                    )
                    if "entries" in log
                    else log.get("key") == value
                )

        log_processor = LogProcessor(filters)  # type: ignore
        for log in logs:
            if "entries" in log and isinstance(log["entries"], list):
                log_processor.process_log(log)
            elif "key" in log:
                log_processor.process_log(log)
            else:
                logger.warning(
                    f"Skipping log due to missing or malformed 'entries': {log}"
                )

        filtered_logs = dict(log_processor.populations.items())

        analytics_data = {}
        if analysis_types and analysis_types.analysis_types:
            for (
                filter_key,
                analysis_config,
            ) in analysis_types.analysis_types.items():
                if filter_key in filtered_logs:
                    analysis_type = analysis_config[0]
                    if analysis_type == "bar_chart":
                        extract_key = analysis_config[1]
                        analytics_data[filter_key] = (
                            AnalysisTypes.generate_bar_chart_data(
                                filtered_logs[filter_key], extract_key
                            )
                        )
                    elif analysis_type == "basic_statistics":
                        extract_key = analysis_config[1]
                        analytics_data[filter_key] = (
                            AnalysisTypes.calculate_basic_statistics(
                                filtered_logs[filter_key], extract_key
                            )
                        )
                    elif analysis_type == "percentile":
                        extract_key = analysis_config[1]
                        percentile = int(analysis_config[2])
                        analytics_data[filter_key] = (
                            AnalysisTypes.calculate_percentile(
                                filtered_logs[filter_key],
                                extract_key,
                                percentile,
                            )
                        )
                    else:
                        logger.warning(
                            f"Unknown analysis type for filter key '{filter_key}': {analysis_type}"
                        )

        return {
            "analytics_data": analytics_data or None,
            "filtered_logs": filtered_logs,
        }

    @telemetry_event("AppSettings")
    async def app_settings(self):
        prompts = await self.providers.database.get_all_prompts()
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
        return await self.providers.database.get_users_overview(
            offset=offset,
            limit=limit,
            user_ids=user_ids,
        )

    @telemetry_event("Delete")
    async def delete(
        self,
        filters: dict[str, Any],
        *args,
        **kwargs,
    ):
        """
        Takes a list of filters like
        "{key: {operator: value}, key: {operator: value}, ...}"
        and deletes entries matching the given filters from both vector and relational databases.

        NOTE: This method is not atomic and may result in orphaned entries in the documents overview table.
        NOTE: This method assumes that filters delete entire contents of any touched documents.
        """
        ### TODO - FIX THIS, ENSURE THAT DOCUMENTS OVERVIEW IS CLEARED

        def validate_filters(filters: dict[str, Any]) -> None:
            ALLOWED_FILTERS = {
                "id",
                "collection_ids",
                "chunk_id",
                # TODO - Modify these checks such that they can be used PROPERLY for nested filters
                "$and",
                "$or",
            }

            if not filters:
                raise R2RException(
                    status_code=422, message="No filters provided"
                )

            for field in filters:
                if field not in ALLOWED_FILTERS:
                    raise R2RException(
                        status_code=422,
                        message=f"Invalid filter field: {field}",
                    )

            for field in ["document_id", "owner_id", "chunk_id"]:
                if field in filters:
                    op = next(iter(filters[field].keys()))
                    try:
                        validate_uuid(filters[field][op])
                    except ValueError:
                        raise R2RException(
                            status_code=422,
                            message=f"Invalid UUID: {filters[field][op]}",
                        )

            if "collection_ids" in filters:
                op = next(iter(filters["collection_ids"].keys()))
                for id_str in filters["collection_ids"][op]:
                    try:
                        validate_uuid(id_str)
                    except ValueError:
                        raise R2RException(
                            status_code=422, message=f"Invalid UUID: {id_str}"
                        )

        validate_filters(filters)

        logger.info(f"Deleting entries with filters: {filters}")

        try:
            vector_delete_results = await self.providers.database.delete(
                filters
            )
        except Exception as e:
            logger.error(f"Error deleting from vector database: {e}")
            vector_delete_results = {}

        document_ids_to_purge: set[UUID] = set()
        if vector_delete_results:
            document_ids_to_purge.update(
                UUID(result.get("document_id"))
                for result in vector_delete_results.values()
                if result.get("document_id")
            )

        # TODO: This might be appropriate to move elsewhere and revisit filter logic in other methods
        def extract_filters(filters: dict[str, Any]) -> dict[str, list[str]]:
            relational_filters: dict = {}

            def process_filter(filter_dict: dict[str, Any]):
                if "document_id" in filter_dict:
                    relational_filters.setdefault(
                        "filter_document_ids", []
                    ).append(filter_dict["document_id"]["$eq"])
                if "owner_id" in filter_dict:
                    relational_filters.setdefault(
                        "filter_user_ids", []
                    ).append(filter_dict["owner_id"]["$eq"])
                if "collection_ids" in filter_dict:
                    relational_filters.setdefault(
                        "filter_collection_ids", []
                    ).extend(filter_dict["collection_ids"]["$in"])

            # Handle nested conditions
            if "$and" in filters:
                for condition in filters["$and"]:
                    process_filter(condition)
            elif "$or" in filters:
                for condition in filters["$or"]:
                    process_filter(condition)
            else:
                process_filter(filters)

            return relational_filters

        relational_filters = extract_filters(filters)
        if relational_filters:
            try:
                documents_overview = (
                    await self.providers.database.get_documents_overview(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
                        offset=0,
                        limit=1000,
                        **relational_filters,  # type: ignore
                    )
                )["results"]
            except Exception as e:
                logger.error(
                    f"Error fetching documents from relational database: {e}"
                )
                documents_overview = []

            if documents_overview:
                document_ids_to_purge.update(
                    doc.id for doc in documents_overview
                )

            if not document_ids_to_purge:
                raise R2RException(
                    status_code=404, message="No entries found for deletion."
                )

            for document_id in document_ids_to_purge:
                remaining_chunks = await self.providers.database.list_document_chunks(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
                    document_id=document_id,
                    offset=0,
                    limit=1000,
                )
                if remaining_chunks["total_entries"] == 0:
                    try:
                        await self.providers.database.delete_from_documents_overview(
                            document_id
                        )
                        logger.info(
                            f"Deleted document ID {document_id} from documents_overview."
                        )
                    except Exception as e:
                        logger.error(
                            f"Error deleting document ID {document_id} from documents_overview: {e}"
                        )
                await self.providers.database.graph_handler.entities.delete(
                    parent_id=document_id,
                    store_type="documents",  # type: ignore
                )
                await self.providers.database.graph_handler.relationships.delete(
                    parent_id=document_id,
                    store_type="documents",  # type: ignore
                )
                collections = (
                    await self.providers.database.get_collections_overview(
                        offset=0, limit=1000, filter_document_ids=[document_id]
                    )
                )
                # TODO - Loop over all collections
                for collection in collections["results"]:
                    await self.providers.database.set_workflow_status(
                        id=collection.id,
                        status_type="graph_sync_status",
                        status=KGEnrichmentStatus.OUTDATED,
                    )
                    await self.providers.database.set_workflow_status(
                        id=collection.id,
                        status_type="graph_cluster_status",
                        status=KGEnrichmentStatus.OUTDATED,
                    )

        return None

    @telemetry_event("DownloadFile")
    async def download_file(
        self, document_id: UUID
    ) -> Optional[Tuple[str, BinaryIO, int]]:
        if result := await self.providers.database.retrieve_file(document_id):
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
        return await self.providers.database.get_documents_overview(
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
        return await self.providers.database.list_document_chunks(
            document_id=document_id,
            offset=offset,
            limit=limit,
            include_vectors=include_vectors,
        )

    @telemetry_event("AssignDocumentToCollection")
    async def assign_document_to_collection(
        self, document_id: UUID, collection_id: UUID
    ):
        await self.providers.database.assign_document_to_collection_vector(
            document_id, collection_id
        )
        await self.providers.database.assign_document_to_collection_relational(
            document_id, collection_id
        )
        await self.providers.database.set_workflow_status(
            id=collection_id,
            status_type="graph_sync_status",
            status=KGEnrichmentStatus.OUTDATED,
        )
        await self.providers.database.set_workflow_status(
            id=collection_id,
            status_type="graph_cluster_status",
            status=KGEnrichmentStatus.OUTDATED,
        )

        return {"message": "Document assigned to collection successfully"}

    @telemetry_event("RemoveDocumentFromCollection")
    async def remove_document_from_collection(
        self, document_id: UUID, collection_id: UUID
    ):
        await self.providers.database.remove_document_from_collection_relational(
            document_id, collection_id
        )
        await self.providers.database.remove_document_from_collection_vector(
            document_id, collection_id
        )
        await self.providers.database.graph_handler.delete_node_via_document_id(
            document_id, collection_id
        )
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
        result = await self.providers.database.create_collection(
            owner_id=owner_id,
            name=name,
            description=description,
        )
        graph_result = await self.providers.database.graph_handler.create(
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
    ) -> CollectionResponse:
        return await self.providers.database.update_collection(
            collection_id=collection_id,
            name=name,
            description=description,
        )

    @telemetry_event("DeleteCollection")
    async def delete_collection(self, collection_id: UUID) -> bool:
        await self.providers.database.delete_collection_relational(
            collection_id
        )
        await self.providers.database.delete_collection_vector(collection_id)
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
        return await self.providers.database.get_collections_overview(
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
        return await self.providers.database.add_user_to_collection(
            user_id, collection_id
        )

    @telemetry_event("RemoveUserFromCollection")
    async def remove_user_from_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> bool:
        return await self.providers.database.remove_user_from_collection(
            user_id, collection_id
        )

    @telemetry_event("GetUsersInCollection")
    async def get_users_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = 100
    ) -> dict[str, list[User] | int]:
        return await self.providers.database.get_users_in_collection(
            collection_id, offset=offset, limit=limit
        )

    @telemetry_event("GetDocumentsInCollection")
    async def documents_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = 100
    ) -> dict[str, list[DocumentResponse] | int]:
        return await self.providers.database.documents_in_collection(
            collection_id, offset=offset, limit=limit
        )

    @telemetry_event("AddPrompt")
    async def add_prompt(
        self, name: str, template: str, input_types: dict[str, str]
    ) -> dict:
        try:
            await self.providers.database.add_prompt(
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
                    await self.providers.database.get_cached_prompt(
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
            return await self.providers.database.get_prompt(  # type: ignore
                prompt_name=prompt_name,
                inputs=inputs,
                prompt_override=prompt_override,
            )
        except ValueError as e:
            raise R2RException(status_code=404, message=str(e))

    @telemetry_event("GetAllPrompts")
    async def get_all_prompts(self) -> dict[str, Prompt]:
        return await self.providers.database.get_all_prompts()

    @telemetry_event("UpdatePrompt")
    async def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> dict:
        try:
            await self.providers.database.update_prompt(
                name, template, input_types
            )
            return f"Prompt '{name}' updated successfully."  # type: ignore
        except ValueError as e:
            raise R2RException(status_code=404, message=str(e))

    @telemetry_event("DeletePrompt")
    async def delete_prompt(self, name: str) -> dict:
        try:
            await self.providers.database.delete_prompt(name)
            return {"message": f"Prompt '{name}' deleted successfully."}
        except ValueError as e:
            raise R2RException(status_code=404, message=str(e))

    @telemetry_event("GetConversation")
    async def get_conversation(
        self,
        conversation_id: str,
        branch_id: Optional[str] = None,
        auth_user=None,
    ) -> Tuple[str, list[Message], list[dict]]:
        return await self.logging_connection.get_conversation(  # type: ignore
            conversation_id, branch_id
        )

    async def verify_conversation_access(
        self, conversation_id: str, user_id: UUID
    ) -> bool:
        return await self.logging_connection.verify_conversation_access(
            conversation_id, user_id
        )

    @telemetry_event("CreateConversation")
    async def create_conversation(
        self, user_id: Optional[UUID] = None, auth_user=None
    ) -> dict:
        return await self.logging_connection.create_conversation(  # type: ignore
            user_id=user_id
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
        return await self.logging_connection.get_conversations_overview(
            offset=offset,
            limit=limit,
            user_ids=user_ids,
            conversation_ids=conversation_ids,
        )

    @telemetry_event("AddMessage")
    async def add_message(
        self,
        conversation_id: str,
        content: Message,
        parent_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        auth_user=None,
    ) -> str:
        return await self.logging_connection.add_message(
            conversation_id, content, parent_id, metadata
        )

    @telemetry_event("EditMessage")
    async def edit_message(
        self, message_id: str, new_content: str, auth_user=None
    ) -> Tuple[str, str]:
        return await self.logging_connection.edit_message(
            message_id, new_content
        )

    @telemetry_event("updateMessageMetadata")
    async def update_message_metadata(
        self, message_id: str, metadata: dict, auth_user=None
    ):
        await self.logging_connection.update_message_metadata(
            message_id, metadata
        )

    @telemetry_event("exportMessagesToCSV")
    async def export_messages_to_csv(
        self, chunk_size: int = 1000, return_type: str = "stream"
    ) -> StreamingResponse | str:
        return await self.logging_connection.export_messages_to_csv(
            chunk_size, return_type
        )

    @telemetry_event("BranchesOverview")
    async def branches_overview(
        self,
        offset: int,
        limit: int,
        conversation_id: str,
        auth_user=None,
    ) -> list[dict]:
        return await self.logging_connection.get_branches(  # type: ignore
            offset=offset,
            limit=limit,
            conversation_id=conversation_id,
        )

    @telemetry_event("GetNextBranch")
    async def get_next_branch(
        self, current_branch_id: str, auth_user=None
    ) -> Optional[str]:
        return await self.logging_connection.get_next_branch(current_branch_id)

    @telemetry_event("GetPrevBranch")
    async def get_prev_branch(
        self, current_branch_id: str, auth_user=None
    ) -> Optional[str]:
        return await self.logging_connection.get_prev_branch(current_branch_id)

    @telemetry_event("BranchAtMessage")
    async def branch_at_message(self, message_id: str, auth_user=None) -> str:
        return await self.logging_connection.branch_at_message(message_id)

    @telemetry_event("DeleteConversation")
    async def delete_conversation(self, conversation_id: str, auth_user=None):
        await self.logging_connection.delete_conversation(conversation_id)
