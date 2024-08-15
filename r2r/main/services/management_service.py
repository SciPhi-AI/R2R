import json
import logging
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from r2r.base import (
    AnalysisTypes,
    LogFilterCriteria,
    LogProcessor,
    R2RException,
    RunLoggingSingleton,
    RunManager,
    VectorDBFilterValue,
)
from r2r.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RAgents, R2RPipelines, R2RProviders
from ..assembly.config import R2RConfig
from .base import Service

logger = logging.getLogger(__name__)


class ManagementService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
        agents: R2RAgents,
        run_manager: RunManager,
        logging_connection: RunLoggingSingleton,
    ):
        super().__init__(
            config,
            providers,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )

    @telemetry_event("UpdatePrompt")
    async def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = {},
        *args,
        **kwargs,
    ):
        self.providers.prompt.update_prompt(name, template, input_types)
        return f"Prompt '{name}' added successfully."

    @telemetry_event("Logs")
    async def alogs(
        self, run_type_filter: Optional[str] = None, max_runs: int = 100
    ):
        if self.logging_connection is None:
            raise R2RException(
                status_code=404, message="Logging provider not found."
            )

        run_info = await self.logging_connection.get_info_logs(
            limit=max_runs,
            run_type_filter=run_type_filter,
        )
        run_ids = [run.run_id for run in run_info]
        if len(run_ids) == 0:
            return []
        logs = await self.logging_connection.get_logs(run_ids)

        aggregated_logs = []
        warning_shown = False

        for run in run_info:
            run_logs = [
                log for log in logs if log["run_id"] == str(run.run_id)
            ]
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
                "run_id": run.run_id,
                "run_type": run.run_type,
                "entries": entries,
            }

            if run.timestamp:
                log_entry["timestamp"] = run.timestamp.isoformat()

            if hasattr(run, "user_id"):
                if run.user_id is not None:
                    log_entry["user_id"] = run.user_id
            elif not warning_shown:
                logger.warning(
                    "Logs are missing user ids. This may be due to an outdated database schema. Please run `r2r migrate` to run database migrations."
                )
                warning_shown = True

            aggregated_logs.append(log_entry)

        return aggregated_logs

    @telemetry_event("Analytics")
    async def aanalytics(
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

        log_processor = LogProcessor(filters)
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
        results = {"filtered_logs": filtered_logs}

        if analysis_types and analysis_types.analysis_types:
            for (
                filter_key,
                analysis_config,
            ) in analysis_types.analysis_types.items():
                if filter_key in filtered_logs:
                    analysis_type = analysis_config[0]
                    if analysis_type == "bar_chart":
                        extract_key = analysis_config[1]
                        results[filter_key] = (
                            AnalysisTypes.generate_bar_chart_data(
                                filtered_logs[filter_key], extract_key
                            )
                        )
                    elif analysis_type == "basic_statistics":
                        extract_key = analysis_config[1]
                        results[filter_key] = (
                            AnalysisTypes.calculate_basic_statistics(
                                filtered_logs[filter_key], extract_key
                            )
                        )
                    elif analysis_type == "percentile":
                        extract_key = analysis_config[1]
                        percentile = int(analysis_config[2])
                        results[filter_key] = (
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

        return results

    @telemetry_event("AppSettings")
    async def aapp_settings(self, *args: Any, **kwargs: Any):
        prompts = self.providers.prompt.get_all_prompts()
        return {
            "config": self.config.to_toml(),
            "prompts": {
                name: prompt.dict() for name, prompt in prompts.items()
            },
        }

    @telemetry_event("ScoreCompletion")
    async def ascore_completion(
        self,
        message_id: uuid.UUID,
        score: float = 0.0,
        run_type_filter: str = None,
        max_runs: int = 100,
        *args: Any,
        **kwargs: Any,
    ):
        try:
            if self.logging_connection is None:
                raise R2RException(
                    status_code=404, message="Logging provider not found."
                )

            run_info = await self.logging_connection.get_info_logs(
                limit=max_runs,
                run_type_filter=run_type_filter,
            )
            run_ids = [run.run_id for run in run_info]

            logs = await self.logging_connection.get_logs(run_ids)

            for log in logs:
                if log["key"] != "completion_record":
                    continue
                completion_record = log["value"]
                try:
                    completion_dict = json.loads(completion_record)
                except json.JSONDecodeError as e:
                    logger.error(f"Error processing completion record: {e}")
                    continue

                if completion_dict.get("message_id") == str(message_id):
                    bounded_score = round(min(max(score, -1.00), 1.00), 2)
                    updated = await RunLoggingSingleton.score_completion(
                        log["run_id"], message_id, bounded_score
                    )
                    if not updated:
                        logger.error(
                            f"Error updating completion record for message_id: {message_id}"
                        )

        except Exception as e:
            logger.error(f"An error occurred in ascore_completion: {e}")

        return "ok"

    @telemetry_event("UsersOverview")
    async def ausers_overview(
        self,
        user_ids: Optional[list[uuid.UUID]] = None,
        *args,
        **kwargs,
    ):
        return self.providers.database.relational.get_users_overview(
            [str(ele) for ele in user_ids] if user_ids else None
        )

    @telemetry_event("Delete")
    async def delete(
        self,
        filters: dict[str, VectorDBFilterValue],
        *args,
        **kwargs,
    ):
        """
        Takes a list of filters like
        "{key: {operator: value}, key: {operator: value}, ...}"
        and deletes entries that match the filters.

        Then, deletes the corresponding entries from the documents overview table.

        NOTE: This method is not atomic and may result in orphaned entries in the documents overview table.
        NOTE: This method assumes that filters delete entire contents of any touched documents.
        """
        logger.info(f"Deleting entries with filters: {filters}")
        results = self.providers.database.vector.delete(filters)
        if not results:
            raise R2RException(
                status_code=404, message="No entries found for deletion."
            )

        document_ids_to_purge = {
            doc_id
            for doc_id in [
                result.get("document_id", None) for result in results.values()
            ]
            if doc_id
        }
        for document_id in document_ids_to_purge:
            self.providers.database.relational.delete_from_documents_overview(
                document_id
            )
        return results

    @telemetry_event("DocumentsOverview")
    async def adocuments_overview(
        self,
        user_ids: Optional[list[uuid.UUID]] = None,
        group_ids: Optional[list[uuid.UUID]] = None,
        document_ids: Optional[list[uuid.UUID]] = None,
        *args: Any,
        **kwargs: Any,
    ):
        return self.providers.database.relational.get_documents_overview(
            filter_document_ids=document_ids,
            filter_user_ids=user_ids,
            filter_group_ids=group_ids,
        )

    @telemetry_event("DocumentChunks")
    async def document_chunks(
        self,
        document_id: uuid.UUID,
        *args,
        **kwargs,
    ):
        return self.providers.database.vector.get_document_chunks(document_id)

    @telemetry_event("UsersOverview")
    async def users_overview(
        self,
        user_ids: Optional[list[uuid.UUID]],
        *args,
        **kwargs,
    ):
        return self.providers.database.relational.get_users_overview(
            [str(ele) for ele in user_ids]
        )

    @telemetry_event("InspectKnowledgeGraph")
    async def inspect_knowledge_graph(
        self, limit=10000, *args: Any, **kwargs: Any
    ):
        if self.providers.kg is None:
            raise R2RException(
                status_code=404, message="Knowledge Graph provider not found."
            )

        rel_query = f"""
        MATCH (n1)-[r]->(n2)
        RETURN n1.id AS subject, type(r) AS relation, n2.id AS object
        LIMIT {limit}
        """

        try:
            with self.providers.kg.client.session(
                database=self.providers.kg._database
            ) as session:
                results = session.run(rel_query)
                relationships = [
                    (record["subject"], record["relation"], record["object"])
                    for record in results
                ]

            # Create graph representation and group relationships
            graph, grouped_relationships = self.process_relationships(
                relationships
            )

            # Generate output
            output = self.generate_output(grouped_relationships, graph)

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Error printing relationships: {str(e)}")
            raise R2RException(
                status_code=500,
                message=f"An error occurred while fetching relationships: {str(e)}",
            )

    @telemetry_event("AssignDocumentToGroup")
    async def aassign_document_to_group(
        self, document_id: str, group_id: uuid.UUID
    ):

        success = self.providers.database.vector.assign_document_to_group(
            document_id, group_id
        )
        if success:
            return {"message": "Document assigned to group successfully"}
        else:
            raise R2RException(
                status_code=404,
                message="Document not found or assignment failed",
            )

    @telemetry_event("RemoveDocumentFromGroup")
    async def aremove_document_from_group(
        self, document_id: str, group_id: uuid.UUID
    ):
        success = self.providers.database.vector.remove_document_from_group(
            document_id, group_id
        )
        if success:
            return {"message": "Document removed from group successfully"}
        else:
            raise R2RException(
                status_code=404, message="Document not found or removal failed"
            )

    @telemetry_event("GetDocumentGroups")
    async def aget_document_groups(self, document_id: str):
        group_ids = self.providers.database.vector.get_document_groups(
            document_id
        )
        return {"group_ids": [str(group_id) for group_id in group_ids]}

    def process_relationships(
        self, relationships: List[Tuple[str, str, str]]
    ) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, List[str]]]]:
        graph = defaultdict(list)
        grouped = defaultdict(lambda: defaultdict(list))
        for subject, relation, obj in relationships:
            graph[subject].append(obj)
            grouped[subject][relation].append(obj)
            if obj not in graph:
                graph[obj] = []
        return dict(graph), dict(grouped)

    def generate_output(
        self,
        grouped_relationships: Dict[str, Dict[str, List[str]]],
        graph: Dict[str, List[str]],
    ) -> List[str]:
        output = []

        # Print grouped relationships
        for subject, relations in grouped_relationships.items():
            output.append(f"\n== {subject} ==")
            for relation, objects in relations.items():
                output.append(f"  {relation}:")
                for obj in objects:
                    output.append(f"    - {obj}")

        # Print basic graph statistics
        output.append("\n== Graph Statistics ==")
        output.append(f"Number of nodes: {len(graph)}")
        output.append(
            f"Number of edges: {sum(len(neighbors) for neighbors in graph.values())}"
        )
        output.append(
            f"Number of connected components: {self.count_connected_components(graph)}"
        )

        # Find central nodes
        central_nodes = self.get_central_nodes(graph)
        output.append("\n== Most Central Nodes ==")
        for node, centrality in central_nodes:
            output.append(f"  {node}: {centrality:.4f}")

        return output

    def count_connected_components(self, graph: Dict[str, List[str]]) -> int:
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

    def get_central_nodes(
        self, graph: Dict[str, List[str]]
    ) -> List[Tuple[str, float]]:
        degree = {node: len(neighbors) for node, neighbors in graph.items()}
        total_nodes = len(graph)
        centrality = {
            node: deg / (total_nodes - 1) for node, deg in degree.items()
        }
        return sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]

    @telemetry_event("AppSettings")
    async def app_settings(
        self,
        *args,
        **kwargs,
    ):
        prompts = self.providers.prompt.get_all_prompts()
        return {
            "config": self.config.to_json(),
            "prompts": {
                name: prompt.dict() for name, prompt in prompts.items()
            },
        }

    @telemetry_event("CreateGroup")
    async def acreate_group(
        self, name: str, description: str = ""
    ) -> uuid.UUID:
        return self.providers.database.relational.create_group(
            name, description
        )

    @telemetry_event("GetGroup")
    async def aget_group(self, group_id: uuid.UUID) -> Optional[dict]:
        return self.providers.database.relational.get_group(group_id)

    @telemetry_event("UpdateGroup")
    async def aupdate_group(
        self, group_id: uuid.UUID, name: str = None, description: str = None
    ) -> bool:
        return self.providers.database.relational.update_group(
            group_id, name, description
        )

    @telemetry_event("DeleteGroup")
    async def adelete_group(self, group_id: uuid.UUID) -> bool:
        return self.providers.database.relational.delete_group(group_id)

    @telemetry_event("ListGroups")
    async def alist_groups(
        self, offset: int = 0, limit: int = 100
    ) -> list[dict]:
        return self.providers.database.relational.list_groups(
            offset=offset, limit=limit
        )

    @telemetry_event("AddUserToGroup")
    async def aadd_user_to_group(
        self, user_id: uuid.UUID, group_id: uuid.UUID
    ) -> bool:
        return self.providers.database.relational.add_user_to_group(
            user_id, group_id
        )

    @telemetry_event("RemoveUserFromGroup")
    async def aremove_user_from_group(
        self, user_id: uuid.UUID, group_id: uuid.UUID
    ) -> bool:
        return self.providers.database.relational.remove_user_from_group(
            user_id, group_id
        )

    @telemetry_event("GetUsersInGroup")
    async def aget_users_in_group(
        self, group_id: uuid.UUID, offset: int = 0, limit: int = 100
    ) -> list[dict]:
        return self.providers.database.relational.get_users_in_group(
            group_id, offset, limit
        )

    @telemetry_event("GetGroupsForUser")
    async def aget_groups_for_user(self, user_id: uuid.UUID) -> list[dict]:
        return self.providers.database.relational.get_groups_for_user(user_id)

    @telemetry_event("GroupsOverview")
    async def agroups_overview(
        self,
        group_ids: Optional[list[uuid.UUID]] = None,
        *args,
        **kwargs,
    ):
        return self.providers.database.relational.get_groups_overview(
            [str(ele) for ele in group_ids] if group_ids else None
        )
