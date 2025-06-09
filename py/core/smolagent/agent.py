import logging
from typing import Any

from smolagents import CodeAgent

from core import R2RRAGAgent
from core.base import Message
from core.smolagent.llm_provider.hf_llm_provider import (
    fetch_hf_inference_from_model,
)

logger = logging.getLogger(__name__)


def smol_to_r2r_messages(smol_run_result: Any) -> list[Message]:
    """
    Convert smolagents RunResult.messages (list of dicts) to list of R2R Message objects.
    """
    logger.debug(
        f"Converting smol run result to R2R messages: {smol_run_result}"
    )
    r2r_messages = []
    if hasattr(smol_run_result, "messages"):
        for msg in smol_run_result.messages:
            # Defensive: Only use fields that Message accepts
            role = msg.get("role", "assistant")
            content = msg.get("content", "")
            # Optionally pass other fields if R2R Message supports them
            r2r_messages.append(Message(role=role, content=content))
    else:
        r2r_messages = [
            Message(role="assistant", content=str(smol_run_result))
        ]
    logger.debug(f"R2R messages: {r2r_messages}")
    return r2r_messages


class R2RSmolRAGAgent(R2RRAGAgent):
    def __init__(
        self,
        database_provider,
        llm_provider,
        config,
        search_settings,
        rag_generation_config,
        knowledge_search_method,
        content_method,
        file_search_method,
        tool_registry=None,
        max_tool_context_length=20000,
        **kwargs,
    ):
        # Prefix all tool names in rag_tools with 'smol_'
        if hasattr(config, "rag_tools") and config.rag_tools:
            config.rag_tools = [
                f"smol_{name}" if not name.startswith("smol_") else name
                for name in config.rag_tools
            ]
            logger.debug(f"Smol RAG tools: {config.rag_tools}")
        super().__init__(
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
            tool_registry=tool_registry,
            max_tool_context_length=max_tool_context_length,
            **kwargs,
        )

        # register tools method called in super init will fill _tools with the tools from the registry
        self._smol_tools = [
            tool._smol_tool
            for tool in getattr(self, "_tools", [])
            if hasattr(tool, "_smol_tool")
        ]
        logger.debug(f"Smol tools: {self._smol_tools}")

        # logger.debug(f"Config: {config}")
        # logger.debug(f"Fetching HF model: {rag_generation_config}")
        self._hf_model = fetch_hf_inference_from_model(
            rag_generation_config.model
        )
        self.hf_agent = CodeAgent(
            tools=self._smol_tools,
            model=self._hf_model,
            use_structured_outputs_internally=True,
            add_base_tools=False,
        )
        self.update_system_prompt()

    def run(self, messages: list[Message], **kwargs):
        # logger.debug(f"Running smol agent with messages: {messages}")
        message = messages[0].content
        # logger.debug(f"Message: {message}")
        return self.hf_agent.run(message)

    async def arun(self, messages: list[Message], **kwargs):
        logger.debug(f"Running smol agent with messages: {messages}")
        message = messages[0].content
        logger.debug(f"Message: {message}")
        # Non stream version
        result = self.hf_agent.run(message)
        return smol_to_r2r_messages(result)

    def update_system_prompt(self):
        if hasattr(self, "hf_agent"):
            # logger.debug(f"Old system prompt: {self.hf_agent.system_prompt}")
            custom_system_prompt_addition = (
                "\n\nWhen asked a question, YOU SHOULD ALWAYS USE YOUR SEARCH TOOL TO ATTEMPT TO SEARCH FOR RELEVANT INFORMATION THAT ANSWERS THE USER QUESTION BUT"
                " if you have access to tools that help you set some filters, like smol_smart_filter_tool, to narrow down and speed up the search, use them BEFORE the search"
            )
            self.hf_agent.system_prompt += custom_system_prompt_addition
            # logger.debug(f"Updated system prompt: {self.hf_agent.system_prompt}")
