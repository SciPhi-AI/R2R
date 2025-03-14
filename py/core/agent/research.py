import logging
import os
import subprocess
import sys
import tempfile
from copy import copy
from typing import Any, Callable, Optional

from core.base import AppConfig
from core.base.abstractions import GenerationConfig, Message, SearchSettings
from core.base.agent import Tool
from core.base.providers import DatabaseProvider
from core.providers import (
    AnthropicCompletionProvider,
    LiteLLMCompletionProvider,
    OpenAICompletionProvider,
    R2RCompletionProvider,
)
from core.utils import extract_citations

from ..base.agent.agent import RAGAgentConfig  # type: ignore

# Import the RAG agents we'll leverage
from .rag import (  # type: ignore
    R2RRAGAgent,
    R2RStreamingRAGAgent,
    R2RXMLToolsRAGAgent,
    R2RXMLToolsStreamingRAGAgent,
    RAGAgentMixin,
)

logger = logging.getLogger(__name__)


class ResearchAgentMixin(RAGAgentMixin):
    """
    A mixin that extends RAGAgentMixin to add research capabilities to any R2R agent.

    This mixin provides all RAG capabilities plus additional research tools:
    - A RAG tool for knowledge retrieval (which leverages the underlying RAG capabilities)
    - A Python execution tool for code execution and computation
    - A reasoning tool for complex problem solving
    - A critique tool for analyzing conversation history
    """

    def __init__(
        self,
        *args,
        app_config: AppConfig,
        search_settings: SearchSettings,
        knowledge_search_method: Callable,
        content_method: Callable,
        file_search_method: Callable,
        max_tool_context_length=10_000,
        **kwargs,
    ):
        # Store the app configuration needed for research tools
        self.app_config = app_config

        # Call the parent RAGAgentMixin's __init__ with explicitly passed parameters
        super().__init__(
            *args,
            search_settings=search_settings,
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
            max_tool_context_length=max_tool_context_length,
            **kwargs,
        )

        # Register our research-specific tools
        self._register_research_tools()

    def _register_research_tools(self):
        """
        Register research-specific tools to the agent.
        This is called by the mixin's __init__ after the parent class initialization.
        """
        # Add our research tools to whatever tools are already registered
        research_tools = []
        for tool_name in set(self.config.research_tools):
            if tool_name == "rag":
                research_tools.append(self.rag_tool())
            elif tool_name == "reasoning":
                research_tools.append(self.reasoning_tool())
            elif tool_name == "critique":
                research_tools.append(self.critique_tool())
            elif tool_name == "python_executor":
                research_tools.append(self.python_execution_tool())
            else:
                logger.warning(f"Unknown research tool: {tool_name}")
                raise ValueError(f"Unknown research tool: {tool_name}")

        logger.debug(f"Registered research tools: {research_tools}")
        self.tools = research_tools

    def rag_tool(self) -> Tool:
        """Tool that provides access to the RAG agent's search capabilities."""
        return Tool(
            name="rag",
            description=(
                "Search for information using RAG (Retrieval-Augmented Generation). "
                "This tool searches across relevant sources and returns comprehensive information. "
                "Use this tool when you need to find specific information on any topic. Be sure to pose your query as a comprehensive query."
            ),
            results_function=self._rag,
            llm_format_function=self._format_search_results,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find information.",
                    }
                },
                "required": ["query"],
            },
        )

    def reasoning_tool(self) -> Tool:
        """Tool that provides access to a strong reasoning model."""
        return Tool(
            name="reasoning",
            description=(
                "A dedicated reasoning system that excels at solving complex problems through step-by-step analysis. "
                "This tool connects to a separate AI system optimized for deep analytical thinking.\n\n"
                "USAGE GUIDELINES:\n"
                "1. Formulate your request as a complete, standalone question to a reasoning expert.\n"
                "2. Clearly state the problem/question at the beginning.\n"
                "3. Provide all relevant context, data, and constraints.\n\n"
                "IMPORTANT: This system has no memory of previous interactions or context from your conversation.\n\n"
                "STRENGTHS: Mathematical reasoning, logical analysis, evaluating complex scenarios, "
                "solving multi-step problems, and identifying potential errors in reasoning."
            ),
            results_function=self._reason,
            llm_format_function=self._format_search_results,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A complete, standalone question with all necessary context, appropriate for a dedicated reasoning system.",
                    }
                },
                "required": ["query"],
            },
        )

    def critique_tool(self) -> Tool:
        """Tool that provides critical analysis of the reasoning done so far in the conversation."""
        return Tool(
            name="critique",
            description=(
                "Analyzes the conversation history to identify potential flaws, biases, and alternative "
                "approaches to the reasoning presented so far.\n\n"
                "Use this tool to get a second opinion on your reasoning, find overlooked considerations, "
                "identify biases or fallacies, explore alternative hypotheses, and improve the robustness "
                "of your conclusions."
            ),
            results_function=self._critique,
            llm_format_function=self._format_search_results,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A specific aspect of the reasoning you want critiqued, or leave empty for a general critique.",
                    },
                    "focus_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional specific areas to focus the critique (e.g., ['logical fallacies', 'methodology'])",
                    },
                },
                "required": ["query"],
            },
        )

    def python_execution_tool(self) -> Tool:
        """Tool that provides Python code execution capabilities."""
        return Tool(
            name="python_executor",
            description=(
                "Executes Python code and returns the results, output, and any errors. "
                "Use this tool for complex calculations, statistical operations, or algorithmic implementations.\n\n"
                "The execution environment includes common libraries such as numpy, pandas, sympy, scipy, statsmodels, biopython, etc.\n\n"
                "USAGE:\n"
                "1. Send complete, executable Python code as a string.\n"
                "2. Use print statements for output you want to see.\n"
                "3. Assign to the 'result' variable for values you want to return.\n"
                "4. Do not use input() or plotting (matplotlib). Output is text-based."
            ),
            results_function=self._execute_python_with_process_timeout,
            llm_format_function=self._format_python_results,
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute.",
                    }
                },
                "required": ["code"],
            },
        )

    async def _rag(
        self,
        query: str,
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        """Execute a search using an internal RAG agent."""
        # Create a copy of the current configuration for the RAG agent
        config_copy = copy(self.config)
        config_copy.max_iterations = 10  # Could be configurable
        config_copy.rag_tools = [
            "web_search",
            "web_scrape",
        ]  # HACK HACK TODO - Fix.

        # Create a generation config for the RAG agent
        generation_config = GenerationConfig(
            model=self.app_config.quality_llm,
            max_tokens_to_sample=16000,
        )

        # Create a new RAG agent - we'll use the non-streaming variant for consistent results
        rag_agent = R2RRAGAgent(
            database_provider=self.database_provider,
            llm_provider=self.llm_provider,
            config=config_copy,
            search_settings=self.search_settings,
            rag_generation_config=generation_config,
            knowledge_search_method=self.knowledge_search_method,
            content_method=self.content_method,
            file_search_method=self.file_search_method,
            max_tool_context_length=self.max_tool_context_length,
        )

        # Run the RAG agent with the query
        user_message = Message(role="user", content=query)
        response = await rag_agent.arun(messages=[user_message])

        # Get the content from the response
        structured_content = response[-1].get("structured_content")
        if structured_content:
            possible_text = structured_content[-1].get("text")
            content = response[-1].get("content") or possible_text
        else:
            content = response[-1].get("content")

        # Extract citations and transfer search results from RAG agent to research agent
        short_ids = extract_citations(content)
        if short_ids:
            logger.info(f"Found citations in RAG response: {short_ids}")

            for short_id in short_ids:
                result = rag_agent.search_results_collector.find_by_short_id(
                    short_id
                )
                if result:
                    self.search_results_collector.add_result(result)

            # Log confirmation for successful transfer
            logger.info(
                "Transferred search results from RAG agent to research agent for citations"
            )
        return content

    async def _reason(
        self,
        query: str,
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        """Execute a reasoning query using a specialized reasoning LLM."""
        msg_list = await self.conversation.get_messages()

        # Create a specialized generation config for reasoning
        gen_cfg = self.get_generation_config(msg_list[-1], stream=False)
        gen_cfg.model = self.app_config.reasoning_llm
        gen_cfg.top_p = None
        gen_cfg.temperature = 0.1
        gen_cfg.max_tokens_to_sample = 64000
        gen_cfg.stream = False
        gen_cfg.tools = None
        gen_cfg.functions = None
        gen_cfg.reasoning_effort = "high"
        gen_cfg.add_generation_kwargs = None

        # Call the LLM with the reasoning request
        response = await self.llm_provider.aget_completion(
            [{"role": "user", "content": query}], gen_cfg
        )
        return response.choices[0].message.content

    async def _critique(
        self,
        query: str,
        focus_areas: Optional[list] = None,
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        """Critique the conversation history."""
        msg_list = await self.conversation.get_messages()
        if not focus_areas:
            focus_areas = []
        # Build the critique prompt
        critique_prompt = (
            "You are a critical reasoning expert. Your task is to analyze the following conversation "
            "and critique the reasoning. Look for:\n"
            "1. Logical fallacies or inconsistencies\n"
            "2. Cognitive biases\n"
            "3. Overlooked questions or considerations\n"
            "4. Alternative approaches\n"
            "5. Improvements in rigor\n\n"
        )

        if focus_areas:
            critique_prompt += f"Focus areas: {', '.join(focus_areas)}\n\n"

        if query.strip():
            critique_prompt += f"Specific question: {query}\n\n"

        critique_prompt += (
            "Structure your critique:\n"
            "1. Summary\n"
            "2. Key strengths\n"
            "3. Potential issues\n"
            "4. Alternatives\n"
            "5. Recommendations\n\n"
        )

        # Add the conversation history to the prompt
        conversation_text = "\n--- CONVERSATION HISTORY ---\n\n"
        for msg in msg_list:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if content and role in ["user", "assistant", "system"]:
                conversation_text += f"{role.upper()}: {content}\n\n"

        final_prompt = critique_prompt + conversation_text

        # Use the reasoning tool to process the critique
        return await self._reason(final_prompt, *args, **kwargs)

    async def _execute_python_with_process_timeout(
        self, code: str, timeout: int = 10, *args, **kwargs
    ) -> dict[str, Any]:
        """
        Executes Python code in a separate subprocess with a timeout.
        This provides isolation and prevents re-importing the current agent module.

        Parameters:
          code (str): Python code to execute.
          timeout (int): Timeout in seconds (default: 10).

        Returns:
          dict[str, Any]: Dictionary containing stdout, stderr, return code, etc.
        """
        # Write user code to a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as tmp_file:
            tmp_file.write(code)
            script_path = tmp_file.name

        try:
            # Run the script in a fresh subprocess
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            return {
                "result": None,  # We'll parse from stdout if needed
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": (
                    None
                    if result.returncode == 0
                    else {
                        "type": "SubprocessError",
                        "message": f"Process exited with code {result.returncode}",
                        "traceback": "",
                    }
                ),
                "locals": {},  # No direct local var capture in a separate process
                "success": (result.returncode == 0),
                "timed_out": False,
                "timeout": timeout,
            }
        except subprocess.TimeoutExpired as e:
            return {
                "result": None,
                "stdout": e.output or "",
                "stderr": e.stderr or "",
                "error": {
                    "type": "TimeoutError",
                    "message": f"Execution exceeded {timeout} second limit.",
                    "traceback": "",
                },
                "locals": {},
                "success": False,
                "timed_out": True,
                "timeout": timeout,
            }
        finally:
            # Clean up the temp file
            if os.path.exists(script_path):
                os.remove(script_path)

    def _format_python_results(self, results: dict[str, Any]) -> str:
        """Format Python execution results for display."""
        output = []

        # Timeout notification
        if results.get("timed_out", False):
            output.append(
                f"⚠️ **Execution Timeout**: Code exceeded the {results.get('timeout', 10)} second limit."
            )
            output.append("")

        # Stdout
        if results.get("stdout"):
            output.append("## Output:")
            output.append("```")
            output.append(results["stdout"].rstrip())
            output.append("```")
            output.append("")

        # If there's a 'result' variable to display
        if results.get("result") is not None:
            output.append("## Result:")
            output.append("```")
            output.append(str(results["result"]))
            output.append("```")
            output.append("")

        # Error info
        if not results.get("success", True):
            output.append("## Error:")
            output.append("```")
            stderr_out = results.get("stderr", "").rstrip()
            if stderr_out:
                output.append(stderr_out)

            err_obj = results.get("error")
            if err_obj and err_obj.get("message"):
                output.append(err_obj["message"])
            output.append("```")

        # Return formatted output
        return (
            "\n".join(output)
            if output
            else "Code executed with no output or result."
        )

    def _format_search_results(self, results) -> str:
        """Simple pass-through formatting for RAG search results."""
        return results


class R2RResearchAgent(ResearchAgentMixin, R2RRAGAgent):
    """
    A non-streaming research agent that uses the standard R2R agent as its base.

    This agent combines research capabilities with the non-streaming RAG agent,
    providing tools for deep research through tool-based interaction.
    """

    def __init__(
        self,
        app_config: AppConfig,
        database_provider: DatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
        config: RAGAgentConfig,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        knowledge_search_method: Callable,
        content_method: Callable,
        file_search_method: Callable,
        max_tool_context_length: int = 20_000,
    ):
        # Set a higher max iterations for research tasks
        config.max_iterations = config.max_iterations or 15

        # Initialize the RAG agent first
        R2RRAGAgent.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
            max_tool_context_length=max_tool_context_length,
        )

        # Then initialize the ResearchAgentMixin
        ResearchAgentMixin.__init__(
            self,
            app_config=app_config,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            max_tool_context_length=max_tool_context_length,
            knowledge_search_method=knowledge_search_method,
            file_search_method=file_search_method,
            content_method=content_method,
        )


class R2RStreamingResearchAgent(ResearchAgentMixin, R2RStreamingRAGAgent):
    """
    A streaming research agent that uses the streaming RAG agent as its base.

    This agent combines research capabilities with streaming text generation,
    providing real-time responses while still offering research tools.
    """

    def __init__(
        self,
        app_config: AppConfig,
        database_provider: DatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
        config: RAGAgentConfig,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        knowledge_search_method: Callable,
        content_method: Callable,
        file_search_method: Callable,
        max_tool_context_length: int = 10_000,
    ):
        # Force streaming on
        config.stream = True
        config.max_iterations = config.max_iterations or 15

        # Initialize the streaming RAG agent first
        R2RStreamingRAGAgent.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
            max_tool_context_length=max_tool_context_length,
        )

        # Then initialize the ResearchAgentMixin
        ResearchAgentMixin.__init__(
            self,
            app_config=app_config,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            max_tool_context_length=max_tool_context_length,
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
        )


class R2RXMLToolsResearchAgent(ResearchAgentMixin, R2RXMLToolsRAGAgent):
    """
    A non-streaming research agent that uses XML tool formatting.

    This agent combines research capabilities with the XML-based tool calling format,
    which might be more appropriate for certain LLM providers.
    """

    def __init__(
        self,
        app_config: AppConfig,
        database_provider: DatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
        config: RAGAgentConfig,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        knowledge_search_method: Callable,
        content_method: Callable,
        file_search_method: Callable,
        max_tool_context_length: int = 20_000,
    ):
        # Set higher max iterations
        config.max_iterations = config.max_iterations or 15

        # Initialize the XML Tools RAG agent first
        R2RXMLToolsRAGAgent.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
            max_tool_context_length=max_tool_context_length,
        )

        # Then initialize the ResearchAgentMixin
        ResearchAgentMixin.__init__(
            self,
            app_config=app_config,
            search_settings=search_settings,
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
            max_tool_context_length=max_tool_context_length,
        )


class R2RXMLToolsStreamingResearchAgent(
    ResearchAgentMixin, R2RXMLToolsStreamingRAGAgent
):
    """
    A streaming research agent that uses XML tool formatting.

    This agent combines research capabilities with streaming and XML-based tool calling,
    providing real-time responses in a format suitable for certain LLM providers.
    """

    def __init__(
        self,
        app_config: AppConfig,
        database_provider: DatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
        config: RAGAgentConfig,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        knowledge_search_method: Callable,
        content_method: Callable,
        file_search_method: Callable,
        max_tool_context_length: int = 10_000,
    ):
        # Force streaming on
        config.stream = True
        config.max_iterations = config.max_iterations or 15

        # Initialize the XML Tools Streaming RAG agent first
        R2RXMLToolsStreamingRAGAgent.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
            max_tool_context_length=max_tool_context_length,
        )

        # Then initialize the ResearchAgentMixin
        ResearchAgentMixin.__init__(
            self,
            app_config=app_config,
            search_settings=search_settings,
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
            max_tool_context_length=max_tool_context_length,
        )
