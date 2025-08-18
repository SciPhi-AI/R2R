import logging
from typing import Any

from pydantic_ai import Tool as PydanticTool

from shared.abstractions.tool import Tool

logger = logging.getLogger(__name__)


class SmartFilterTool(Tool):
    """
    A tool to refine metadata and collection filters for a RAG search using LLM analysis.
    This tool does NOT perform the RAG search itself, only returns the refined filters and prompt.
    """

    def __init__(self):
        super().__init__(
            name="smart_filter_tool",
            description=(
                "Analyzes the user query and available collections, then returns refined collection IDs, "
                "metadata filters, and a possibly modified prompt for downstream RAG search. "
                "Does NOT perform the search itself."
                "The tool is editing the search settings internally, so no need to use its results afterwards."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user query to analyze.",
                    },
                },
                "required": ["query"],
            },
            results_function=self.execute,
            llm_format_function=None,
        )
        pyd_params = self.parameters.copy()
        pyd_params["additionalProperties"] = False
        self._pydantic_ai_tool = PydanticTool.from_schema(
            function=self.execute,
            name=self.name,
            description=self.description,
            json_schema=pyd_params,
        )

    async def execute(self, query: str, *args, **kwargs):
        """
        Uses the LLM to analyze the query and available collections, returning collection IDs, filters, and prompt_mod.
        """
        logger.debug(f"Executing SmartFilterTool with query: {query}")

        from core.base.abstractions import (
            AggregateSearchResult,
            SmartFilterResult,
        )

        context = self.context
        if (
            not context
            or not hasattr(context, "database_provider")
            or not hasattr(context, "config")
            or not hasattr(context, "rag_generation_config")
        ):
            logger.error(
                "Context missing database_provider or config or rag_generation_config for SmartRagTool"
            )
            return {"collections": [], "filters": {}, "prompt_mod": query}

        if not hasattr(context, "search_settings"):
            logger.error("Context missing search_settings for SmartRagTool")
            return {"collections": [], "filters": {}, "prompt_mod": query}

        try:
            collections_overview = await context.database_provider.collections_handler.get_collections_overview(
                offset=0, limit=50
            )
            collections_brief = [
                {
                    "id": str(c.id),
                    "name": c.name,
                    "description": getattr(c, "description", ""),
                }
                for c in collections_overview.get("results", [])
            ]
        except Exception as e:
            logger.error(f"Error fetching collections: {e}")
            return {"collections": [], "filters": {}, "prompt_mod": query}

        collections_str = "\n".join(
            [
                f"- {c['name']} (ID: {c['id']}): {c['description']}"
                for c in collections_brief
            ]
        )
        llm_prompt = (
            f"Here are the available collections with data the user might be interested in (with IDs and descriptions):\n{collections_str}\n\n"
            f'User query: "{query}"\n\n'
            "Please return a JSON with:\n"
            "- 'collections': [list of relevant collection IDs as strings]\n"
            "- 'filters': (optional) metadata filters\n"
            "- 'prompt_mod': (optional) a modified prompt for the RAG search"
            "We will use this new params to query the database (RAG search) and filter the collections."
        )
        model = context.rag_generation_config.model
        try:
            GenerationConfig = __import__(
                "core.base.abstractions", fromlist=["GenerationConfig"]
            ).GenerationConfig
            gen_cfg = GenerationConfig(
                model=model,
                max_tokens_to_sample=1024,
                temperature=0.0,
                stream=False,
                tools=None,
                functions=None,
            )
            response = await context.llm_provider.aget_completion(
                [{"role": "user", "content": llm_prompt}], gen_cfg
            )
            llm_response = response.choices[0].message.content
            import json

            try:
                result = json.loads(llm_response)
                logger.debug(f"SmartFilter raw response:\n{result}")
                filtered_collections_ids = result.get("collections", [])
                # filters = result.get("filters", {})
                if len(filtered_collections_ids) > 0 and hasattr(
                    context, "search_settings"
                ):
                    new_filters = self.merge_filters(
                        context.search_settings.filters,
                        filtered_collections_ids,
                        collections_brief,
                    )
                    logger.debug(f"SmartFilter output Filters:\n{new_filters}")
                    context.search_settings.filters = new_filters

                smart_filter_result = SmartFilterResult(
                    collections=filtered_collections_ids,
                    filters=new_filters,
                    prompt_mod=query,
                )
                result = AggregateSearchResult(
                    smart_filter_result=smart_filter_result
                )
                return result
            except Exception:
                logger.error(f"LLM did not return valid JSON: {llm_response}")
                return {"collections": [], "filters": {}, "prompt_mod": query}
        except Exception as e:
            logger.error(f"Error in SmartRagTool LLM analysis: {e}")
            return {"collections": [], "filters": {}, "prompt_mod": query}

    def merge_filters(
        self,
        existing_filters: dict[str, Any],
        collections_ids_to_filter_on: list[str],
        collections_brief: list[dict[str, Any]],
    ):
        from uuid import UUID

        new_collection_filter = {
            "collection_ids": {
                "$in": [UUID(c) for c in collections_ids_to_filter_on]
            }
        }
        new_category_metadata_filter = {
            "metadata.category": {
                "$in": [
                    c["name"]
                    for c in collections_brief
                    if c["id"] in collections_ids_to_filter_on
                ]
            }
        }
        new_filters = [new_collection_filter, new_category_metadata_filter]
        if not existing_filters:
            return {"$and": new_filters}
        if not collections_ids_to_filter_on:
            return existing_filters
        # If existing is already an $and, append new filters
        if "$and" in existing_filters:
            # Avoid duplicating filters if already present
            combined = existing_filters["$and"] + new_filters
            return {"$and": combined}
        else:
            # Combine the single filter with the new filters
            return {"$and": [existing_filters] + new_filters}
