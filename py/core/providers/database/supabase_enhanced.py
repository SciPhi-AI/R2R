"""
Enhanced Supabase Database Provider for R2R
Extends the standard Postgres provider with Supabase-specific features.
"""

import os
import json
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from core.base.providers.database import PostgresDBProvider


class SupabaseEnhancedProvider(PostgresDBProvider):
    """
    Enhanced database provider with Supabase-specific features.
    
    Features:
    - Spreadsheet data storage for Tool-Augmented Orchestration
    - Enhanced document metadata for better citations
    - Web search caching for performance
    - Citation logging for audit trails
    - Supabase RLS integration
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Supabase-specific configuration
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        # Feature flags
        self.enable_spreadsheet_storage = config.get("enable_spreadsheet_storage", True)
        self.enable_web_cache = config.get("enable_web_cache", True)
        self.enable_citation_logging = config.get("enable_citation_logging", True)
        self.web_cache_ttl_hours = config.get("web_cache_ttl_hours", 24)
    
    async def store_spreadsheet_data(
        self, 
        document_id: str,
        filename: str,
        dataframe_data: List[Dict[str, Any]]
    ) -> bool:
        """
        Store spreadsheet data for Tool-Augmented Orchestration.
        """
        if not self.enable_spreadsheet_storage:
            return False
        
        try:
            # Create table name from filename
            table_name = f"spreadsheet_{filename.replace('.', '_').replace('-', '_').lower()}"
            
            # Prepare records for batch insert
            records = []
            for row_data in dataframe_data:
                row_index = row_data.get("row_index", 0)
                for column_name, cell_value in row_data.get("data", {}).items():
                    if cell_value is not None:
                        records.append({
                            "document_id": document_id,
                            "filename": filename,
                            "table_name": table_name,
                            "row_index": row_index,
                            "column_name": column_name,
                            "cell_value": str(cell_value),
                            "data_type": row_data.get("data_types", {}).get(column_name, "text")
                        })
            
            if not records:
                return False
            
            # Batch insert records
            batch_size = 1000
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                
                # Build INSERT query
                columns = list(batch[0].keys())
                placeholders = ", ".join([f"({', '.join(['%s'] * len(columns))})" for _ in batch])
                query = f"""
                    INSERT INTO spreadsheet_cells ({', '.join(columns)})
                    VALUES {placeholders}
                    ON CONFLICT (document_id, filename, row_index, column_name) 
                    DO UPDATE SET 
                        cell_value = EXCLUDED.cell_value,
                        data_type = EXCLUDED.data_type,
                        updated_at = NOW()
                """
                
                # Flatten batch data for query
                values = []
                for record in batch:
                    values.extend(record.values())
                
                await self.execute_query(query, values)
            
            return True
            
        except Exception as e:
            print(f"Error storing spreadsheet data: {e}")
            return False
    
    async def query_spreadsheet_data(
        self,
        filename: str,
        columns: Optional[List[str]] = None,
        where_clause: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query spreadsheet data for Tool-Augmented Orchestration.
        """
        try:
            # Build query
            column_filter = ""
            if columns:
                column_list = "', '".join(columns)
                column_filter = f"AND column_name IN ('{column_list}')"
            
            where_filter = ""
            if where_clause:
                where_filter = f"AND {where_clause}"
            
            query = f"""
                SELECT row_index, column_name, cell_value, data_type
                FROM spreadsheet_cells
                WHERE filename = %s {column_filter} {where_filter}
                ORDER BY row_index, column_name
            """
            
            results = await self.fetch_query(query, [filename])
            
            # Group by row for easier processing
            rows = {}
            for row in results:
                row_idx = row["row_index"]
                if row_idx not in rows:
                    rows[row_idx] = {}
                rows[row_idx][row["column_name"]] = {
                    "value": row["cell_value"],
                    "type": row["data_type"]
                }
            
            return [{"row_index": idx, "data": data} for idx, data in rows.items()]
            
        except Exception as e:
            print(f"Error querying spreadsheet data: {e}")
            return []
    
    async def store_enhanced_document_metadata(
        self,
        document_id: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Store enhanced document metadata for better citations.
        """
        try:
            query = """
                INSERT INTO document_metadata (
                    document_id, filename, file_path, file_size, mime_type,
                    author, title, subject, modified_at, document_fingerprint,
                    page_count, word_count, character_count, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (document_id) DO UPDATE SET
                    filename = EXCLUDED.filename,
                    file_path = EXCLUDED.file_path,
                    file_size = EXCLUDED.file_size,
                    mime_type = EXCLUDED.mime_type,
                    author = EXCLUDED.author,
                    title = EXCLUDED.title,
                    subject = EXCLUDED.subject,
                    modified_at = EXCLUDED.modified_at,
                    document_fingerprint = EXCLUDED.document_fingerprint,
                    page_count = EXCLUDED.page_count,
                    word_count = EXCLUDED.word_count,
                    character_count = EXCLUDED.character_count,
                    metadata = EXCLUDED.metadata,
                    processed_at = NOW()
            """
            
            values = [
                document_id,
                metadata.get("filename"),
                metadata.get("file_path"),
                metadata.get("file_size"),
                metadata.get("mime_type"),
                metadata.get("author"),
                metadata.get("title"),
                metadata.get("subject"),
                metadata.get("modified_at"),
                metadata.get("document_fingerprint"),
                metadata.get("page_count"),
                metadata.get("word_count"),
                metadata.get("character_count"),
                json.dumps(metadata.get("extra_metadata", {}))
            ]
            
            await self.execute_query(query, values)
            return True
            
        except Exception as e:
            print(f"Error storing document metadata: {e}")
            return False
    
    async def cache_web_search_results(
        self,
        query: str,
        provider: str,
        results: List[Dict[str, Any]]
    ) -> bool:
        """
        Cache web search results for performance.
        """
        if not self.enable_web_cache:
            return False
        
        try:
            # Generate query hash
            query_hash = hashlib.sha256(f"{query}:{provider}".encode()).hexdigest()
            
            # Set expiration time
            expires_at = datetime.utcnow() + timedelta(hours=self.web_cache_ttl_hours)
            
            query_sql = """
                INSERT INTO web_search_cache (query_hash, query_text, search_provider, results, expires_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (query_hash) DO UPDATE SET
                    results = EXCLUDED.results,
                    expires_at = EXCLUDED.expires_at,
                    created_at = NOW()
            """
            
            await self.execute_query(query_sql, [
                query_hash, query, provider, json.dumps(results), expires_at
            ])
            
            return True
            
        except Exception as e:
            print(f"Error caching web search results: {e}")
            return False
    
    async def get_cached_web_search_results(
        self,
        query: str,
        provider: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve cached web search results.
        """
        if not self.enable_web_cache:
            return None
        
        try:
            query_hash = hashlib.sha256(f"{query}:{provider}".encode()).hexdigest()
            
            query_sql = """
                SELECT results FROM web_search_cache
                WHERE query_hash = %s AND expires_at > NOW()
            """
            
            results = await self.fetch_query(query_sql, [query_hash])
            
            if results:
                return json.loads(results[0]["results"])
            
            return None
            
        except Exception as e:
            print(f"Error retrieving cached web search results: {e}")
            return None
    
    async def log_citation(
        self,
        query_text: str,
        response_text: str,
        citations: List[Dict[str, Any]],
        source_breakdown: Dict[str, int],
        confidence_score: Optional[float] = None,
        web_search_used: bool = False,
        web_search_reason: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Log citation for audit trails.
        """
        if not self.enable_citation_logging:
            return None
        
        try:
            query = """
                INSERT INTO citation_log (
                    query_text, response_text, citations, source_breakdown,
                    confidence_score, web_search_used, web_search_reason, user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            result = await self.fetch_query(query, [
                query_text,
                response_text,
                json.dumps(citations),
                json.dumps(source_breakdown),
                confidence_score,
                web_search_used,
                web_search_reason,
                user_id
            ])
            
            return str(result[0]["id"]) if result else None
            
        except Exception as e:
            print(f"Error logging citation: {e}")
            return None
    
    async def cleanup_expired_cache(self) -> int:
        """
        Clean up expired web search cache entries.
        """
        try:
            query = "SELECT cleanup_expired_web_cache()"
            result = await self.fetch_query(query)
            return result[0]["cleanup_expired_web_cache"] if result else 0
        except Exception as e:
            print(f"Error cleaning up expired cache: {e}")
            return 0
    
    async def get_citation_analytics(
        self,
        user_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get citation analytics for insights.
        """
        try:
            where_clause = "WHERE created_at >= NOW() - INTERVAL '%s days'"
            params = [days]
            
            if user_id:
                where_clause += " AND user_id = %s"
                params.append(user_id)
            
            query = f"""
                SELECT 
                    COUNT(*) as total_queries,
                    AVG(confidence_score) as avg_confidence,
                    COUNT(*) FILTER (WHERE web_search_used = true) as web_search_count,
                    COUNT(*) FILTER (WHERE (source_breakdown->>'web_search')::int > 0) as queries_with_web_sources,
                    AVG((source_breakdown->>'internal_knowledge')::int) as avg_internal_sources,
                    AVG((source_breakdown->>'web_search')::int) as avg_web_sources
                FROM citation_log
                {where_clause}
            """
            
            result = await self.fetch_query(query, params)
            
            if result:
                return {
                    "total_queries": result[0]["total_queries"],
                    "avg_confidence": float(result[0]["avg_confidence"] or 0),
                    "web_search_usage_rate": result[0]["web_search_count"] / max(result[0]["total_queries"], 1),
                    "queries_with_web_sources": result[0]["queries_with_web_sources"],
                    "avg_internal_sources": float(result[0]["avg_internal_sources"] or 0),
                    "avg_web_sources": float(result[0]["avg_web_sources"] or 0)
                }
            
            return {}
            
        except Exception as e:
            print(f"Error getting citation analytics: {e}")
            return {}
