"""Defines the abstract base classes and enums for agent objects"""
import logging
import logging.config
from abc import ABC, abstractmethod
from typing import Sequence

from ..abstractions.tool import Tool
from ..providers.llm import LLMChatCompletion, LLMProvider
from ..providers.prompt import PromptProvider

logger = logging.getLogger(__name__)


class Agent(ABC):
    """
    An abstract class for implementing a agent.

    An agent is an autonomous entity that can perform actions and communicate
    with other providers.
    """

    def __init__(
        self, prompt_provider: PromptProvider, llm_provider: LLMProvider
    ) -> None:
        self.prompt_provider = prompt_provider

        self._initialized = False

    @abstractmethod
    def __iter__(self):
        pass

    @abstractmethod
    def __next__(self) -> LLMChatCompletion:
        """
        Iterates the agent by performing a single step of its task.

        A single step is a new conversation turn, which consists of generating
        a new 'asisstant' message, and parsing the reply from the 'user'.

        Raises:
            AgentStopIterationError: If the agent has already completed its task
            or exceeded the maximum number of iterations.
        """
        pass

    @property
    @abstractmethod
    def tools(self) -> Sequence[Tool]:
        """An abstract property for getting the tools associated with the agent."""
        pass

    @abstractmethod
    def run(self, message: str) -> str:
        """
        Runs the agent until it completes its task.

        The task is complete when next returns None.
        """
        pass

    @abstractmethod
    def run_stream(self, message: str) -> str:
        """
        Runs the agent until it completes its task. Stream the result when it is ready.
        """
        pass

    @abstractmethod
    def _setup(self) -> None:
        """An abstract method for setting up the agent before running."""
        pass
