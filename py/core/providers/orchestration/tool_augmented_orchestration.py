"""
Tool-Augmented Orchestration Provider for R2R
Enables Text-to-SQL retrieval within RAG pipeline for structured data.
"""

import json
import re
from typing import Any, Dict, List, Optional
from core.base import OrchestrationProvider, VectorSearchResult
from shared.abstractions import GenerationConfig


class ToolAugmentedOrchestrationProvider(OrchestrationProvider):
    """
    Enhanced orchestration that can pivot to SQL queries for structured data.
    
    Workflow:
    1. Perform standard hybrid vector search
    2. Inspect metadata for structured data sources
    3. If spreadsheet data found, generate and execute SQL queries
    4. Fuse SQL results with RAG context
    5. Generate comprehensive response
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.enable_sql_workflow = config.get("enable_sql_workflow", True)
        self.sql_confidence_threshold = config.get("sql_confidence_threshold", 0.7)
        self.max_sql_results = config.get("max_sql_results", 50)
        self.structured_data_types = config.get("structured_data_types", ["spreadsheet", "csv", "xlsx"])
    
    async def arun_rag_pipeline(
        self,
        message: str,
        vector_search_settings: Dict[str, Any],
        kg_search_settings: Dict[str, Any],
        rag_generation_config: GenerationConfig,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run RAG pipeline with tool augmentation for structured data.
        """
        # Step 1: Perform standard hybrid vector search
        search_results = await self._perform_vector_search(
            message, vector_search_settings
        )
        
        # Step 2: Inspect metadata for structured data
        structured_sources = await self._identify_structured_sources(search_results)
        
        # Step 3: Workflow pivot - check if we should use SQL
        if self.enable_sql_workflow and structured_sources:
            # Generate and execute SQL queries
            sql_results = await self._execute_sql_workflow(
                message, structured_sources, rag_generation_config
            )
            
            # Step 4: Fuse SQL results with RAG context
            enhanced_context = await self._fuse_sql_with_rag(
                search_results, sql_results
            )
        else:
            # Standard RAG workflow
            enhanced_context = search_results
        
        # Step 5: Generate final response
        response = await self._generate_augmented_response(
            message, enhanced_context, rag_generation_config
        )
        
        return {
            "response": response,
            "sources": enhanced_context,
            "sql_executed": bool(structured_sources and self.enable_sql_workflow),
            "structured_data_found": len(structured_sources) if structured_sources else 0
        }
    
    async def _identify_structured_sources(
        self, search_results: List[VectorSearchResult]
    ) -> List[Dict[str, Any]]:
        """
        Identify chunks that contain structured data requiring SQL queries.
        """
        structured_sources = []
        
        for result in search_results:
            metadata = result.metadata or {}
            source_type = metadata.get("source_type", "")
            
            # Check if this is structured data
            if source_type in self.structured_data_types:
                # Check if we have structured data available
                if metadata.get("structured_data") or metadata.get("has_structured_data"):
                    structured_sources.append({
                        "result": result,
                        "source_type": source_type,
                        "filename": metadata.get("filename"),
                        "structured_data": metadata.get("structured_data"),
                        "data_schema": metadata.get("data_schema", [])
                    })
        
        return structured_sources
    
    async def _execute_sql_workflow(
        self,
        message: str,
        structured_sources: List[Dict[str, Any]],
        generation_config: GenerationConfig
    ) -> List[Dict[str, Any]]:
        """
        Execute Text-to-SQL workflow for structured data sources.
        """
        sql_results = []
        
        for source in structured_sources:
            try:
                # Generate SQL query
                sql_query = await self._generate_sql_query(
                    message, source, generation_config
                )
                
                if sql_query:
                    # Execute SQL query (simulated - would need actual DB connection)
                    query_result = await self._execute_sql_query(
                        sql_query, source["structured_data"]
                    )
                    
                    if query_result:
                        sql_results.append({
                            "source_file": source["filename"],
                            "sql_query": sql_query,
                            "results": query_result,
                            "result_count": len(query_result) if isinstance(query_result, list) else 1
                        })
                        
            except Exception as e:
                # Log error but continue with other sources
                print(f"SQL workflow error for {source.get('filename', 'unknown')}: {e}")
                continue
        
        return sql_results
    
    async def _generate_sql_query(
        self,
        message: str,
        source: Dict[str, Any],
        generation_config: GenerationConfig
    ) -> Optional[str]:
        """
        Generate SQL query based on user message and data schema.
        """
        if not hasattr(self, 'llm_provider') or not self.llm_provider:
            return None
        
        schema = source.get("data_schema", [])
        filename = source.get("filename", "data")
        
        prompt = f"""
        You are a SQL query generator. Based on the user's question and the available data schema, 
        generate a SQL query to retrieve relevant information.
        
        User Question: {message}
        
        Available Data Schema for {filename}:
        Columns: {', '.join(schema)}
        
        Generate a SQL query that would answer the user's question. 
        Use the table name 'data' and only use columns that exist in the schema.
        Return ONLY the SQL query, no explanations.
        
        Example format:
        SELECT column1, column2 FROM data WHERE condition ORDER BY column1 LIMIT 10;
        
        SQL Query:
        """
        
        try:
            response = await self.llm_provider.aget_completion(
                messages=[{"role": "user", "content": prompt}],
                generation_config=GenerationConfig(max_tokens=200)
            )
            
            sql_query = response.choices[0].message.content.strip()
            
            # Basic SQL validation
            if self._validate_sql_query(sql_query, schema):
                return sql_query
            else:
                return None
                
        except Exception as e:
            print(f"Error generating SQL query: {e}")
            return None
    
    def _validate_sql_query(self, sql_query: str, schema: List[str]) -> bool:
        """
        Basic validation of generated SQL query.
        """
        if not sql_query or not sql_query.strip():
            return False
        
        # Check for basic SQL structure
        sql_lower = sql_query.lower()
        if not sql_lower.startswith('select'):
            return False
        
        # Check that only valid columns are referenced
        for column in schema:
            if column.lower() in sql_lower:
                return True
        
        return False
    
    async def _execute_sql_query(
        self, sql_query: str, structured_data: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Execute SQL query against structured data.
        Note: This is a simplified implementation. In production, you'd use a proper SQL engine.
        """
        try:
            # For now, simulate SQL execution by filtering the structured data
            records = structured_data.get("records", [])
            
            if not records:
                return None
            
            # Simple keyword-based filtering (would be replaced with actual SQL execution)
            # This is a placeholder - in production you'd use SQLite, DuckDB, or similar
            
            # For demonstration, return first few records
            return records[:self.max_sql_results]
            
        except Exception as e:
            print(f"Error executing SQL query: {e}")
            return None
    
    async def _fuse_sql_with_rag(
        self,
        rag_results: List[VectorSearchResult],
        sql_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Fuse SQL query results with RAG context.
        """
        enhanced_context = []
        
        # Add RAG results
        for result in rag_results:
            enhanced_context.append({
                "type": "rag",
                "content": result.content,
                "score": result.score,
                "metadata": result.metadata
            })
        
        # Add SQL results
        for sql_result in sql_results:
            # Convert SQL results to narrative format
            narrative = await self._sql_results_to_narrative(sql_result)
            
            enhanced_context.append({
                "type": "sql",
                "content": narrative,
                "score": 1.0,  # High relevance for direct query results
                "sql_query": sql_result["sql_query"],
                "source_file": sql_result["source_file"],
                "result_count": sql_result["result_count"]
            })
        
        return enhanced_context
    
    async def _sql_results_to_narrative(self, sql_result: Dict[str, Any]) -> str:
        """
        Convert SQL query results to narrative text.
        """
        results = sql_result["results"]
        source_file = sql_result["source_file"]
        query = sql_result["sql_query"]
        
        if not results:
            return f"No results found in {source_file} for the query."
        
        # Create narrative from results
        narrative_parts = [
            f"Query results from {source_file}:",
            f"SQL Query: {query}",
            f"Found {len(results)} matching records:",
            ""
        ]
        
        # Add sample results
        for i, record in enumerate(results[:5]):  # Show first 5 results
            record_desc = ", ".join([f"{k}: {v}" for k, v in record.items() if v is not None])
            narrative_parts.append(f"Record {i+1}: {record_desc}")
        
        if len(results) > 5:
            narrative_parts.append(f"... and {len(results) - 5} more records")
        
        return "\n".join(narrative_parts)
    
    async def _generate_augmented_response(
        self,
        message: str,
        enhanced_context: List[Dict[str, Any]],
        generation_config: GenerationConfig
    ) -> str:
        """
        Generate response using both RAG and SQL context.
        """
        if not hasattr(self, 'llm_provider') or not self.llm_provider:
            return "Tool-augmented response generation not available."
        
        # Separate RAG and SQL context
        rag_context = [ctx for ctx in enhanced_context if ctx["type"] == "rag"]
        sql_context = [ctx for ctx in enhanced_context if ctx["type"] == "sql"]
        
        # Build comprehensive context
        context_parts = []
        
        if rag_context:
            context_parts.append("Document Context:")
            for ctx in rag_context[:3]:  # Limit for token efficiency
                context_parts.append(f"- {ctx['content'][:300]}...")
        
        if sql_context:
            context_parts.append("\nStructured Data Results:")
            for ctx in sql_context:
                context_parts.append(f"- {ctx['content']}")
        
        context = "\n".join(context_parts)
        
        prompt = f"""
        Answer the following question using both the document context and structured data results provided.
        
        Question: {message}
        
        Available Information:
        {context}
        
        Instructions:
        - Provide a comprehensive answer using both sources
        - Cite specific data points from structured results when relevant
        - Indicate when information comes from documents vs. structured data
        - Be precise and factual
        
        Answer:
        """
        
        try:
            response = await self.llm_provider.aget_completion(
                messages=[{"role": "user", "content": prompt}],
                generation_config=generation_config
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating augmented response: {e}"
