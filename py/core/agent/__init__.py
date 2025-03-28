# FIXME: Once the agent is properly type annotated, remove the type: ignore comments
from .base import (  # type: ignore
    R2RAgent,
    R2RStreamingAgent,
    R2RXMLStreamingAgent,
)
from .rag import (  # type: ignore
    R2RRAGAgent,
    R2RStreamingRAGAgent,
    R2RXMLToolsRAGAgent,
    R2RXMLToolsStreamingRAGAgent,
)

# Import the concrete implementations
from .research import (
    R2RResearchAgent,
    R2RStreamingResearchAgent,
    R2RXMLToolsResearchAgent,
    R2RXMLToolsStreamingResearchAgent,
)

__all__ = [
    # Base
    "R2RAgent",
    "R2RStreamingAgent",
    "R2RXMLStreamingAgent",
    # RAG Agents
    "R2RRAGAgent",
    "R2RXMLToolsRAGAgent",
    "R2RStreamingRAGAgent",
    "R2RXMLToolsStreamingRAGAgent",
    "R2RResearchAgent",
    "R2RStreamingResearchAgent",
    "R2RXMLToolsResearchAgent",
    "R2RXMLToolsStreamingResearchAgent",
]
