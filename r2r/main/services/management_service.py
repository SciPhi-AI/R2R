import logging
import uuid
from typing import Any, Optional, Union

from r2r.base import (
    AnalysisTypes,
    FilterCriteria,
    KVLoggingSingleton,
    LogProcessor,
    RunManager,
)
from r2r.main.abstractions import R2RException
from r2r.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RPipelines, R2RProviders
from ..assembly.config import R2RConfig
from .base import Service

logger = logging.getLogger(__name__)


class ManagementService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
        run_manager: RunManager,
        logging_connection: KVLoggingSingleton,
    ):
        super().__init__(
            config, providers, pipelines, run_manager, logging_connection
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
        self,
        log_type_filter: Optional[str] = None,
        max_runs_requested: int = 100,
        *args: Any,
        **kwargs: Any,
    ):
        if self.logging_connection is None:
            raise R2RException(
                status_code=404, message="Logging provider not found."
            )
        if (
            self.config.app.get("max_logs_per_request", 100)
            > max_runs_requested
        ):
            raise R2RException(
                status_code=400,
                message="Max runs requested exceeds the limit.",
            )

        run_info = await self.logging_connection.get_run_info(
            limit=max_runs_requested,
            log_type_filter=log_type_filter,
        )
        run_ids = [run.run_id for run in run_info]
        if len(run_ids) == 0:
            return []
        logs = await self.logging_connection.get_logs(run_ids)
        # Aggregate logs by run_id and include run_type
        aggregated_logs = []

        for run in run_info:
            run_logs = [log for log in logs if log["log_id"] == run.run_id]
            entries = [
                {"key": log["key"], "value": log["value"]} for log in run_logs
            ][
                ::-1
            ]  # Reverse order so that earliest logged values appear first.
            aggregated_logs.append(
                {
                    "run_id": run.run_id,
                    "run_type": run.log_type,
                    "entries": entries,
                }
            )

        return aggregated_logs

    @telemetry_event("Analytics")
    async def aanalytics(
        self,
        filter_criteria: FilterCriteria,
        analysis_types: AnalysisTypes,
        *args,
        **kwargs,
    ):
        run_info = await self.logging_connection.get_run_info(limit=100)
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
            "config": self.config.to_json(),
            "prompts": {
                name: prompt.dict() for name, prompt in prompts.items()
            },
        }

    @telemetry_event("UsersOverview")
    async def ausers_overview(
        self,
        user_ids: Optional[list[uuid.UUID]] = None,
        *args,
        **kwargs,
    ):
        return self.providers.vector_db.get_users_overview(
            [str(ele) for ele in user_ids] if user_ids else None
        )

    @telemetry_event("Delete")
    async def delete(
        self,
        keys: list[str],
        values: list[Union[bool, int, str]],
        *args,
        **kwargs,
    ):
        metadata = ", ".join(
            f"{key}={value}" for key, value in zip(keys, values)
        )
        values = [str(value) for value in values]
        logger.info(f"Deleting entries with metadata: {metadata}")
        ids = self.providers.vector_db.delete_by_metadata(keys, values)
        if not ids:
            raise R2RException(
                status_code=404, message="No entries found for deletion."
            )
        self.providers.vector_db.delete_documents_overview(ids)
        return f"Documents {ids} deleted successfully."

    @telemetry_event("DocumentsOverview")
    async def adocuments_overview(
        self,
        document_ids: Optional[list[uuid.UUID]] = None,
        user_ids: Optional[list[uuid.UUID]] = None,
        *args: Any,
        **kwargs: Any,
    ):
        return self.providers.vector_db.get_documents_overview(
            filter_document_ids=(
                [str(ele) for ele in document_ids] if document_ids else None
            ),
            filter_user_ids=(
                [str(ele) for ele in user_ids] if user_ids else None
            ),
        )

    @telemetry_event("DocumentChunks")
    async def document_chunks(
        self,
        document_id: uuid.UUID,
        *args,
        **kwargs,
    ):
        return self.providers.vector_db.get_document_chunks(str(document_id))

    @telemetry_event("UsersOverview")
    async def users_overview(
        self,
        user_ids: Optional[list[uuid.UUID]],
        *args,
        **kwargs,
    ):
        return self.providers.vector_db.get_users_overview(
            [str(ele) for ele in user_ids]
        )

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
