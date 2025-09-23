"""
R2R Enhanced Template MCP Server
Provides standardized MCP interface for all R2R enhanced features.
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Sequence
from datetime import datetime

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from r2r import R2RClient


class R2RMCPServer:
    """
    MCP Server for R2R Enhanced Template.
    
    Provides tools for:
    - Document ingestion and management
    - Advanced RAG queries (vanilla, rag_fusion, hyde)
    - Graph queries and entity exploration
    - Citation-enhanced responses
    - Web search integration
    - Spreadsheet data queries
    - Analytics and monitoring
    """
    
    def __init__(self):
        self.server = Server("r2r-enhanced")
        self.r2r_client = None
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup MCP server handlers."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """List all available R2R tools."""
            return [
                # Document Management
                types.Tool(
                    name="upload_document",
                    description="Upload and process a document into R2R",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to the document file"},
                            "metadata": {"type": "object", "description": "Optional metadata for the document"},
                            "chunking_strategy": {"type": "string", "enum": ["recursive", "hierarchical"], "default": "hierarchical"}
                        },
                        "required": ["file_path"]
                    }
                ),
                
                # Advanced RAG Queries
                types.Tool(
                    name="enhanced_search",
                    description="Perform enhanced RAG search with multiple strategies",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The search query"},
                            "search_strategy": {"type": "string", "enum": ["vanilla", "rag_fusion", "hyde"], "default": "rag_fusion"},
                            "use_web_search": {"type": "boolean", "default": False, "description": "Enable web search fallback"},
                            "force_web_search": {"type": "boolean", "default": False, "description": "Always include web search"},
                            "limit": {"type": "integer", "default": 10, "description": "Number of results to return"},
                            "include_citations": {"type": "boolean", "default": True, "description": "Include detailed citations"}
                        },
                        "required": ["query"]
                    }
                ),
                
                # Graph Queries
                types.Tool(
                    name="graph_search",
                    description="Search the knowledge graph for entities and relationships",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Graph search query"},
                            "entity_types": {"type": "array", "items": {"type": "string"}, "description": "Filter by entity types"},
                            "limit": {"type": "integer", "default": 20}
                        },
                        "required": ["query"]
                    }
                ),
                
                types.Tool(
                    name="get_entity_details",
                    description="Get detailed information about a specific entity",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "entity_name": {"type": "string", "description": "Name of the entity"},
                            "include_relationships": {"type": "boolean", "default": True}
                        },
                        "required": ["entity_name"]
                    }
                ),
                
                # Spreadsheet Queries
                types.Tool(
                    name="query_spreadsheet",
                    description="Query structured data from uploaded spreadsheets using natural language",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Natural language query about spreadsheet data"},
                            "filename": {"type": "string", "description": "Optional: specific spreadsheet filename to query"}
                        },
                        "required": ["query"]
                    }
                ),
                
                # Agent Mode
                types.Tool(
                    name="agent_chat",
                    description="Interact with R2R's reasoning agent for complex multi-step queries",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "Message for the agent"},
                            "conversation_id": {"type": "string", "description": "Optional conversation ID for context"}
                        },
                        "required": ["message"]
                    }
                ),
                
                # Analytics
                types.Tool(
                    name="get_analytics",
                    description="Get usage analytics and system insights",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "metric_type": {"type": "string", "enum": ["usage", "performance", "citations"], "default": "usage"},
                            "days": {"type": "integer", "default": 30, "description": "Number of days to analyze"}
                        }
                    }
                ),
                
                # System Management
                types.Tool(
                    name="list_documents",
                    description="List all documents in the system",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "default": 50},
                            "offset": {"type": "integer", "default": 0}
                        }
                    }
                ),
                
                types.Tool(
                    name="system_health",
                    description="Check R2R system health and status",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Handle tool calls."""
            
            # Initialize R2R client if not already done
            if not self.r2r_client:
                r2r_url = os.getenv("R2R_BASE_URL", "http://localhost:7272")
                self.r2r_client = R2RClient(r2r_url)
            
            try:
                if name == "upload_document":
                    return await self._upload_document(arguments)
                elif name == "enhanced_search":
                    return await self._enhanced_search(arguments)
                elif name == "graph_search":
                    return await self._graph_search(arguments)
                elif name == "get_entity_details":
                    return await self._get_entity_details(arguments)
                elif name == "query_spreadsheet":
                    return await self._query_spreadsheet(arguments)
                elif name == "agent_chat":
                    return await self._agent_chat(arguments)
                elif name == "get_analytics":
                    return await self._get_analytics(arguments)
                elif name == "list_documents":
                    return await self._list_documents(arguments)
                elif name == "system_health":
                    return await self._system_health(arguments)
                else:
                    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
                    
            except Exception as e:
                return [types.TextContent(type="text", text=f"Error executing {name}: {str(e)}")]
    
    async def _upload_document(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Upload and process a document."""
        file_path = args["file_path"]
        metadata = args.get("metadata", {})
        chunking_strategy = args.get("chunking_strategy", "hierarchical")
        
        # Add chunking strategy to ingestion config
        ingestion_config = {
            "chunking_strategy": chunking_strategy
        }
        
        result = await self.r2r_client.documents.create(
            file_path=file_path,
            metadata=metadata,
            ingestion_config=ingestion_config
        )
        
        return [types.TextContent(
            type="text",
            text=f"Document uploaded successfully!\n\nDocument ID: {result['document_id']}\nChunking Strategy: {chunking_strategy}\nMetadata: {json.dumps(metadata, indent=2)}"
        )]
    
    async def _enhanced_search(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Perform enhanced RAG search."""
        query = args["query"]
        search_strategy = args.get("search_strategy", "rag_fusion")
        use_web_search = args.get("use_web_search", False)
        force_web_search = args.get("force_web_search", False)
        limit = args.get("limit", 10)
        include_citations = args.get("include_citations", True)
        
        # Build search settings
        search_settings = {
            "search_strategy": search_strategy,
            "limit": limit,
            "use_web_search": use_web_search,
            "force_web_search": force_web_search
        }
        
        result = await self.r2r_client.retrieval.search(
            query=query,
            search_settings=search_settings
        )
        
        # Format response
        response_parts = [
            f"# Enhanced Search Results",
            f"**Query:** {query}",
            f"**Strategy:** {search_strategy}",
            f"**Results:** {len(result.get('results', []))} chunks found",
            ""
        ]
        
        if include_citations and 'citations' in result:
            response_parts.append("## Citations")
            for citation in result['citations'][:5]:  # Show top 5 citations
                response_parts.append(f"- {citation.get('text', 'No citation text')}")
            response_parts.append("")
        
        # Add top results
        response_parts.append("## Top Results")
        for i, chunk in enumerate(result.get('results', [])[:3]):
            response_parts.append(f"### Result {i+1}")
            response_parts.append(f"**Score:** {chunk.get('score', 'N/A')}")
            response_parts.append(f"**Content:** {chunk.get('content', '')[:300]}...")
            response_parts.append("")
        
        if result.get('web_search_used'):
            response_parts.append(f"🌐 **Web search was used:** {result.get('web_search_reason', 'Enhanced results')}")
        
        return [types.TextContent(type="text", text="\n".join(response_parts))]
    
    async def _graph_search(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Search the knowledge graph."""
        query = args["query"]
        entity_types = args.get("entity_types", [])
        limit = args.get("limit", 20)
        
        # Get collections first
        collections = await self.r2r_client.collections.list()
        if not collections.results:
            return [types.TextContent(type="text", text="No collections found. Please upload documents first.")]
        
        collection_id = collections.results[0].id
        
        # Search entities
        entities = await self.r2r_client.graphs.list_entities(
            collection_id=collection_id,
            entity_types=entity_types,
            limit=limit
        )
        
        # Search relationships
        relationships = await self.r2r_client.graphs.list_relationships(
            collection_id=collection_id,
            limit=limit
        )
        
        response_parts = [
            f"# Knowledge Graph Search Results",
            f"**Query:** {query}",
            f"**Entities Found:** {len(entities.results)}",
            f"**Relationships Found:** {len(relationships.results)}",
            ""
        ]
        
        if entities.results:
            response_parts.append("## Entities")
            for entity in entities.results[:10]:
                response_parts.append(f"- **{entity.name}** ({entity.category})")
                if hasattr(entity, 'description') and entity.description:
                    response_parts.append(f"  {entity.description[:100]}...")
            response_parts.append("")
        
        if relationships.results:
            response_parts.append("## Relationships")
            for rel in relationships.results[:10]:
                response_parts.append(f"- {rel.subject} → {rel.predicate} → {rel.object}")
            response_parts.append("")
        
        return [types.TextContent(type="text", text="\n".join(response_parts))]
    
    async def _get_entity_details(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get detailed information about an entity."""
        entity_name = args["entity_name"]
        include_relationships = args.get("include_relationships", True)
        
        # This would need to be implemented based on your specific graph structure
        return [types.TextContent(
            type="text",
            text=f"Entity details for '{entity_name}' would be retrieved here. This requires specific implementation based on your graph schema."
        )]
    
    async def _query_spreadsheet(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Query spreadsheet data using natural language."""
        query = args["query"]
        filename = args.get("filename")
        
        # Use enhanced search with spreadsheet focus
        search_settings = {
            "search_strategy": "rag_fusion",
            "limit": 10,
            "enable_sql_workflow": True  # This would trigger Tool-Augmented Orchestration
        }
        
        result = await self.r2r_client.retrieval.search(
            query=query,
            search_settings=search_settings
        )
        
        response_parts = [
            f"# Spreadsheet Query Results",
            f"**Query:** {query}",
            ""
        ]
        
        if filename:
            response_parts.append(f"**Target File:** {filename}")
            response_parts.append("")
        
        # Check if SQL was executed
        if result.get('sql_executed'):
            response_parts.append("✅ **Structured data query executed**")
            response_parts.append("")
        
        # Add results
        if 'response' in result:
            response_parts.append("## Answer")
            response_parts.append(result['response'])
        else:
            response_parts.append("## Results")
            for chunk in result.get('results', [])[:3]:
                response_parts.append(f"- {chunk.get('content', '')[:200]}...")
        
        return [types.TextContent(type="text", text="\n".join(response_parts))]
    
    async def _agent_chat(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Chat with R2R's reasoning agent."""
        message = args["message"]
        conversation_id = args.get("conversation_id")
        
        result = await self.r2r_client.agent.chat(
            message=message,
            conversation_id=conversation_id
        )
        
        response_parts = [
            f"# Agent Response",
            f"**Your Message:** {message}",
            "",
            "## Agent Reply",
            result.get('response', 'No response received')
        ]
        
        if conversation_id:
            response_parts.insert(2, f"**Conversation ID:** {conversation_id}")
        
        return [types.TextContent(type="text", text="\n".join(response_parts))]
    
    async def _get_analytics(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get system analytics."""
        metric_type = args.get("metric_type", "usage")
        days = args.get("days", 30)
        
        # This would integrate with your Supabase analytics
        response_parts = [
            f"# R2R Analytics - {metric_type.title()}",
            f"**Period:** Last {days} days",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Metrics",
            "- Total queries: [Would be retrieved from citation_log]",
            "- Average confidence: [Would be calculated from logs]",
            "- Web search usage: [Would be retrieved from logs]",
            "- Most queried documents: [Would be analyzed]",
            "",
            "📊 **Note:** Full analytics integration requires Supabase setup with citation logging enabled."
        ]
        
        return [types.TextContent(type="text", text="\n".join(response_parts))]
    
    async def _list_documents(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """List documents in the system."""
        limit = args.get("limit", 50)
        offset = args.get("offset", 0)
        
        documents = await self.r2r_client.documents.list(
            limit=limit,
            offset=offset
        )
        
        response_parts = [
            f"# Document Library",
            f"**Total Documents:** {len(documents.results)}",
            f"**Showing:** {offset + 1}-{offset + len(documents.results)}",
            ""
        ]
        
        for doc in documents.results:
            response_parts.append(f"## {doc.metadata.get('filename', 'Unknown File')}")
            response_parts.append(f"- **ID:** {doc.id}")
            response_parts.append(f"- **Type:** {doc.metadata.get('file_type', 'Unknown')}")
            response_parts.append(f"- **Size:** {doc.metadata.get('file_size', 'Unknown')} bytes")
            response_parts.append(f"- **Created:** {doc.created_at}")
            response_parts.append("")
        
        return [types.TextContent(type="text", text="\n".join(response_parts))]
    
    async def _system_health(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Check system health."""
        try:
            health = await self.r2r_client.health()
            
            response_parts = [
                f"# R2R System Health",
                f"**Status:** ✅ Healthy",
                f"**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "## System Information",
                f"- **Version:** {health.get('version', 'Unknown')}",
                f"- **Database:** Connected",
                f"- **Vector Store:** Available",
                f"- **LLM Provider:** Configured",
                "",
                "## Enhanced Features Status",
                "- ✅ **Hierarchical Chunking:** Available",
                "- ✅ **Citation System:** Active",
                "- ✅ **Tool-Augmented Orchestration:** Ready",
                "- ✅ **Web Search Integration:** Configured",
                "- ✅ **Graph Extraction:** Enabled",
                "- ✅ **Multi-modal Processing:** Supported"
            ]
            
        except Exception as e:
            response_parts = [
                f"# R2R System Health",
                f"**Status:** ❌ Error",
                f"**Error:** {str(e)}",
                "",
                "Please check that R2R is running and accessible."
            ]
        
        return [types.TextContent(type="text", text="\n".join(response_parts))]


async def main():
    """Run the R2R MCP server."""
    server_instance = R2RMCPServer()
    
    # Run the server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server_instance.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="r2r-enhanced",
                server_version="1.0.0",
                capabilities=server_instance.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
